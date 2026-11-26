#!/usr/bin/env python3
"""Validate E14-frame's unprofiled, paired 3x100 PS double/NEON/PL DMA trials."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re

import numpy as np

from compare_board import spectrum, stats, timings
from ps_precision.prepare_reference import FIXTURE_SHA, ROOT, reference


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest(folder, name, check):
    entries = {}
    verified = (folder/check).read_text().splitlines()
    for line in (folder/name).read_text().splitlines():
        sha, item = line.split(maxsplit=1)
        item = item.lstrip('*')
        require(re.fullmatch('[0-9a-f]{64}', sha) and item not in entries, 'Invalid manifest')
        require(f'{item}: OK' in verified, f'Artifact not verified on board: {item}')
        entries[item] = sha
    require(entries.get('frame.rspb') == FIXTURE_SHA, 'Fixture identity mismatch')
    return entries


def accuracy(actual, expected, maximum, relative):
    delta = abs(actual-expected)
    result = dict(max_complex_q15_lsb=float(np.max(delta)),
                  rms_q15_lsb=float(np.sqrt(np.mean(delta**2))),
                  relative_l2=float(np.linalg.norm(delta)/np.linalg.norm(expected)))
    require(result['max_complex_q15_lsb'] <= maximum and result['relative_l2'] <= relative,
            f'Numerical tolerance exceeded: {result}')
    require(np.argmax(abs(actual)) == np.argmax(abs(expected)), 'Peak mismatch')
    return result


def integer_reference(q):
    spec = importlib.util.spec_from_file_location('q15_oracle', ROOT/'src/PS/fft128/receiver.py')
    model = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(model)
    rows = [model.fft_q15([model.pack_iq((z.real, z.imag)) for z in row]) for row in q]
    columns = [model.fft_q15([rows[ch][r] for ch in range(128)]) for r in range(128)]
    return np.array([[complex(*model.unpack_iq(columns[r][d])) for r in range(128)] for d in range(128)])


def irq_counts(path):
    result = {}
    for line in path.read_text().splitlines():
        match = re.match(r'\s*\d+:\s+(\d+)\s+(\d+)\s+GIC-\d+\s+(67|68)\s+Level\s+xilinx-dma-controller', line)
        if match:
            require(int(match[3]) not in result, 'Duplicate DMA interrupt')
            result[int(match[3])] = (int(match[1]), int(match[2]))
    require(set(result) == {67, 68}, 'Expected two DMA IRQ sources')
    return result


def validate_config(config):
    expected=dict(experiment='E14-frame',register_abi=8,parallel_cores=1,streaming_stages=7,total_butterflies=7,
                  frame_initiation_interval=128,group_barrier=False,buffering='per_stage_double_frame_slots_and_inplace_matrix',
                  stage_frame_slots=True,next_vector_prefetch=True,external_buffers=False,length_width=17,
                  pl_transpose=True,pl_output_reorder=True,cpu_transpose=False,in_place_matrix=True,matrix_bytes=65536,
                  fft_per_request=256,frame_words=16384,dma_requests_per_frame=1,dma_channel_submissions_per_frame=2,
                  payload_bytes_per_frame=131072,output_order='doppler-major/range-minor')
    require(all(config.get(k)==v for k,v in expected.items()),'E14 full-frame architecture differs')


def validate_frame_contract(batch):
    expected=dict(experiment='E14-frame',register_abi=8,hardware=True,dma_requests_per_frame=1,dma_channel_submissions_per_frame=2,
                  fft_per_request=256,frame_words=16384,bytes_per_direction_per_request=65536,payload_bytes_per_frame=131072,
                  parallel_cores=1,streaming_stages=7,total_butterflies=7,pl_transpose=True,pl_output_reorder=True,cpu_transpose=False,
                  matrix_bytes=65536,in_place_matrix=True,output_order='doppler-major/range-minor',buffering='per_stage_double_frame_slots_and_inplace_matrix')
    require(all(batch.get(k)==v for k,v in expected.items()),'Actual E14 hardware full-frame contract required')


def analyze(folder, clock_hz=50000000):
    require(50000000 <= clock_hz <= 200000000, 'Invalid expected PL clock')
    expected, q, scale = reference(ROOT/'benchmarks/fixtures/radarsimpy_128x128.rspb')
    integer = integer_reference(q)
    env = (folder/'environment.txt').read_text()
    require('E14-frame CPU0 warmup=10 repeats=100 trials=3' in env, 'Measurement contract missing')
    dma = manifest(folder, 'dma_artifacts.sha256', 'dma_artifact_check.txt')
    ps = manifest(folder, 'ps_artifacts.sha256', 'ps_artifact_check.txt')
    require(all(item in dma for item in ('fft128_e14_frame.bin', 'fft128_e14_frame.dtbo', 'fft128_dma_frame.ko',
                                          'fft128-receiver', 'test-dma-frame-client', 'run_board.sh')),
            'Incomplete DMA artifact manifest')
    require(all(item in ps for item in ('double/bin/receiver', 'double/lib/libfftw3.so.3',
                                        'float_neon/bin/receiver', 'float_neon/lib/libfftw3f.so.3')),
            'Incomplete PS artifact manifest')
    require(ps.get('reference.json') == digest(folder/'reference.json'), 'Reference metadata mismatch')
    metadata = json.loads((folder/'reference.json').read_text())
    require(metadata['fixture_sha256'] == FIXTURE_SHA and metadata['shape'] == [128, 128], 'Reference identity')
    require(ps.get('reference.csv') == metadata['reference_csv_sha256'], 'Reference CSV identity')
    require(np.isclose(metadata['input_to_q15_scale'], scale, rtol=1e-12), 'Reference scale')
    for item in ('dma_config.json', 'fft128_e14_frame.json', 'pl_source.sha256', 'host_source.sha256',
                 'module_source.sha256', 'module_build_environment.txt'):
        require(dma.get(item) == digest(folder/item), f'Copied DMA evidence differs: {item}')
    config = json.loads((folder/'dma_config.json').read_text())
    validate_config(config)
    require((config['experiment'], config['core'], config['clock_hz'], config['memory_port'],
             config['fft_per_request'], config['bytes_per_direction'], config['sg'], config['dre']) ==
            ('E14-frame', 'pipeline', clock_hz, 'HP0', 256, 65536, False, False), 'DMA architecture differs')
    variants = ('double', 'float_neon', 'pl')
    orders = (folder/'order.txt').read_text().splitlines()
    require(orders == [f'trial={i+1} order={" ".join(variants[i:]+variants[:i])}' for i in range(3)],
            'Trial rotation differs')
    results = {}
    for variant in variants:
        directory = folder/variant
        require({p.name for p in directory.glob('trial_*.timings.csv')} ==
                {f'trial_{i}.timings.csv' for i in range(1, 4)}, 'Expected exactly three trials')
        if variant != 'pl':
            for item in ('build_environment.txt', 'fftw_build_environment.txt'):
                require(ps.get(f'{variant}/{item}') == digest(directory/item), 'PS build identity differs')
            plan = (directory/'preflight.log').read_text().split('Range plan', 1)[-1].split('FFT:', 1)[0]
            require(variant != 'float_neon' or 'neon' in plan.lower(), 'NEON plan absent')
        samples, trials = [], []
        for trial in range(1, 4):
            prefix = directory/f'trial_{trial}'
            log = prefix.with_suffix('.log').read_text()
            require('CPU_AFFINITY=0' in log, 'CPU0 affinity absent')
            times = timings(prefix.with_suffix('.timings.csv'))
            require(len(times) == 100, 'Expected 100 measured repetitions')
            output = spectrum(prefix.with_suffix('.csv'))
            if variant == 'pl':
                report = json.loads(prefix.with_suffix('.json').read_text())
                require(report['backend'] == 'PL_DMA_FRAME' and report['profiling'] is False,
                        'Actual unprofiled PL_DMA_FRAME required')
                require((report['warmup'], report['repeats'], report['fft_calls'], report['shape'],
                         report['mismatched_complex_bins']) == (10, 100, 256, [128, 128], 0), 'PL contract')
                batch=json.loads(prefix.with_suffix('.batch.json').read_text())
                validate_frame_contract(batch)
                require(report['window'] == 'none' and report['total_normalization'] == '1/16384', 'PL scaling')
                require('FRAME_PASS backend=PL_DMA_FRAME bit_exact_bins=16384' in log and
                        'BENCHMARK: warmup=10 repeat=100' in log, 'PL per-repeat verification absent')
                require(np.isclose(np.mean(times)/1000, report['fft_and_transfer_seconds'], rtol=1e-7), 'PL time summary differs')
                require(np.isclose(report['input_to_q15_scale'], scale, rtol=1e-12), 'PL input scale')
                source = np.loadtxt(prefix.with_suffix('.input.csv'), delimiter=',', skiprows=1)
                ch, sample = np.indices((128, 128))
                require(source.shape == (16384, 4) and np.all(np.isfinite(source)), 'Invalid PL input CSV')
                require(np.array_equal(source[:, :2], np.column_stack((ch.ravel(), sample.ravel()))), 'Input order')
                quantized = (np.rint(source[:, 2]*scale)+1j*np.rint(source[:, 3]*scale)).reshape(128, 128)
                require(np.array_equal(quantized, q), 'PL quantized input differs from fixture')
                require(np.array_equal(output, integer), 'PL result differs from independent Python integer model')
                errors = accuracy(output, expected, 12, 0.02)
            else:
                precision = 'float64' if variant == 'double' else 'float32'
                maximum, relative = (1e-7, 1e-12) if variant == 'double' else (0.01, 1e-5)
                for marker in ('FFTW WISDOM', 'Q15-quantized integers', 'output normalization=1/(pulses*samples)',
                               f'PS_PRECISION={precision} PS_VARIANT={variant}',
                               'Warmup: 10, repeats of SAME frame: 100'):
                    require(marker in log, f'Missing PS marker: {marker}')
                verified = re.search(r'PS_VERIFY_PASS repeats=100 bins=16384 max_error_q15_lsb=(\S+) '
                                     r'worst_rms_q15_lsb=(\S+) worst_relative_l2=(\S+)', log)
                require(verified is not None, 'PS per-repeat verification absent')
                numbers = np.array(list(map(float, verified.groups())))
                require(np.all(np.isfinite(numbers)) and np.all(numbers >= 0) and
                        numbers[0] <= maximum and numbers[2] <= relative, 'PS per-repeat accuracy')
                scale_match = re.search(r'Input: Q15-quantized integers, scale=([^,]+)', log)
                require(scale_match is not None and np.isclose(float(scale_match[1]), scale, rtol=1e-12), 'PS input scale')
                require(variant != 'float_neon' or 'neon' in log.split('Range plan', 1)[-1].split('FFT:', 1)[0].lower(),
                        'NEON plan absent from trial')
                errors = accuracy(output, expected, maximum, relative)
            samples.extend(times)
            trials.append(dict(trial=trial, timing=stats(times), accuracy=errors))
        results[variant] = dict(timing=stats(samples), trials=trials)
    before, after = (irq_counts(folder/f'interrupts_{phase}.txt') for phase in ('before', 'after'))
    delta = {irq: [after[irq][cpu]-before[irq][cpu] for cpu in (0,1)] for irq in before}
    require(all(min(counts) >= 0 and sum(counts) == 330 for counts in delta.values()),
            'Expected 330 frames x 1 complete-frame request = 330 IRQs per DMA direction')
    med = {v: results[v]['timing']['median_ms'] for v in variants}
    return dict(status='E14_FRAME_PAIRED_SAME_BOARD_VALIDATED', results=results,
                parallel_cores=1, streaming_stages=7, group_barrier=False, dma_irq_deltas=delta, dma_requests_per_frame=1, dma_channel_submissions_per_frame=2, payload_bytes_per_frame=131072, pl_transpose=True, pl_output_reorder=True,
                double_over_pl=med['double']/med['pl'], float_neon_over_pl=med['float_neon']/med['pl'],
                fixture_sha256=FIXTURE_SHA, dma_artifacts=dma, ps_artifacts=ps,
                scope='Q15 input to CPU-available 2D FFT output; required copies, DMA, IRQ wait, transpose and normalization included; IO/planning/validation excluded',
                limitation='Same recorded warm-cache frame, CPU0, one ioctl/full frame, coherent HP0 bounce buffers; one reused seven-stage DIT FFT, in-place 64KiB PL transpose and row-major output drain; no continuous-stream throughput claim',
                environment=env)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results', type=Path)
    parser.add_argument('--clock-hz', type=int, default=50000000)
    args = parser.parse_args()
    result = analyze(args.results, args.clock_hz)
    (args.results/'comparison.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
