# Reproducible receiver experiments

See [the experiment log](../docs/experiment_log.md) for the chronological
problem/change/result history and links to captured evidence, including failed runs.

Run commands from the repository root. Shared procedures and scripts are tracked;
`data/` (raw/packet input) and `results/` (CSV/plots) are local and ignored by Git.
Record OS, CPU, compiler and flags, FFTW version, window, dimensions, warmup,
repeat count and whether wisdom was applied with every reported measurement.

After building the C++ receiver on Linux/macOS/WSL:

```bash
python benchmarks/make_frame.py --pulses 160 --samples 160
mkdir -p benchmarks/results
./build/udp_radar_receiver --input benchmarks/data/frame.bin --warmup 5 --repeat 100 --timings benchmarks/results/timings.csv --output benchmarks/results/spectrum.csv
python src/PS/receiver/select_wisdom.py --input benchmarks/data/frame.bin
```

`make_frame.py` needs only NumPy and generates a synthetic tone with range bin 3
and Doppler bin -2 (modulo the chosen dimensions). It does not simulate a physical
radar target. The packet container is `RSPB0001`, followed by repeated big-endian
uint32 packet lengths and full RSPY UDP packets. Offline replay repeats the same
frame; it measures processing and replay cost, not continuous UDP performance.

Use the Windows simulator and `receiver_numpy.py` as described in
[the sender guide](../tools/sender/README.md) for live PC checks. Record the
scenario parameters and compare the detected range/velocity with ground truth.
For PS/PL comparison, generate wisdom on the target and record DMA transfer,
queue wait, processing time and drops separately. The verified fixed-size MMIO
experiment is described below; continuous-frame and DMA measurements remain work.

## Zybo Z7-10: optimized PS FFTW versus verified 128x128 PL

For separate MMIO/cycle/transpose profiling and the experimental pipelined 50 MHz
core, see [FFT128 optimization procedure](../docs/fft128_optimization.md).
The published report below remains the original serial 20 MHz measurement.
The [validated pipeline/50 MHz results](reports/2026-11-15-pipeline50-benchmark/README.md)
give medians of PS 5.557 ms and PL 25.259 ms. PL improved by 3.225x over its
serial baseline and remains 4.545x slower than PS; MMIO transfer is now dominant.

This experiment uses the already-validated V3 bitstream; no Vivado rebuild is
needed. Both programs run on the same board using the same recorded RadarSimPy
frame. The CPU implementation is the existing `udp_radar_receiver.cpp`, retaining
its 32x32 tiled transpose, contiguous Doppler FFTs and reusable FFTW buffers/plans.
The PL implementation remains AXI4-Lite MMIO, **not DMA**.

The [2026-11-15 board report](reports/2026-11-15-zybo128/README.md) records PS
median 5.550 ms and PL median 81.460 ms with 300 measurements per path.
The exact input fixture is tracked under `benchmarks/fixtures/`; deployment
does not depend on an untracked simulation recording under `build/`.

Both receive the same Q15-quantized input and use no window and total 1/16384
normalization. FFTW computes in double; the PL computes in Q15. CPU output remains
internally range-major, PL output row-major; both CSVs serialize the same logical
matrix after the timed interval. This is an implementation comparison with
different arithmetic precision, not a claim of identical floating-point hardware.

Compare `fft_pipeline`: CPU input copy, Range FFT, tiled transpose, Doppler FFT
and output normalization, versus PL MMIO transfers, both FFTs and PS gather/scatter.
Both allocate work buffers before timing and exclude UDP/file input, input
quantization, plan creation, warmup, correctness checks, peak/axis calculations
and file output. CPU stage profiling adds timer bookkeeping within its pipeline.

