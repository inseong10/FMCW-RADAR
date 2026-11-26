"""Independent ADC input + fixed integer Hann + existing integer FFT oracle."""
import json
import hashlib
from pathlib import Path
import sys
import numpy as np
import cfar_reference as ref
import verify_s1c as integer

sys.path.insert(0, str(ref.ROOT/'tools/sender'))
from adc16_record import read_adc_frame


def load(record):
    rows, fs, profile = read_adc_frame(Path(record))
    values = np.frombuffer(b''.join(rows), dtype='>i2').reshape(128,128,2).astype(np.int64)
    return values[...,0]+1j*values[...,1], fs, profile


def window_codes(codes, window):
    if window == 'none':
        return codes.copy()
    if window != 'hann':
        raise ValueError('Unknown window')
    h = np.rint(np.hanning(128)*32768).astype(np.int64)
    weights = h[:,None]*h[None,:]
    def rounded(values):
        product = values.astype(np.int64)*weights
        magnitude = np.abs(product)
        whole = magnitude >> 30
        remainder = magnitude & ((1 << 30)-1)
        whole += (remainder > (1 << 29)) | ((remainder == (1 << 29)) & ((whole & 1) != 0))
        return np.where(product < 0, -whole, whole)
    return rounded(codes.real)+1j*rounded(codes.imag)


def spectrum(codes, backend, window):
    if backend in ('pl', 'model'):
        return integer.integer_spectrum(window_codes(codes, window))
    if backend != 'ps':
        raise ValueError('Unknown backend')
    w = np.hanning(128)[:,None]*np.hanning(128)[None,:] if window == 'hann' else 1
    return np.fft.fft2(codes*w)/16384


def accuracy(record, backend, window):
    record = Path(record)
    codes, fs, _ = load(record)
    meta = json.loads(record.with_suffix('.json').read_text(encoding='utf-8'))
    if hashlib.sha256(record.read_bytes()).hexdigest()!=meta['record_sha256']:
        raise ValueError('ADC fixture SHA differs from frozen sidecar')
    bins = spectrum(codes, backend, window)
    power = bins.real**2+bins.imag**2
    cells, thresholds = ref.ca_cfar_2d(power, (2,2), (8,8), 1e-6)
    peaks = ref.cluster_peaks(power, cells)
    truth, false = ref.evaluate(peaks, meta['targets'], 128, 128, fs)
    return bins, thresholds, peaks, {'hits':sum(t['hit'] for t in truth), 'targets':len(truth),
                                   'false':len(false), 'peaks':peaks, 'truth':truth, 'false_peaks':false}
