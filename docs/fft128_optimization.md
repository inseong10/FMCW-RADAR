# FFT128: time breakdown, pipelined core and 50 MHz experiment

The existing serial 20 MHz board result remains the measured baseline (PS median
5.550 ms, PL median 81.460 ms). The new pipelined core passes PC RTL tests and
50 MHz routed timing (WNS 9.807 ns, WHS 0.034 ns). Board full-frame profiling passed:
861 cycles/FFT, 4.408320 ms PL internal and 27.327809 ms instrumented total mean.
The unprofiled 300-frame comparison and independent NumPy checks have also passed:
PS median 5.557368 ms, PL median 25.2591725 ms. PL is 3.225x faster than its
serial baseline but 4.545x slower than PS. See [final report](../benchmarks/reports/2026-11-15-pipeline50-benchmark/README.md).
See the [implementation report](../benchmarks/reports/2026-11-15-pipeline50-build/README.md).
Do not report the cycle-derived estimates below as measured board latency.

The [experiment log](experiment_log.md) records the motivation and progression.
E09 profiling has now completed on the serial 20 MHz board: input writes 23.429884 ms,
start/wait 39.927098 ms, output reads 18.370430 ms, gather/scatter 0.947203 ms,
and 3,073 hardware cycles/FFT (39.334400 ms internal per frame). Instrumented mean
wall time was 83.694257 ms. See the [console evidence](../benchmarks/reports/2026-11-15-serial20-profile/README.md).
The internal interval overlaps start/wait. Both original individual profile CSVs
have now been collected, validated and archived with their analyzer summaries. E10 pipeline/50 MHz board self-test and full-frame profiling
also passed; see [profile evidence](../benchmarks/reports/2026-11-15-pipeline50-profile/README.md).

## 1. Measure the existing firmware first; no FPGA rebuild

The new receiver remains compatible with the existing serial firmware. Build and
deploy on the Ubuntu host as the HGFS mounting user:

```bash
bash "$HOME/fmcw_share/FMCW-FFT-test/benchmarks/build_arm.sh"
bash "$HOME/fmcw_share/FMCW-FFT-test/benchmarks/deploy_board.sh"
```

On the board, while the verified serial 20 MHz firmware is still programmed:

```sh
sudo sh /opt/fft128/benchmark/profile_board.sh 20000000
```

This performs two warmups and 20 instrumented frames with exact integer-model
verification. It records each measured frame in a separate `.profile.csv`:

| Field | Meaning |
|---|---|
| `wall_ms` | Entire instrumented FFT/transfer/transpose pipeline |
| `input_write_ms` | Initial idle check and 128 input MMIO stores, summed over 256 FFTs |
| `start_wait_ms` | Start command, deadline setup and completion polling |
| `counter_read_ms` | Additional cycle-register reads introduced by profiling |
| `output_read_ms` | Output MMIO reads and small profiling bookkeeping |
| `gather_ms`, `scatter_ms` | PS column gather and result scatter |
| `pl_cycles` | Sum of hardware register 0x010 over 256 FFTs |
| `pl_internal_ms` | `pl_cycles * 1000 / declared_clock_hz` |
| `min_cycles`, `max_cycles` | Minimum/maximum individual FFT counter |

The hardware counter runs from accepted start until the last internal output
sample is saved. It includes input staging, butterfly schedule and output staging,
but excludes host input/output MMIO. It is not pure multiplier/addition time.
PL internal time overlaps `start_wait_ms`: never add it again to host stage times.
Polling CPU activity occurs concurrently with PL execution. The remainder of
total wall time after subtracting PL internal time is not pure AXI transfer time.

The clock argument is mandatory and must match the programmed firmware. It is a
declared frequency, not an independent clock measurement. Profiling adds timestamps
and MMIO reads; use a separate unprofiled run for PS/PL performance comparisons.
The comparison analyzer rejects an instrumented PL run.

Copy profiles back through the Ubuntu NFS root:

