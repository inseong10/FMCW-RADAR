"""S2a-int16 portable production wire/pipeline and ADC boundary regression tests."""
import json
import struct
import tempfile
import unittest
import argparse
from contextlib import redirect_stdout
import io
import socket
import threading
from pathlib import Path
import numpy as np
import adc16_reference as adc
import make_adc16_fixture as fixture
import test_s2a as legacy
import check_adc16_stream
from adc16_record import ADC_SCALE, read_adc_frame, write_adc_frame


class BoundaryTests(unittest.TestCase):
    def test_udp_sender_keeps_unwindowed_signed16_payload(self):
        record=legacy.ROOT/'benchmarks/fixtures/adc16/radarsimpy_128x128_sim_multi4_noise_adc16.rspb'
        rows,_,_=read_adc_frame(record)
        with tempfile.TemporaryDirectory() as tmp,socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as listener:
            listener.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,1024*1024)
            listener.bind(('127.0.0.1',0));listener.settimeout(3)
            received=[]
            def collect():
                for _ in range(128):received.append(listener.recvfrom(2048)[0])
            thread=threading.Thread(target=collect);thread.start()
            args=argparse.Namespace(record=record,ip='127.0.0.1',port=listener.getsockname()[1],
                frames=1,run_id=9,period_ms=50,chirp_gap_us=0,drop_frame=0,out=Path(tmp)/'sender.json')
            try:
                with redirect_stdout(io.StringIO()):legacy.sender.send(args)
            finally:thread.join(timeout=4)
            self.assertEqual(len(received),128)
            for i,p in enumerate(received):
                self.assertEqual(len(p),568)
                self.assertEqual(p[4:6],bytes([3,2]))
                self.assertEqual(struct.unpack_from('!I',p,52)[0],1)
                self.assertEqual(p[56:],rows[i])
            summary=json.loads(args.out.read_text())
            self.assertEqual(summary['protocol_version'],3)
            self.assertEqual(summary['schedule'][0]['bytes'],72704)

    def test_ties_even_and_saturation(self):
        values = np.array([.5,1.5,2.5,-.5,-1.5,-2.5,40000,-40000])/ADC_SCALE
        codes, stats = fixture.quantize(values.astype(complex))
        np.testing.assert_array_equal(codes[:,0], [0,2,2,0,-2,-2,32767,-32768])
        self.assertEqual(stats['clipped_components'], 2)

    def test_all_frozen_records_sha_gain_and_no_window(self):
        folder = legacy.ROOT/'benchmarks/fixtures/adc16'
        manifest = json.loads((folder/'adc16_profile.json').read_text())
        for case in manifest['records']:
            path = folder/case['file']
            self.assertEqual(fixture.sha(path), case['record_sha256'])
            source = folder.parent/case['source_file']
            self.assertEqual(fixture.sha(source), case['source_sha256'])
            original, _ = fixture.ref.read_rspb(source)
            expected, stats = fixture.quantize(original)
            rows, _, profile = read_adc_frame(path)
            np.testing.assert_array_equal(np.frombuffer(b''.join(rows), '>i2').reshape(128,128,2), expected)
            self.assertFalse(profile['window_applied'])
            self.assertEqual(stats['clipped_components'], 0)

    def test_record_strictness_and_exclusive_write(self):
        path = legacy.ROOT/'benchmarks/fixtures/adc16/radarsimpy_128x128_sim_single_noise_adc16.rspb'
        raw = path.read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/'bad.rspb'
            for content in (raw[:-1], raw+b'x', raw[:36]+struct.pack('!I', 99)+raw[40:]):
                out.write_bytes(content)
                with self.assertRaises(ValueError):read_adc_frame(out)
            out.unlink()
            rows, fs, _ = read_adc_frame(path)
            write_adc_frame(out, b''.join(rows), fs)
            with self.assertRaises(FileExistsError):write_adc_frame(out, b''.join(rows), fs)


