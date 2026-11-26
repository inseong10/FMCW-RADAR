"""Frozen ADC profile1 and unwindowed RSPB0002 records; standard library only.

S3a-1: a record may hold M chirps x N samples (M in 128/256/512, N in 128/256). 128x128 behaviour,
header and profile dictionary are unchanged.
"""
import math
from pathlib import Path
import struct

ADC_BITS = 16
ADC_SCALE = 1600000.0
ADC_PROFILE = 1
RECORD = struct.Struct('!8sIIddHHI')
ROW_BYTES = 128*4  # 128-sample row; see row_bytes() for other shapes
CHIRPS = (128, 256, 512)
SAMPLES = (128, 256)


def row_bytes(samples=128):
    return samples*4


def read_adc_frame(path):
    data = Path(path).read_bytes()
    if len(data) < RECORD.size:
        raise ValueError('Expected one complete ADC16 frame')
    magic, chirps, samples, fs, scale, bits, reserved, profile = RECORD.unpack_from(data)
    if ((magic, bits, reserved, profile) != (b'RSPB0002', ADC_BITS, 0, ADC_PROFILE) or
            chirps not in CHIRPS or samples not in SAMPLES or
            scale != ADC_SCALE or not math.isfinite(fs) or fs <= 0):
        raise ValueError('Invalid or unsupported ADC profile/header')
    row = row_bytes(samples)
    if len(data) != RECORD.size+chirps*row:
        raise ValueError('Expected one complete ADC16 frame')
    rows = [data[RECORD.size+i*row:RECORD.size+(i+1)*row] for i in range(chirps)]
    info = {'profile': profile, 'bits': bits, 'scale_codes_per_unit': scale,
            'window_applied': False, 'payload_bytes_per_frame': chirps*row}
    if (chirps, samples) != (128, 128):
        info.update({'chirps': chirps, 'samples': samples})
    return rows, fs, info


def write_adc_frame(path, payload, fs, chirps=128, samples=128):
    if (chirps not in CHIRPS or samples not in SAMPLES or len(payload) != chirps*row_bytes(samples) or
            not math.isfinite(fs) or fs <= 0):
        raise ValueError('Invalid ADC payload or rate')
    path = Path(path)
    # Never replace original float records or a previous generated file.
    with path.open('xb') as stream:
        stream.write(RECORD.pack(b'RSPB0002', chirps, samples, fs, ADC_SCALE,
                                 ADC_BITS, 0, ADC_PROFILE))
        stream.write(payload)
