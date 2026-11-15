#!/usr/bin/env python3
"""Validate PS01 raw results against the pinned input and summarize 3x100 timings."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from compare_board import spectrum, stats, timings
from prepare_reference import FIXTURE_SHA, ROOT, reference

VARIANTS = ('double', 'float_scalar', 'float_neon')


def error_metrics(actual, expected, maximum, relative):
    if not np.all(np.isfinite(actual)):
        raise ValueError('Nonfinite spectrum')
    error = abs(actual-expected)
    result = dict(max_complex_q15_lsb=float(np.max(error)),
                  rms_q15_lsb=float(np.sqrt(np.mean(error**2))),
                  relative_l2=float(np.linalg.norm(error)/np.linalg.norm(expected)))
    if result['max_complex_q15_lsb'] > maximum or result['relative_l2'] > relative:
        raise ValueError(f'Numerical tolerance exceeded: {result}')
    if np.argmax(abs(actual)) != np.argmax(abs(expected)):
        raise ValueError('Peak differs from NumPy')
    return result


def analyze(folder, smoke=False):
    environment = (folder/'environment.txt').read_text(encoding='utf-8')
    match = re.search(r'repeat=(\d+) warmup=(\d+) trials=(\d+)', environment)
    if not match:
        raise ValueError('Missing repeat/warmup/trials')
    repeat, warmup, trials = map(int, match.groups())
    if not smoke and (repeat, warmup, trials) != (100, 10, 3):
        raise ValueError('Performance report requires warmup=10, repeats=100, trials=3; use --smoke for diagnostics')
    if min(repeat, trials) < 1:
        raise ValueError('Empty measurement')
    metadata = json.loads((folder/'reference.json').read_text(encoding='utf-8'))
    if metadata['fixture_sha256'] != FIXTURE_SHA or metadata['shape'] != [128, 128]:
        raise ValueError('Input identity mismatch')
    expected, _, scale = reference(ROOT/'benchmarks/fixtures/radarsimpy_128x128.rspb')
    if not np.isclose(metadata['input_to_q15_scale'], scale, rtol=1e-12):
        raise ValueError('Quantization scale mismatch')
    artifact_text = (folder/'artifacts.sha256').read_text(encoding='utf-8')
    checks = (folder/'artifact_check.txt').read_text(encoding='utf-8')
    artifact_hashes = {}
    for line in artifact_text.splitlines():
        digest, name = line.split(maxsplit=1)
        name = name.lstrip('*')
        if not re.fullmatch('[0-9a-f]{64}', digest) or name in artifact_hashes:
            raise ValueError('Invalid artifact manifest')
        artifact_hashes[name] = digest
        if f'{name}: OK' not in checks.splitlines():
            raise ValueError(f'Missing board artifact verification: {name}')
    if artifact_hashes.get('frame.rspb') != FIXTURE_SHA:
        raise ValueError('Fixture not verified on board')
    if artifact_hashes.get('reference.json') != hashlib.sha256((folder/'reference.json').read_bytes()).hexdigest():
        raise ValueError('Reference metadata hash mismatch')
    if artifact_hashes.get('reference.csv') != metadata['reference_csv_sha256']:
        raise ValueError('Reference spectrum hash mismatch')
    required_artifacts = ['reference.csv', 'run_board.sh']
    for variant in VARIANTS:
        library = 'libfftw3.so.3' if variant == 'double' else 'libfftw3f.so.3'
        required_artifacts += [f'{variant}/bin/receiver', f'{variant}/lib/{library}',
                               f'{variant}/build_environment.txt', f'{variant}/fftw_build_environment.txt']
    if any(name not in artifact_hashes for name in required_artifacts):
        raise ValueError('Incomplete artifact manifest')
    order = (folder/'order.txt').read_text(encoding='utf-8').splitlines()
    if len(order) != trials:
        raise ValueError('Incomplete trial order')
    for trial, line in enumerate(order, 1):
        rotated = VARIANTS[(trial-1) % 3:] + VARIANTS[:(trial-1) % 3]
        if line != f'trial={trial} order={" ".join(rotated)}':
            raise ValueError('Trial order mismatch')
    results = {}
    for variant in VARIANTS:
        precision = 'float64' if variant == 'double' else 'float32'
        maximum, relative = (1e-7, 1e-12) if variant == 'double' else (0.01, 1e-5)
        for name in ('build_environment.txt', 'fftw_build_environment.txt'):
            file = folder/variant/name
            if hashlib.sha256(file.read_bytes()).hexdigest() != artifact_hashes[f'{variant}/{name}']:
                raise ValueError(f'Build environment hash mismatch: {variant}/{name}')
        preflight = (folder/variant/'preflight.log').read_text(encoding='utf-8')
        plan = preflight.split('Range plan', 1)[-1].split('FFT:', 1)[0]
        if variant == 'float_neon' and 'neon' not in plan.lower():
            raise ValueError('NEON codelet not selected')
        if variant == 'float_scalar' and 'neon' in plan.lower():
            raise ValueError('Scalar variant selected NEON')
        ids = {int(p.name.split('_')[1].split('.')[0]) for p in (folder/variant).glob('trial_*.timings.csv')}
        if ids != set(range(1, trials+1)):
            raise ValueError(f'Incomplete trials for {variant}')
        samples, per_trial = [], []
        for trial in range(1, trials+1):
            prefix = folder/variant/f'trial_{trial}'
            log = prefix.with_suffix('.log').read_text(encoding='utf-8')
            for marker in ('CPU_AFFINITY=0', 'FFTW WISDOM', 'Q15-quantized integers',
                           'output normalization=1/(pulses*samples)',
                           f'PS_PRECISION={precision} PS_VARIANT={variant}',
                           f'Warmup: {warmup}, repeats of SAME frame: {repeat}'):
                if marker not in log:
                    raise ValueError(f'Missing {marker} in {prefix}')
            verification = re.search(r'PS_VERIFY_PASS repeats=(\d+) bins=(\d+) max_error_q15_lsb=(\S+) worst_rms_q15_lsb=(\S+) worst_relative_l2=(\S+)', log)
            if not verification or tuple(map(int, verification.group(1, 2))) != (repeat, 16384):
                raise ValueError(f'Missing per-repeat verification: {prefix}')
            errors = np.array(list(map(float, verification.group(3, 4, 5))))
            if not np.all(np.isfinite(errors)) or np.any(errors < 0) or errors[0] > maximum or errors[2] > relative:
                raise ValueError('Per-repeat accuracy failure')
            scale_match = re.search(r'Input: Q15-quantized integers, scale=([^,]+)', log)
            if not scale_match or not np.isclose(float(scale_match[1]), scale, rtol=1e-12):
                raise ValueError('Receiver quantization scale mismatch')
            accuracy = error_metrics(spectrum(prefix.with_suffix('.csv')), expected, maximum, relative)
            times = timings(prefix.with_suffix('.timings.csv'))
            if len(times) != repeat:
                raise ValueError('Incomplete timing iterations')
            samples.extend(times)
            per_trial.append(dict(trial=trial, timing=stats(times), accuracy=accuracy,
                                  per_repeat_max_error_q15_lsb=float(errors[0]),
                                  per_repeat_worst_relative_l2=float(errors[2])))
        results[variant] = dict(timing=stats(samples), trials=per_trial)
    medians = {name: value['timing']['median_ms'] for name, value in results.items()}
    return dict(status='PS01_SMOKE_VALIDATED' if smoke else 'PS01_SAME_BOARD_VALIDATED',
                scope='fft_pipeline: input copy, FFT axes, tiled transpose, normalization; excludes IO/planning/validation',
                shape=[128, 128], results=results,
                double_over_float_neon=medians['double']/medians['float_neon'],
                float_scalar_over_float_neon=medians['float_scalar']/medians['float_neon'],
                limits=dict(float64=dict(max_complex_q15_lsb=1e-7, relative_l2=1e-12),
                            float32=dict(max_complex_q15_lsb=0.01, relative_l2=1e-5)),
                fixture_sha256=FIXTURE_SHA, artifacts=artifact_hashes, environment=environment,
                limitation='No PL comparison or continuous UDP throughput in this PS-only experiment')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results', type=Path)
    parser.add_argument('--smoke', action='store_true', help='Allow diagnostic repeat counts; not a performance report')
    args = parser.parse_args()
    result = analyze(args.results, args.smoke)
    (args.results/'comparison.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
