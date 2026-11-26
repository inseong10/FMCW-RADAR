"""Data integrity, numerical conventions and HTTP boundaries for the visualizer."""
import csv
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import numpy as np

import data
from server import Handler, ThreadingHTTPServer


def csv_text(pairs, q15=False):
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(['doppler_bin_unshifted', 'range_bin',
                     'real_q15' if q15 else 'real', 'imag_q15' if q15 else 'imag'])
    for i, (real, imag) in enumerate(pairs):
        writer.writerow([i // 128, i % 128, real, imag])
    return stream.getvalue()


class DataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frame = data.recording()

    def test_fixture_peak_and_report_accuracy(self):
        frame = self.frame
        self.assertEqual(frame['peaks']['pl']['doppler_bin'], 107)
        self.assertEqual(frame['peaks']['pl']['range_bin'], 20)
        self.assertAlmostEqual(frame['errors']['pl']['relative_l2'], 0.013610209282866827, places=12)
        self.assertEqual(frame['peaks']['pl']['shifted_doppler_bin'], 43)
        self.assertLess(frame['peaks']['pl']['velocity_mps'], 0)
        self.assertAlmostEqual(frame['axes']['range_m'][20], 29.9792458, places=6)
        self.assertEqual(len(frame['input_iq']), 16384)

    def test_model_matches_saved_hardware_when_available(self):
        saved = data.RAW / 'results_e14_frame_01/pl/trial_1.csv'
        if not saved.exists():
            self.skipTest('Saved board CSV is optional in a fresh checkout')
        packets, _ = data.REPLAY.read_frame(data.ROOT / 'benchmarks/fixtures/radarsimpy_128x128.rspb')
        raw = np.empty((128, 128), dtype=complex)
        for packet in packets:
            _, chirp, _, row = data.MODEL.decode_packet(packet)
            raw[chirp] = row
        _, model, _, _ = data.q15_transform(raw)
        actual = data.read_csv(saved.read_text())
        self.assertTrue(np.array_equal(model, actual))

    def test_missing_board_files_are_explicit_software_models(self):
        data.recording.cache_clear()
        try:
            with tempfile.TemporaryDirectory() as directory, patch.object(data, 'RAW', Path(directory)):
                frame = data.recording()
                self.assertIn('소프트웨어 모델', frame['labels']['pl'])
                self.assertNotIn('float_neon', frame['spectra'])
                self.assertEqual(len(frame['sources']), 1)
        finally:
            data.recording.cache_clear()

    def test_modified_board_file_is_rejected(self):
        data.recording.cache_clear()
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                item = root / 'results_e14_frame_01/pl/trial_1.csv'
                item.parent.mkdir(parents=True)
                item.write_text('modified')
                with patch.object(data, 'RAW', root), self.assertRaisesRegex(ValueError, 'SHA-256'):
                    data.recording()
        finally:
            data.recording.cache_clear()

    def test_synthetic_known_target_and_deterministic_noise(self):
        a = data.simulate(dict(range_m=45, velocity_mps=5, snr_db=40))
        b = data.simulate(dict(range_m=45, velocity_mps=5, snr_db=40))
        self.assertEqual(a['spectra'], b['spectra'])
        self.assertEqual(a['kind'], 'simulation')
        self.assertEqual(a['engine'], 'tone')
        self.assertLess(abs(a['peaks']['pl']['range_m']-45), 1.5)
        self.assertLess(abs(a['peaks']['pl']['velocity_mps']-5), 0.5)
        self.assertNotIn('timing', a)

    def test_csv_roundtrip_import(self):
        ps = csv_text(self.frame['spectra']['double'])
        pl = csv_text(self.frame['spectra']['pl'], q15=True)
        imported = data.import_spectra(dict(ps_csv=ps, pl_csv=pl))
        self.assertEqual(imported['peaks'], {k: self.frame['peaks'][k] for k in ('double', 'pl')})
        self.assertEqual(imported['kind'], 'import')
        self.assertIsNone(imported['truth'])
        self.assertIsNone(imported['input_iq'])

    def test_csv_missing_duplicate_nonfinite_and_index_rejected(self):
        header = 'doppler_bin_unshifted,range_bin,real,imag\n'
        for rows in ['0,0,1,2\n', '0,0,1,2\n0,0,3,4\n', '0,0,nan,0\n', '128,0,0,0\n']:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                data.read_csv(header + rows)

    def test_zero_spectrum_l2_is_undefined(self):
        zero = np.zeros((128, 128), complex)
        frame = data.dataset('zero', 'import', dict(double=zero, pl=zero), {}, data.DEFAULT_RADAR)
        self.assertIsNone(frame['errors']['pl']['relative_l2'])
        json.dumps(frame, allow_nan=False)

    def test_invalid_radar_and_targets_rejected(self):
        for args in [dict(range_m=float('nan')), dict(velocity_mps=31), dict(snr_db=-1),
                     dict(prp_us=1), dict(fc_ghz=0), dict(engine='unknown')]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                data.simulate(args)

    def test_profile_nested_totals_and_paired_count(self):
        baseline = data.board_baseline()
        for result in baseline['comparison']['results'].values():
            self.assertEqual(result['timing']['count'], 300)
        profile = baseline['profile']
        self.assertAlmostEqual(sum(profile['phase_ms'].values()), profile['mean_ms']['pl_active_ms'])
        m = profile['mean_ms']
        self.assertAlmostEqual(m['host_input_copy_ms']+m['ioctl_ms']+m['host_output_copy_ms']+profile['host_residual_ms'],m['wall_ms'])


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_static_and_baseline(self):
        for route, content_type in [('/', 'text/html'), ('/app.js', 'text/javascript'), ('/style.css', 'text/css'), ('/api/baseline', 'application/json')]:
            with self.subTest(route=route), urlopen(self.base+route) as response:
                self.assertEqual(response.status, 200)
                self.assertIn(content_type, response.headers['Content-Type'])
                self.assertGreater(len(response.read()), 100)

    def test_invalid_post_is_json_error(self):
        request = Request(self.base+'/api/import', data=b'{}', headers={'Content-Type':'application/json'})
        with self.assertRaises(HTTPError) as error:
            urlopen(request)
        self.assertEqual(error.exception.code, 400)
        self.assertIn('error', json.loads(error.exception.read()))

    def test_cross_origin_rejected(self):
        request = Request(self.base+'/api/simulate', data=b'{}', headers={'Content-Type':'application/json', 'Origin':'https://example.invalid'})
        with self.assertRaises(HTTPError) as error:
            urlopen(request)
        self.assertEqual(error.exception.code, 403)

    def test_unknown_file_cannot_read_repository(self):
        for path in ['/data.py', '/../../README.md', '/api/missing']:
            with self.subTest(path=path), self.assertRaises(HTTPError) as error:
                urlopen(self.base+path)
            self.assertEqual(error.exception.code, 404)


if __name__ == '__main__':
    unittest.main()
