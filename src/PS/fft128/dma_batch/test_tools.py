"""E11b host regression: real gather/scatter, independent oracle and error paths."""
import ctypes
import csv
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent))
from test_native import Profile

SPEC = importlib.util.spec_from_file_location('batch_profile', HERE/'analyze_profile.py')
analysis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analysis)
SPEC = importlib.util.spec_from_file_location('q15_oracle', HERE.parent/'receiver.py')
oracle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(oracle)


class BatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = ROOT/'build/fft128_dma_batch_tools_tests'
        cls.work.mkdir(parents=True, exist_ok=True)
        stub = cls.work/'axis_stub.c'
        stub.write_text('''#include "batch_process.h"
static int calls, failure;
void reset_stub(int fail) {calls=0;failure=fail;}
int stub_calls(void) {return calls;}
int fft128_batch_axis(const uint32_t *in,uint32_t *out,unsigned count,uint32_t timeout,fft128_profile *p) {
    ++calls;
    if(count!=128 || timeout!=1000) return -88;
    if(calls==failure) return -77;
    for(unsigned k=0;k<count;++k) fft128_model(in+128*k,out+128*k,0);
    if(p) {++p->calls;p->pl_cycles+=861*128;p->min_cycles=p->max_cycles=861*128;}
    return 0;
}
''')
        dll = cls.work/('batch.dll' if sys.platform=='win32' else 'batch.so')
        subprocess.run([shutil.which('gcc'), '-O2', '-std=c11', '-Wall', '-Wextra', '-Werror',
                        '-shared', '-fPIC', '-I', str(HERE), str(stub),
                        str(HERE/'batch_process.c'), str(HERE.parent/'native_core.c'),
                        '-lm', '-o', str(dll)], check=True, capture_output=True)
        cls.lib = ctypes.CDLL(str(dll))
        cls.array = ctypes.c_uint32*16384
        cls.lib.fft128_process_batch.argtypes = [ctypes.POINTER(ctypes.c_uint32)]*5+[ctypes.POINTER(Profile)]

    def run_batch(self, source, fail=0):
        self.lib.reset_stub(fail)
        arrays = [self.array(*source), self.array(), self.array(), self.array(), self.array()]
        p = Profile()
        ret = self.lib.fft128_process_batch(*arrays, ctypes.byref(p))
        return ret, np.array(arrays[1], dtype=np.uint32), p

    def test_two_axes_match_independent_python_integer_model(self):
        rng = np.random.default_rng(1119)
        iq = rng.integers(-16000, 16001, (128,128,2))
        source = ((iq[:,:,0].astype(np.uint32)&65535) |
                  ((iq[:,:,1].astype(np.uint32)&65535)<<16))
        rows = [oracle.fft_q15(list(map(int,row))) for row in source]
        cols = [oracle.fft_q15([rows[ch][r] for ch in range(128)]) for r in range(128)]
        expected = np.array(cols, dtype=np.uint32).T.ravel()
        ret, actual, profile = self.run_batch(source.ravel())
        self.assertEqual(ret, 0)
        np.testing.assert_array_equal(actual, expected)
        self.assertEqual(self.lib.stub_calls(), 2)
        self.assertEqual(profile.calls, 2)
        self.assertEqual(profile.pl_cycles, 256*861)

    def test_first_and_second_axis_errors_propagate(self):
        for fail in (1,2):
            ret, _, _ = self.run_batch(np.zeros(16384,dtype=np.uint32),fail)
            self.assertEqual(ret,-77)
            self.assertEqual(self.lib.stub_calls(),fail)

    def test_profile_rejects_unbatched_or_bad_cycle_data(self):
        row = {k: '0' for k in (*analysis.HOST,*analysis.KERNEL)}
        row.update(iteration=1,fft_calls=256,pl_clock_hz_declared=50000000,
                   pl_active_cycles=256*861,min_active_cycles=128*861,max_active_cycles=128*861,
                   input_stall_cycles=0,output_stall_cycles=0,bytes_each_direction_per_fft=512,
                   dma_requests=2,dma_channel_submissions=4,fft_per_request=128,
                   bytes_each_direction_per_request=65536,wall_ms=8,pl_active_ms=4.40832,ioctl_ms=6)
        path=self.work/'profile.csv'
        def write():
            with path.open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=row);w.writeheader();w.writerow(row)
        write()
        self.assertEqual(analysis.analyze(path)['frames'],1)
        row['dma_requests']=256;write()
        with self.assertRaises(ValueError): analysis.analyze(path)
        row['dma_requests']=2;row['input_stall_cycles']=1;write()
        with self.assertRaises(ValueError): analysis.analyze(path)


if __name__=='__main__':
    unittest.main()
