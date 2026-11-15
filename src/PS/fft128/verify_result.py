#!/usr/bin/env python3
"""PC NumPy comparison of artifacts produced by receiver.py (model or PL)."""
import argparse
import json
from pathlib import Path
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('prefix', type=Path, help='Output prefix, without .csv/.json')
    args = parser.parse_args()
    report = json.loads(args.prefix.with_suffix('.json').read_text())
    source = np.loadtxt(args.prefix.with_suffix('.input.csv'), delimiter=',', skiprows=1)
    result = np.loadtxt(args.prefix.with_suffix('.csv'), delimiter=',', skiprows=1)
    if source.shape != (16384,4) or result.shape != (16384,4):
        raise ValueError('Expected complete 128x128 input and output')
    d, r = np.indices((128,128))
    if not (np.array_equal(source[:,0],d.ravel()) and np.array_equal(source[:,1],r.ravel())
            and np.array_equal(result[:,0],d.ravel()) and np.array_equal(result[:,1],r.ravel())):
        raise ValueError('CSV bin order mismatch')
    scale = report['input_to_q15_scale']
    q = np.rint(source[:,2]*scale)+1j*np.rint(source[:,3]*scale)
    reference = np.fft.fft2(q.reshape(128,128))/16384
    measured = (result[:,2]+1j*result[:,3]).reshape(128,128)
    error = float(np.max(abs(measured-reference)))
    peak = tuple(map(int,np.unravel_index(np.argmax(abs(measured)), measured.shape)))
    expected_peak = tuple(map(int,np.unravel_index(np.argmax(abs(reference)), reference.shape)))
    print(f"backend={report['backend']} max_error={error:.6f} Q15 LSB "
          f"peak={peak} reference_peak={expected_peak}")
    # Numerical FFT check complements the bit-exact check run on PS.
    if error>12:
        raise RuntimeError('FLOAT_REFERENCE_FAIL: >12 Q15 LSB complex error')
    print('FLOAT_REFERENCE_PASS; hardware evidence only when backend=PL_MMIO')


if __name__ == '__main__':
    main()
