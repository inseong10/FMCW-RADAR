"""E14 real C export/routing and profile/identity corruption guards, no FPGA."""
import copy
import csv
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unittest

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

analysis=module('frame_profile',HERE/'analyze_profile.py')
sys.path.insert(0,str(ROOT/'benchmarks'))
comparison=module('frame_comparison',ROOT/'benchmarks/compare_dma_frame_board.py')

class FrameTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work=ROOT/'build/fft128_dma_frame_tools_tests';cls.work.mkdir(exist_ok=True)
        source=cls.work/'export.c'
        source.write_text(r'''#define main receiver_main
#include "native_receiver.c"
#undef main
static unsigned transfers;
int fft128_frame_transfer(const uint32_t *in,uint32_t *out,uint32_t timeout,fft128_profile *p) {
    (void)p;if(timeout!=1000) return -1;++transfers;
    for(unsigned k=0;k<FFT128_BINS;++k) out[k]=in[k];
    return 0;
}
int main(int argc,char **argv) {
    if(argc!=2) return 2;
    static uint32_t input[FFT128_BINS],output[FFT128_BINS];
    for(unsigned k=0;k<FFT128_BINS;++k) input[k]=k*997u;
    if(fft128_process_frame(input,output,NULL) || transfers!=1) return 3;
    for(unsigned k=0;k<FFT128_BINS;++k) if(output[k]!=input[k]) return 4;
    options o={0};o.prefix=argv[1];o.repeat=1;o.profile=1;o.pl_clock_hz=50000000;
    fft128_profile p={0};double elapsed=.002;
    p.calls=1;p.pl_cycles=51927;p.min_cycles=p.max_cycles=51927;
    p.input_write_ns=100000;p.start_wait_ns=1700000;p.output_read_ns=150000;
    p.dma_copy_in_ns=100000;p.dma_submit_ns=20000;p.dma_wait_ns=1100000;
    p.dma_check_ns=20000;p.dma_copy_out_ns=400000;
    p.frame_range_cycles=17771;p.frame_doppler_cycles=17771;p.frame_drain_cycles=16385;
    p.frame_matrix_reads=p.frame_matrix_writes=32768;
    p.frame_range_outputs=p.frame_doppler_inputs=p.frame_doppler_outputs=p.frame_matrix_words=16384;
    p.frame_stage_busy_cycles=121856;p.frame_multi_stage_cycles=33280;p.frame_vector_overlap_cycles=34772;
    for(unsigned s=0;s<7;++s) p.frame_issue_events[s]=p.frame_retire_events[s]=16384;
    if(save_profiles(&o,&p,&elapsed)) return 5;
    static fft128_sample frame[FFT128_BINS];collector c={0};c.frame=frame;o.model=1;
    return save(&o,&c,output,1,elapsed,HARDWARE_LABEL,&elapsed);
}
''',encoding='utf-8')
        exe=cls.work/('export.exe' if sys.platform=='win32' else 'export')
        cmd=[shutil.which('gcc'),'-O2','-std=c11','-Wall','-Wextra','-Werror','-DFFT128_DMA_BACKEND','-DFFT128_DMA_BATCH_BACKEND','-DFFT128_DMA_FRAME_BACKEND',
             '-I',str(HERE.parent),str(source),str(HERE.parent/'native_core.c'),str(HERE/'frame_process.c')]
        if sys.platform=='win32':cmd+=['-lws2_32']
        else:raise unittest.SkipTest('Windows C export harness; real ARM transport build is separate')
        result=subprocess.run(cmd+['-lm','-o',str(exe)],capture_output=True,text=True)
        if result.returncode:raise RuntimeError(result.stdout+result.stderr)
        cls.prefix=cls.work/'frame';subprocess.run([str(exe),str(cls.prefix)],check=True,capture_output=True,text=True)
        cls.path=cls.prefix.with_suffix('.profile.csv')
        with cls.path.open() as f:cls.row=next(csv.DictReader(f))
        cls.config=json.loads(re.search(r'puts \$f \{(\{"experiment":"E14-frame".*?\})\}',(ROOT/'src/PL/fft128_ps/build_dma_frame.tcl').read_text()).group(1))
        cls.contract=json.loads(cls.prefix.with_suffix('.batch.json').read_text())

    def mutate(self,**changes):
        row=copy.copy(self.row);row.update(changes);path=self.work/'changed.profile.csv'
        with path.open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=row);writer.writeheader();writer.writerow(row)
        return path

    def test_real_export_and_single_request_without_cpu_transpose(self):
        result=analysis.analyze(self.path)
        self.assertEqual(result['payload_bytes_per_frame'],131072)
        self.assertEqual(self.row['dma_requests'],'1');self.assertEqual(self.row['fft_per_request'],'256')
        self.assertEqual((self.row['gather_ms'],self.row['scatter_ms']),('0','0'))

    def test_old_axis_contract_rejected(self):
        for changes in [dict(dma_requests=2),dict(dma_channel_submissions=4),dict(fft_per_request=128),dict(payload_bytes_per_frame=262144)]:
            with self.assertRaises(ValueError):analysis.analyze(self.mutate(**changes))

    def test_phase_partition_and_drain_are_checked(self):
        for changes in [dict(range_cycles=17770),dict(doppler_cycles=0),dict(drain_cycles=16384)]:
            with self.assertRaises(ValueError):analysis.analyze(self.mutate(**changes))

    def test_in_place_matrix_conservation(self):
        for changes in [dict(matrix_reads=32767),dict(matrix_writes=32767),dict(doppler_inputs=16383),dict(range_outputs=16383),dict(doppler_outputs=16383),dict(overwrite_errors=1),dict(matrix_words=32768)]:
            with self.assertRaises(ValueError):analysis.analyze(self.mutate(**changes))

    def test_stage_conservation(self):
        for changes in [dict(stage0_issue=16383),dict(stage6_retire=16383),dict(stage_busy_cycles=121855),dict(multi_stage_cycles=0)]:
            with self.assertRaises(ValueError):analysis.analyze(self.mutate(**changes))

    def test_no_false_simultaneous_external_io_or_cpu_transpose(self):
        for changes in [dict(io_overlap_cycles=1),dict(gather_ms=.1),dict(scatter_ms=.1)]:
            with self.assertRaises(ValueError):analysis.analyze(self.mutate(**changes))

    def test_nested_intervals_nonfinite_and_clock(self):
        for changes in [dict(kernel_wait_ms=5),dict(ioctl_ms=5),dict(wall_ms='nan'),dict(pl_clock_hz_declared=100000000)]:
            with self.assertRaises(ValueError):analysis.analyze(self.mutate(**changes))

    def test_config_rejects_old_or_partial_design(self):
        comparison.validate_config(self.config)
        for key,value in [('register_abi',7),('pl_transpose',False),('pl_output_reorder',False),('cpu_transpose',True),('matrix_bytes',131072),('fft_per_request',128),('output_order','range-major')]:
            d=dict(self.config);d[key]=value
            with self.assertRaises(ValueError):comparison.validate_config(d)

    def test_software_export_cannot_claim_hardware(self):
        self.assertFalse(self.contract['hardware'])
        with self.assertRaises(ValueError):comparison.validate_frame_contract(self.contract)
        d=dict(self.contract);d['hardware']=True;comparison.validate_frame_contract(d)
        d['register_abi']=7
        with self.assertRaises(ValueError):comparison.validate_frame_contract(d)

    def test_bundle_guard_and_mutations(self):
        text=(HERE/'prepare_bundle.sh').read_text();guard=text.split("<<'PY'\n",1)[1].split('\nPY',1)[0]
        for change in [None,('fft_per_request',128),('matrix_bytes',131072),('register_abi',7),('pl_output_reorder',False),('output_order','range-major')]:
            d=dict(self.config)
            if change:d[change[0]]=change[1]
            p=self.work/'config.json';p.write_text(json.dumps(d))
            result=subprocess.run([sys.executable,'-c',guard,str(p)],capture_output=True,text=True)
            self.assertEqual(result.returncode==0,change is None)

if __name__=='__main__':unittest.main()
