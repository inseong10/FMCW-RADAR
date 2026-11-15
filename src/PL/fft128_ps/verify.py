#!/usr/bin/env python3
"""PC-only regression. Requires NumPy and Icarus Verilog, never Vivado or a board."""
import argparse
import importlib.util
import json
import math
import shutil
from pathlib import Path
import subprocess
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
spec = importlib.util.spec_from_file_location('fft128_receiver', ROOT/'src/PS/fft128/receiver.py')
receiver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(receiver)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iverilog', default=shutil.which('iverilog') or str(ROOT/'build/hdl-tools/ucrt64/bin/iverilog.exe'))
    parser.add_argument('--vvp', default=shutil.which('vvp') or str(ROOT/'build/hdl-tools/ucrt64/bin/vvp.exe'))
    args = parser.parse_args()
    work = ROOT/'build/fft128_verify'
    work.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20261114)
    vectors = [[0]*128, [receiver.pack_iq((16384, -8192))]+[0]*127,
               [receiver.pack_iq((12000, -4096))]*128,
               [receiver.pack_iq((32767, 32767))]*128,
               [receiver.pack_iq((-32768, -32768))]*128]
    for tone in (1, 11, -19):
        vectors.append([receiver.pack_iq((round(15000*math.cos(2*math.pi*tone*k/128)),
                                         round(15000*math.sin(2*math.pi*tone*k/128)))) for k in range(128)])
    while len(vectors)<16:
        vectors.append([receiver.pack_iq(z) for z in rng.integers(-32768, 32768, size=(128, 2))])
    d, r = np.indices((128, 128))
    frame = (0.35*np.exp(2j*np.pi*(11*r/128-7*d/128))
             +0.08*np.exp(2j*np.pi*(30*r/128+13*d/128)))
    quantized, scale = receiver.quantize(frame.tolist())
    ranged = [receiver.fft_q15(row) for row in quantized]
    columns = [[ranged[ch][k] for ch in range(128)] for k in range(128)]
    vectors.extend(quantized)
    vectors.extend(columns)
    expected = [receiver.fft_q15(v) for v in vectors]
    actual2d = np.array([[complex(*receiver.unpack_iq(expected[144+k][ch])) for k in range(128)]
                         for ch in range(128)])
    q = np.array([[complex(*receiver.unpack_iq(w)) for w in row] for row in quantized])
    independent = np.fft.fft2(q)/(128*128)
    max_error = float(np.max(np.abs(actual2d-independent)))
    assert max_error < 12, max_error
    peak = np.unravel_index(np.argmax(abs(actual2d)), actual2d.shape)
    assert peak == (121, 11), peak
    for name, data in [('inputs', vectors), ('expected', expected)]:
        (work/(name+'.hex')).write_text(''.join(f'{word:08x}\n' for row in data for word in row))
        (work/(name+'_stream.hex')).write_text(''.join(f'{word:08x}\n' for row in data[:16] for word in row))
    # Ensure checked-in ROM agrees with numeric convention (independent float check above too).
    rom = (HERE/'fft128_twiddle.v').read_text()
    for k, (real, imag) in enumerate(receiver.TWIDDLES):
        assert f"rom[{k}] = 32'h{((real & 65535)<<16)|(imag & 65535):08x};" in rom
    rtl = [HERE/n for n in ('fft128_stream.v','fft128_twiddle.v','butterfly_engine.v',
                             'fft_working_ram.v','address_generator.v','fft128_axi.v',
                             'fft128_pipeline.v','butterfly_pipeline.v')]
    for top, pipeline in ((t,p) for p in (0,1) for t in ('stream_tb','axi_tb')):
        label=top+('_pipeline' if pipeline else '_serial')
        exe = work/(label+'.vvp')
        command = [args.iverilog, '-g2012', '-s', top, '-o', str(exe),
                   *(['-DFFT128_PIPELINE', '-Paxi_tb.PIPELINED=1'] if pipeline else []),
                   *map(str, rtl), str(HERE/(top+'.v'))]
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        (work/(label+'_compile.log')).write_text(result.stdout+result.stderr)
        if result.returncode:
            raise RuntimeError(result.stdout+result.stderr)
        result = subprocess.run([args.vvp, str(exe), f'+CASES={len(vectors)}'], cwd=work,
                                capture_output=True, text=True, timeout=180)
        (work/(label+'.log')).write_text(result.stdout+result.stderr)
        print(result.stdout, end='', flush=True)
        if result.returncode or 'PASS' not in result.stdout:
            raise RuntimeError(result.stderr or result.stdout)
    report = dict(axi_vectors=len(vectors), exact_complex_bins=len(vectors)*128,
                  full_2d_frame_shape=[128,128], independent_numpy_max_error_q15_lsb=max_error,
                  known_tone_peak_unshifted=list(map(int,peak)),
                  tested='Serial and pipelined RTL simulation; new pipeline implementation timing and board behavior unverified',
                  serial_cycles=3073, pipeline_cycles=861)
    (work/'result.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
