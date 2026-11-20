#!/usr/bin/env python3
"""Summarize E13-stream's nested host/kernel/PL profile without double-counting."""
import argparse
import csv
import json
import math
from pathlib import Path
import statistics

HOST = ('host_input_copy_ms', 'ioctl_ms', 'host_output_copy_ms', 'gather_ms', 'scatter_ms')
KERNEL = ('kernel_copy_in_ms', 'kernel_submit_ms', 'kernel_wait_ms', 'kernel_check_ms', 'kernel_copy_out_ms')


def analyze(path):
    with Path(path).open() as source:
        rows = list(csv.DictReader(source))
    if not rows:
        raise ValueError('Empty DMA profile')
    for index, row in enumerate(rows, 1):
        if int(row['iteration']) != index or int(row['fft_calls']) != 256:
            raise ValueError('Missing iteration/FFT calls')
        if tuple(int(row[k]) for k in ('dma_requests','dma_channel_submissions','fft_per_request','bytes_each_direction_per_request')) != (2,4,128,65536):
            raise ValueError('E13-stream batching contract differs')
        hz, cycles = int(row['pl_clock_hz_declared']), int(row['pl_active_cycles'])
        lo, hi = int(row['min_active_cycles']), int(row['max_active_cycles'])
        if hz != 50000000 or not 0 < lo <= hi or not lo*2 <= cycles <= hi*2:
            raise ValueError('Invalid E13-stream clock/cycle counters')
        if min(int(row['input_stall_cycles']),int(row['output_stall_cycles'])) < 0 or max(int(row['input_stall_cycles']),int(row['output_stall_cycles'])) > cycles or int(row['bytes_each_direction_per_fft']) != 512:
            raise ValueError('Invalid stall counters/transfer size')
        if (int(row['streaming_cores']),int(row['streaming_stages'])) != (1,7):
            raise ValueError('Expected one seven-stage pipeline')
        busy,multi,vectors=(int(row[k]) for k in ('stage_busy_cycles','multi_stage_cycles','vector_overlap_cycles'))
        if busy!=256*7*68 or busy>7*cycles or not 0<multi<=cycles or 2*multi>busy or not 0<vectors<=cycles:
            raise ValueError('Streaming stage/vector counters invalid')
        for stage in range(7):
            if (int(row[f'stage{stage}_issue']),int(row[f'stage{stage}_retire']))!=(16384,16384):
                raise ValueError('Stage issue/retire conservation failed')
        io,iw,ow,three=(int(row[k]) for k in ('io_overlap_cycles','input_calc_overlap_cycles','output_calc_overlap_cycles','three_overlap_cycles'))
        if not 0<three<=min(io,iw,ow)<=max(io,iw,ow)<=min(cycles,32768):
            raise ValueError('Streaming IO/CALC overlap counters invalid')
        values = [float(row[k]) for k in ('wall_ms', 'pl_active_ms', *HOST, *KERNEL)]
        if any(not math.isfinite(x) or x < 0 for x in values) or values[0] <= 0:
            raise ValueError('Nonfinite/negative profile time')
        if not math.isclose(float(row['pl_active_ms']),cycles*1000/hz,rel_tol=1e-7):
            raise ValueError('Cycle conversion mismatch')
        if sum(float(row[k]) for k in HOST) > float(row['wall_ms'])+.01:
            raise ValueError('Overlapping/corrupt host stages')
        if sum(float(row[k]) for k in KERNEL) > float(row['ioctl_ms'])+.01:
            raise ValueError('Nested kernel stages exceed host ioctl')
    means = {k: statistics.mean(float(r[k]) for r in rows) for k in ('wall_ms','pl_active_ms',*HOST,*KERNEL)}
    return dict(status='E13_STREAM_DMA_DIAGNOSTIC_ONLY', frames=len(rows), mean_ms=means,
                wall_median_ms=statistics.median(float(r['wall_ms']) for r in rows),
                host_residual_ms=means['wall_ms']-sum(means[k] for k in HOST),
                ioctl_residual_ms=means['ioctl_ms']-sum(means[k] for k in KERNEL),
                streaming_counters_mean={k:statistics.mean(int(r[k]) for r in rows) for k in
                    ('stage_busy_cycles','multi_stage_cycles','vector_overlap_cycles','io_overlap_cycles','input_calc_overlap_cycles','output_calc_overlap_cycles','three_overlap_cycles',
                     *[f'stage{i}_issue' for i in range(7)],*[f'stage{i}_retire' for i in range(7)])},
                payload_bytes_per_frame=256*512*2,
                interpretation='Seven dedicated DIT stages with double input/output frame slots. '
                    'Stage busy cycles sum across stages and exceed wall cycles. '
                    'Multi-stage CALC and multiple in-flight vectors prove inter-frame pipelining. '
                    'Nested kernel and PL intervals overlap ioctl; never add these to host stages. '
                    'Separate unprofiled paired trials establish performance; fixed-frame offline latency is not continuous UDP throughput.')



if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile',type=Path)
    args=parser.parse_args()
    report=analyze(args.profile)
    args.profile.with_suffix('.summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
