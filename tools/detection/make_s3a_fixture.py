"""S3a fixtures: RadarSimPy multi4+noise scenes at M chirps x N samples, ADC16 profile 1 (no window).

Same chain as the 128x128 fixtures: cfar_reference.simulate (per-target RadarSimPy baseband sum plus
NumPy seed-42 noise) -> make_fixture.write_rspb (float RSPB0001, kept as a fixture) -> read_rspb ->
make_adc16_fixture.quantize (frozen gain 1.6e6 codes/unit, ties to even,
signed16 saturation) -> RSPB0002. --check-128 regenerates 128x128 and requires the committed
radarsimpy_128x128_sim_multi4_noise_adc16.rspb byte for byte before writing anything else.
Existing files are never replaced (write_adc_frame opens with 'xb').
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import cfar_reference as ref
import adc16_reference as adc
from make_adc16_fixture import quantize
from make_fixture import write_rspb
import tempfile

sys.path.insert(0, str(ref.ROOT/'tools/sender'))
from adc16_record import ADC_PROFILE, ADC_SCALE, read_adc_frame, write_adc_frame

SCENARIO = 'sim_multi4_noise'


def scene():
    sc = {s['name']: s for s in json.loads((Path(__file__).with_name('s1a_scenarios.json'))
                                            .read_text(encoding='utf-8'))['scenarios']}[SCENARIO]
    return sc['targets'], bool(sc.get('noise', False))


def codes_for(M, N, float_path=None):
    """float_path: where the RSPB0001 float record is written (must not exist); None = temporary."""
    targets, noise = scene()
    frame, fs = ref.simulate(targets, M, N, noise)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(float_path) if float_path else Path(tmp)/'float.rspb'
        if path.exists():
            raise FileExistsError(path)
        write_rspb(path, frame, fs)
        stored, rate = ref.read_rspb(path)
    if rate != fs or stored.shape != (M, N):
        raise ValueError('Float record roundtrip failed')
    codes, stats = quantize(stored)
    return codes, fs, targets, noise, stats


def check_128():
    codes, fs, _, _, _ = codes_for(128, 128)
    frozen = ref.ROOT/'benchmarks/fixtures/adc16/radarsimpy_128x128_sim_multi4_noise_adc16.rspb'
    rows, rate, _ = read_adc_frame(frozen)
    same = rate == fs and np.array_equal(np.frombuffer(b''.join(rows), '>i2').reshape(128, 128, 2), codes)
    if not same:
        raise ValueError('Generator does not reproduce the frozen 128x128 multi4 noise fixture')
    print('S3A_FIXTURE_128_REPRODUCED', hashlib.sha256(frozen.read_bytes()).hexdigest())


def make(out, M, N):
    target = out/f'radarsimpy_{M}x{N}_{SCENARIO}_adc16.rspb'
    if target.exists():
        raise FileExistsError(target)
    source = out/f'radarsimpy_{M}x{N}_{SCENARIO}.rspb'
    codes, fs, targets, noise, stats = codes_for(M, N, source)
    write_adc_frame(target, codes.astype('>i2').tobytes(), fs, M, N)
    rows, rate, profile = read_adc_frame(target)
    np.testing.assert_array_equal(np.frombuffer(b''.join(rows), '>i2').reshape(M, N, 2), codes)
    meta = {'file': target.name, 'record_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
            'source': 'RadarSimPy 15.5.0 per-target baseband sum + NumPy seed-42 noise (make_s3a_fixture.py)',
            'scenario': SCENARIO, 'chirps': M, 'samples': N, 'sample_rate_hz': fs, 'profile': profile,
            'adc_profile': ADC_PROFILE, 'scale_codes_per_unit': ADC_SCALE, 'targets': targets, 'noise': noise,
            'window_applied': False, 'source_file': source.name,
            'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(), **stats}
    target.with_suffix('.json').write_text(json.dumps(meta, indent=2)+'\n', encoding='utf-8')
    result = {'file': target.name, 'record_sha256': meta['record_sha256'],
              'clipped_components': stats['clipped_components']}
    for backend in ('model', 'ps'):
        _, _, peaks, acc = adc.accuracy(target, backend, 'hann')
        result[backend] = {'hits': acc['hits'], 'targets': acc['targets'], 'false': acc['false'], 'peaks': peaks}
    print('S3A_FIXTURE', json.dumps(result))
    if stats['clipped_components'] or any(result[b]['hits'] != 4 or result[b]['false'] for b in ('model', 'ps')):
        raise ValueError('Fixture clips or reference model misses a target')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, default=ref.ROOT/'benchmarks/fixtures/s3a')
    p.add_argument('--shape', nargs=2, type=int, action='append', required=True, metavar=('M', 'N'))
    p.add_argument('--check-128', action='store_true')
    a = p.parse_args()
    if a.check_128:
        check_128()
    a.out.mkdir(parents=True, exist_ok=True)
    results = [make(a.out, M, N) for M, N in a.shape]
    print(f'S3A_FIXTURES_READY count={len(results)}')


if __name__ == '__main__':
    main()
