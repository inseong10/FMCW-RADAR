# E13-2core Vivado/ARM build — 2026-11-20

Run: `fft128_dma_e13_2core_20261120_153153`.
Actual generated reset IP/AXI ID/ABI/core-count/lock-loss simulation, routed
50 MHz timing, bitstream/XSA, static ARM32 receiver/client and kernel module builds PASS.
Build source SHA values match both the shared source and current checkout.
Host/module artifact manifests were independently checked; binaries are ARM32 ELF.

- Setup WNS9.292 ns, hold WHS0.029 ns; failing endpoints0/0.
- No-clock pins and unconstrained internal endpoints0.
- LUT3818/17600 (21.69%), FF4460/35200 (12.67%), BRAM tiles7/60 (11.67%), DSP8/80 (10%).
- Hierarchical implementation report contains core0 and core1 with4 DSP each.
- Generated BD transport parameters/interfaces/addressing/IRQs match E11b:
  HP0 64-bit, AXIS32, Simple DMA, SG/DRE off, burst16, length17, F2P6/7.
- Actual generated reset netlist confirms external reset active-low and auxiliary active-high.
- ARM GCC9.4.0; module vermagic5.15.19-xilinx SMP/preempt/modversions/ARMv7.
  A normal board insmod must still accept the actual symbol CRCs.
- Recorded DT overlay compilation and fdtoverlay validation passed in prepare_host.sh.
  Standalone dtc external GIC warning is preserved in host_dtc.log.

These are build/offline checks. Firmware conversion/bundle deployment, live overlay,
module CRC acceptance, DMA data transfer/self-test, full frame/profile and paired
300-sample performance are pending. There is no new E13 board performance result.
The DSP count proves physical arithmetic replication; board counters still need to
confirm actual concurrent calculation under DMA.

Raw compact reports, manifests and verification JSON are preserved here.
Large bitstream/XSA/ARM binaries remain in ignored shared build/ paths; exact sizes
and SHA256 are in implementation.json. Build metadata board_verified:false is retained.

[Board commands](../../../src/PS/fft128/dma_parallel/README.md),
[RTL preparation](../2026-11-20-e13-2core-preparation/README.md).

## Board self-test follow-up

User PetaLinux console now confirms FPGA Manager programming, AXI DMA/client binding,
normal module load and self-test PASS. One512 B and two65536 B packets completed
1/128/128 FFTs with exact integer validation. Exclusive ownership and ABI/timeout/
flags/count rejection checks passed. Receiver self-test passed4vectors/512bins.
The deployment bundle's22 artifact hashes were independently checked and preserved
as bundle_artifacts.sha256; details and console are in board_selftest.json/log.

Both-work22336cycles in a128FFT packet exceeds the maximum64cycles of initial
output read latency outside simultaneous CALC. The conservative actual CALC overlap
lower bound is22272cycles. Thus board DMA execution confirms concurrent arithmetic,
in addition to the implementation's physical8DSP/two-core evidence.
Both-busy55054cycles is a separate overlapping busy counter, not pure compute time.

FPGA programming73ms is not FFT latency. Overlay removal memory leak and out-of-tree
taint warnings were present; execution continued through DMA_E13_2CORE_SELFTEST_READY.
Full-frame validation, separate20-frame profile and paired300-sample timings remain pending.
The earlier build-only pending statements and board_verified:false metadata are preserved.

## Final follow-up

Full-frame/profile/paired300-sample comparison and independent raw validation now PASS.
PL median4.920621 ms/paired PS double5.767263/NEON3.646212 ms.
See [final E13-2core board report](../2026-11-20-e13-2core-board/README.md).
The pending statements above preserve the earlier build/self-test stage.