@unittest.skipUnless(legacy.CXX and legacy.CC, 'C/C++ compilers required')
class AdcPipelineTests(unittest.TestCase):
    # Own build harness: the shared folder's user-edited legacy tests stay intact.
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.folder=Path(cls.tmp.name)
        cls.binary=cls.folder/('stream.exe' if legacy.os.name=='nt' else 'stream')
        obj=cls.folder/'core.o'
        legacy.subprocess.run([legacy.CC,'-O2','-std=c11','-Wall','-Wextra','-Werror','-c',
            str(legacy.ROOT/'src/PS/fft128/native_core.c'),'-o',str(obj)],capture_output=True,check=True)
        legacy.subprocess.run([legacy.CXX,'-O2','-std=c++17','-Wall','-Wextra','-Werror',
            str(legacy.ROOT/'src/PS/receiver/tests/stream_driver.cpp'),str(obj),
            *([] if legacy.os.name=='nt' else ['-ldl']),'-o',str(cls.binary)],capture_output=True,check=True)
        cls.adc_binary=cls.folder/('adc.exe' if legacy.os.name=='nt' else 'adc')
        legacy.subprocess.run([legacy.CXX,'-std=c++17','-Wall','-Wextra','-Werror',
            str(legacy.ROOT/'src/PS/receiver/tests/adc16_driver.cpp'),'-o',str(cls.adc_binary)],
            capture_output=True,check=True)

    def test_integer_window_ties_and_abi_packing(self):
        run=legacy.subprocess.run([str(self.adc_binary)],capture_output=True,text=True,check=True)
        self.assertIn('ADC16_NUMERIC_PASS',run.stdout)

    @classmethod
    def tearDownClass(cls):
        report=legacy.os.environ.get('ADC16_TEST_REPORT')
        if report:
            out=Path(report)/'binaries';out.mkdir(parents=True,exist_ok=True)
            for path in (cls.binary,cls.adc_binary,cls.folder/'core.o'):
                legacy.shutil.copy2(path,out/path.name)
        cls.tmp.cleanup()

    def run_wire(self,packets,backend='model',window='hann'):
        path=self.folder/'wire';path.write_bytes(b''.join(packets))
        return legacy.subprocess.run([str(self.binary),str(path),backend,window,legacy.FFTW or '',
            str(self.folder/'out')],capture_output=True,text=True,timeout=30)

    def load(self,name):
        packets,_=legacy.sender.read_frame(legacy.ROOT/f'benchmarks/fixtures/radarsimpy_128x128_sim_{name}_noise.rspb')
        return None,[legacy.sender.packet_v2(p,9,1,123456789) for p in packets]
    def adc_wire(self, name):
        path = legacy.ROOT/f'benchmarks/fixtures/adc16/radarsimpy_128x128_sim_{name}_noise_adc16.rspb'
        rows, fs, _ = read_adc_frame(path)
        return [legacy.sender.packet_v3(row, i, fs, 9, 1, 123456789) for i,row in enumerate(rows)]

    def compare_adc(self, backend):
        comparisons = []
        for name in ('single','multi4','close_weak'):
            wire = self.adc_wire(name)
            path = legacy.ROOT/f'benchmarks/fixtures/adc16/radarsimpy_128x128_sim_{name}_noise_adc16.rspb'
            original, fs = fixture.ref.read_rspb(path.parent.parent/f'radarsimpy_128x128_sim_{name}_noise.rspb')
            meta = json.loads(path.with_suffix('.json').read_text())
            for window in ('none','hann'):
                with self.subTest(name=name,window=window,backend=backend):
                    run = self.run_wire(wire[::-1]+wire[:1], backend, window)
                    self.assertEqual(run.returncode,0,run.stderr)
                    expected, threshold, peaks, result = adc.accuracy(path, backend, window)
                    bins = np.loadtxt(self.folder/'out.bins.csv',delimiter=',')
                    bins = (bins[:,0]+1j*bins[:,1]).reshape(128,128)
                    actual_power = np.loadtxt(self.folder/'out.power.csv').reshape(128,128)
                    if backend == 'model':np.testing.assert_array_equal(bins,expected)
                    else:np.testing.assert_allclose(bins,expected,atol=1e-9,rtol=1e-9)
                    np.testing.assert_allclose(actual_power,expected.real**2+expected.imag**2,atol=1e-7,rtol=1e-9)
                    with (self.folder/'out.peaks.csv').open(newline='') as f:rows=list(legacy.csv.DictReader(f))
                    self.assertEqual([(int(r['doppler']),int(r['range'])) for r in rows],peaks)
                    for row, peak in zip(rows,peaks):
                        np.testing.assert_allclose(float(row['threshold']),threshold[peak],rtol=1e-9)
                    float_peaks = fixture.ref.cluster_peaks(*self.float_cells(original,window))
                    truth, false = fixture.ref.evaluate(float_peaks,meta['targets'],128,128,fs)
                    comparisons.append({'case':name+'_'+window,'backend':backend,**result,
                                        'float_hits':sum(t['hit'] for t in truth),'float_false':len(false),
                                        'same_peak_bins_as_float':peaks==float_peaks})
        report = legacy.os.environ.get('ADC16_TEST_REPORT')
        if report:
            Path(report).mkdir(parents=True,exist_ok=True)
            (Path(report)/(backend+'_accuracy.json')).write_text(json.dumps(comparisons,indent=2)+'\n')

    @staticmethod
    def float_cells(original,window):
        power = fixture.ref.range_doppler_power(original,window)
        cells,_ = fixture.ref.ca_cfar_2d(power,(2,2),(8,8),1e-6)
        return power,cells

    def test_adc_model_all_bins_six_cases(self):self.compare_adc('model')

    @unittest.skipUnless(legacy.FFTW,'Set S2A_FFTW')
    def test_adc_ps_all_bins_six_cases(self):self.compare_adc('ps')

    def test_adc_protocol_mixed_profile_truncation_rejected(self):
        wire = self.adc_wire('single')
        bad_profile=bytearray(wire[0]);struct.pack_into('!I',bad_profile,52,2)
        bad_type=bytearray(wire[0]);bad_type[5]=1
        _, floats=self.load('single')
        for packets in ([bad_profile]+wire[1:],[bad_type]+wire[1:],wire[:-1]+[wire[-1][:-1]],
                        [floats[0]]+wire[1:]):
            self.assertNotEqual(self.run_wire(packets).returncode,0)

    def test_adc_full_scale_identity_and_integer_hann(self):
        values=np.resize(np.array([-32768,32767,-1,0,1,3,-3],dtype=np.int16),(128,128,2))
        codes=values[...,0].astype(float)+1j*values[...,1]
        wire=[legacy.sender.packet_v3(row.tobytes(),i,1e6,9,1,123456789)
              for i,row in enumerate(values.astype('>i2'))]
        for window in ('none','hann'):
            run=self.run_wire(wire,'model',window)
            self.assertEqual(run.returncode,0,run.stderr)
            rows=np.loadtxt(self.folder/'out.bins.csv',delimiter=',')
            np.testing.assert_array_equal((rows[:,0]+1j*rows[:,1]).reshape(128,128),adc.spectrum(codes,'model',window))


