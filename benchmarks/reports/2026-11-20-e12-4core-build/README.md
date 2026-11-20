# E12-4core Vivado/ARM build — 2026-11-20

Run: `fft128_dma_e12_4core_20261120_180134`.
Actual generated reset IP/AXI ID/ABI5/core-count/lock-loss simulation, routed50 MHz timing,
bitstream/XSA and ARM32 receiver/client/module builds PASS. Source hashes independently match
both current checkout and VMware shared source. Host/module artifact manifests also PASS.

- Setup WNS8.709 ns, hold WHS0.026 ns; setup/hold failing endpoints0/0.
- No-clock pins/unconstrained internal endpoints0; all user timing constraints met.
- LUT5311/17600 (30.18%), FF5555/35200 (15.78%), BRAM15/60 (25%), DSP16/80 (20%).
- E13-4core used LUT4868/FF5169/BRAM11/DSP16: E12 adds443 LUT,386 FF,4 BRAM tiles;
  arithmetic DSP count remains unchanged.
- Routed hierarchy contains core0..3, each4 DSP, plus ingress/egress RAM FIFO per lane.
  All8 FIFO instances each use1 RAMB18 and0 DSP, totaling4 BRAM tiles.
- Generated BD PS7/DMA/clock/reset/interconnect/IRQ parameters and all interface nets,
  nets/addressing are identical to actual E13-4core BD. Single Simple DMA,
  HP0 64-bit/AXIS32-bit, SG/DRE off, burst16, length17, F2P6/7 are retained.
- Generated reset VHDL confirms external active-low/auxiliary active-high reset.
- ARM32 receiver and packet client are statically linked ELF and compiled successfully.
  Header112/input112/output65648/extra131184/request131224B static assertions passed.
- Module compiled against prepared5.15.19-xilinx/ARMv7/SMP/preempt/modversions kernel.
  Normal board insmod must still accept its symbol CRCs; no force options are used.
- prepare_host completed dtc and recorded-DT fdtoverlay validation. Standalone dtc GIC
  phandle warnings are preserved in host_dtc.log; merged-tree validation passed.

These are implementation/offline checks. Firmware conversion/bundle assembly, deployment,
live overlay/module loading, actual DMA packet/self-test/overlap, full-frame/profile and paired
300-sample measurements remain pending. No E12 board performance result is available.
The1.123920ms RTL cycle model is not a measured board/frame latency.

Compact reports/manifests are preserved here; large bitstream/XSA/ARM binaries stay in ignored
shared build/ paths. `implementation.json` records their exact paths, sizes, SHA256,
manifest verification, ELF identities, timing/resources and actual BD/FIFO hierarchy checks.
Original build metadata `board_verified:false` is retained.

Ubuntu next:
```bash
P="$HOME/fmcw_share/FMCW-FFT-test"
bash "$P/src/PS/fft128/dma_overlap/prepare_bundle.sh" &&
bash "$P/src/PS/fft128/dma_overlap/deploy.sh"
```
After successful deployment, reboot the board to clear old DMA module/overlay before switching:
```sh
sudo sh /opt/fft128/e12_4core/load_board.sh
```

[Board procedure](../../../src/PS/fft128/dma_overlap/README.md),
[RTL preparation](../2026-11-20-e12-4core-preparation/README.md),
[Previous E13 board baseline](../2026-11-20-e13-4core-board/README.md).


## Board self-test follow-up

User PetaLinux console confirms FPGA Manager load, live overlay/client binding and
normal module loading, followed by packet/receiver self-test PASS. Exact supplied console
is preserved in `board_selftest_console.log`; this is user-reported board evidence.
Shared bundle22 artifact hashes were independently checked and saved in
`bundle_artifacts.sha256`/`board_selftest.json`. Firmware BIN matches the generated
firmware conversion. FPGA programming56ms is not FFT performance.

Packets1/2/3/4/5/127/128/128 passed integer checking, including partial groups and repeated
full axes. Exclusive ownership, invalid ABI/timeout/flags/count rejection and receiver
4vector/512bin self-test passed through `DMA_E12_4CORE_SELFTEST_READY`.

Last128FFT axis reported external input/output simultaneous handshakes11415cycles,
input/work16097, output/work16096 and three-way11386. multi-work19360/all-work2976.
Work includes first output RAM read; independent lanes require a conservative bound
of at most128 non-CALC work clocks per axis. Thus simultaneous4-CALC is at least2848cycles
and external input/output with actual CALC is at least11258cycles. These are positive
board counter bounds, not whole-frame FFT latency. Overlapping counters are not additive.

Overlay removal memory-leak and out-of-tree module taint warnings were present; execution
continued through all self-test markers. Full-frame20 profile and each300 paired PS/PL
measurements remain pending. Earlier build-only pending statements preserve that stage;
`implementation.json` and generated build metadata retain `board_verified:false`.


## Final follow-up

Full-frame/profile/paired300-sample raw validation now PASS.
PL median3.129210ms/paired NEON3.488904ms; profile active1.124590ms.
See [final E12 board results](../2026-11-20-e12-4core-board/README.md).
Earlier pending statements and build metadata preserve their original stages.
