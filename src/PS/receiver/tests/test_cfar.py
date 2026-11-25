"""Portable C++ CA-CFAR checks against the independent S1a NumPy kernel."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
SPEC = importlib.util.spec_from_file_location("s1a_cfar", ROOT / "tools/detection/cfar_reference.py")
ref = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ref)
COMPILER = os.environ.get("CXX") or shutil.which("g++") or shutil.which("clang++")


@unittest.skipUnless(COMPILER, "C++17 compiler required for portable CFAR checks")
class CfarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.binary = Path(cls.temp.name) / ("cfar.exe" if os.name == "nt" else "cfar")
        result = subprocess.run([COMPILER, "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror",
                                 str(Path(__file__).with_name("cfar_driver.cpp")), "-o", str(cls.binary)],
                                capture_output=True, text=True, timeout=60)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_cpp(self, power, guard=(2, 2), train=(8, 8), pfa=1e-6):
        header = " ".join(map(str, (*power.shape, *guard, *train, pfa)))
        return subprocess.run([str(self.binary)], input=header+"\n"+" ".join(map(repr, power.ravel().tolist())),
                              capture_output=True, text=True, timeout=15)

    def compare(self, power, guard=(2, 2), train=(8, 8), pfa=1e-6):
        result = self.run_cpp(power, guard, train, pfa)
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.splitlines()
        actual_threshold = np.fromstring(lines[0], sep=" ").reshape(power.shape)
        actual_peaks = [tuple(map(int, line.split())) for line in lines[1:]]
        det, threshold = ref.ca_cfar_2d(power, guard, train, pfa)
        # Summed-area subtraction changes the accumulation order.
        np.testing.assert_allclose(actual_threshold, threshold, rtol=2e-10,
                                   atol=max(1.0, float(threshold.max()))*2e-13)
        self.assertEqual(actual_peaks, ref.cluster_peaks(power, det))

    def test_random_rectangular_and_wrapped_small_maps(self):
        rng = np.random.default_rng(20261125)
        for shape, guard, train in [((32, 48), (2, 2), (8, 8)),
                                     ((5, 7), (1, 0), (3, 2)),
                                     ((1, 9), (0, 1), (2, 2))]:
            with self.subTest(shape=shape):
                power = rng.exponential(size=shape)
                power[0, 0] = power[-1, -1] = 1000
                self.compare(power, guard, train)

    def test_zero_and_tied_peaks(self):
        self.compare(np.zeros((32, 32)))
        power = np.ones((32, 32))
        power[0, 0] = power[31, 0] = power[15, 31] = 1000
        self.compare(power)

    def test_committed_noise_recordings(self):
        for name in ("single", "multi4", "close_weak"):
            path = ROOT / f"benchmarks/fixtures/radarsimpy_128x128_sim_{name}_noise.rspb"
            frame, _ = ref.read_rspb(path)
            for window in ("none", "hann"):
                with self.subTest(name=name, window=window):
                    self.compare(ref.range_doppler_power(frame, window))

    def test_invalid_parameters_and_negative_power(self):
        for guard, train, pfa in [((2, 2), (0, 0), 1e-6),
                                   ((-1, 2), (8, 8), 1e-6),
                                   ((2, 2), (8, 8), 1.0)]:
            with self.subTest(guard=guard, train=train, pfa=pfa):
                self.assertNotEqual(self.run_cpp(np.ones((8, 8)), guard, train, pfa).returncode, 0)
        self.assertNotEqual(self.run_cpp(-np.ones((8, 8))).returncode, 0)


if __name__ == "__main__":
    unittest.main()
