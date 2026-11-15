#!/usr/bin/env python3
"""Prepare a float64 NumPy oracle for the pinned 128x128 Q15 fixture."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import struct
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_SHA = 'aa06ff124034310216693c1398f2f1061c9a6ce32e9ea6f5687675849934c976'


def reference(path):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != FIXTURE_SHA:
        raise ValueError('PS01 requires the pinned RadarSimPy fixture')
    if raw[:8] != b'RSPB0001':
        raise ValueError('Invalid recording')
    frame = np.empty((128, 128), dtype=np.complex128)
    seen = set()
    offset = 8
    while offset < len(raw):
        size, = struct.unpack_from('!I', raw, offset)
        offset += 4
        packet = raw[offset:offset+size]
        offset += size
        magic, version, kind, channel, index, pulses, samples, fs = struct.unpack('!4sBBHIIId', packet[:28])
        if (magic, version, kind, channel, pulses, samples, fs, size) != (b'RSPY', 1, 1, 0, 128, 128, 1.6e6, 1052):
            raise ValueError('Unexpected fixture metadata')
        if index >= 128 or index in seen:
            raise ValueError('Invalid chirp index')
        seen.add(index)
        iq = np.frombuffer(packet[28:], dtype='>f4').astype(np.float64).reshape(128, 2)
        frame[index] = iq[:, 0] + 1j*iq[:, 1]
    if offset != len(raw) or len(seen) != 128 or not np.all(np.isfinite(frame)):
        raise ValueError('Incomplete/nonfinite recording')
    scale = 16384/np.max(np.hypot(frame.real, frame.imag))
    q = np.rint(frame.real*scale) + 1j*np.rint(frame.imag*scale)
    return np.fft.fft2(q)/16384, q, float(scale)


def prepare(output):
    fixture = ROOT/'benchmarks/fixtures/radarsimpy_128x128.rspb'
    expected, q, scale = reference(fixture)
    output.mkdir(parents=True, exist_ok=True)
    (output/'frame.rspb').write_bytes(fixture.read_bytes())
    with (output/'reference.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(['doppler_bin_unshifted', 'range_bin', 'real', 'imag'])
        for d, r in np.ndindex(expected.shape):
            writer.writerow([d, r, format(expected[d, r].real, '.17g'), format(expected[d, r].imag, '.17g')])
    metadata = dict(experiment='PS01', shape=[128, 128], fixture_sha256=FIXTURE_SHA,
                    input_to_q15_scale=scale, q15_interleaved_le_sha256=hashlib.sha256(
                        np.stack((q.real, q.imag), axis=-1).astype('<i2').tobytes()).hexdigest(),
                    reference_csv_sha256=hashlib.sha256((output/'reference.csv').read_bytes()).hexdigest(),
                    numpy_version=np.__version__, normalization='1/16384', window='none',
                    peak_unshifted=list(map(int, np.unravel_index(np.argmax(abs(expected)), expected.shape))),
                    accuracy_limits=dict(float64=dict(max_complex_q15_lsb=1e-7, relative_l2=1e-12),
                                         float32=dict(max_complex_q15_lsb=0.01, relative_l2=1e-5)))
    (output/'reference.json').write_text(json.dumps(metadata, indent=2)+'\n', encoding='utf-8')
    print('PS_REFERENCE_READY:', output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    prepare(parser.parse_args().output)
