"""Small smoke tests for the NumPy receiver reference path."""
import argparse
import contextlib
import io
import importlib.util
from pathlib import Path
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[4]
REFERENCE_PATH = ROOT / "src/PS/receiver/reference/receiver_numpy.py"
SPEC = importlib.util.spec_from_file_location("receiver_numpy_smoke", REFERENCE_PATH)
reference = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reference)


class ReceiverReferenceSmokeTests(unittest.TestCase):
    def test_unit_impulse_has_flat_range_doppler_magnitude(self):
        frame = np.zeros((4, 8), dtype=np.complex128)
        frame[0, 0] = 1.0
        options = argparse.Namespace(
            window="none", warmup=0, repeat=1,
            chirp_us=80, prp_us=100, bandwidth_mhz=100, fc_ghz=24.05,
        )

        with contextlib.redirect_stdout(io.StringIO()):
            result = reference.process_frame(
                frame, 2e6, options, reference.Profiler()
            )

        magnitudes = np.abs(result["range_doppler"])
        np.testing.assert_allclose(magnitudes, np.full((4, 8), 1.0), atol=1e-12)


if __name__ == "__main__":
    unittest.main()
