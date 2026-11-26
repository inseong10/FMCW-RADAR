#!/usr/bin/env python3
"""Measure VM deadline wakeups without network traffic; not an offered-load test."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import sys
import time


def wait_until(deadline, mode, clock=time.monotonic_ns, sleep=time.sleep):
    if mode == 'sleep':
        remaining = deadline - clock()
        if remaining > 0:
            sleep(remaining / 1e9)
    elif mode == 'spin':
        while clock() < deadline:
            pass
    else:
        raise ValueError('Unknown wait mode')


def measure(mode, frames, period_ns, clock=time.monotonic_ns,
            cpu_clock=time.process_time_ns, sleep=time.sleep):
    # A short initial wait is outside measured wakeups and CPU consumption.
    sleep(.05)
    start = clock() + period_ns
    cpu_start = cpu_clock()
    wall_start = clock()
    rows = []
    for frame_id in range(1, frames + 1):
        intended = start + (frame_id - 1) * period_ns
        wait_until(intended, mode, clock, sleep)
        rows.append({'frame_id': frame_id, 'intended_ns': intended, 'wake_ns': clock()})
    wall_end = clock()
    cpu_end = cpu_clock()
    lateness = sorted((r['wake_ns'] - r['intended_ns']) / 1e6 for r in rows)
    threshold_ns = period_ns * .1
    return {'mode': mode, 'frames': frames,
            'median_lateness_ms': lateness[len(lateness)//2],
            'max_lateness_ms': max(lateness),
            'lateness_ge_10pct_period': sum(
                r['wake_ns'] - r['intended_ns'] >= threshold_ns for r in rows),
            'deadline_wakeup_valid': max(lateness) < period_ns / 1e6 * .1,
            'process_cpu_pct_one_core': 100*(cpu_end-cpu_start)/(wall_end-wall_start),
            'schedule': rows}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--period-ms', type=float, default=12.8)
    p.add_argument('--frames', type=int, default=200)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    if (not math.isfinite(args.period_ms) or args.period_ms <= 0 or
            not 1 <= args.frames <= 10000 or args.period_ms*args.frames > 30000 or
            round(args.period_ms*1e6) < 1000):
        p.error('Require positive period >=1us, 1..10000 frames, <=30s per mode')
    if args.out.exists():
        p.error('Use a new output path')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    period_ns = round(args.period_ms*1e6)
    result = {'schema': 1, 'experiment': 'S2b-pacing',
              'scope': 'deadline wakeups only; no packets; no receiver or offered-load claim',
              'python': platform.python_version(), 'platform': platform.platform(),
              'cpu_count': os.cpu_count(),
              'allowed_cpus': sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else None,
              'monotonic_resolution_seconds': time.get_clock_info('monotonic').resolution,
              'period_ms': period_ns/1e6, 'frames': args.frames,
              'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'cases': []}
    for mode in ('sleep', 'spin'):
        case = measure(mode, args.frames, period_ns)
        result['cases'].append(case)
        # Write after each completed case to preserve partial results too.
        args.out.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
        print('PACING mode={} max_late_ms={:.3f} late_frames={} cpu_pct={:.1f}'.format(
            mode, case['max_lateness_ms'], case['lateness_ge_10pct_period'],
            case['process_cpu_pct_one_core']), flush=True)
    print('PACING_RECORDED {} (no network test)'.format(args.out))


if __name__ == '__main__':
    main()
