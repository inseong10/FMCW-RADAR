"""PC regression for the C receiver. NumPy/Python are test tools, not board dependencies."""
import ctypes
import csv
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import unittest

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
WORK = ROOT/'build/fft128_native_tests'
SPEC = importlib.util.spec_from_file_location('fft128_reference', HERE/'receiver.py')
reference = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reference)
U32 = ctypes.c_uint32
PTR = ctypes.POINTER(U32)
CALLBACK = ctypes.CFUNCTYPE(ctypes.c_int, PTR, PTR, ctypes.c_void_p)


def packet(row, index, fs=1.6e6, channel=0):
    payload = np.column_stack((np.real(row),np.imag(row))).astype('>f4').tobytes()
    return reference.HEADER.pack(b'RSPY',1,1,channel,index,128,128,fs)+payload


def replay(path, packets):
    with path.open('wb') as out:
        out.write(b'RSPB0001')
        for data in packets:
            out.write(struct.pack('!I',len(data)))
            out.write(data)


class Sample(ctypes.Structure):
    _fields_ = [('real',ctypes.c_double),('imag',ctypes.c_double)]

class Profile(ctypes.Structure):
    _fields_ = [(n,ctypes.c_uint64) for n in ('input_write_ns','start_wait_ns',
        'counter_read_ns','output_read_ns','gather_ns','scatter_ns','pl_cycles')]
    _fields_ += [(n,ctypes.c_uint32) for n in ('calls','min_cycles','max_cycles')]
    _fields_ += [(n,ctypes.c_uint64) for n in ('dma_copy_in_ns','dma_submit_ns',
        'dma_wait_ns','dma_check_ns','dma_copy_out_ns','dma_input_stalls','dma_output_stalls')]

