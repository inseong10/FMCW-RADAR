"""S1c numeric conventions and portable CSV boundary checks."""
import csv
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import numpy as np

import verify_s1c as s1c

COMPILER = os.environ.get("CXX") or shutil.which("g++") or shutil.which("clang++")


class QuantizerTests(unittest.TestCase):
    def test_zero_and_complex_magnitude_scale(self):
        q, scale = s1c.quantize(np.zeros((128, 128), dtype=complex))
        self.assertEqual(scale, 1)
        np.testing.assert_array_equal(q, 0)
        frame = np.zeros((128, 128), dtype=complex)
        frame[0, 0] = 1 + 1j
        q, scale = s1c.quantize(frame)
        self.assertAlmostEqual(scale, 16384 / np.sqrt(2))
        self.assertEqual(q[0, 0], 11585 + 11585j)


@unittest.skipUnless(COMPILER, "C++17 compiler required")
class SpectrumCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.folder = Path(cls.temp.name)
        cls.binary = cls.folder / ("cfar.exe" if os.name == "nt" else "cfar")
        subprocess.run([COMPILER, "-O2", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                        str(Path(__file__).with_name("cfar_spectrum.cpp")), "-o", str(cls.binary)],
                       check=True, capture_output=True, timeout=60)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_cli(self, text):
        path = self.folder / "spectrum.csv"
        path.write_text(text, encoding="utf-8")
        return subprocess.run([str(self.binary), "--input", str(path),
                               "--output", str(self.folder / "detections.csv"),
                               "--timings", str(self.folder / "timings.csv"),
                               "--warmup", "1", "--repeat", "2"], capture_output=True, text=True, timeout=15)

    def test_zero_spectrum_and_time_sample_count(self):
        text = "doppler_bin_unshifted,range_bin,real_q15,imag_q15\n"
        text += "".join(f"{d},{r},0,0\n" for d in range(128) for r in range(128))
        result = self.run_cli(text)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("peaks=0", result.stdout)
        with (self.folder / "detections.csv").open() as f:
            self.assertEqual(list(csv.DictReader(f)), [])
        with (self.folder / "timings.csv").open() as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(float(r["wall_ms"]) > 0 for r in rows))

    def test_bad_header_order_q15_and_truncated_input(self):
        header = "doppler_bin_unshifted,range_bin,real_q15,imag_q15\n"
        for data in ("bad header\n", header, header + "1,0,0,0\n",
                     header + "0,0,32768,0\n", header + "0,0,1.5,0\n",
                     header + "0,0,0,0,extra\n", header + "0,0,nan,0\n"):
            with self.subTest(data=data):
                self.assertNotEqual(self.run_cli(data).returncode, 0)


if __name__ == "__main__":
    unittest.main()
