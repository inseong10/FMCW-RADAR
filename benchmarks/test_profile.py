import csv
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest

from analyze_profile import analyze, HOST_STAGES


class ProfileTests(unittest.TestCase):
    def run_profile(self, **changes):
        row = dict(iteration=1, fft_calls=256, pl_clock_hz_declared=20000000,
                   pl_cycles=3073*256, min_cycles=3073, max_cycles=3073,
                   wall_ms=82, pl_internal_ms=39.3344,
                   input_write_ms=20, start_wait_ms=40, counter_read_ms=.1,
                   output_read_ms=20, gather_ms=.3, scatter_ms=.4)
        row.update(changes)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'profile.csv'
            with path.open('w', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=row)
                writer.writeheader(); writer.writerow(row)
            return analyze(path)

    def test_counter_is_overlapped_not_added_to_host(self):
        result = self.run_profile()
        self.assertAlmostEqual(result['wall_minus_pl_internal_mean_ms'],42.6656)
        self.assertAlmostEqual(result['unattributed_host_mean_ms'],1.2)
        self.assertAlmostEqual(sum(result['mean_ms'][k] for k in HOST_STAGES),80.8)

    def test_wrong_clock_conversion_rejected(self):
        with self.assertRaisesRegex(ValueError,'conversion mismatch'):
            self.run_profile(pl_clock_hz_declared=50000000)

    def test_partial_frame_and_overlapping_host_stages_rejected(self):
        with self.assertRaisesRegex(ValueError,'Incomplete frame'):
            self.run_profile(fft_calls=128)
        with self.assertRaisesRegex(ValueError,'Host stage times exceed'):
            self.run_profile(start_wait_ms=80)

    def test_speed_comparison_rejects_instrumented_run(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            for backend in ('ps','pl'):
                (folder/f'{backend}_1.timings.csv').write_text('stage,iteration,wall_ms\nfft_pipeline,1,1\n')
            (folder/'pl_1.json').write_text(json.dumps(dict(backend='PL_MMIO',shape=[128,128],
                mismatched_complex_bins=0,profiling=True)))
            result=subprocess.run([sys.executable,str(Path(__file__).with_name('compare_board.py')),str(folder)],
                                  capture_output=True,text=True,timeout=10)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('separate unprofiled benchmark',result.stderr)


if __name__ == '__main__':
    unittest.main()