class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = os.environ.get('FFT128_TEST_CC') or shutil.which('gcc')
        if not compiler:
            raise unittest.SkipTest('GCC required for native C regression')
        WORK.mkdir(parents=True,exist_ok=True)
        cls.exe = WORK/('fft128-receiver.exe' if sys.platform=='win32' else 'fft128-receiver')
        dll = WORK/('native_core.dll' if sys.platform=='win32' else 'native_core.so')
        common = [compiler,'-O2','-std=c11','-Wall','-Wextra','-Werror']
        sources = [str(HERE/'native_receiver.c'),str(HERE/'native_core.c')]
        libs = ['-lws2_32'] if sys.platform=='win32' else []
        if sys.platform!='win32':
            sources.append(str(HERE/'mmio.c'))
        subprocess.run(common+sources+libs+['-lm','-o',str(cls.exe)],check=True,capture_output=True)
        subprocess.run(common+['-shared','-fPIC',str(HERE/'native_core.c'),'-lm','-o',str(dll)],
                       check=True,capture_output=True)
        cls.lib = ctypes.CDLL(str(dll))
        cls.lib.fft128_model.argtypes = [PTR,PTR,ctypes.c_void_p]
        cls.lib.fft128_model.restype = ctypes.c_int
        cls.lib.fft128_quantize.argtypes = [ctypes.POINTER(Sample),PTR,ctypes.POINTER(ctypes.c_double)]
        cls.lib.fft128_quantize.restype = ctypes.c_int
        cls.lib.fft128_process.argtypes = [PTR,PTR,CALLBACK,ctypes.c_void_p]
        cls.lib.fft128_process.restype = ctypes.c_int
        cls.lib.fft128_process_profiled.argtypes = [PTR,PTR,PTR,CALLBACK,ctypes.c_void_p,ctypes.POINTER(Profile)]
        cls.lib.fft128_process_profiled.restype = ctypes.c_int

    def run_cli(self, *args):
        return subprocess.run([str(self.exe),*map(str,args)],capture_output=True,text=True,timeout=20)

    def test_profile_context_and_transpose_preserve_result(self):
        packed=(U32*16384)(); plain=(U32*16384)(); profiled=(U32*16384)(); workspace=(U32*16384)()
        packed[0]=0x10002000
        model=CALLBACK(lambda src,dst,ctx: self.lib.fft128_model(src,dst,None))
        self.assertEqual(self.lib.fft128_process(packed,plain,model,None),0)
        profile=Profile()
        def mocked_hardware(src,dst,ctx):
            p=ctypes.cast(ctx,ctypes.POINTER(Profile)).contents
            p.calls+=1; p.pl_cycles+=861; p.input_write_ns+=100
            return self.lib.fft128_model(src,dst,None)
        callback=CALLBACK(mocked_hardware)
        self.assertEqual(self.lib.fft128_process_profiled(packed,profiled,workspace,callback,
                         ctypes.byref(profile),ctypes.byref(profile)),0)
        self.assertEqual(bytes(plain),bytes(profiled))
        self.assertEqual((profile.calls,profile.pl_cycles,profile.input_write_ns),(256,256*861,25600))
        self.assertGreater(profile.gather_ns,0)
        self.assertGreater(profile.scatter_ns,0)

    def test_profile_requires_explicit_hardware_clock(self):
        for args in (('--profile-mmio',),('--backend','model','--profile-mmio','--pl-clock-hz','20000000'),
                     ('--pl-clock-hz','50000000'),('--self-test','--profile-mmio','--pl-clock-hz','20000000')):
            result=self.run_cli(*args)
            self.assertEqual(result.returncode,2,result.stderr)
            self.assertIn('Profiling requires',result.stderr)

    def test_repeated_frame_timing_excludes_warmup_and_preserves_result(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td); record=folder/'frame.rspb'; prefix=folder/'result'
            frame=np.zeros((128,128),dtype=np.complex128)
            frame[0,0]=0.25-0.125j
            replay(record,[packet(frame[k],k) for k in range(128)])
            result=self.run_cli('--backend','model','--input',record,'--output',prefix,
                                '--warmup','2','--repeat','3')
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('FRAME_PASS backend=SOFTWARE_MODEL',result.stdout)
            report=json.loads(prefix.with_suffix('.json').read_text())
            self.assertEqual((report['warmup'],report['repeats']),(2,3))
            with prefix.with_suffix('.timings.csv').open() as stream:
                times=list(csv.DictReader(stream))
            self.assertEqual(len(times),3)
            self.assertEqual([int(r['iteration']) for r in times],[1,2,3])
            self.assertTrue(all(r['stage']=='fft_pipeline' and float(r['wall_ms'])>0 for r in times))
            mean=sum(float(r['wall_ms']) for r in times)/3000
            self.assertAlmostEqual(mean,report['fft_and_transfer_seconds'],places=8)
            bad=self.run_cli('--backend','model','--repeat','0')
            self.assertNotEqual(bad.returncode,0)

    def test_c_reference_matches_python_and_existing_rtl_vectors(self):
        rng = np.random.default_rng(501)
        vectors = [[0]*128,[reference.pack_iq((-32768,32767))]*128]
        vectors += [[reference.pack_iq(z) for z in rng.integers(-32768,32768,(128,2))] for _ in range(30)]
        for vector in vectors:
            out = (U32*128)()
            self.assertEqual(self.lib.fft128_model((U32*128)(*vector),out,None),0)
            self.assertEqual(list(out),reference.fft_q15(vector))
        source, expected = ROOT/'build/fft128_verify/inputs.hex', ROOT/'build/fft128_verify/expected.hex'
        if source.is_file() and expected.is_file():
            words = [int(x,16) for x in source.read_text().split()]
            golden = [int(x,16) for x in expected.read_text().split()]
            self.assertEqual(len(words),len(golden))
            for k in range(0,len(words),128):
                out = (U32*128)()
                self.lib.fft128_model((U32*128)(*words[k:k+128]),out,None)
                self.assertEqual(list(out),golden[k:k+128])

    def test_quantization_and_callback_failure(self):
        rng = np.random.default_rng(502)
        frame = rng.normal(size=(128,128))+1j*rng.normal(size=(128,128))
        source = (Sample*16384)(*(Sample(z.real,z.imag) for z in frame.flat))
        packed, output = (U32*16384)(), (U32*16384)()
        scale = ctypes.c_double()
        self.assertEqual(self.lib.fft128_quantize(source,packed,ctypes.byref(scale)),0)
        expected, expected_scale = reference.quantize(frame.tolist())
        np.testing.assert_array_equal(np.array(packed),np.array(expected).ravel())
        self.assertAlmostEqual(scale.value,expected_scale)
        calls = []
        @CALLBACK
        def failing(incoming,out,context):
            calls.append(1)
            return -77 if len(calls)==131 else self.lib.fft128_model(incoming,out,context)
        self.assertEqual(self.lib.fft128_process(packed,output,failing,None),-77)
        self.assertEqual(len(calls),131)
        source[0].real = float('nan')
        self.assertEqual(self.lib.fft128_quantize(source,packed,ctypes.byref(scale)),-1)

    def check_artifacts(self, prefix):
        report = json.loads(prefix.with_suffix('.json').read_text())
        self.assertIn('SOFTWARE_MODEL',report['backend'])
        self.assertEqual(report['implementation'],'native C')
        source = np.loadtxt(prefix.with_suffix('.input.csv'),delimiter=',',skiprows=1)
        measured = np.loadtxt(prefix.with_suffix('.csv'),delimiter=',',skiprows=1)
        z = (source[:,2]+1j*source[:,3]).reshape(128,128)
        expected, scale = reference.quantize(z.tolist())
        ranged = [reference.fft_q15(row) for row in expected]
        exact = np.empty((128,128),dtype=np.complex128)
        for r in range(128):
            column = reference.fft_q15([ranged[ch][r] for ch in range(128)])
            exact[:,r] = [complex(*reference.unpack_iq(word)) for word in column]
        actual = (measured[:,2]+1j*measured[:,3]).reshape(128,128)
        np.testing.assert_array_equal(actual,exact)
        quantized = np.rint(z.real*scale)+1j*np.rint(z.imag*scale)
        self.assertLess(float(np.max(abs(actual-np.fft.fft2(quantized)/16384))),12)
        return report

    def test_reordered_offline_frame_and_numpy_reference(self):
        d,r = np.indices((128,128))
        frame = np.exp(2j*np.pi*(20*r/128-21*d/128)).astype(np.complex64)
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            data, prefix = folder/'frame.rspb',folder/'result'
            packets = [packet(frame[127],127),packet(frame[127],127)]
            packets += [packet(frame[k],k) for k in reversed(range(127))]
            replay(data,packets)
            result = self.run_cli('--backend','model','--input',data,'--output',prefix)
            self.assertEqual(result.returncode,0,result.stderr+result.stdout)
            self.assertIn('FRAME_PASS backend=SOFTWARE_MODEL',result.stdout)
            report = self.check_artifacts(prefix)
            self.assertEqual(report['peak_unshifted'],[107,20])
            self.assertEqual(report['duplicate_packets'],1)

    def test_reject_incomplete_changed_rate_truncated_and_invalid_payload(self):
        row = np.zeros(128,dtype=np.complex64)
        with tempfile.TemporaryDirectory() as td:
            data = Path(td)/'bad.rspb'
            for packets, message in [([packet(row,k) for k in range(127)],'Incomplete frame'),
                                     ([packet(row,0),packet(row,1,fs=2e6)],'Sampling rate changed'),
                                     ([packet(np.full(128,complex(np.nan,0)),0)],'Incomplete frame'),
                                     ([packet(row,128)],'Incomplete frame'),
                                     ([packet(row,0)[:-1]],'Incomplete frame')]:
                replay(data,packets)
                result = self.run_cli('--backend','model','--input',data)
                self.assertNotEqual(result.returncode,0)
                self.assertIn(message,result.stderr)
            data.write_bytes(b'RSPB0001'+struct.pack('!I',2000)+b'short')
            self.assertIn('Truncated',self.run_cli('--backend','model','--input',data).stderr)

    def test_actual_radarsimpy_udp_frame_peer_lock_and_reference(self):
        captured = ROOT/'build/fft128_udp/radarsimpy.input.csv'
        if captured.is_file():
            values = np.loadtxt(captured,delimiter=',',skiprows=1)
            frame = (values[:,2]+1j*values[:,3]).reshape(128,128)
        else:
            d,r = np.indices((128,128))
            frame = np.exp(2j*np.pi*(11*r/128-7*d/128))
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as probe:
            probe.bind(('127.0.0.1',0)); port = probe.getsockname()[1]
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td); logpath=folder/'receiver.log'; prefix=folder/'result'
            with logpath.open('w') as log:
                process = subprocess.Popen([str(self.exe),'--backend','model','--bind','127.0.0.1',
                                            '--port',str(port),'--timeout','10','--output',str(prefix)],
                                           stdout=log,stderr=subprocess.STDOUT)
                try:
                    deadline=time.monotonic()+5
                    while 'LISTENING' not in logpath.read_text():
                        if process.poll() is not None or time.monotonic()>deadline:
                            self.fail(logpath.read_text())
                        time.sleep(.01)
                    dest=('127.0.0.1',port)
                    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sender:
                        sender.sendto(packet(frame[127],127),dest)
                        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as stranger:
                            stranger.sendto(packet(frame[0],0,fs=3e6),dest)
                        sender.sendto(packet(frame[127],127),dest)
                        sender.sendto(packet(frame[0],0,channel=1),dest)
                        sender.sendto(b'invalid',dest)
                        for k in reversed(range(127)):
                            sender.sendto(packet(frame[k],k),dest)
                            time.sleep(.001)
                    self.assertEqual(process.wait(timeout=15),0,logpath.read_text())
                finally:
                    if process.poll() is None: process.kill(); process.wait()
            report = self.check_artifacts(prefix)
            self.assertEqual(report['duplicate_packets'],1)
            self.assertEqual(report['dropped_packets'],3)
            if captured.is_file(): self.assertEqual(report['peak_unshifted'],[107,20])
            (WORK/'udp_result.json').write_text(json.dumps(report,indent=2)+'\n')

    def test_selftest_help_and_udp_timeout(self):
        self.assertEqual(self.run_cli('--help').returncode,0)
        result=self.run_cli('--backend','model','--self-test')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('SELFTEST_PASS backend=SOFTWARE_MODEL',result.stdout)
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as probe:
            probe.bind(('127.0.0.1',0)); port=probe.getsockname()[1]
        result=self.run_cli('--backend','model','--bind','127.0.0.1','--port',port,'--timeout','.1')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Incomplete frame',result.stderr)
        if sys.platform=='win32':
            result=self.run_cli('--self-test')
            self.assertNotEqual(result.returncode,0)
            self.assertIn('no software fallback',result.stderr)


if __name__=='__main__':
    unittest.main()