class AdcTraceTests(legacy.TraceTests):
    def test_independent_checker_accepts_valid_bins_and_rejects_corruption(self):
        record=check_adc16_stream.DEFAULT
        bins,threshold,peaks,_=adc.accuracy(record,'model','hann')
        self.row['peaks']=str(len(peaks));self.write()
        (self.folder/'environment.txt').write_text(
            'frames=1\nrun_id=9\nbackend=model\nhardware=0\ninput_format=adc16\n'
            'protocol_version=3\nadc_profile=1\nadc_bits=16\nadc_scale=1600000\n'
            'queue=4\npartial=4\nwindow=hann\ndiagnostic_probe=1\ndiagnostic_spectrum=1\n')
        power=bins.real**2+bins.imag**2
        detections='run_id,frame_id,doppler_bin,range_bin,power,threshold\n'+''.join(
            f'9,1,{d},{r},{power[d,r]:.17g},{threshold[d,r]:.17g}\n' for d,r in peaks)
        (self.folder/'detections.csv').write_text(detections)
        d,r=np.indices((128,128))
        data=np.column_stack((np.ones(16384),d.ravel(),r.ravel(),bins.real.ravel(),bins.imag.ravel()))
        path=self.folder/'diagnostic_spectrum.csv'
        np.savetxt(path,data,delimiter=',',header='frame_id,doppler,range,real,imag',comments='',fmt='%.17g')
        sender=self.folder/'sender.json'
        sender.write_text(json.dumps({'run_id':9,'frames':1,'record_sha256':fixture.sha(record),
            'input_format':'adc16','protocol_version':3,'adc_profile':{'profile':1},'period_ms':50,
            'chirp_gap_us':0,'max_lateness_ms':0,'overrun_frames':0,'drop_frame':0}))
        result=check_adc16_stream.check(self.folder,sender,require_board=False)
        self.assertTrue(result['first_frame_all_bins_checked'])
        data[0,3]+=1
        np.savetxt(path,data,delimiter=',',header='frame_id,doppler,range,real,imag',comments='',fmt='%.17g')
        with self.assertRaises(AssertionError):
            check_adc16_stream.check(self.folder,sender,require_board=False)


if __name__=='__main__':unittest.main()
