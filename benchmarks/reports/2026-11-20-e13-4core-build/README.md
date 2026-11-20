# E13-4core Vivado/ARM build — 2026-11-20

Run: `fft128_dma_e13_4core_20261120_163555`.
Actual generated reset IP/AXI ID/ABI/core-count/lock-loss simulation, routed
50 MHz timing, bitstream/XSA and ARM32 receiver/client/module builds PASS.
PL/host/module source SHA values match both shared source and current checkout.
Host/module artifact manifests and ELF ARM32 identities were independently checked.

- Setup WNS9.982 ns, hold WHS0.024 ns; failing endpoints0/0.
- No-clock pins and unconstrained internal endpoints0.
- LUT4868/17600 (27.66%), FF5169/35200 (14.68%), BRAM tiles11/60 (18.33%), DSP16/80 (20%).
- Routed hierarchy contains core0/core1/core2/core3, each with4 DSP.
- Generated BD transport parameters/interfaces/addressing/IRQs match E11b/E13-2core:
  HP0 64bit, AXIS32, Simple DMA, SG/DRE off, burst16, length17, F2P6/7.
- Generated reset netlist confirms external reset active-low and auxiliary active-high.
- ARM receiver and packet client compiled; ABI4 layout static assertions passed:
  header112/input112/output65648/extra131184/request131208 B.
- Module build succeeded against prepared5.15.19-xilinx kernel, with ARMv7/SMP/preempt/modversions.
  Actual board insmod must still accept symbol CRCs.
- Recorded-DT overlay compilation and fdtoverlay validation passed in prepare_host.sh.
  Standalone dtc external GIC warning is preserved in host_dtc.log.

These are implementation/offline checks, including physical arithmetic replication.
Firmware conversion/bundle deployment, live overlay/module CRC, DMA packet/self-test,
actual concurrent arithmetic under DMA, full frame/profile and paired300-sample timings
remain pending. No new4core board performance result is available.

Compact reports/manifests/verification JSON are preserved here. Large bitstream/XSA/ARM
binaries remain in ignored shared build/ paths. implementation.json records exact
artifact paths, sizes and SHA256. Original build board_verified:false metadata is retained.

[Board commands](../../../src/PS/fft128/dma_quad/README.md),
[RTL preparation](../2026-11-20-e13-4core-preparation/README.md),
[Previous2core board result](../2026-11-20-e13-2core-board/README.md).

## Board self-test follow-up

User PetaLinux console confirms FPGA Manager load, normal module load/CRC acceptance,
DMA/client binding and E13-4core self-test PASS. The packet client completed and
validated1/2/3/4/5/127/128/128 FFT requests, including incomplete four-vector groups.
Exclusive ownership, invalid ABI/timeout/flags/count rejection and receiver4vector/
512bin self-test passed through DMA_E13_4CORE_SELFTEST_READY.

The last128FFT axis reported multi-busy43854/all-busy27534/multi-work19360/all-work2976cycles.
Subtracting the maximum32cycles of all-work outside simultaneous CALC gives a positive
four-core CALC lower bound2944cycles/axis. This confirms actual four-core calculation
under DMA in addition to the implemented16DSP/four-core physical evidence.
Busy/work-window counters are overlapping intervals, not whole-frame FFT latency.

The22 deployment artifact hashes were independently checked and preserved in
bundle_artifacts.sha256/board_selftest.json. User console is in board_selftest_console.log.
FPGA programming55ms is not FFT performance. Overlay removal memory-leak and
out-of-tree taint warnings were present; operation continued to all self-test markers.
Full-frame/profile/paired300-sample comparison remains pending. Earlier build-only
pending statements and board_verified:false build metadata are preserved.

## Final follow-up

Full-frame/profile/paired300-sample comparison and independent raw validation now PASS.
PL median4.186353 ms/paired PS double5.767911/NEON3.649998 ms.
See [final4core board report](../2026-11-20-e13-4core-board/README.md).
The earlier pending statements preserve the build/self-test stages.
