"""E12 export/counter guards; arithmetic and gather/scatter reuse E11b regressions."""
import copy
import csv
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
spec=importlib.util.spec_from_file_location('parallel_profile',HERE/'analyze_profile.py')
analysis=importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


class OverlapTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work=ROOT/'build/fft128_dma_overlap_tools_tests'
        cls.work.mkdir(parents=True,exist_ok=True)
        source=cls.work/'profile_writer.c'
        source.write_text(r'''#define main receiver_main
#include "native_receiver.c"
#undef main
int fft128_batch_axis(const uint32_t *in,uint32_t *out,unsigned count,uint32_t timeout,fft128_profile *p) {
    (void)in;(void)out;(void)count;(void)timeout;(void)p;return -99;
}
int main(int argc,char **argv) {
    if(argc!=2) return 2;
    options o={0};o.prefix=argv[1];o.repeat=1;o.profile=1;o.pl_clock_hz=50000000;
    fft128_profile p={0};double elapsed=0.005;
    p.calls=2;p.pl_cycles=104064;p.min_cycles=p.max_cycles=52032;
    p.input_write_ns=200000;p.start_wait_ns=4200000;p.output_read_ns=100000;
    p.gather_ns=p.scatter_ns=200000;
    p.dma_copy_in_ns=200000;p.dma_submit_ns=30000;p.dma_wait_ns=3000000;
    p.dma_check_ns=10000;p.dma_copy_out_ns=600000;
    p.quad_core0_cycles=55040;p.quad_core1_cycles=71360;
    p.quad_core2_cycles=87680;p.quad_core3_cycles=104000;
    p.quad_any_busy_cycles=104000;p.quad_multi_busy_cycles=87680;p.quad_all_busy_cycles=55040;
    p.quad_multi_work_cycles=38720;p.quad_all_work_cycles=5952;
    p.quad_arbitration_stalls=40000;
    p.overlap_io_cycles=10000;p.overlap_input_work_cycles=15000;
    p.overlap_output_work_cycles=12000;p.overlap_three_cycles=5000;
    if(save_profiles(&o,&p,&elapsed)) return 1;
    static fft128_sample frame[FFT128_BINS];static uint32_t spectrum[FFT128_BINS];
    collector c={0};c.frame=frame;o.model=1;
    return save(&o,&c,spectrum,1,elapsed,HARDWARE_LABEL,&elapsed);
}
''',encoding='utf-8')
        cls.exe=cls.work/('profile_writer.exe' if sys.platform=='win32' else 'profile_writer')
        cmd=[shutil.which('gcc'),'-O2','-std=c11','-Wall','-Wextra','-Werror',
             '-DFFT128_DMA_BACKEND','-DFFT128_DMA_BATCH_BACKEND','-DFFT128_DMA_OVERLAP_BACKEND',
             '-I',str(HERE.parent),str(source),str(HERE.parent/'native_core.c'),
             str(HERE.parent/'dma_batch/batch_process.c')]
        if sys.platform=='win32': cmd+=['-lws2_32']
        else:
            # This host export test is Windows-based; Linux also needs transport stubs.
            raise unittest.SkipTest('Windows host export harness; ARM real transport builds separately')
        cmd+=['-lm','-o',str(cls.exe)]
        result=subprocess.run(cmd,capture_output=True,text=True)
        if result.returncode: raise RuntimeError(result.stdout+result.stderr)
        prefix=cls.work/'export'
        subprocess.run([str(cls.exe),str(prefix)],check=True,capture_output=True,text=True)
        cls.path=prefix.with_suffix('.profile.csv')
        with cls.path.open() as f: cls.row=next(csv.DictReader(f))

    def mutate(self,**changes):
        row=copy.copy(self.row);row.update(changes)
        path=self.work/'mutated.profile.csv'
        with path.open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=row);writer.writeheader();writer.writerow(row)
        return path

    def test_real_c_export_is_accepted(self):
        self.assertEqual(self.row['fft_calls'],'256')
        self.assertEqual(self.row['dma_requests'],'2')
        self.assertEqual(self.row['parallel_cores'],'4')
        report=analysis.analyze(self.path)
        self.assertEqual(report['all_work_cycles']['mean'],5952)

    def test_no_concurrent_work_is_rejected(self):
        for work in (0,1,64):
            with self.subTest(work=work), self.assertRaises(ValueError):
                analysis.analyze(self.mutate(all_work_cycles=work))

    def test_serial_or_missing_overlap_is_rejected(self):
        with self.assertRaises(ValueError):
            analysis.analyze(self.mutate(parallel_cores=2))
        with self.assertRaises(ValueError):
            analysis.analyze(self.mutate(three_overlap_cycles=10001))

    def test_invalid_overlap_and_nested_time_are_rejected(self):
        with self.assertRaises(ValueError):
            analysis.analyze(self.mutate(all_work_cycles=55041))
        with self.assertRaises(ValueError):
            analysis.analyze(self.mutate(multi_work_cycles=256))
        with self.assertRaises(ValueError):
            analysis.analyze(self.mutate(kernel_wait_ms=10))

    def test_batch_metadata_distinguishes_fifo_overlap_from_old_group_barrier(self):
        d=json.loads((self.work/'export.batch.json').read_text(encoding='utf-8'))
        self.assertEqual(d['experiment'],'E12-4core')
        self.assertFalse(d['hardware'])
        self.assertFalse(d['group_barrier'])
        self.assertTrue(d['next_group_prefetch'])
        self.assertTrue(d['external_buffers'])
        self.assertFalse(d['external_ping_pong'])
        self.assertEqual(d['buffering'],'per_lane_fifos')

    def test_missing_or_impossible_io_overlap_is_rejected(self):
        for values in (dict(io_overlap_cycles=0),dict(input_work_overlap_cycles=0),
                       dict(output_work_overlap_cycles=0),dict(three_overlap_cycles=0),
                       dict(io_overlap_cycles=104065)):
            with self.subTest(values=values), self.assertRaises(ValueError):
                analysis.analyze(self.mutate(**values))

    def test_impossible_busy_sum_is_rejected(self):
        with self.assertRaises(ValueError):
            analysis.analyze(self.mutate(core0_active_cycles=55040,core1_active_cycles=55040,
                                         core2_active_cycles=55040,core3_active_cycles=55040))


if __name__=='__main__':
    unittest.main()
