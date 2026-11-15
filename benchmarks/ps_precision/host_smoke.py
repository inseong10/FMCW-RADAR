#!/usr/bin/env python3
"""Windows-only numerical smoke of the actual processing/loader code, not a benchmark.

Uses official FFTW 3.3.5 Windows DLLs supplied via --archive (never downloads).
Only socket reception and main/CPU affinity are replaced; processing/replay,
public FFTW declarations, timing and verification code are extracted unchanged.
This does not validate Linux/ARM, FFTW 3.3.11, or NEON execution.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile
import numpy as np
from analyze import error_metrics
from prepare_reference import ROOT, prepare, reference

ARCHIVE_SHA = 'cfd88dc0e8d7001115ea79e069a2c695d52c8947f5b4f3b7ac54a192756f439f'


def main(archive, out):
    if os.name != 'nt':
        raise ValueError('Use the real Linux build on Linux')
    if hashlib.sha256(archive.read_bytes()).hexdigest() != ARCHIVE_SHA:
        raise ValueError('Unexpected official FFTW DLL archive')
    prepare(out)
    with zipfile.ZipFile(archive) as z:
        for name in ('libfftw3-3.dll', 'libfftw3f-3.dll'):
            (out/name).write_bytes(z.read(name))
    source = (ROOT/'src/PS/receiver/udp_radar_receiver.cpp').read_text(encoding='utf-8')
    includes = ''.join(line+'\n' for line in source.splitlines() if line.startswith('#include <')
                       and not any(x in line for x in ('dlfcn', 'arpa/', 'netinet/', 'poll.h', 'sys/socket', 'unistd', 'sched.h')))
    shim = '''
#define NOMINMAX
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#define RTLD_NOW 0
#define RTLD_LOCAL 0
void* dlopen(const char* p,int){return reinterpret_cast<void*>(LoadLibraryA(p));}
void* dlsym(void* p,const char* s){return reinterpret_cast<void*>(GetProcAddress(reinterpret_cast<HMODULE>(p),s));}
void dlclose(void* p){FreeLibrary(reinterpret_cast<HMODULE>(p));}
'''
    code = shim + includes
    code += source[source.index('using Steady ='):source.index('struct Socket {')]
    code += re.search(r'struct Frame \{[^\n]+', source)[0]+'\n'
    code += source[source.index('using Packets='):source.index('\nint main(')]
    code += '''
int main(int argc,char**argv) {
 try {
  auto o=parse(argc,argv); FFTW api(o.fftw_lib); Profiler prof(false);
  auto frame=replay(read_packets(o),o,prof); process(frame,o,prof,api); save_timings(o,prof);
  return 0;
 } catch(const std::exception& e) {std::cerr<<e.what()<<'\\n';return 1;}
}
'''
    cpp = out/'processing_smoke.cpp'
    cpp.write_text(code, encoding='utf-8')
    expected, _, _ = reference(out/'frame.rspb')
    reports = {}
    for variant, library in (('double', 'libfftw3-3.dll'), ('float', 'libfftw3f-3.dll')):
        binary = out/(variant+'.exe')
        command = ['g++', '-O3', '-std=c++17', '-Wall', '-Wextra', str(cpp), '-pthread', '-o', str(binary)]
        if variant == 'float':
            command += ['-DFFT128_SINGLE=1']
        subprocess.run(command, check=True, timeout=60, capture_output=True)
        common = [str(binary), '--input', str(out/'frame.rspb'), '--fftw-lib', str(out/library),
                  '--window', 'none', '--q15-input', '--normalize-output',
                  '--verify-spectrum', str(out/'reference.csv'), '--warmup', '1', '--repeat', '3']
        first = subprocess.run(common + ['--measure-plan', '--plan-time-limit', '1', '--wisdom-out', str(out/(variant+'.wis')),
                               '--output', str(out/(variant+'.csv'))], capture_output=True, text=True, timeout=30)
        (out/(variant+'.log')).write_text(first.stdout+first.stderr, encoding='utf-8')
        if first.returncode or 'PS_VERIFY_PASS repeats=3 bins=16384' not in first.stdout:
            raise ValueError(first.stdout+first.stderr)
        rows = np.loadtxt(out/(variant+'.csv'), delimiter=',', skiprows=1)
        actual = (rows[:, 2]+1j*rows[:, 3]).reshape(128, 128)
        limits = (1e-7, 1e-12) if variant == 'double' else (.01, 1e-5)
        reports[variant] = error_metrics(actual, expected, *limits)
        second = subprocess.run(common+['--wisdom-in', str(out/(variant+'.wis'))], capture_output=True, text=True, timeout=30)
        if second.returncode or 'FFTW WISDOM' not in second.stdout:
            raise ValueError('Wisdom reload failed: '+second.stderr)
    summary = dict(status='HOST_PROCESSING_SMOKE_PASS', precision=reports,
                   dll_archive_sha256=ARCHIVE_SHA, fftw_version='3.3.5 Windows x86-64',
                   scope='Actual receiver processing/replay/FFTW ABI; Windows loader bridge, no sockets/main affinity',
                   limitation='No ARM/Linux/NEON/3.3.11 validation; no host timings used for board comparison')
    (out/'validation.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    main(args.archive.resolve(), args.output.resolve())
