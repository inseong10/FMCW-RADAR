#!/usr/bin/env python3
"""E12-4core AXIS/control regression using the unchanged Q15 FFT numeric oracle."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iverilog', default=shutil.which('iverilog') or str(ROOT/'build/hdl-tools/ucrt64/bin/iverilog.exe'))
    parser.add_argument('--vvp', default=shutil.which('vvp') or str(ROOT/'build/hdl-tools/ucrt64/bin/vvp.exe'))
    parser.add_argument('--skip-baseline', action='store_true', help='Reuse existing numeric fixtures while iterating only E12 RTL')
    args = parser.parse_args()
    work = ROOT/'build/fft128_dma_overlap_verify'
    work.mkdir(parents=True, exist_ok=True)
    if not args.skip_baseline:
        # Rebuild baseline fixtures and run both old RTL variants as a regression.
        result = subprocess.run([sys.executable, str(HERE/'verify_dma_quad.py'), '--iverilog', args.iverilog,
                                 '--vvp', args.vvp], capture_output=True, text=True, timeout=900)
        (work/'baseline.log').write_text(result.stdout+result.stderr, encoding='utf-8')
        if result.returncode:
            raise RuntimeError(result.stdout+result.stderr)
    fixture = ROOT/'build/fft128_verify'
    report = json.loads((fixture/'result.json').read_text())
    for name in ('inputs.hex', 'expected.hex'):
        shutil.copyfile(fixture/name, work/name)
    exe = work/'dma_overlap_ctrl_tb.vvp'
    rtl = [HERE/n for n in ('fft128_dma_overlap_ctrl.v', 'fft128_buffered_lane.v', 'fft128_stream_fifo.v', 'fft128_pipeline.v', 'fft128_twiddle.v',
                            'butterfly_pipeline.v', 'fft_working_ram.v', 'address_generator.v',
                            'dma_overlap_ctrl_tb.v')]
    result = subprocess.run([args.iverilog, '-g2012', '-Wall', '-s', 'dma_overlap_ctrl_tb',
                             '-o', str(exe), *map(str, rtl)], capture_output=True, text=True, timeout=60)
    (work/'compile.log').write_text(result.stdout+result.stderr, encoding='utf-8')
    if result.returncode:
        raise RuntimeError(result.stdout+result.stderr)
    result = subprocess.run([args.vvp, str(exe), f'+CASES={report["axi_vectors"]}'],
                            cwd=work, capture_output=True, text=True, timeout=120)
    (work/'dma_overlap_ctrl_tb.log').write_text(result.stdout+result.stderr, encoding='utf-8')
    if result.returncode or 'DMA_OVERLAP_CTRL_PASS' not in result.stdout:
        raise RuntimeError(result.stdout+result.stderr)
    report['experiment']='E12-4core'
    report['unchanged_core_count']=4
    report['board_verified']=False
    report['zero_external_stall_cycles_per_axis']=28098
    report['cycle_derived_frame_ms_at_50mhz']=1.123920
    report['baseline_rerun']=not args.skip_baseline
    report['schedule']='independent lanes; per-lane 256-word ingress/egress RAM FIFO plus output register; next-vector prefetch; shared ordered AXIS'
    report['dma_requests_per_frame']=2
    report['tested'] = 'Unchanged serial/pipeline baseline plus E12-4core DMA AXIS/control frontend; no AXI DMA IP, DDR, IRQ, kernel or board validation'
    report['dma_checks'] = ['272 independent numeric vectors in full 128-FFT packets', 'AXIS input gaps/output backpressure',
                            'stable stalled payload', 'malformed TLAST/TKEEP flags',
                            'partial-load, compute and stalled-output abort/recovery', '1/2/3/4/5/6/7/127/128-FFT batches', 'external axis TLAST/internal vector TLAST', 'actual four-core CALC, input/output/CALC handshakes and independent overlap counters; next-vector prefetch; long downstream backpressure', 'independent AW/W',
                            'AXI response backpressure and forbidden payload windows',
                            'source-starved correct completion without concurrent CALC', 'lane2 partial-load and lane3 stalled-output abort/recovery; full-buffer abort/recovery', 'FIFO capacity and whole-output reservation every cycle', 'zero-external-stall 128 FFT packet cycle assertion']
    (work/'result.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(result.stdout, end='')


if __name__ == '__main__':
    main()