```bash
cp -r /nfsroot/opt/fft128/benchmark/profiles "$HOME/fmcw_share/FMCW-FFT-test/build/fft128_board_benchmark/"
```

On a development PC, analyze an individual CSV:

```bash
python benchmarks/analyze_profile.py path/to/profile_YYYYMMDD_HHMMSS.profile.csv
```

## 2. Pipelined arithmetic and stage ping-pong RAM

`fft128_axi` retains `PIPELINED=0` as its default. `PIPELINED=1` selects the new
`fft128_pipeline.v` and `butterfly_pipeline.v`. Register protocol and Q15 bit
packing, per-stage /2 truncation and saturation are unchanged.

The core still reuses one butterfly datapath, with four parallel real multipliers.
It now overlaps synchronous memory reads, multiplication, add/subtract, quantization
and destination-memory writes for different butterflies. Two dual-port banks
alternate source/destination at each FFT stage. Every stage issues 64 butterflies
at one per clock, drains the arithmetic pipeline, then swaps banks. Stage barriers
ensure all writes finish before the next stage reads. It does not run multiple
whole FFTs simultaneously or overlap PS MMIO transfers with computation.

PC RTL tests cover the same 272 vectors per variant, exact output bins, independent
AXI AW/W timing, stalled responses, output backpressure, malformed TLAST, and abort
during computation followed by a clean recomputation. Counter checks are exact:

| Variant | Cycles per FFT | 256 FFTs at 20 MHz | 256 FFTs at 50 MHz |
|---|---:|---:|---:|
| Serial | 3,073 | 39.3344 ms | 15.73376 ms |
| Pipelined | 861 | 11.0208 ms | 4.40832 ms |

These are PL internal intervals only. Host transfer/transpose time remains.
DMA, host/PL ping-pong buffers and multiple FFT cores are separate future work.
New RAM/register/DSP utilization must be checked after implementation.

## 3. Build the 50 MHz pipelined experiment

After collecting the serial profile, run once in the Vivado 2022.1 Tcl Console:

```tcl
source [file join $env(HOME) fmcw_share FMCW-FFT-test src PL fft128_ps build_fast.tcl]
```

The build selects the pipelined core and requests a 50 MHz MMCM output. Reset
generation remains the verified board-clock/MMCM-lock V3 scheme. The script checks
the generated reset IP, routed setup and hold slack, and the actual generated
clock period before generating the bitstream. Failure is a stop, not a timing
override. This host cannot run Vivado; successful PC RTL tests alone do not certify
50 MHz implementation or board operation.

`build.tcl` alone continues to build serial/20 MHz. To isolate the effects,
serial/50 MHz and pipeline/20 MHz are also available through explicit Tcl settings:

```tcl
set ::fft128_build_core serial
set ::fft128_build_mhz 50.0
source [file join $env(HOME) fmcw_share FMCW-FFT-test src PL fft128_ps build.tcl]
unset ::fft128_build_core ::fft128_build_mhz
```

Keep separate run directories. `clock_source.txt` and `build_config.json` identify
each completed build and the frequency verified from timing constraints.

After `FFT128_BUILD_PASS`, use the existing `prepare_firmware.sh` and mounting-user
copy → local staging → `sudo install` workflow to place the new `.bin` under
`/nfsroot/opt/fft128`. Preserve the verified serial firmware as a separate file.
Program the new firmware on the board, then run the hardware self-test before
profiling at **50000000** Hz. Do not use the 50 MHz divisor with old 20 MHz firmware.

Finally run the unprofiled benchmark into a separate directory:

```sh
sudo sh /opt/fft128/benchmark/run_board.sh /opt/fft128/benchmark/results_pipeline50
```

Collect the complete directory and run `compare_board.py` again. Keep the original
serial/20 MHz report separate from the new pipeline/50 MHz report. Both measured
reports are linked above; do not replace measured data with cycle-derived estimates.
