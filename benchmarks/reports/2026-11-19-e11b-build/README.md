# E11b Vivado/ARM build - 2026-11-19

50 MHz implementation, generated reset IP simulation, bitstream/XSA and ARM32 static
receiver/ABI checker/kernel module builds PASS. Current checkout raw source SHA values
match the PL/host/module build manifests; artifact manifests were checked independently.

- Setup WNS 10.618 ns; hold WHS 0.016 ns; setup/hold failing endpoints 0.
- No-clock pins and unconstrained internal endpoints 0.
- LUT 3,243/17,600; FF 4,017/35,200; BRAM tiles 5/60; DSP 4/80.
- Generated BD checked: HP0 64-bit, AXIS 32-bit, Simple DMA, SG/DRE off,
  length width 17 (65,536 B supported), F2P6/7, control/DMA address and DDR mappings.
- Recorded live DT overlay compiled and fdtoverlay validation PASS in prepare_host.sh.
  dtc reports an external GIC phandle warning when compiling the standalone overlay;
  this is preserved in dtc.log. Actual live-tree/driver binding is still unverified.

These are build/offline checks. Board module CRC acceptance, client binding, DMA data
transfer/accuracy, full-frame profile and paired 300-sample timing remain pending.
No E11b board performance number is available yet. Binary files stay in ignored build/;
implementation.json records exact paths, lengths and hashes.

## Board self-test follow-up

User PetaLinux console confirms normal module load/CRC acceptance, AXI DMA and FFT
client binding, one 512 B packet and two 65,536 B packets with 1/128/128 completed FFTs,
ABI rejection/exclusive ownership checks, and four-vector/512-bin receiver self-test PASS.
See board_selftest_console.log and board_selftest.json. The local deployment bundle
manifest was independently checked and preserved as bundle_artifacts.sha256.

The 63 ms FPGA configuration load is not an FFT measurement. Overlay removal memory
leak warnings and the out-of-tree module taint message were present; operation continued
through DMA_E11B_SELFTEST_READY. Full 128x128 frame/profile/paired timing remain pending.

## Final follow-up

Full-frame/profile/paired 300-sample measurement and independent raw validation now PASS.
See [E11b final board report](../2026-11-19-e11b-board/README.md). Prior pending statements record the earlier build/self-test stage.
