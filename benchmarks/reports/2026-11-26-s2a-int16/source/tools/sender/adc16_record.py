"""Frozen ADC profile1 and unwindowed RSPB0002 records; standard library only."""
import math
from pathlib import Path
import struct

ADC_BITS = 16
ADC_SCALE = 1600000.0
ADC_PROFILE = 1
RECORD = struct.Struct('!8sIIddHHI')
ROW_BYTES = 128*4


def read_adc_frame(path):
    data = Path(path).read_bytes()
    if len(data) != RECORD.size+128*ROW_BYTES:
        raise ValueError('Expected one complete ADC16 128x128 frame')
    magic, chirps, samples, fs, scale, bits, reserved, profile = RECORD.unpack_from(data)
    if ((magic, chirps, samples, bits, reserved, profile) !=
            (b'RSPB0002', 128, 128, ADC_BITS, 0, ADC_PROFILE) or
            scale != ADC_SCALE or not math.isfinite(fs) or fs <= 0):
        raise ValueError('Invalid or unsupported ADC profile/header')
    rows = [data[RECORD.size+i*ROW_BYTES:RECORD.size+(i+1)*ROW_BYTES] for i in range(128)]
    return rows, fs, {'profile': profile, 'bits': bits, 'scale_codes_per_unit': scale,
                      'window_applied': False, 'payload_bytes_per_frame': 65536}


def write_adc_frame(path, payload, fs):
    if len(payload) != 65536 or not math.isfinite(fs) or fs <= 0:
        raise ValueError('Invalid ADC payload or rate')
    path = Path(path)
    # Never replace original float records or a previous generated file.
    with path.open('xb') as stream:
        stream.write(RECORD.pack(b'RSPB0002', 128, 128, fs, ADC_SCALE,
                                 ADC_BITS, 0, ADC_PROFILE))
        stream.write(payload)