1. On Ubuntu, inspect the target NFS rootfs and compiler availability:

   ```bash
   bash "$HOME/fmcw_share/FMCW-FFT-test/benchmarks/check_target.sh"
   ```

   The C++ program needs an ARM32 Linux loader/libc and compatible double FFTW
   runtime `libfftw3.so.3`. Its C++/GCC runtimes are linked statically by the build
   helper. Match the ARM floating-point ABI and target libc. Do not install the
   Ubuntu x86 FFTW library into the board rootfs. This board was confirmed as
   ARMv7 ELF32 hard-float with `/lib/ld-linux-armhf.so.3`; FFTW and taskset were
   absent. Ubuntu already has ARM GCC 9.4 but needs the ARM C++ compiler.

   On Ubuntu install the missing compiler/build dependency:

   ```bash
   sudo apt update
   sudo apt install g++-arm-linux-gnueabihf make curl
   ```

2. Build on Ubuntu, then stage and install as the HGFS mounting user:

   ```bash
   bash "$HOME/fmcw_share/FMCW-FFT-test/benchmarks/build_arm.sh"
   bash "$HOME/fmcw_share/FMCW-FFT-test/benchmarks/deploy_board.sh"
   ```

   The scripts preserve the known-good firmware and receiver in `/opt/fft128/`;
   benchmark files go under `/opt/fft128/benchmark/`.
   `build_arm.sh` also invokes `build_fftw_arm.sh`: it verifies the pinned
   official FFTW 3.3.11 archive under `build/third_party` (downloads it from
   fftw.org with SHA256 verification when missing), builds ARMv7 hard-float
   double-precision single-thread FFTW in `$HOME/fft128_fftw_arm`, and stages
   `lib/libfftw3.so.3`. Deployment installs this private library under the
   benchmark directory; system `/lib` and `/usr/lib` are not modified. The C++
   program opens it through an explicit `--fftw-lib` path.
   Compiler flags, source SHA256, library ABI and exported symbols are recorded.
   `--with-slow-timer` enables portable planning measurements without assuming
   access to ARM PMU registers. It affects plan selection measurements, not the
   arithmetic/timing interval used for benchmark results. ARMv7 NEON lacks
   double SIMD support, so FFTW's single/AArch64 NEON codelets are not enabled.
   Official sources: [FFTW download](https://www.fftw.org/download.html),
   [build options](https://www.fftw.org/fftw3_doc/Installation-on-Unix.html).

3. With the verified V3 FPGA firmware programmed, run on the board:

   ```bash
   sudo sh /opt/fft128/benchmark/run_board.sh
   ```

   CPU preflight generates 128x128 FFTW MEASURE wisdom on this board, then every
   timed CPU trial uses that wisdom. Each plan has an approximate 10-second
   planning limit; planning is excluded. Both programs pin themselves to CPU 0
   through `sched_setaffinity` (`--cpu0`), so taskset is unnecessary. Failure to
   pin terminates the run. Default:
   warmup 10, repeats 100, three PS/PL trial pairs, on the same frame. Every PL
   iteration is checked against the integer model outside its timed interval.
   CPU frequency/governor are logged when available; the script does not change
   them. Results overwrite the same benchmark result names on another run.

4. On Ubuntu, collect the board files through the NFS root:

   ```bash
   mkdir -p "$HOME/fmcw_share/FMCW-FFT-test/build/fft128_board_benchmark/results"
   cp -r /nfsroot/opt/fft128/benchmark/results/. "$HOME/fmcw_share/FMCW-FFT-test/build/fft128_board_benchmark/results/"
   ```

   On the development PC (NumPy required), run:

   ```bash
   python benchmarks/compare_board.py build/fft128_board_benchmark/results
   ```

   The analyzer verifies all output bins against NumPy, validates matched input
   settings and actual PL_MMIO evidence, then computes median/mean/5th/95th
   percentile. Acceleration is PS median / PL median; values below 1 mean this PL
   path is slower. It refuses incomplete or software-model-only PL results.
   Offline repeated-frame latency is distinct from continuous UDP throughput.
