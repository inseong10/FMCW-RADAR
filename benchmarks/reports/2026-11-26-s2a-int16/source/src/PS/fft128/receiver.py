#!/usr/bin/env python3
"""128x128 RSPY frame -> 256 calls to the PL FFT. Standard library only.

--backend model is explicitly a software reference, never a hardware fallback.
The MMIO helper performs aligned volatile 32-bit accesses and ARM barriers.
"""
import argparse
import csv
import ctypes
import json
import math
import socket
import struct
import time
from pathlib import Path

N = 128
ID = 0x46543128
HEADER = struct.Struct("!4sBBHIIId")
TWIDDLES = tuple((max(-32768, min(32767, round(32768*math.cos(-2*math.pi*k/N)))),
                  max(-32768, min(32767, round(32768*math.sin(-2*math.pi*k/N)))))
                 for k in range(N//2))


def pack_iq(z):
    return (int(z[0]) & 65535) | ((int(z[1]) & 65535) << 16)


def unpack_iq(word):
    r, i = word & 65535, (word >> 16) & 65535
    return (r-65536 if r & 32768 else r, i-65536 if i & 32768 else i)


def fft_q15(words):
    """Bit-exact radix-2 model: floor division and saturation each stage."""
    if len(words) != N:
        raise ValueError("FFT requires 128 packed complex words")
    values = [None]*N
    for index, word in enumerate(words):
        values[int(format(index, '07b')[::-1], 2)] = unpack_iq(word)
    for stage in range(7):
        half = 1 << stage
        for base in range(0, N, half*2):
            for j in range(half):
                ar, ai = values[base+j]
                br, bi = values[base+j+half]
                wr, wi = TWIDDLES[j*(N//(half*2))]
                pr, pi = br*wr-bi*wi, br*wi+bi*wr
                sat = lambda x: max(-32768, min(32767, x >> 16))
                values[base+j] = (sat((ar << 15)+pr), sat((ai << 15)+pi))
                values[base+j+half] = (sat((ar << 15)-pr), sat((ai << 15)-pi))
    return [pack_iq(z) for z in values]


class Model:
    label = "SOFTWARE_MODEL (no FPGA access)"

    def fft(self, words):
        return fft_q15(words)

    def close(self):
        pass


class MMIO:
    label = "PL_MMIO"

    def __init__(self, base, library):
        self.lib = ctypes.CDLL(str(Path(library).resolve()), use_errno=True)
        self.lib.fft128_open.argtypes = [ctypes.c_uint32]
        self.lib.fft128_open.restype = ctypes.c_int
        self.lib.fft128_run.argtypes = [ctypes.POINTER(ctypes.c_uint32),
                                      ctypes.POINTER(ctypes.c_uint32), ctypes.c_uint32]
        self.lib.fft128_run.restype = ctypes.c_int
        self.lib.fft128_close.argtypes = []
        self.lib.fft128_close.restype = None
        result = self.lib.fft128_open(base)
        if result:
            raise RuntimeError(f"MMIO open failed ({result}); verify bitstream, DT, FCLK and root access")

    def fft(self, words):
        if len(words) != N:
            raise ValueError("FFT requires 128 words")
        incoming, outgoing = (ctypes.c_uint32*N)(*words), (ctypes.c_uint32*N)()
        result = self.lib.fft128_run(incoming, outgoing, 1000)
        if result:
            raise RuntimeError(f"PL FFT failed ({result}); frame aborted")
        return list(outgoing)

    def close(self):
        self.lib.fft128_close()


def decode_packet(packet):
    if len(packet) != HEADER.size+N*8:
        raise ValueError("Expected one 128-sample RSPY chirp")
    magic, version, kind, channel, index, chirps, samples, fs = HEADER.unpack_from(packet)
    if (magic, version, kind, chirps, samples) != (b'RSPY', 1, 1, N, N):
        raise ValueError("Expected RSPY v1, 128 chirps x 128 samples")
    if index >= N or not math.isfinite(fs) or fs <= 0:
        raise ValueError("Invalid chirp index/sample rate")
    iq = struct.unpack_from('!256f', packet, HEADER.size)
    if not all(math.isfinite(x) for x in iq):
        raise ValueError("Nonfinite I/Q")
    return channel, index, fs, [complex(iq[k], iq[k+1]) for k in range(0, 256, 2)]


def receive(bind, port, channel, timeout):
    frame, peer, fs = [None]*N, None, None
    deadline = time.monotonic()+timeout
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024*1024)
        sock.bind((bind, port))
        print(f"LISTENING {bind}:{port} channel={channel} 128x128", flush=True)
        while any(row is None for row in frame):
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"Incomplete frame: {sum(row is not None for row in frame)}/128 chirps")
            sock.settimeout(remaining)
            packet, source = sock.recvfrom(65535)
            try:
                ch, index, rate, row = decode_packet(packet)
            except ValueError:
                continue
            if ch != channel or (peer is not None and source != peer):
                continue
            if peer is None:
                peer, fs = source, rate
            if rate != fs:
                raise ValueError("Sampling rate changed during frame")
            if frame[index] is None:
                frame[index] = row
    return frame, fs


def quantize(frame):
    peak = max(abs(z) for row in frame for z in row)
    # Half full-scale complex magnitude leaves headroom. One scale for whole frame.
    scale = 16384/peak if peak else 1.0
    return [[pack_iq((round(z.real*scale), round(z.imag*scale))) for z in row]
            for row in frame], scale


def process(frame, backend):
    quantized, scale = quantize(frame)
    started = time.perf_counter()
    ranged = [backend.fft(row) for row in quantized]
    columns = [backend.fft([ranged[ch][r] for ch in range(N)]) for r in range(N)]
    spectrum = [[columns[r][d] for r in range(N)] for d in range(N)]
    return spectrum, scale, time.perf_counter()-started, quantized


def validate(spectrum, quantized):
    ranged = [fft_q15(row) for row in quantized]
    errors = 0
    for r in range(N):
        expected = fft_q15([ranged[ch][r] for ch in range(N)])
        errors += sum(expected[d] != spectrum[d][r] for d in range(N))
    if errors:
        raise RuntimeError(f"BIT_EXACT_FAIL: {errors}/16384 complex bins")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', choices=['mmio', 'model'], default='mmio')
    parser.add_argument('--base', type=lambda v: int(v, 0), default=0x43c00000)
    parser.add_argument('--library', default=str(Path(__file__).with_name('libfft128_mmio.so')))
    parser.add_argument('--bind', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=5000)
    parser.add_argument('--channel', type=int, default=0)
    parser.add_argument('--timeout', type=float, default=60)
    parser.add_argument('--output', type=Path, default=Path('fft128_result'))
    parser.add_argument('--self-test', action='store_true', help='Test PL before receiving UDP and exit')
    args = parser.parse_args()
    backend = Model() if args.backend == 'model' else MMIO(args.base, args.library)
    try:
        print(f"BACKEND={backend.label}", flush=True)
        if args.self_test:
            vectors = [[0]*N, [pack_iq((16384, -8192))]+[0]*(N-1),
                       [pack_iq((8192, -4096))]*N,
                       [pack_iq((round(12000*math.cos(2*math.pi*11*k/N)),
                                 round(12000*math.sin(2*math.pi*11*k/N)))) for k in range(N)]]
            for vector in vectors:
                if backend.fft(vector) != fft_q15(vector):
                    raise RuntimeError('SELFTEST_FAIL')
            print(f"SELFTEST_PASS backend={backend.label} vectors=4 bins=512")
            return
        frame, fs = receive(args.bind, args.port, args.channel, args.timeout)
        spectrum, scale, elapsed, quantized = process(frame, backend)
        validate(spectrum, quantized)  # No silent tolerance or CPU fallback.
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.with_suffix('.input.csv').open('w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['chirp', 'sample', 'real', 'imag'])
            for ch, row in enumerate(frame):
                for k, z in enumerate(row):
                    writer.writerow([ch, k, z.real, z.imag])
        with args.output.with_suffix('.csv').open('w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['doppler_bin_unshifted', 'range_bin', 'real_q15', 'imag_q15'])
            for d, row in enumerate(spectrum):
                for r, word in enumerate(row):
                    writer.writerow([d, r, *unpack_iq(word)])
        peak = max(((d, r) for d in range(N) for r in range(N)),
                   key=lambda pos: sum(x*x for x in unpack_iq(spectrum[pos[0]][pos[1]])))
        report = dict(backend=backend.label, shape=[N, N], fft_calls=2*N,
                      sample_rate_hz=fs, input_to_q15_scale=scale, window='none',
                      per_fft_normalization='1/128', total_normalization='1/16384',
                      fft_and_transfer_seconds=elapsed, mismatched_complex_bins=0,
                      peak_unshifted=list(peak),
                      timing_scope=('PL FFT calls, MMIO transfers and PS memory operations'
                                    if args.backend == 'mmio' else
                                    'Software FFT calls and memory operations on this host'),
                      note='Single-frame functional test; not a DMA or speedup measurement.')
        args.output.with_suffix('.json').write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(report, indent=2))
        print(f"FRAME_PASS backend={backend.label} bit_exact_bins=16384")
    finally:
        backend.close()


if __name__ == '__main__':
    main()
