# S2b-opt1 — CPU processing candidate after valid-load failures

Status: PC correctness checks passed; source staged to the VMware share.
Ubuntu host smoke/ARM build, board NEON selection, accuracy and performance
are pending. No throughput improvement or acceptance is claimed.

## Why this candidate

The independently verified [valid-spin baselines](../2026-11-26-s2b/README.md)
receive all25,600 packets without clock/receive errors but discard complete
frames: PS179/200, queue_full21; PL123/200, queue_full77. Worker elapsed-time
medians14.463708ms and22.209787ms exceed the12.8ms input period. The PS FFT
median5.751816ms is a measured optimization target; the PL FFT1.265694ms is
already smaller than its preparation12.114900ms and power/CFAR8.596980ms.

## Changes and numerical scope

- Optional `S2A_PRECISION=float` selects FFTW float symbols and buffers; double
  remains the build default. Hann is computed in double, then FFT input is
  rounded to float. Power/CA-CFAR remains double; normalization remains1/16384.
- FFTW allocates its own aligned PS buffers, enabling SIMD plans; PL no longer
  allocates unused FFTW buffers. No change to PL window/Q15 quantization, ABI,
  FPGA image, receiver wire/reassembly, queue capacities or CA parameters.
- `--measure-plan` plans before warmup/socket readiness, with FFTW's2s planning
  time-limit hint. `--require-neon` checks actual Linux plan text and rejects
  a missing NEON plan. It does not silently substitute a scalar plan.
- Optional `S2A_TUNED=1` enablesO3/LTO and ARM Cortex-A9/NEON/hard-float flags
  for the native C/C++ build. No fast-math. The same candidate binary can run
  PS or PL; the float FFT precision is relevant only to the PS FFT.
- The candidate combines precision, alignment, planning and compilation changes.
  Any result is an optimized-candidate result, not an isolated NEON speedup.

The original PS double vs PL Q15 accuracy/throughput records remain unchanged.
Float precision is not described as double-equivalent arithmetic. PC checks
cover every exported FFT bin, power-map error and the detection list before any
board acceptance. Weak/close targets retain the known1/3 CA masking limitation.

## PC validation

`pc_tests.txt`:11 tests pass, including integer6cases, double6cases,
float6cases each with ESTIMATE and MEASURE, reversed/duplicate wire packets,
malformed-input rejection, time32/time64 timestamps, non-NEON requirement
rejection, sender sleep/spin and monitor failure classification.

Float global limits: spectrum relativeL2<2e-6, maximum complex error relative
to peak<2e-6, power relativeL2<5e-6. Detection bins match the NumPy reference;
the six float-input reference lists also match their original double-input
lists. PC FFTW DLLs use x86 SIMD, not ARM NEON. Initial validation caught an
incorrect diagnostic-string deallocator; the correction uses ordinary `free`
on Linux and avoids transferring malloc-owned diagnostic text across the
Windows DLL runtime boundary. This follows the [FFTW plan API](https://www.fftw.org/fftw3_doc/Using-Plans.html).
No failing candidate was deployed to the board.

Exact source/runtime identities and numerical limits are in `pc_validation.json`.
Copies under `source/` preserve the tested source. Shell syntax checks passed
for build, preparation and board runner scripts; those checks do not establish
an ARM build or board result.

## Ubuntu preparation and board run

```sh
cd /home/user/fmcw_share/FMCW-FFT-test
bash tools/detection/prepare_s2b_opt1.sh 20261126_01
```

The helper refuses existing paths, builds a tuned double host receiver and
runs the3 existing loopback smoke cases, then builds the float ARM candidate.
It reuses `/nfsroot/opt/fft128/ps_precision/float_neon/lib/libfftw3f.so.3`,
requiring its previously verified SHA256
`9c06dfa6f7e6f686b5eabda0845b75d38c5f05b852234364edfd84c423315653`.
It deploys a new6-file bundle under `/opt/fft128/s2b_opt1_20261126_01` with
artifact/source hashes and build flags. Build output goes to a log. No FPGA
load, clock change or old-directory overwrite is performed.

After successful preparation, the proposed first board run is:

```sh
B=/opt/fft128/s2b_opt1_20261126_01
sudo sh "$B/run_board.sh" ps 92201 200 "$B/ps_12p8ms_200_01" \
  2>&1 | sudo tee "$B/ps_12p8ms_200_01.console.log"
```

The sender remains the verified spin sender at12.8ms/200, run92201, with a new
JSON path. Start sending only after READY. The runner requires online/allowed
CPUs0-1, checks artifacts and actual NEON plan, captures CPU/DT clock context,
boot ID, runtime hashes, interrupts and actual receiver exit status before/after.
Its fresh output container holds the receiver files under `trace/`.

Next: independently validate preparation and the board run, then address the
measured PL preparation/CPU costs without changing the fixed-point contract.
Final acceptance still requires valid offered load, zero drops, the original
latency anchor/P99 target, accuracy and longer-run evidence. Enlarging the
queue is not treated as fixing the measured service-time bottleneck.
