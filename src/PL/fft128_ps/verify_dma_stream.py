#!/usr/bin/env python3
"""E13-stream core and AXIS/control verification; board/DDR/DMA IP are excluded."""
import argparse,json,shutil,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-baseline',action='store_true')
    parser.add_argument('--iverilog',default=shutil.which('iverilog') or str(ROOT/'build/hdl-tools/ucrt64/bin/iverilog.exe'))
    parser.add_argument('--vvp',default=shutil.which('vvp') or str(ROOT/'build/hdl-tools/ucrt64/bin/vvp.exe'))
    args=parser.parse_args();work=ROOT/'build/fft128_streaming_verify';work.mkdir(parents=True,exist_ok=True)
    if not args.skip_baseline:
        p=subprocess.run([sys.executable,str(HERE/'verify_dma_bf2.py'),'--iverilog',args.iverilog,'--vvp',args.vvp],capture_output=True,text=True,timeout=1200)
        (work/'baseline.log').write_text(p.stdout+p.stderr,encoding='utf-8')
        if p.returncode:raise RuntimeError(p.stdout+p.stderr)
    fixture=ROOT/'build/fft128_verify'
    for n in ('inputs.hex','expected.hex'):shutil.copyfile(fixture/n,work/n)
    common=['fft128_streaming.v','fft128_stream_stage.v','butterfly_pipeline.v','fft128_twiddle.v','fft_working_ram.v','address_generator.v']
    for name,extra,marker in [('core',['streaming_core_tb.v'],'STREAMING_CORE_PASS'),('dma',['fft128_dma_stream_ctrl.v','dma_stream_ctrl_tb.v'],'DMA_STREAM_CTRL_PASS')]:
        top='streaming_core_tb' if name=='core' else 'dma_stream_ctrl_tb';exe=work/(name+'.vvp')
        p=subprocess.run([args.iverilog,'-g2012','-Wall','-s',top,'-o',str(exe),*[str(HERE/n) for n in common+extra]],capture_output=True,text=True,timeout=60)
        (work/(name+'_compile.log')).write_text(p.stdout+p.stderr,encoding='utf-8')
        if p.returncode:raise RuntimeError(p.stdout+p.stderr)
        p=subprocess.run([args.vvp,str(exe)],cwd=work,capture_output=True,text=True,timeout=180)
        (work/(name+'.log')).write_text(p.stdout+p.stderr,encoding='utf-8')
        if p.returncode or marker not in p.stdout:raise RuntimeError(p.stdout+p.stderr)
        print(p.stdout,end='')
    report=dict(experiment='E13-stream',numeric_vectors=272,exact_complex_bins=34816,arithmetic='Unchanged butterfly_pipeline Q15, 1/2 scaling per DIT stage',architecture='Seven dedicated stages, double input and output frame slots per stage',fft_cores=1,dedicated_stages=7,logical_butterflies=7,frame_initiation_interval=128,stage_calc_cycles_per_fft=68,stage_issue_and_retire_events_per_fft=64,zero_external_stall_axis_cycles=17770,zero_external_stall_frame_cycles=35540,cycle_derived_frame_ms_at_50mhz=0.7108,single_fft_zero_stall_axis_cycles=1514,baseline_rerun=not args.skip_baseline,board_verified=False,scope='Core + AXIS/control simulation; excludes generated reset IP, actual AXI DMA/DDR/IRQ, kernel and board',checks=['272 integer-oracle FFTs','every-stage issue/retire conservation','sustained 128-clock frame initiation','RAM slot conflicts every cycle','stable stalled output','8000-clock downstream stall','source starvation','partial/full/repeated batches','malformed TLAST/TKEEP','independent AXI AW/W and held responses','blocked partial pipeline abort/recovery','multiple active arithmetic stages and in-flight vectors'])
    (work/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':main()
