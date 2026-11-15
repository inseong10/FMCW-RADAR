#!/usr/bin/env python3
"""Validate and summarize the same-board C++/FFTW versus PL benchmark artifacts."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import numpy as np


def timings(path):
    with path.open() as stream:
        rows=[r for r in csv.DictReader(stream) if r['stage']=='fft_pipeline']
    if not rows or [int(r['iteration']) for r in rows] != list(range(1,len(rows)+1)):
        raise ValueError(f'Incomplete timing iterations: {path}')
    values=np.array([float(r['wall_ms']) for r in rows])
    if not np.all(np.isfinite(values)) or np.any(values<=0):
        raise ValueError(f'Invalid timing values: {path}')
    return values


def spectrum(path):
    rows=np.loadtxt(path,delimiter=',',skiprows=1)
    d,r=np.indices((128,128))
    if rows.shape!=(16384,4) or not np.all(np.isfinite(rows)):
        raise ValueError(f'Invalid spectrum: {path}')
    if not np.array_equal(rows[:,0],d.ravel()) or not np.array_equal(rows[:,1],r.ravel()):
        raise ValueError(f'Invalid bin order: {path}')
    return (rows[:,2]+1j*rows[:,3]).reshape(128,128)


def stats(values):
    return {'count':len(values),'mean_ms':float(np.mean(values)),
            'median_ms':float(np.median(values)),'p05_ms':float(np.quantile(values,.05)),
            'p95_ms':float(np.quantile(values,.95)),'min_ms':float(np.min(values)),
            'max_ms':float(np.max(values))}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results',type=Path)
    args=parser.parse_args()
    folder=args.results
    ps_ids={p.name.split('_')[1].split('.')[0] for p in folder.glob('ps_*.timings.csv')}
    pl_ids={p.name.split('_')[1].split('.')[0] for p in folder.glob('pl_*.timings.csv')}
    if not ps_ids or ps_ids!=pl_ids:
        raise ValueError('Expected matching nonempty PS/PL trials')
    cpu_times=[]; pl_times=[]; trials=[]; input_digest=None
    for trial in sorted(ps_ids,key=int):
        report=json.loads((folder/f'pl_{trial}.json').read_text())
        if report['backend']!='PL_MMIO' or report['shape']!=[128,128] or report['mismatched_complex_bins']!=0:
            raise ValueError('PL result must be verified actual PL_MMIO, shape 128x128')
        digest=hashlib.sha256((folder/f'pl_{trial}.input.csv').read_bytes()).hexdigest()
        if input_digest is not None and digest!=input_digest:
            raise ValueError('Input differs between trials')
        input_digest=digest
        ps_log=(folder/f'ps_{trial}.log').read_text()
        if 'Q15-quantized integers' not in ps_log or 'output normalization=1/(pulses*samples)' not in ps_log:
            raise ValueError('PS run did not use matched Q15 input and normalization')
        if 'FFTW WISDOM' not in ps_log:
            raise ValueError('PS did not use the target-generated FFTW wisdom')
        if 'CPU_AFFINITY=0' not in ps_log or 'CPU_AFFINITY=0' not in (folder/f'pl_{trial}.log').read_text():
            raise ValueError('Both PS and PL host program must be pinned to CPU0')
        source=np.loadtxt(folder/f'pl_{trial}.input.csv',delimiter=',',skiprows=1)
        if source.shape!=(16384,4) or not np.all(np.isfinite(source)):
            raise ValueError('Invalid board input CSV')
        scale=report['input_to_q15_scale']
        q=(np.rint(source[:,2]*scale)+1j*np.rint(source[:,3]*scale)).reshape(128,128)
        reference=np.fft.fft2(q)/16384
        cpu=spectrum(folder/f'ps_{trial}.csv')
        pl=spectrum(folder/f'pl_{trial}.csv')
        cpu_error=float(np.max(abs(cpu-reference)))
        pl_error=float(np.max(abs(pl-reference)))
        if cpu_error>1e-7 or pl_error>12:
            raise ValueError(f'Accuracy failure trial={trial}: PS={cpu_error}, PL={pl_error}')
        a=timings(folder/f'ps_{trial}.timings.csv'); b=timings(folder/f'pl_{trial}.timings.csv')
        if len(a)!=len(b) or len(b)!=report['repeats']:
            raise ValueError('Repeat counts differ')
        if not np.isclose(np.mean(b)/1000,report['fft_and_transfer_seconds'],rtol=1e-7,atol=1e-9):
            raise ValueError('PL timing CSV/JSON do not agree')
        cpu_times.extend(a); pl_times.extend(b)
        trials.append({'trial':int(trial),'ps':stats(a),'pl':stats(b),
                       'ps_max_error_q15_lsb':cpu_error,'pl_max_error_q15_lsb':pl_error})
    cpu_stats=stats(cpu_times); pl_stats=stats(pl_times)
    result={'status':'SAME_BOARD_BENCHMARK_VALIDATED','shape':[128,128],
            'ps_implementation':'existing optimized C++/FFTW double, 32x32 tiled transpose',
            'pl_implementation':'Q15 iterative FFT + AXI4-Lite MMIO + PS transpose; no DMA',
            'input':'same Q15-quantized simulator frame; window none; normalization 1/16384',
            'scope':'fft_pipeline only; buffers/plans/input preparation/IO/postprocessing excluded',
            'layout':'PS FFTW output internally range-major; PL result row-major; CSV serialization excluded',
            'ps':cpu_stats,'pl':pl_stats,
            'speedup_ps_median_over_pl_median':cpu_stats['median_ms']/pl_stats['median_ms'],
            'trials':trials,'input_csv_sha256':input_digest,
            'environment':(folder/'environment.txt').read_text()}
    (folder/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
