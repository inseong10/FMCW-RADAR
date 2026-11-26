"""ADC-emulate existing float recordings at one frozen gain; never apply Hann."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import cfar_reference as ref

sys.path.insert(0, str(ref.ROOT/'tools/sender'))
from adc16_record import ADC_BITS, ADC_PROFILE, ADC_SCALE, read_adc_frame, write_adc_frame


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def quantize(frame):
    scaled = np.stack((frame.real, frame.imag), axis=-1)*ADC_SCALE
    if not np.isfinite(scaled).all():
        raise ValueError('Non-finite ADC source')
    rounded = np.rint(scaled)
    clipped = (rounded < -32768) | (rounded > 32767)
    return np.clip(rounded, -32768, 32767).astype(np.int16), {
        'clipped_components': int(clipped.sum()),
        'clipped_complex_samples': int(clipped.any(axis=-1).sum()),
        'total_components': int(scaled.size),
        'peak_source_complex': float(np.max(np.abs(frame))),
        'peak_source_component': float(np.max(np.abs(np.stack((frame.real, frame.imag), axis=-1)))),
        'peak_quantized_component': int(np.max(np.abs(np.clip(rounded, -32768, 32767)))),
        'rounding_error_complex_rms_lsb': float(np.sqrt(np.mean(np.sum((rounded-scaled)**2, axis=-1))))}


def generate(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    names = ['radarsimpy_128x128', *['radarsimpy_128x128_sim_'+name+'_noise'
              for name in ('single', 'multi4', 'close_weak')]]
    manifest = {'experiment': 'S2a-int16', 'adc_profile': ADC_PROFILE, 'adc_bits': ADC_BITS,
                'scale_codes_per_unit': ADC_SCALE, 'gain_policy': 'fixed across all samples/frames/scenarios',
                'rounding': 'nearest ties to even, then signed16 saturation',
                'window_applied': False, 'frame_normalization': False,
                'noise_model_complex_rms_lsb': ref.NOISE_RMS*ADC_SCALE, 'records': []}
    for name in names:
        source = ref.ROOT/'benchmarks/fixtures'/(name+'.rspb')
        frame, fs = ref.read_rspb(source)
        codes, stats = quantize(frame)
        target = out/(name+'_adc16.rspb')
        write_adc_frame(target, codes.astype('>i2').tobytes(), fs)
        # Independent byte-order roundtrip; conversion never includes a window.
        rows, rate, profile = read_adc_frame(target)
        np.testing.assert_array_equal(np.frombuffer(b''.join(rows), '>i2').reshape(128,128,2), codes)
        assert rate == fs
        meta = json.loads(source.with_suffix('.json').read_text()) if source.with_suffix('.json').exists() else {}
        record = {'file': target.name, 'record_sha256': sha(target), 'source_file': source.name,
                  'source_sha256': sha(source), 'sample_rate_hz': fs, 'profile': profile,
                  'targets': meta.get('targets', [{'range_m':30.0,'speed_mps':-10.0}]),
                  'noise': meta.get('noise', False), **stats}
        target.with_suffix('.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
        manifest['records'].append(record)
    peak = max(r['peak_source_complex'] for r in manifest['records'])
    manifest['calibration_peak_complex'] = peak
    manifest['calibration_complex_headroom_db'] = float(20*np.log10(32767/(peak*ADC_SCALE)))
    (out/'adc16_profile.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    print('ADC16_FIXTURES_READY records=4 profile=1 bits=16 scale=1600000 clips='+
          str(sum(r['clipped_components'] for r in manifest['records'])))
    return manifest


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, default=ref.ROOT/'benchmarks/fixtures/adc16')
    generate(p.parse_args().out)
