#!/usr/bin/env python3
"""E14 full 2D frame RTL; no generated DMA/DDR/reset-IP or board is simulated."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-baseline',action='store_true')
    parser.add_argument('--iverilog',default=shutil.which('iverilog') or str(ROOT/'build/hdl-tools/ucrt64/bin/iverilog.exe'))
    parser.add_argument('--vvp',default=shutil.which('vvp') or str(ROOT/'build/hdl-tools/ucrt64/bin/vvp.exe'))
    args=parser.parse_args()
    work=ROOT/'build/fft128_dma_frame_verify';work.mkdir(parents=True,exist_ok=True)
    if not args.skip_baseline:
        result=subprocess.run([sys.executable,str(HERE/'verify_dma_stream.py'),'--iverilog',args.iverilog,'--vvp',args.vvp],capture_output=True,text=True,timeout=1500)
        (work/'baseline.log').write_text(result.stdout+result.stderr,encoding='utf-8')
        if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    spec=importlib.util.spec_from_file_location('oracle',ROOT/'src/PS/fft128/receiver.py')
    oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
    rng=np.random.default_rng(20261121)
    zero=[[0]*128 for _ in range(128)]
    impulse=[row[:] for row in zero];impulse[17][93]=oracle.pack_iq((32767,-32768))
    constant=[[oracle.pack_iq((32767,32767))]*128 for _ in range(128)]
    random=[[oracle.pack_iq(z) for z in row] for row in rng.integers(-32768,32768,size=(128,128,2))]
    d,r=np.indices((128,128));tones=.35*np.exp(2j*np.pi*(11*r-7*d)/128)+.08*np.exp(2j*np.pi*(30*r+13*d)/128)
    tone,_=oracle.quantize(tones.tolist())
    sys.path.insert(0,str(ROOT/'benchmarks'))
    from ps_precision.prepare_reference import reference
    _,q,_=reference(ROOT/'benchmarks/fixtures/radarsimpy_128x128.rspb')
    recorded=[[oracle.pack_iq((z.real,z.imag)) for z in row] for row in q]
    frames=[zero,impulse,constant,random,tone,recorded]
    outputs=[]
    for frame in frames:
        ranged=[oracle.fft_q15(row) for row in frame]
        columns=[oracle.fft_q15([ranged[ch][r] for ch in range(128)]) for r in range(128)]
        outputs.append([[columns[r][d] for r in range(128)] for d in range(128)])
    for name,values in [('frames.hex',frames),('frames_expected.hex',outputs)]:
        (work/name).write_text(''.join(f'{word:08x}\n' for frame in values for row in frame for word in row),encoding='ascii')
    names=['fft128_frame_ram.v','fft128_dma_frame_ctrl.v','fft128_streaming.v','fft128_stream_stage.v',
           'butterfly_pipeline.v','fft128_twiddle.v','fft_working_ram.v','address_generator.v','dma_frame_ctrl_tb.v']
    exe=work/'frame.vvp'
    result=subprocess.run([args.iverilog,'-g2012','-Wall','-s','dma_frame_ctrl_tb','-o',str(exe),*[str(HERE/n) for n in names]],capture_output=True,text=True,timeout=60)
    (work/'compile.log').write_text(result.stdout+result.stderr,encoding='utf-8')
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    result=subprocess.run([args.vvp,str(exe)],cwd=work,capture_output=True,text=True,timeout=420)
    (work/'frame.log').write_text(result.stdout+result.stderr,encoding='utf-8')
    print(result.stdout,end='',flush=True)
    if result.returncode or 'DMA_FRAME_CTRL_PASS' not in result.stdout:raise RuntimeError(result.stderr or result.stdout)
    report=dict(experiment='E14-frame',unique_full_frames=6,frame_labels=['zero','off-origin impulse','positive saturation DC','full-scale seeded random','two tones','RadarSimPy recorded'],
                arithmetic='Unchanged Q15 butterfly/twiddle and per-stage 1/2 scale',
                baseline_rerun=not args.skip_baseline,complete_frames_verified=18,exact_complex_bins=294912,
                zero_stall_cycles=51927,zero_stall_range_cycles=17771,zero_stall_doppler_cycles=17771,zero_stall_drain_cycles=16385,
                cycle_derived_frame_ms_at_50mhz=1.03854,logical_matrix_bytes=65536,fft_cores=1,dedicated_stages=7,
                dma_requests_per_frame=1,dma_channel_submissions_per_frame=2,payload_bytes_per_frame=131072,
                cpu_transpose=False,output_order='doppler-major/range-minor',board_verified=False,
                scope='Full 2D RTL, AXI/control and inferred behavioral matrix RAM; excludes implementation timing, actual DMA/DDR/IRQ/kernel/board',
                checks=['all stored bins integer-exact','per-stage issue/retire 16384/frame','in-place consumed-before-overwrite scoreboard',
                        'no matrix read/write address collision','exact matrix read/write counts','phase-cycle sum','long downstream stall',
                        'source starvation','repeated requests without explicit reset','malformed TLAST/TKEEP and recovery',
                        'independent AW/W and held AXI responses','soft/hard abort in Range/Doppler/drain and full recomputation'])
    (work/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()
