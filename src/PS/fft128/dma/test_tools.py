"""PC tests for live-DT resource selection and the DMA receiver CLI variant."""
import importlib.util
import csv
import io
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SPEC = importlib.util.spec_from_file_location('dma_overlay', HERE/'make_overlay.py')
overlay = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(overlay)
PROFILE_SPEC = importlib.util.spec_from_file_location('dma_profile', HERE/'analyze_profile.py')
profile = importlib.util.module_from_spec(PROFILE_SPEC)
PROFILE_SPEC.loader.exec_module(profile)


def be(*words):
    return struct.pack('>'+'I'*len(words), *words)


class OverlayTests(unittest.TestCase):
    def generate(self, overrides=None):
        data = {'#address-cells': be(1), '#size-cells': be(1),
                'amba_pl/compatible': b'simple-bus\0', 'amba_pl/#address-cells': be(1),
                'amba_pl/#size-cells': be(1), 'amba_pl/ranges': b'',
                'axi/gic/compatible': b'arm,cortex-a9-gic\0',
                'axi/gic/#interrupt-cells': be(3), 'axi/gic/phandle': be(19)}
        data.update(overrides or {})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'dt.tar'
            with tarfile.open(path, 'w') as archive:
                for name, value in data.items():
                    entry = tarfile.TarInfo('./'+name)
                    entry.size = len(value)
                    archive.addfile(entry, io.BytesIO(value))
            return overlay.make_overlay(path)

    def test_uses_live_gic_and_accepts_nonoverlapping_legacy_video(self):
        text, meta = self.generate({'amba_pl/vtc@43c00000/reg': be(0x43c00000,0x10000),
                                   'amba_pl/vdma/interrupts': be(0,29,4)})
        self.assertIn('interrupt-parent = <0x13>',text)
        self.assertEqual(meta['gic_phandle'],19)
        self.assertEqual(meta['dt_spi'],[35,36])
        self.assertEqual(meta['target_bus'],'/amba_pl')
        self.assertIn('target-path = "/amba_pl"',text)
        self.assertNotIn('fft128-e11a-bus',text)

    def test_rejects_fft_or_dma_address_overlap(self):
        for address in (overlay.FFT_BASE-16,overlay.DMA_BASE):
            with self.subTest(address=address), self.assertRaisesRegex(ValueError,'Address conflict'):
                self.generate({'amba_pl/other/reg': be(address,4096)})

    def test_rejects_used_irq(self):
        for irq in overlay.SPI:
            with self.subTest(irq=irq), self.assertRaisesRegex(ValueError,'IRQ conflict'):
                self.generate({'amba_pl/other/interrupts': be(0,irq,4)})

    def test_rejects_unknown_address_or_interrupt_cell_layout(self):
        for key in ('#address-cells','#size-cells','axi/gic/#interrupt-cells',
                    'amba_pl/#address-cells','amba_pl/#size-cells'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.generate({key:be(2)})

    def test_rejects_missing_bus_or_translated_bus(self):
        for key,value in (('amba_pl/compatible',b'unknown\0'),('amba_pl/ranges',be(0,0,1024))):
            with self.subTest(key=key),self.assertRaises(ValueError):
                self.generate({key:value})


class ProfileTests(unittest.TestCase):
    def row(self):
        return dict(iteration=1,wall_ms=10,host_input_copy_ms=.1,ioctl_ms=8,
                    host_output_copy_ms=.1,gather_ms=.4,scatter_ms=.4,
                    kernel_copy_in_ms=.2,kernel_submit_ms=.3,kernel_wait_ms=7,
                    kernel_check_ms=.1,kernel_copy_out_ms=.2,pl_active_cycles=256*861+1000,
                    pl_active_ms=(256*861+1000)*1000/50000000,input_stall_cycles=600,
                    output_stall_cycles=400,fft_calls=256,min_active_cycles=861,
                    max_active_cycles=870,pl_clock_hz_declared=50000000,
                    bytes_each_direction_per_fft=512)

    def analyze(self,row):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'profile.csv'
            with path.open('w',newline='') as out:
                writer=csv.DictWriter(out,fieldnames=list(row));writer.writeheader();writer.writerow(row)
            return profile.analyze(path)

    def test_nested_times_are_not_added_to_wall(self):
        data=self.analyze(self.row())
        self.assertAlmostEqual(data['host_residual_ms'],1)
        self.assertAlmostEqual(data['ioctl_residual_ms'],.2)
        self.assertEqual(data['active_minus_stream_stalls_cycles_per_fft']['min'],861)

    def test_rejects_bad_clock_or_stall_accounting(self):
        for key,value in (('pl_clock_hz_declared',20000000),('input_stall_cycles',601)):
            row=self.row();row[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.analyze(row)

    def test_rejects_overlapping_host_or_impossible_nested_kernel_times(self):
        for key,value in (('host_input_copy_ms',20),('kernel_wait_ms',20)):
            row=self.row();row[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.analyze(row)


class CLITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = os.environ.get('FFT128_TEST_CC') or shutil.which('gcc')
        if not compiler:
            raise unittest.SkipTest('GCC required')
        cls.work = ROOT/'build/fft128_dma_tools_tests'
        cls.work.mkdir(parents=True,exist_ok=True)
        cls.exe=cls.work/('dma-cli.exe' if sys.platform=='win32' else 'dma-cli')
        command=[compiler,'-O2','-std=c11','-Wall','-Wextra','-Werror','-DFFT128_DMA_BACKEND',
                 str(HERE.parent/'native_receiver.c'),str(HERE.parent/'native_core.c')]
        command += ['-lws2_32'] if sys.platform=='win32' else [str(HERE/'dma_backend.c')]
        subprocess.run(command+['-lm','-o',str(cls.exe)],check=True,capture_output=True)

    def run_cli(self,*args):
        return subprocess.run([str(self.exe),*args],capture_output=True,text=True,timeout=15)

    def test_default_hardware_has_no_automatic_model_fallback(self):
        run=self.run_cli('--self-test')
        # If a Linux board actually has the accelerator, this is a hardware test.
        if sys.platform!='win32' and Path('/dev/fft128-dma').exists():
            self.skipTest('Real hardware present; use board self-test separately')
        self.assertNotEqual(run.returncode,0)
        self.assertNotIn('SELFTEST_PASS',run.stdout)
        self.assertEqual(self.run_cli('--backend','mmio','--self-test').returncode,2)

    def test_explicit_model_selftest(self):
        run=self.run_cli('--backend','model','--self-test')
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertIn('SOFTWARE_MODEL',run.stdout)

    def test_profile_options_are_transport_specific(self):
        self.assertEqual(self.run_cli('--profile-mmio').returncode,2)
        self.assertEqual(self.run_cli('--backend','model','--profile-dma','--pl-clock-hz','50000000').returncode,2)
        self.assertIn('--profile-dma',self.run_cli('--help').stdout)

    def test_full_frame_model_metadata_does_not_claim_dma(self):
        prefix=self.work/'model'
        run=self.run_cli('--backend','model','--input',str(ROOT/'benchmarks/fixtures/radarsimpy_128x128.rspb'),
                         '--output',str(prefix),'--repeat','2')
        self.assertEqual(run.returncode,0,run.stderr)
        data=json.loads(prefix.with_suffix('.json').read_text())
        self.assertIn('SOFTWARE_MODEL',data['backend'])
        self.assertIn('no FPGA or DMA',data['note'])
        self.assertEqual(data['mismatched_complex_bins'],0)


if __name__ == '__main__':
    unittest.main()
