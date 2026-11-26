"""S3a-1 host loopback for size generalization (no board/throughput claim).

1. The independent method-A integer spectrum equals the frozen 128x128 oracle (verify_s1c) on every
   128x128 ADC fixture and an edge-value frame.
2. For each shape, a seeded synthetic ADC16 record (four tones + noise, targets at exact bins) is sent to the
   production receiver (model and ps). check_adc16_stream verifies the first frame's full spectrum
   (model: exact, ps: 1e-9) and every frame's detections/thresholds against the NumPy reference.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import smoke_s2a
import check_adc16_stream
import adc16_reference as adc
import cfar_reference as ref
import sys

sys.path.insert(0, str(ref.ROOT/'tools/sender'))
from adc16_record import write_adc_frame

SHAPES = ((256, 128), (128, 256), (256, 256), (512, 128))


def synthetic(path, M, N, seed):
    """Tones at integer (doppler, range) bins; targets expressed physically for cfar_reference.evaluate."""
    fs = N/80e-6
    bins = [(10, 10), (M-21, 40), (4, N//2+17), (M//2+23, N-30)]
    rng = np.random.default_rng(seed)
    d, r = np.indices((M, N))
    x = sum(6000*np.exp(2j*np.pi*(bd*d/M+br*r/N+k/7)) for k, (bd, br) in enumerate(bins))
    x = x+rng.normal(0, 150, (M, N))+1j*rng.normal(0, 150, (M, N))
    codes = np.stack((np.rint(x.real), np.rint(x.imag)), axis=-1)
    if np.abs(codes).max() > 32767:
        raise ValueError('synthetic record clips')
    write_adc_frame(path, codes.astype('>i2').tobytes(), fs, M, N)
    targets = []
    for bd, br in bins:
        signed = bd-M if bd >= M//2 else bd
        targets.append({'range_m': br*(fs/N)*ref.C/(2*ref.SLOPE),
                        'speed_mps': signed/(M*ref.PRP_S)*ref.LAMBDA/2})
    meta = {'file': path.name, 'record_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'sample_rate_hz': fs, 'chirps': M, 'samples': N, 'seed': seed, 'targets': targets,
            'note': 'S3a-1 synthetic smoke record, not a radarsimpy scenario'}
    path.with_suffix('.json').write_text(json.dumps(meta, indent=2)+'\n', encoding='utf-8')
    return meta


def oracle_check(out):
    rows = []
    folder = ref.ROOT/'benchmarks/fixtures/adc16'
    frames = [(p.name, adc.load(p)[0]) for p in sorted(folder.glob('*.rspb'))]
    edge = np.resize(np.array([-32768, 32767, -1, 0, 1, 3, -3]), (128, 128, 2))
    frames.append(('edge_values', edge[..., 0]+1j*edge[..., 1]))
    for name, codes in frames:
        for window in ('hann', 'none'):
            q = adc.window_codes(codes, window)
            if not np.array_equal(adc.split_integer_spectrum(q), adc.integer.integer_spectrum(q)):
                raise ValueError(f'method-A oracle differs from 128x128 oracle: {name} {window}')
            rows.append({'input': name, 'window': window, 'equal': True})
    (out/'oracle_128_equivalence.json').write_text(json.dumps(rows, indent=1)+'\n', encoding='utf-8')
    print(f'S3A1_ORACLE_128_EQUAL cases={len(rows)}', flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    oracle_check(a.out)
    results = []
    run = 92390
    for i, (M, N) in enumerate(SHAPES):
        record = a.out/f'synthetic_{M}x{N}_adc16.rspb'
        meta = synthetic(record, M, N, 20261126+i)
        for backend in ('model', 'ps'):
            run += 1
            sub = a.out/f'{M}x{N}_{backend}'
            sub.mkdir()
            summary = smoke_s2a.case(a.binary.resolve(), sub, backend, run, diagnostic=True, adc16=True,
                                     record=record, shape=(M, N), period_ms=M*0.1+10, frames=5,
                                     chirp_gap_us=100)
            folder = sub/(backend+'_normal')
            verified = check_adc16_stream.check(folder, sub/(folder.name+'_sender.json'), record=record,
                                                require_board=False)
            acc = verified['accuracy']
            if not verified['first_frame_all_bins_checked'] or acc['hits'] != 4 or acc['false'] != 0:
                raise ValueError(f'{M}x{N} {backend}: accuracy {acc["hits"]}/4 false {acc["false"]}')
            results.append({'shape': [M, N], 'backend': backend, 'run_id': run, 'record_sha256': meta['record_sha256'],
                            'frames_checked': verified['processed_frames_checked'],
                            'hits': acc['hits'], 'false': acc['false'], 'peaks': acc['peaks'],
                            'all_bins': verified['first_frame_all_bins_checked'],
                            'preparation_ms': summary['metrics'].get('preparation'),
                            'fft_ms': summary['metrics'].get('fft_transfer')})
            print(f'S3A1_SMOKE_PASS shape={M}x{N} backend={backend} hits={acc["hits"]}/4 false={acc["false"]}', flush=True)
    (a.out/'smoke_s3a1_summary.json').write_text(json.dumps(results, indent=1)+'\n', encoding='utf-8')
    print(f'S3A1_HOST_SMOKE_PASS cases={len(results)} (no board/throughput claim)')


if __name__ == '__main__':
    main()
