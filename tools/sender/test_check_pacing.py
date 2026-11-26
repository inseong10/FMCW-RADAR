"""Deterministic clock checks; these tests make no VM timing claim."""
import argparse
import json
from pathlib import Path
import socket
import tempfile
import unittest
import check_pacing as pacing
import replay_stream as replay


class Clock:
    def __init__(self, oversleep_ns=0):
        self.now = 0
        self.oversleep_ns = oversleep_ns
        self.sleeps = []

    def clock(self):
        self.now += 1000
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += round(seconds*1e9) + self.oversleep_ns


class PacingTests(unittest.TestCase):
    def test_sleep_overshoot_and_catchup_remain_visible(self):
        c = Clock(20_000_000)
        r = pacing.measure('sleep', 5, 12_800_000, c.clock, c.clock, c.sleep)
        self.assertFalse(r['deadline_wakeup_valid'])
        self.assertGreaterEqual(r['max_lateness_ms'], 20)
        intended = [s['intended_ns'] for s in r['schedule']]
        self.assertEqual([b-a for a, b in zip(intended, intended[1:])], [12_800_000]*4)
        self.assertGreater(r['lateness_ge_10pct_period'], 0)

    def test_spin_reaches_absolute_deadlines_without_sleeping_between_them(self):
        c = Clock()
        r = pacing.measure('spin', 5, 12_800_000, c.clock, c.clock, c.sleep)
        self.assertTrue(r['deadline_wakeup_valid'])
        self.assertLess(r['max_lateness_ms'], .01)
        self.assertEqual(c.sleeps, [.05])

    def test_expired_deadline_does_not_sleep(self):
        c = Clock()
        pacing.wait_until(0, 'sleep', c.clock, c.sleep)
        self.assertEqual(c.sleeps, [])

    def test_production_sender_spin_reaches_deadline_without_sleep(self):
        c = Clock()
        replay.wait_until(12_800_000, 'spin', c.clock, c.sleep)
        self.assertGreaterEqual(c.now, 12_800_000)
        self.assertLess(c.now, 12_802_000)
        self.assertEqual(c.sleeps, [])

    def test_production_sender_preserves_sleep_overshoot_and_expired_deadline(self):
        c = Clock(20_000_000)
        replay.wait_until(12_800_000, 'sleep', c.clock, c.sleep)
        self.assertGreaterEqual(c.now, 32_800_000)
        replay.wait_until(25_600_000, 'sleep', c.clock, c.sleep)
        self.assertEqual(len(c.sleeps), 1)

    def test_production_sender_rejects_unknown_wait_mode(self):
        c = Clock()
        with self.assertRaises(ValueError):
            replay.wait_until(1000, 'unknown', c.clock, c.sleep)


