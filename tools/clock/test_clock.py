"""PC-only timing rejection and Tcl entry/cleanup checks; no Vivado claim."""
import importlib.util
from pathlib import Path
import re
import shutil
import subprocess
import unittest

import validate_clock as gate

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT/'benchmarks/reports/2026-11-21-e14-frame-build/timing.rpt'


class ClockGate(unittest.TestCase):
    def setUp(self):
        self.text = REPORT.read_text()

    def test_real_archived_50mhz_timing(self):
        result = gate.timing_summary(self.text, 50000000)
        self.assertEqual(result['setup_wns_ns'], 10.166)
        self.assertEqual(result['hold_whs_ns'], .020)

    def test_wrong_candidate_clock_rejected(self):
        with self.assertRaises(ValueError):
            gate.timing_summary(self.text, 100000000)

    def test_each_timing_domain_failure_rejected(self):
        pattern = r'(?m)^(\s*10\.166\s+0\.000\s+0\s+21473\s+0\.020\s+0\.000\s+0\s+21473\s+2\.000\s+0\.000\s+0\s+6756\s*)$'
        row = re.search(pattern, self.text).group(1).split()
        for index in (0, 4, 8):
            changed = list(row); changed[index] = '-0.001'
            with self.subTest(slack_column=index), self.assertRaises(ValueError):
                gate.timing_summary(re.sub(pattern, ' '.join(changed), self.text), 50000000)
        for index in (2, 6, 10):
            changed = list(row); changed[index] = '1'
            with self.subTest(endpoint_column=index), self.assertRaises(ValueError):
                gate.timing_summary(re.sub(pattern, ' '.join(changed), self.text), 50000000)

    def test_unconstrained_and_missing_checks_rejected(self):
        for name in ('no_clock', 'unconstrained_internal_endpoints', 'no_input_delay', 'generated_clocks'):
            changed = self.text.replace('checking %s (0)' % name, 'checking %s (1)' % name)
            with self.subTest(name=name), self.assertRaises(ValueError):
                gate.timing_summary(changed, 50000000)
        with self.assertRaises(ValueError):
            gate.timing_summary(self.text.replace('WNS(ns)', 'missing'), 50000000)

    def test_explicit_profile_clock_and_conversion(self):
        spec = importlib.util.spec_from_file_location('profile', ROOT/'src/PS/fft128/dma_frame/analyze_profile.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        # Use an existing measured 50 MHz profile, then mutate only declared rate
        # and the derived active-ms field to exercise explicit rate rejection.
        import csv
        import tempfile
        path = ROOT/'benchmarks/reports/2026-11-21-e14-frame-board/raw_compact/profile_e14_frame_01/pl.profile.csv'
        with path.open() as source:
            reader = csv.DictReader(source); fields = reader.fieldnames; rows = list(reader)
        for row in rows:
            row['pl_clock_hz_declared'] = '100000000'
            row['pl_active_ms'] = str(int(row['pl_active_cycles']) * 1000 / 100000000)
        with tempfile.TemporaryDirectory() as folder:
            changed = Path(folder)/'mutated.profile.csv'
            with changed.open('w', newline='') as dest:
                writer = csv.DictWriter(dest, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
            with self.assertRaises(ValueError): module.analyze(changed)
            result = module.analyze(changed, 100000000)
        expected = sum(int(row['drain_cycles']) for row in rows)/len(rows)*1000/100000000
        self.assertAlmostEqual(result['phase_ms']['drain_cycles'], expected)

    def test_tcl_parameter_guard_and_failure_cleanup(self):
        tcl = shutil.which('tclsh')
        if not tcl: self.skipTest('Tcl interpreter unavailable')
        script = (ROOT/'src/PL/fft128_ps/build_dma_frame_clock.tcl').as_posix()
        for value in ('0', '201', 'Inf', 'not_a_frequency'):
            harness = ('set argc 1\nset argv [list {%s}]\n' % value +
                       'set code [catch {source {%s}} message]\n' % script +
                       'puts "$code|[info exists ::fft128_frame_clock_mhz]|$message"\n')
            result = subprocess.run([tcl], input=harness, text=True, capture_output=True, check=True)
            self.assertIn('1|0|E14 clock candidate must', result.stdout)
        # A plain Tcl interpreter deliberately stops on its first Vivado API.
        # This verifies requested frequency/isolated paths/cleanup, not a build.
        harness = ('set argc 1\nset argv [list 100]\n' +
                   'set code [catch {source {%s}} message]\n' % script +
                   'puts "$code|[info exists ::fft128_frame_clock_mhz]|$::fft128::clock_mhz|$::fft128::latest_file|$message"\n')
        result = subprocess.run([tcl], input=harness, text=True, capture_output=True, check=True)
        self.assertIn('1|0|100|fft128_dma_frame_clock_100p000mhz_latest.txt|', result.stdout)
        self.assertIn('invalid command name "get_projects"', result.stdout)

    def test_actual_tcl_metadata_substitution(self):
        import json
        import tempfile
        tcl = shutil.which('tclsh')
        if not tcl: self.skipTest('Tcl interpreter unavailable')
        text = (ROOT/'src/PL/fft128_ps/build_dma_frame.tcl').read_text()
        block = text.split(' set frame_config ', 1)[1].split('\n close $f', 1)[0]
        baseline = json.loads(re.search(r'set frame_config \{(\{.*?\})\}', text).group(1))
        with tempfile.TemporaryDirectory() as folder:
            target = (Path(folder)/'config.json').as_posix()
            harness = ('set clock_mhz 100\nset f [open {%s} w]\n' % target +
                       'set frame_config ' + block + '\nclose $f\n')
            subprocess.run([tcl], input=harness, text=True, capture_output=True, check=True)
            self.assertEqual(json.loads(Path(target).read_text()), dict(baseline, clock_hz=100000000))


if __name__ == '__main__':
    unittest.main()
