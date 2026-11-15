import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import numpy as np
from analyze import analyze, error_metrics, VARIANTS
from prepare_reference import prepare, reference, ROOT


class ReferenceTests(unittest.TestCase):
    def test_pinned_reference_matches_existing_double_board_output(self):
        expected, q, _ = reference(ROOT/'benchmarks/fixtures/radarsimpy_128x128.rspb')
        self.assertEqual(np.unravel_index(np.argmax(abs(expected)), expected.shape), (107, 20))
        np.testing.assert_array_equal(q.real, q.real.astype(np.int16))
        np.testing.assert_array_equal(q.imag, q.imag.astype(np.int16))
        path = ROOT/'build/fft128_board_benchmark/results_pipeline50/ps_1.csv'
        if path.exists():
            rows = np.loadtxt(path, delimiter=',', skiprows=1)
            actual = (rows[:, 2]+1j*rows[:, 3]).reshape(128, 128)
            error_metrics(actual, expected, 1e-7, 1e-12)

    def test_tolerance_detects_nonfinite_and_wrong_result(self):
        expected, _, _ = reference(ROOT/'benchmarks/fixtures/radarsimpy_128x128.rspb')
        error_metrics(expected.astype(np.complex64), expected, .01, 1e-5)
        for value in (np.nan, 1):
            wrong = expected.copy()
            wrong[0, 0] += value
            with self.assertRaises(ValueError):
                error_metrics(wrong, expected, .01, 1e-5)


class AnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        prepare(self.folder)
        (self.folder/'environment.txt').write_text('repeat=1 warmup=0 trials=1\n', encoding='utf-8')
        (self.folder/'order.txt').write_text('trial=1 order=double float_scalar float_neon\n', encoding='utf-8')
        meta = json.loads((self.folder/'reference.json').read_text(encoding='utf-8'))
        for variant in VARIANTS:
            p = self.folder/variant
            p.mkdir()
            for name in ('build_environment.txt', 'fftw_build_environment.txt'):
                (p/name).write_text(variant, encoding='utf-8')
            (p/'preflight.log').write_text('Range plan:\n(dft-neon)\nFFT: single\n' if variant == 'float_neon' else 'Range plan:\n(dft-scalar)\nFFT: scalar\n', encoding='utf-8')
            shutil.copyfile(self.folder/'reference.csv', p/'trial_1.csv')
            precision = 'float64' if variant == 'double' else 'float32'
            (p/'trial_1.log').write_text(
                f'PS_PRECISION={precision} PS_VARIANT={variant}\nCPU_AFFINITY=0\nFFT: FFTW WISDOM\n'
                f'Warmup: 0, repeats of SAME frame: 1\nInput: Q15-quantized integers, scale={meta["input_to_q15_scale"]:.17g}, output normalization=1/(pulses*samples)\n'
                'PS_VERIFY_PASS repeats=1 bins=16384 max_error_q15_lsb=0 worst_rms_q15_lsb=0 worst_relative_l2=0\n', encoding='utf-8')
            (p/'trial_1.timings.csv').write_text('stage,iteration,wall_ms,cpu_ms\nfft_pipeline,1,5,4\n', encoding='utf-8')
        (self.folder/'run_board.sh').write_text('test', encoding='utf-8')
        names = ['frame.rspb', 'reference.csv', 'reference.json', 'run_board.sh']
        hashes = {}
        for name in names:
            hashes[name] = hashlib.sha256((self.folder/name).read_bytes()).hexdigest()
        for variant in VARIANTS:
            lib = 'libfftw3.so.3' if variant == 'double' else 'libfftw3f.so.3'
            for name in ('build_environment.txt', 'fftw_build_environment.txt'):
                hashes[f'{variant}/{name}'] = hashlib.sha256((self.folder/variant/name).read_bytes()).hexdigest()
            for name in ('bin/receiver', f'lib/{lib}'):
                hashes[f'{variant}/{name}'] = '0'*64
        (self.folder/'artifacts.sha256').write_text(''.join(f'{v}  {k}\n' for k, v in hashes.items()), encoding='utf-8')
        (self.folder/'artifact_check.txt').write_text(''.join(f'{k}: OK\n' for k in hashes), encoding='utf-8')

    def test_smoke_is_labelled_and_not_a_300_frame_performance_report(self):
        self.assertEqual(analyze(self.folder, smoke=True)['status'], 'PS01_SMOKE_VALIDATED')
        with self.assertRaisesRegex(ValueError, 'Performance report requires'):
            analyze(self.folder)

    def test_variant_label_cannot_substitute_for_neon_plan(self):
        (self.folder/'float_neon/preflight.log').write_text('PS_VARIANT=float_neon\nRange plan:\n(dft-scalar)\nFFT: single\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'NEON codelet'):
            analyze(self.folder, smoke=True)

    def test_missing_per_repeat_validation_and_timing_rejected(self):
        log = self.folder/'double/trial_1.log'
        original = log.read_text(encoding='utf-8')
        log.write_text(original.replace('repeats=1 bins=16384', 'repeats=0 bins=16384'), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'per-repeat verification'):
            analyze(self.folder, smoke=True)
        log.write_text(original, encoding='utf-8')
        (self.folder/'double/trial_1.timings.csv').write_text('stage,iteration,wall_ms,cpu_ms\nfft_pipeline,2,5,4\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'timing iterations'):
            analyze(self.folder, smoke=True)

    def test_changed_metadata_and_missing_board_artifact_check_rejected(self):
        file = self.folder/'reference.json'
        original = file.read_text(encoding='utf-8')
        file.write_text(original+' ', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'metadata hash'):
            analyze(self.folder, smoke=True)
        file.write_text(original, encoding='utf-8')
        file = self.folder/'artifact_check.txt'
        file.write_text(file.read_text(encoding='utf-8').replace('frame.rspb: OK\n', ''), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Missing board artifact verification'):
            analyze(self.folder, smoke=True)


class CppAccuracyTests(unittest.TestCase):
    """Compile the actual portable checker in both precisions, including on Windows.

    This does not compile the Linux socket/profiler path or certify ARM/NEON FFTW.
    """
    def test_reference_parser_numeric_thresholds_and_nonfinite_detection(self):
        compiler = shutil.which('g++')
        if not compiler:
            self.skipTest('g++ unavailable for portable C++ checker')
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            prepare(p)
            source = (ROOT/'src/PS/receiver/udp_radar_receiver.cpp').read_text(encoding='utf-8')
            checker = source[source.index('struct Accuracy {'):source.index('\nvoid process(')]
            for real, maximum, relative in (('float', .01, 1e-5), ('double', 1e-7, 1e-12)):
                code = '\n'.join('#include <'+h+'>' for h in ('algorithm', 'cmath', 'complex', 'fstream', 'sstream', 'stdexcept', 'string', 'vector', 'limits'))
                code += f'\nusing Real={real}; using FComplex=Real[2]; constexpr double VERIFY_MAX={maximum},VERIFY_REL={relative};\n'+checker
                code += '''
int main(int argc,char**argv) {
 try {
  Accuracy a; a.load(argv[1],128,128);
  std::vector<Real> data(a.reference.size()*2);
  for(size_t i=0;i<a.reference.size();++i){data[2*i]=Real(a.reference[i].real());data[2*i+1]=Real(a.reference[i].imag());}
  if(argc>2 && std::string(argv[2])=="corrupt") data[0]+=1;
  if(argc>2 && std::string(argv[2])=="nan") data[0]=std::numeric_limits<Real>::quiet_NaN();
  a.check(reinterpret_cast<const FComplex*>(data.data())); return 0;
 } catch(const std::exception&) { return 2; }
}
'''
                cpp = p/(real+'.cpp'); binary = p/(real+'.exe')
                cpp.write_text(code, encoding='utf-8')
                result = subprocess.run([compiler, '-std=c++17', '-O2', str(cpp), '-o', str(binary)], capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stderr)
                for mode, status in (('', 0), ('corrupt', 2), ('nan', 2)):
                    result = subprocess.run([str(binary), str(p/'reference.csv'), mode], timeout=10)
                    self.assertEqual(result.returncode, status, (real, mode))
                broken = p/'broken.csv'
                broken.write_text('doppler_bin_unshifted,range_bin,real,imag\n1,0,0,0\n', encoding='utf-8')
                self.assertEqual(subprocess.run([str(binary), str(broken)], timeout=10).returncode, 2)


if __name__ == '__main__':
    unittest.main()
