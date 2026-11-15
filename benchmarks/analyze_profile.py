#!/usr/bin/env python3
"""Summarize a separate MMIO diagnostic run; PL cycles overlap host start/wait."""
import argparse
import csv
import json
import math
from pathlib import Path
import statistics

HOST_STAGES = ('input_write_ms', 'start_wait_ms', 'counter_read_ms',
               'output_read_ms', 'gather_ms', 'scatter_ms')


def analyze(path):
    with path.open() as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError('Empty profile')
    clocks = set()
    for index, row in enumerate(rows, 1):
        if int(row['iteration']) != index or int(row['fft_calls']) != 256:
            raise ValueError('Incomplete frame/iteration in MMIO profile')
        hz = int(row['pl_clock_hz_declared'])
        cycles = int(row['pl_cycles'])
        low, high = int(row['min_cycles']), int(row['max_cycles'])
        if hz <= 0 or low <= 0 or high < low or not low*256 <= cycles <= high*256:
            raise ValueError('Invalid cycle counter/declared clock')
        clocks.add(hz)
        values = [float(row[k]) for k in ('wall_ms', 'pl_internal_ms', *HOST_STAGES)]
        if any(not math.isfinite(v) or v < 0 for v in values):
            raise ValueError('Invalid time measurement')
        if not math.isclose(float(row['pl_internal_ms']), cycles*1000/hz, rel_tol=1e-7):
            raise ValueError('Counter-to-time conversion mismatch')
        if sum(float(row[k]) for k in HOST_STAGES) > float(row['wall_ms'])+.01:
            raise ValueError('Host stage times exceed total; possible overlap or corrupt profile')
    if len(clocks) != 1:
        raise ValueError('Do not combine different declared clocks')
    means = {k: statistics.mean(float(r[k]) for r in rows) for k in ('wall_ms', *HOST_STAGES, 'pl_internal_ms')}
    result = {
        'status': 'MMIO_DIAGNOSTIC_PROFILE', 'frames': len(rows),
        'pl_clock_hz_declared': clocks.pop(), 'mean_ms': means,
        'wall_median_ms': statistics.median(float(r['wall_ms']) for r in rows),
        'cycles_per_fft_min': min(int(r['min_cycles']) for r in rows),
        'cycles_per_fft_max': max(int(r['max_cycles']) for r in rows),
        'unattributed_host_mean_ms': means['wall_ms']-sum(means[k] for k in HOST_STAGES),
        'wall_minus_pl_internal_mean_ms': means['wall_ms']-means['pl_internal_ms'],
        'interpretation': 'PL internal interval includes load/compute/output and overlaps start_wait_ms. '
                          'Never add PL internal time to host stages. Clock is declared from firmware, '
                          'not independently measured. Diagnostic instrumentation adds overhead; '
                          'use separate unprofiled runs for PS/PL speed comparisons.'}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile', type=Path)
    args = parser.parse_args()
    report = analyze(args.profile)
    output = args.profile.with_suffix('.summary.json')
    output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
