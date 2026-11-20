#!/usr/bin/env python3
"""Summarize E12-4core's nested host/kernel/PL profile without double-counting."""
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
    multi_windows = []; all_windows = []
    for index, row in enumerate(rows, 1):
        if int(row['iteration']) != index or int(row['fft_calls']) != 256:
            raise ValueError('Missing iteration/FFT calls')
        if tuple(int(row[k]) for k in ('dma_requests','dma_channel_submissions','fft_per_request','bytes_each_direction_per_request')) != (2,4,128,65536):
            raise ValueError('E12-4core batching contract differs')
        hz, cycles = int(row['pl_clock_hz_declared']), int(row['pl_active_cycles'])
        lo, hi = int(row['min_active_cycles']), int(row['max_active_cycles'])
        if hz != 50000000 or not 0 < lo <= hi or not lo*2 <= cycles <= hi*2:
            raise ValueError('Invalid E12-4core clock/cycle counters')
        if min(int(row['input_stall_cycles']),int(row['output_stall_cycles'])) < 0 or max(int(row['input_stall_cycles']),int(row['output_stall_cycles'])) > cycles or int(row['bytes_each_direction_per_fft']) != 512:
            raise ValueError('Invalid stall counters/transfer size')
        if int(row['parallel_cores']) != 4:
            raise ValueError('Expected four arithmetic cores')
        cores=[int(row[f'core{i}_active_cycles']) for i in range(4)]
        any_busy,multi_busy,all_busy,multi_work,all_work,arb=(int(row[k]) for k in
            ('any_busy_cycles','multi_busy_cycles','all_busy_cycles','multi_work_cycles','all_work_cycles','arbitration_stall_cycles'))
        if not (0 < all_busy <= min(cores) <= max(cores) <= any_busy <= cycles) or not all_busy <= multi_busy <= any_busy:
            raise ValueError('Quad busy counter hierarchy invalid')
        if not any_busy+multi_busy+2*all_busy <= sum(cores) <= any_busy+2*multi_busy+all_busy:
            raise ValueError('Impossible core/union busy counters')
        if not (256 < all_work <= min(multi_work,all_busy)) or not 256 < multi_work <= multi_busy or not 0 <= arb <= cycles:
            raise ValueError('Four-core CALC overlap not established or work-window hierarchy invalid')
        overlap=[int(row[k]) for k in ('io_overlap_cycles','input_work_overlap_cycles','output_work_overlap_cycles','three_overlap_cycles')]
        io,iw,ow,three=overlap
        if not (0 < three <= min(io,iw,ow) <= max(io,iw,ow) <= cycles):
            raise ValueError('Input/work/output overlap counters invalid or overlap absent')
        values = [float(row[k]) for k in ('wall_ms', 'pl_active_ms', *HOST, *KERNEL)]
        if any(not math.isfinite(x) or x < 0 for x in values) or values[0] <= 0:
            raise ValueError('Nonfinite/negative profile time')
        if not math.isclose(float(row['pl_active_ms']),cycles*1000/hz,rel_tol=1e-7):
            raise ValueError('Cycle conversion mismatch')
        if sum(float(row[k]) for k in HOST) > float(row['wall_ms'])+.01:
            raise ValueError('Overlapping/corrupt host stages')
        if sum(float(row[k]) for k in KERNEL) > float(row['ioctl_ms'])+.01:
            raise ValueError('Nested kernel stages exceed host ioctl')
        multi_windows.append(multi_work);all_windows.append(all_work)
    means = {k: statistics.mean(float(r[k]) for r in rows) for k in ('wall_ms','pl_active_ms',*HOST,*KERNEL)}
    return dict(status='E12_4CORE_DMA_DIAGNOSTIC_ONLY', frames=len(rows), mean_ms=means,
                wall_median_ms=statistics.median(float(r['wall_ms']) for r in rows),
                host_residual_ms=means['wall_ms']-sum(means[k] for k in HOST),
                ioctl_residual_ms=means['ioctl_ms']-sum(means[k] for k in KERNEL),
                multi_work_cycles=dict(min=min(multi_windows),max=max(multi_windows),mean=statistics.mean(multi_windows)),
                all_work_cycles=dict(min=min(all_windows),max=max(all_windows),mean=statistics.mean(all_windows)),
                simultaneous_multi_calc_cycles_lower_bound=dict(min=min(multi_windows)-256,max=max(multi_windows)-256,mean=statistics.mean(multi_windows)-256),
                simultaneous_four_calc_cycles_lower_bound=dict(min=min(all_windows)-256,max=max(all_windows)-256,mean=statistics.mean(all_windows)-256),
                parallel_counters_mean={k:statistics.mean(int(r[k]) for r in rows) for k in
                    ('core0_active_cycles','core1_active_cycles','core2_active_cycles','core3_active_cycles','any_busy_cycles','multi_busy_cycles','all_busy_cycles','multi_work_cycles','all_work_cycles','arbitration_stall_cycles','io_overlap_cycles','input_work_overlap_cycles','output_work_overlap_cycles','three_overlap_cycles')},
                payload_bytes_per_frame=256*512*2,
                interpretation='Kernel stages and PL active time overlap ioctl. Do not sum them with host stages. '
                               'Input and output stalls may overlap each other across lanes; never subtract their sum as pure compute time. '
                               'Work window spans last input handshake to first output valid, including initial output read latency. IO overlap counts simultaneous external handshakes; work overlap includes that initial read clock. Bounds subtract 256 cycles/frame for multi-work and 256 for all-four-work. Coherent HP0 copies included. '
                               'Separate unprofiled paired trials are required for performance comparisons.')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile',type=Path)
    args=parser.parse_args()
    report=analyze(args.profile)
    args.profile.with_suffix('.summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
