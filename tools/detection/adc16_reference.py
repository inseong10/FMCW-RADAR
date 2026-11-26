"""Independent ADC input + fixed integer Hann + existing integer FFT oracle.

S3a-1: records may be M chirps x N samples. 128x128 keeps the original oracle (verify_s1c, pure-Python
Q15 model). Larger shapes use an independent vectorized integer radix-2 DIT over the full axis length with
the same Q15 butterfly (floor /2 and saturation per stage). The stage order is the method-A contract:
range stages 0..6, Doppler stages 0..6 (what one 128x128 E14 frame computes per block), then the
remaining Doppler stages, then the remaining range stages.
"""
import json
import hashlib
import math
from pathlib import Path
import sys
import numpy as np
import cfar_reference as ref
import verify_s1c as integer

sys.path.insert(0, str(ref.ROOT/'tools/sender'))
from adc16_record import read_adc_frame


def load(record):
    rows, fs, profile = read_adc_frame(Path(record))
    chirps, samples = len(rows), len(rows[0])//4
    values = np.frombuffer(b''.join(rows), dtype='>i2').reshape(chirps, samples, 2).astype(np.int64)
    return values[...,0]+1j*values[...,1], fs, profile


def hann_q15(length):
    return np.rint(np.hanning(length)*32768).astype(np.int64)


def window_codes(codes, window):
    if window == 'none':
        return codes.copy()
    if window != 'hann':
        raise ValueError('Unknown window')
    M, N = codes.shape
    weights = hann_q15(M)[:,None]*hann_q15(N)[None,:]
    def rounded(values):
        product = values.astype(np.int64)*weights
        magnitude = np.abs(product)
        whole = magnitude >> 30
        remainder = magnitude & ((1 << 30)-1)
        whole += (remainder > (1 << 29)) | ((remainder == (1 << 29)) & ((whole & 1) != 0))
        return np.where(product < 0, -whole, whole)
    return rounded(codes.real)+1j*rounded(codes.imag)


def q15_twiddles(length):
    """round(32768*cos/sin(-2*pi*k/L)) saturated to Q15, k < L/2 (round = half-even, like lrint)."""
    sat = lambda v: max(-32768, min(32767, round(v)))
    re = [sat(32768*math.cos(-2*math.pi*k/length)) for k in range(length//2)]
    im = [sat(32768*math.sin(-2*math.pi*k/length)) for k in range(length//2)]
    return np.array(re, dtype=np.int64), np.array(im, dtype=np.int64)


def bit_reverse(length):
    bits = length.bit_length()-1
    return np.array([int(format(k, f'0{bits}b')[::-1], 2) for k in range(length)])


def dit_stages(re, im, axis, stages):
    """Run radix-2 DIT stages (half = 2**s) along axis on bit-reversed data, Q15 floor/saturate."""
    re, im = np.moveaxis(re, axis, -1).copy(), np.moveaxis(im, axis, -1).copy()
    L = re.shape[-1]
    wr_all, wi_all = q15_twiddles(L)
    sat = lambda x: np.clip(x >> 16, -32768, 32767)
    for s in stages:
        h = 1 << s
        shape = re.shape[:-1]+(L//(2*h), 2, h)
        r4, i4 = re.reshape(shape), im.reshape(shape)
        t = np.arange(h)*(L//(2*h))
        wr, wi = wr_all[t], wi_all[t]
        ar, ai, br, bi = r4[...,0,:], i4[...,0,:], r4[...,1,:], i4[...,1,:]
        pr, pi = br*wr-bi*wi, br*wi+bi*wr
        new = (sat((ar << 15)+pr), sat((ai << 15)+pi), sat((ar << 15)-pr), sat((ai << 15)-pi))
        r4[...,0,:], i4[...,0,:], r4[...,1,:], i4[...,1,:] = new
        re, im = r4.reshape(re.shape), i4.reshape(im.shape)
    return np.moveaxis(re, -1, axis), np.moveaxis(im, -1, axis)


def split_integer_spectrum(q):
    """Method-A integer spectrum for any supported M x N (also valid, and tested, at 128x128)."""
    M, N = q.shape
    re = np.real(q).astype(np.int64)[bit_reverse(M)][:, bit_reverse(N)]
    im = np.imag(q).astype(np.int64)[bit_reverse(M)][:, bit_reverse(N)]
    re, im = dit_stages(re, im, 1, range(7))
    re, im = dit_stages(re, im, 0, range(7))
    re, im = dit_stages(re, im, 0, range(7, M.bit_length()-1))
    re, im = dit_stages(re, im, 1, range(7, N.bit_length()-1))
    return re+1j*im


def spectrum(codes, backend, window):
    M, N = codes.shape
    if backend in ('pl', 'model'):
        q = window_codes(codes, window)
        return integer.integer_spectrum(q) if (M, N) == (128, 128) else split_integer_spectrum(q)
    if backend != 'ps':
        raise ValueError('Unknown backend')
    w = np.hanning(M)[:,None]*np.hanning(N)[None,:] if window == 'hann' else 1
    return np.fft.fft2(codes*w)/(M*N)


def accuracy(record, backend, window):
    record = Path(record)
    codes, fs, _ = load(record)
    M, N = codes.shape
    meta = json.loads(record.with_suffix('.json').read_text(encoding='utf-8'))
    if hashlib.sha256(record.read_bytes()).hexdigest()!=meta['record_sha256']:
        raise ValueError('ADC fixture SHA differs from frozen sidecar')
    bins = spectrum(codes, backend, window)
    power = bins.real**2+bins.imag**2
    cells, thresholds = ref.ca_cfar_2d(power, (2,2), (8,8), 1e-6)
    peaks = ref.cluster_peaks(power, cells)
    truth, false = ref.evaluate(peaks, meta['targets'], M, N, fs)
    return bins, thresholds, peaks, {'hits':sum(t['hit'] for t in truth), 'targets':len(truth),
                                   'false':len(false), 'peaks':peaks, 'truth':truth, 'false_peaks':false}
