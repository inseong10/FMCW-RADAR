# Zybo Z7-10: 128x128 PS versus PL, 2026-11-15

The experiment completed on the physical board, with PetaLinux kernel
5.15.19-xilinx, Vivado 2022.1 firmware, a 20 MHz PL clock, and a single reused
128-point Q15 FFT core. PS baseline: existing single-thread double FFTW receiver
with a 32x32 tiled transpose and contiguous Doppler FFTs. Both host programs were
pinned to CPU0. See `environment.txt` and the build environment files.

Both paths used the exact [recorded simulator input](../../fixtures/README.md),
the same Q15 quantization, no window, and total normalization 1/16384.
Each trial warmed up 10 frames, then measured the same frame 100 times. Three
PS/PL trial pairs give 300 measured frames per path. These are warm-cache offline
latencies, not live UDP throughput or a sample-size sweep.

| fft_pipeline | PS C++/FFTW | PL MMIO |
|---|---:|---:|
| Median, ms | 5.550039 | 81.460246 |
| Mean, ms | 5.542663 | 81.525070 |
| 5th–95th percentile, ms | 5.489259–5.597602 | 81.421093–81.724731 |

PS median / PL median = **0.06813**; the current PL path takes **14.677 times**
as long. There is no DMA. The PS timer includes input copy, both FFT axes, tiled
transpose and normalization. The PL timer includes AXI4-Lite transfers, FFTs,
status polling and PS column gather/scatter. Both exclude file/network input,
input quantization, allocation, plans, warmup, validation and output serialization.
PS per-stage profiling introduces timer bookkeeping inside its pipeline.
PL compute, MMIO and transpose were not timed separately, so their individual
contributions cannot be inferred from this measurement.

| Error versus NumPy fft2(Q15 input)/16384 | PS double | PL Q15 |
|---|---:|---:|
| Maximum complex error, Q15 integer units | 1.833e-12 | 8.749842 |
| RMS complex error, Q15 integer units | 3.705e-14 | 1.734691 |
| Relative L2 error, percent | 2.907e-14 | 1.361021 |

Both peaks are (Doppler unshifted 107, Range 20). Every measured PL iteration
matched the fixed-point integer model at all 16,384 complex bins. The two paths
use different arithmetic precision; they are not bit-identical to each other.

`comparison.json` and `accuracy_and_stages.json` preserve validation results;
`*.timings.csv` preserve individual measurements and `*.log` preserve console
evidence. `artifact_sha256.json` records the analyzed artifacts, including full
spectra and reconstructed input CSVs kept locally under `build/`. Those repeated
full spectra and input CSVs are omitted here. This compact report can reproduce
timing statistics; rerunning all accuracy checks requires a fresh board run or
the original complete local results.
The hashes identify the original local artifact bytes; Git may normalize text
line endings in the committed copies.

To repeat the hardware experiment, follow [the benchmark procedure](../../README.md).
Run `compare_board.py` against the complete newly generated result directory,
not this compact report. PC NumPy timing is not used as a performance baseline.
