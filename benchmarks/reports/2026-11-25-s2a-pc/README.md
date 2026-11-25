# S2a preparation — portable production pipeline and monitor tests

Evidence: Windows PC tests only. No Linux receive thread or FPGA measurement.
`tests.log` records 7 passing unittest methods; two methods cover PS/model ×
six noisy fixture/window configurations. The production pipeline header is
compiled directly by `src/PS/receiver/tests/stream_driver.cpp`.

Every complex FFT bin, power cell, and CFAR detection list is compared against
independent NumPy/Python references. Integer bins and integer squared powers
match exactly. PS double uses numerical tolerances. Reversed and duplicate
chirps are exercised, and partial/truncated/non-finite/mixed-metadata packets
are rejected. A real localhost UDP sender test verifies 383 packets over three
frame IDs with one intentionally omitted chirp. Trace fixtures test missing
IDs, timestamp reversal, partial-frame drops and kernel-drop invalidation.

Initial numerical-test failure: the oracle used `abs(z)**2`, introducing a sqrt
and square roundoff (up to 7.45e-9 for integer powers). It was corrected to
`real**2+imag**2`, and exact complex-bin checks were added. Final exact checks
pass. An initial Windows loader function-pointer cast warning was also fixed;
it did not affect processing behavior.

Compiler flags: C `-O2 -std=c11 -Wall -Wextra -Werror`; C++
`-O2 -std=c++17 -Wall -Wextra -Werror`. Build/source/runtime identities are in
`identity.json`. The retained portable driver is in ignored
`build/s2a_host_validation/`; the unittest suite also compiles an isolated copy.

```powershell
$env:CC='C:/msys64/ucrt64/bin/gcc.exe'
$env:CXX='C:/msys64/ucrt64/bin/g++.exe'
$env:S2A_FFTW=(Resolve-Path build/fft128_ps_precision_host/libfftw3-3.dll).Path
python -m unittest discover -s tools/detection -p test_s2a.py -v
```

Linux socket/thread code, queue overflow behavior, resource sampling from
`/proc`, ARM compilation, and direct E14 integration await Ubuntu/board execution.
No continuous latency, frame-rate, or CPU performance claim is made here.
See [S2a procedure](../../../tools/detection/S2A.md).
