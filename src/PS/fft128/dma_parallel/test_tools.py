"""E13 export/counter guards; arithmetic and gather/scatter reuse E11b regressions."""
import copy
import csv
import importlib.util
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


class ParallelTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work=ROOT/'build/fft128_dma_parallel_tools_tests'
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
    p.calls=2;p.pl_cycles=142848;p.min_cycles=p.max_cycles=71424;
    p.input_write_ns=200000;p.start_wait_ns=4200000;p.output_read_ns=100000;
    p.gather_ns=p.scatter_ns=200000;
    p.dma_copy_in_ns=200000;p.dma_submit_ns=30000;p.dma_wait_ns=3000000;
    p.dma_check_ns=10000;p.dma_copy_out_ns=600000;
    p.parallel_core0_cycles=110080;p.parallel_core1_cycles=142720;
    p.parallel_both_busy_cycles=110080;p.parallel_both_work_cycles=44672;
    p.parallel_arbitration_stalls=16256;
    return save_profiles(&o,&p,&elapsed);
}
''',encoding='utf-8')
        cls.exe=cls.work/('profile_writer.exe' if sys.platform=='win32' else 'profile_writer')
        cmd=[shutil.which('gcc'),'-O2','-std=c11','-Wall','-Wextra','-Werror',
             '-DFFT128_DMA_BACKEND','-DFFT128_DMA_BATCH_BACKEND','-DFFT128_DMA_PARALLEL_BACKEND',
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
        self.assertEqual(self.row['parallel_cores'],'2')
        report=analysis.analyze(self.path)
        self.assertEqual(report['both_work_cycles']['mean'],44672)

    def test_no_concurrent_work_is_rejected(self):
        for work in (0,1,128):
            with self.subTest(work=work), self.assertRaises(ValueError):
                analysis.analyze(self.mutate(both_work_cycles=work))

    def test_serial_or_changed_pair_schedule_is_rejected(self):
        with self.assertRaises(ValueError):
            analysis.analyze(self.mutate(parallel_cores=1))
        with self.assertRaises(ValueError):
            analysis.analyze(self.mutate(core0_active_cycles=110081))

    def test_invalid_overlap_and_nested_time_are_rejected(self):
        with self.assertRaises(ValueError):
            analysis.analyze(self.mutate(both_work_cycles=110081))
        with self.assertRaises(ValueError):
            analysis.analyze(self.mutate(kernel_wait_ms=10))


if __name__=='__main__':
    unittest.main()
