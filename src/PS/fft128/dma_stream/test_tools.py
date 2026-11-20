"""E13-stream export/counter guards; arithmetic and gather/scatter reuse E11b regressions."""
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


class StreamingTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work=ROOT/'build/fft128_dma_stream_tools_tests'
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
    fft128_profile p={0};double elapsed=0.0035;
    p.calls=2;p.pl_cycles=35540;p.min_cycles=p.max_cycles=17770;
    p.input_write_ns=200000;p.start_wait_ns=2500000;p.output_read_ns=100000;
    p.gather_ns=p.scatter_ns=200000;
    p.dma_copy_in_ns=200000;p.dma_submit_ns=30000;p.dma_wait_ns=1000000;
    p.dma_check_ns=10000;p.dma_copy_out_ns=600000;
    p.stream_stage_busy_cycles=121856;p.stream_multi_stage_cycles=33280;p.stream_vector_overlap_cycles=34772;
    p.stream_io_cycles=20000;p.stream_input_calc_cycles=10000;
    p.stream_output_calc_cycles=11000;p.stream_three_cycles=9000;
    for(unsigned stage=0;stage<7;++stage) {p.stream_issue_events[stage]=16384;p.stream_retire_events[stage]=16384;}
    if(save_profiles(&o,&p,&elapsed)) return 1;
    static fft128_sample frame[FFT128_BINS];static uint32_t spectrum[FFT128_BINS];
    collector c={0};c.frame=frame;o.model=1;
    return save(&o,&c,spectrum,1,elapsed,HARDWARE_LABEL,&elapsed);
}
''',encoding='utf-8')
        cls.exe=cls.work/('profile_writer.exe' if sys.platform=='win32' else 'profile_writer')
        cmd=[shutil.which('gcc'),'-O2','-std=c11','-Wall','-Wextra','-Werror',
             '-DFFT128_DMA_BACKEND','-DFFT128_DMA_BATCH_BACKEND','-DFFT128_DMA_STREAM_BACKEND',
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

    def test_real_c_export_and_exact_stage_counts(self):
        self.assertEqual(self.row['fft_calls'],'256')
        self.assertEqual(self.row['dma_requests'],'2')
        self.assertEqual(self.row['streaming_cores'],'1')
        self.assertEqual(self.row['streaming_stages'],'7')
        self.assertEqual(analysis.analyze(self.path)['frames'],1)

    def test_wrong_architecture_is_rejected(self):
        for values in (dict(streaming_cores=4),dict(streaming_stages=6)):
            with self.assertRaises(ValueError):analysis.analyze(self.mutate(**values))

    def test_per_stage_issue_and_retire_conservation(self):
        for values in (dict(stage0_issue=16383),dict(stage6_retire=16383),dict(stage_busy_cycles=121855)):
            with self.assertRaises(ValueError):analysis.analyze(self.mutate(**values))

    def test_no_interframe_overlap_or_impossible_overlap_rejected(self):
        for values in (dict(multi_stage_cycles=0),dict(vector_overlap_cycles=0),dict(vector_overlap_cycles=35541),dict(multi_stage_cycles=35541)):
            with self.assertRaises(ValueError):analysis.analyze(self.mutate(**values))

    def test_nested_kernel_stages_do_not_double_count(self):
        with self.assertRaises(ValueError):analysis.analyze(self.mutate(kernel_wait_ms=5))

    def test_external_overlap_invalid_rejected(self):
        for values in (dict(io_overlap_cycles=0),dict(three_overlap_cycles=20001),dict(input_calc_overlap_cycles=0)):
            with self.assertRaises(ValueError):analysis.analyze(self.mutate(**values))

    def test_batch_export_identifies_frame_pipeline(self):
        d=json.loads((self.work/'export.batch.json').read_text())
        self.assertEqual((d['experiment'],d['parallel_cores'],d['streaming_stages'],d['total_butterflies']),('E13-stream',1,7,7))
        self.assertEqual((d['frame_initiation_interval'],d['buffering']),(128,'per_stage_double_frame_slots'))
        self.assertFalse(d['hardware'])
        self.assertFalse(d['external_buffers'])
        self.assertTrue(d['stage_frame_slots'])
        self.assertTrue(d['next_vector_prefetch'])

    def test_nonfinite_and_wrong_clock_rejected(self):
        for values in (dict(wall_ms='nan'),dict(pl_clock_hz_declared=100000000)):
            with self.assertRaises(ValueError):analysis.analyze(self.mutate(**values))

if __name__=='__main__':unittest.main()
