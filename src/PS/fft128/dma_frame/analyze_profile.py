#!/usr/bin/env python3
"""E14 one full-frame request; phase sums are PL wall cycles, stage sums overlap."""
import argparse
import csv
import json
import math
from pathlib import Path
import statistics

HOST=('host_input_copy_ms','ioctl_ms','host_output_copy_ms','gather_ms','scatter_ms')
KERNEL=('kernel_copy_in_ms','kernel_submit_ms','kernel_wait_ms','kernel_check_ms','kernel_copy_out_ms')
COUNTERS=('range_cycles','doppler_cycles','drain_cycles','matrix_reads','matrix_writes','range_outputs','doppler_inputs','doppler_outputs',
          'overwrite_errors','io_overlap_cycles','matrix_words','stage_busy_cycles','multi_stage_cycles','vector_overlap_cycles',
          *[f'stage{s}_issue' for s in range(7)],*[f'stage{s}_retire' for s in range(7)])

def analyze(path):
    with Path(path).open() as source:rows=list(csv.DictReader(source))
    if not rows:raise ValueError('Empty frame profile')
    for index,row in enumerate(rows,1):
        contract=('fft_calls','dma_requests','dma_channel_submissions','fft_per_request','bytes_each_direction_per_request','payload_bytes_per_frame','bytes_each_direction_per_fft','streaming_cores','streaming_stages')
        if int(row['iteration'])!=index or tuple(int(row[k]) for k in contract)!=(256,1,2,256,65536,131072,0,1,7):
            raise ValueError('E14 full-frame contract differs')
        hz,cycles=int(row['pl_clock_hz_declared']),int(row['pl_active_cycles'])
        if hz!=50000000 or cycles<=0 or int(row['min_active_cycles'])!=cycles or int(row['max_active_cycles'])!=cycles:
            raise ValueError('Invalid frame clock/cycles')
        phase=[int(row[k]) for k in ('range_cycles','doppler_cycles','drain_cycles')]
        if min(phase)<=0 or phase[2]<16385 or sum(phase)!=cycles:raise ValueError('Phase cycles do not partition active cycles')
        for k in ('input_stall_cycles','output_stall_cycles'):
            if not 0<=int(row[k])<=cycles:raise ValueError('Invalid external stalls')
        expected=dict(matrix_reads=32768,matrix_writes=32768,range_outputs=16384,doppler_inputs=16384,doppler_outputs=16384,
                      overwrite_errors=0,io_overlap_cycles=0,matrix_words=16384,stage_busy_cycles=121856)
        if any(int(row[k])!=v for k,v in expected.items()):raise ValueError('Matrix/stage conservation failed')
        if any(int(row[f'stage{s}_{event}'])!=16384 for s in range(7) for event in ('issue','retire')):
            raise ValueError('Stage issue/retire conservation failed')
        busy,multi,vectors=(int(row[k]) for k in ('stage_busy_cycles','multi_stage_cycles','vector_overlap_cycles'))
        if busy>7*cycles or not 0<multi<=cycles or 2*multi>busy or not 0<vectors<=cycles:
            raise ValueError('Invalid stage/vector overlap')
        values=[float(row[k]) for k in ('wall_ms','pl_active_ms',*HOST,*KERNEL)]
        if any(not math.isfinite(x) or x<0 for x in values) or values[0]<=0:raise ValueError('Nonfinite/negative profile time')
        if float(row['gather_ms'])!=0 or float(row['scatter_ms'])!=0:raise ValueError('CPU transpose present in E14')
        if not math.isclose(float(row['pl_active_ms']),cycles*1000/hz,rel_tol=1e-7):raise ValueError('Cycle conversion mismatch')
        if sum(float(row[k]) for k in HOST)>float(row['wall_ms'])+.01:raise ValueError('Host stages exceed wall')
        if sum(float(row[k]) for k in KERNEL)>float(row['ioctl_ms'])+.01:raise ValueError('Nested kernel stages exceed ioctl')
    means={k:statistics.mean(float(row[k]) for row in rows) for k in ('wall_ms','pl_active_ms',*HOST,*KERNEL)}
    return dict(status='E14_FRAME_DMA_DIAGNOSTIC_ONLY',frames=len(rows),mean_ms=means,
                wall_median_ms=statistics.median(float(row['wall_ms']) for row in rows),
                host_residual_ms=means['wall_ms']-sum(means[k] for k in HOST),
                ioctl_residual_ms=means['ioctl_ms']-sum(means[k] for k in KERNEL),
                frame_counters_mean={k:statistics.mean(int(row[k]) for row in rows) for k in COUNTERS},
                phase_ms={k:statistics.mean(int(row[k]) for row in rows)/50000 for k in ('range_cycles','doppler_cycles','drain_cycles')},
                payload_bytes_per_frame=131072,
                interpretation='One reused FFT for both axes, one in-place 64KiB matrix, PL transpose and row-major drain. '
                    'Range/Doppler/drain cycles partition PL active; seven stage CALC counters overlap. '
                    'PL active and kernel stages are nested within ioctl, not extra host costs. '
                    'Copies are retained for the initial input and final output. Separate paired trials measure offline latency; continuous UDP is unverified.')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('profile',type=Path);args=parser.parse_args()
    result=analyze(args.profile);args.profile.with_suffix('.summary.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