class ChirpPacingTests(unittest.TestCase):
    """Loopback structure checks only; no VM or wire timing claim."""
    RECORD = (Path(__file__).resolve().parents[2] /
              'benchmarks/fixtures/adc16/radarsimpy_128x128_sim_multi4_noise_adc16.rspb')

    def run_sender(self, **kw):
        rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        rx.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 << 20)
        rx.bind(('127.0.0.1', 0))
        rx.settimeout(.2)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.addCleanup(rx.close)
        a = dict(record=self.RECORD, ip='127.0.0.1', port=rx.getsockname()[1], frames=2, run_id=7,
                 period_ms=20.0, wait_mode='spin', chirp_gap_us=0.0, drop_frame=0,
                 chirp_late_p99_limit_us=10.0, chirp_detail=False, out=Path(tmp.name)/'s.json')
        a.update(kw)
        # Read after the send (no reader thread: it would perturb spin timing via the GIL).
        # Linux caps SO_RCVBUF at net.core.rmem_max (~208KiB by default), so only 2-frame
        # runs assert the loopback packet count; longer runs check the sender JSON.
        replay.send(argparse.Namespace(**a))
        got = []
        try:
            while True:
                got.append(rx.recv(2048))
        except socket.timeout:
            pass
        return json.loads(a['out'].read_text()), got

    def test_burst_json_has_no_chirp_fields(self):
        s, got = self.run_sender()
        self.assertNotIn('chirp_pacing', s)
        self.assertEqual(set(s['schedule'][0]), {'frame_id', 'intended_ns', 'first_send_ns', 'last_send_ns', 'bytes'})
        self.assertEqual(len(got), 256)

    def test_paced_records_every_chirp_against_absolute_deadline(self):
        s, got = self.run_sender(chirp_gap_us=100.0, chirp_detail=True)
        c = s['chirp_pacing']
        self.assertEqual((c['gap_us'], c['late_p99_limit_us'], c['late_max_limit_ms'], c['chirps']),
                         (100.0, 10.0, 2.0, 256))
        for r in s['schedule']:
            self.assertEqual(r['chirps_sent'], 128)
            self.assertEqual(len(r['chirp_late_ns']), 128)
            self.assertTrue(all(v >= 0 for v in r['chirp_late_ns']))
            self.assertEqual(r['chirp_late_max_ns'], max(r['chirp_late_ns']))
            self.assertEqual(r['chirp_late_total_max_ns'],
                             r['first_send_ns']-r['intended_ns']+max(r['chirp_late_ns']))
            self.assertEqual(r['chirp_late_ge_100us'], sum(v >= 100_000 for v in r['chirp_late_ns']))
            self.assertGreaterEqual(r['last_send_ns']-r['first_send_ns'], 127*100_000)
        self.assertEqual(c['valid'], c['late_p99_ms']*1e3 < 10 and c['late_total_max_ms'] < 2.0)
        self.assertEqual(c['frame_boundary_overruns'], s['overrun_frames'])
        self.assertEqual(len(got), 256)
        chirps = [replay.HEADER.unpack_from(p)[6] for p in got[:128]]
        self.assertEqual(chirps, list(range(128)))

    def test_paced_drop_frame_and_limit_validation(self):
        s, got = self.run_sender(chirp_gap_us=100.0, drop_frame=2, chirp_detail=True)
        self.assertEqual([r['chirps_sent'] for r in s['schedule']], [128, 127])
        self.assertEqual(len(got), 255)
        with self.assertRaises(ValueError):
            self.run_sender(chirp_gap_us=100.0, chirp_late_p99_limit_us=0.0)

    def test_tiny_p99_limit_marks_pacing_invalid(self):
        s, _ = self.run_sender(chirp_gap_us=100.0, chirp_late_p99_limit_us=1e-6)
        self.assertFalse(s['chirp_pacing']['valid'])

    def test_stall_beyond_10pct_period_is_invalid_even_with_good_p99(self):
        real = replay.wait_until
        calls = {'n': 0}
        def stalling(deadline, mode='sleep', clock=replay.time.monotonic_ns, sleep=replay.time.sleep):
            calls['n'] += 1
            real(deadline + (3_000_000 if calls['n'] == 140 else 0), mode)
        replay.wait_until = stalling
        self.addCleanup(setattr, replay, 'wait_until', real)
        s, _ = self.run_sender(chirp_gap_us=100.0, chirp_detail=True)
        c = s['chirp_pacing']
        self.assertGreaterEqual(c['late_total_max_ms'], 2.0)
        self.assertFalse(c['valid'])
        self.assertEqual(c['schedule'], 'absolute')
        # Absolute schedule catches up after the stall: spacing collapses below the gap.
        detail = [v for r in s['schedule'] for v in r['chirp_late_ns']]
        self.assertGreater(sum(v >= 1_000_000 for v in detail), 5)

    def stall_run(self, at, **kw):
        real = replay.wait_until
        calls = {'n': 0}
        def stalling(deadline, mode='sleep', clock=replay.time.monotonic_ns, sleep=replay.time.sleep):
            calls['n'] += 1
            real(deadline + (3_000_000 if calls['n'] == at else 0), mode)
        replay.wait_until = stalling
        self.addCleanup(setattr, replay, 'wait_until', real)
        return self.run_sender(chirp_gap_us=100.0, chirp_detail=True, schedule='reanchor', **kw)

    def test_reanchor_fields_and_spacing_guarantee(self):
        s, got = self.run_sender(chirp_gap_us=100.0, chirp_detail=True, schedule='reanchor', frames=3)
        c = s['chirp_pacing']
        self.assertEqual(c['schedule'], 'reanchor')
        self.assertEqual((c['reanchor_threshold_us'], c['stall_threshold_ms'], c['stall_frames_limit']), (10.0, 2.0, 0))
        self.assertGreaterEqual(c['min_chirp_spacing_us'], 90.0)
        self.assertGreaterEqual(c['min_frame_spacing_ms'], 20.0-0.01)
        self.assertEqual(s['schedule'][0]['frame_spacing_ns'], None)
        for r in s['schedule']:
            self.assertEqual(r['stall_max_ns'], max(r['first_send_ns']-r['intended_ns'], r['chirp_late_max_ns']))
        self.assertEqual(sum(r['chirps_sent'] for r in s['schedule']), 384)
        self.assertEqual(sum(r['bytes'] for r in s['schedule']), 3*72704)
        self.assertLessEqual(len(got), 384)  # loopback count is OS-buffer limited for 3 frames

    def test_reanchor_mid_frame_stall_inserts_gap_without_burst(self):
        s, got = self.stall_run(140)  # wait call 140 = frame 2 chirp ~10
        c = s['chirp_pacing']
        self.assertGreaterEqual(c['stall_max_ms'], 3.0)
        self.assertGreaterEqual(c['stall_frames'], 1)
        self.assertGreaterEqual(c['chirp_reanchors'], 1)
        self.assertGreaterEqual(c['min_chirp_spacing_us'], 90.0)   # no catch-up burst
        late = [v for r in s['schedule'] for v in r['chirp_late_ns']]
        self.assertLessEqual(sum(v >= 1_000_000 for v in late), 1)  # only the stalled chirp
        self.assertFalse(c['valid'])  # 2 frames: 1% limit is 0 stall frames
        self.assertEqual(len(got), 256)

    def test_reanchor_frame_start_stall_moves_frame_schedule(self):
        s, _ = self.stall_run(130, frames=3)  # 129 waits in frame 1 -> frame 2 start
        c = s['chirp_pacing']
        self.assertGreaterEqual(c['frame_reanchors'], 1)
        self.assertGreaterEqual(c['min_frame_spacing_ms'], 20.0-0.01)
        r3 = s['schedule'][2]
        self.assertLess(r3['first_send_ns']-r3['intended_ns'], 1_000_000)  # recovered, not accumulated

    def test_reanchor_rejected_value(self):
        with self.assertRaises(ValueError):
            self.run_sender(chirp_gap_us=100.0, schedule='bogus')


if __name__ == '__main__':
    unittest.main()
