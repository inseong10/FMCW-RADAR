#!/usr/bin/env python3
"""Summarize E11b's nested host/kernel/PL profile without double-counting."""
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
    nonstall = []
    for index, row in enumerate(rows, 1):
        if int(row['iteration']) != index or int(row['fft_calls']) != 256:
            raise ValueError('Missing iteration/FFT calls')
        if tuple(int(row[k]) for k in ('dma_requests','dma_channel_submissions','fft_per_request','bytes_each_direction_per_request')) != (2,4,128,65536):
            raise ValueError('E11b batching contract differs')
        hz, cycles = int(row['pl_clock_hz_declared']), int(row['pl_active_cycles'])
        lo, hi = int(row['min_active_cycles']), int(row['max_active_cycles'])
        if hz != 50000000 or not 0 < lo <= hi or not lo*2 <= cycles <= hi*2:
            raise ValueError('Invalid E11b clock/cycle counters')
        stalls = int(row['input_stall_cycles'])+int(row['output_stall_cycles'])
        if stalls < 0 or stalls > cycles or int(row['bytes_each_direction_per_fft']) != 512:
            raise ValueError('Invalid stall counters/transfer size')
        if cycles-stalls != 256*861:
            raise ValueError('E11b nonstall interval differs from unchanged pipeline RTL (861/FFT)')
        values = [float(row[k]) for k in ('wall_ms', 'pl_active_ms', *HOST, *KERNEL)]
        if any(not math.isfinite(x) or x < 0 for x in values) or values[0] <= 0:
            raise ValueError('Nonfinite/negative profile time')
        if not math.isclose(float(row['pl_active_ms']),cycles*1000/hz,rel_tol=1e-7):
            raise ValueError('Cycle conversion mismatch')
        if sum(float(row[k]) for k in HOST) > float(row['wall_ms'])+.01:
            raise ValueError('Overlapping/corrupt host stages')
        if sum(float(row[k]) for k in KERNEL) > float(row['ioctl_ms'])+.01:
            raise ValueError('Nested kernel stages exceed host ioctl')
        nonstall.append((cycles-stalls)/256)
    means = {k: statistics.mean(float(r[k]) for r in rows) for k in ('wall_ms','pl_active_ms',*HOST,*KERNEL)}
    return dict(status='E11B_DMA_DIAGNOSTIC_ONLY', frames=len(rows), mean_ms=means,
                wall_median_ms=statistics.median(float(r['wall_ms']) for r in rows),
                host_residual_ms=means['wall_ms']-sum(means[k] for k in HOST),
                ioctl_residual_ms=means['ioctl_ms']-sum(means[k] for k in KERNEL),
                active_minus_stream_stalls_cycles_per_fft=dict(min=min(nonstall),max=max(nonstall)),
                payload_bytes_per_frame=256*512*2,
                interpretation='Kernel stages and PL active time overlap ioctl. Do not sum them with host stages. '
                               'Active cycles include AXIS stalls; subtracting stalls is a diagnostic RTL interval, '
                               'not a measured end-to-end saving. Coherent HP0 bounce copies included; no streaming sync. '
                               'Separate unprofiled paired trials are required for performance comparisons.')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile',type=Path)
    args=parser.parse_args()
    report=analyze(args.profile)
    args.profile.with_suffix('.summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
