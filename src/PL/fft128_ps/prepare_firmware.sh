#!/usr/bin/env bash
# Ubuntu: raw Zynq bitstream preparation only; no FPGA or NFS writes.
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
root=$(cd -- "$here/../../.." && pwd)
if [[ $# -gt 1 ]]; then printf '%s\n' 'Usage: prepare_firmware.sh [Vivado output directory]' >&2; exit 1; fi
if [[ $# -eq 1 ]]; then
    run=$1
else
    run=$(cat "$root/build/fft128_latest.txt")
fi
if [[ ! -r "$run/clock_source.txt" ]] || \
   ! grep -q 'FCLK0 not used' "$run/clock_source.txt" || \
   ! grep -q 'RESET_SCHEME=BOARD_MMCM_LOCK_V3_AUX_HIGH' "$run/clock_source.txt"; then
    printf '%s\n' 'Build the updated board-clock/reset V3 design first; clock_source.txt must contain RESET_SCHEME=BOARD_MMCM_LOCK_V3_AUX_HIGH.' >&2
    exit 1
fi
bit="$run/fft128_ps.runs/impl_1/system_wrapper.bit"
if [[ ! -r "$bit" ]]; then printf 'Missing bitstream: %s\n' "$bit" >&2; exit 1; fi
bootgen=${FFT128_BOOTGEN:-}
if [[ -z "$bootgen" ]]; then
    for candidate in bootgen /tools/Xilinx/Vitis/2022.1/bin/bootgen /tools/Xilinx/Vivado/2022.1/bin/bootgen; do
        if command -v "$candidate" >/dev/null 2>&1; then bootgen=$candidate; break; fi
    done
fi
if [[ -z "$bootgen" ]]; then printf '%s\n' 'Bootgen not found. Set FFT128_BOOTGEN to its executable.' >&2; exit 1; fi
work="$run/firmware"
mkdir -p -- "$work"
cp -- "$bit" "$work/fft128.bit"
printf 'all:\n{\n  fft128.bit\n}\n' > "$work/fft128.bif"
(
    cd -- "$work"
    "$bootgen" -arch zynq -image fft128.bif -process_bitstream bin -w on
    test -s fft128.bit.bin
    cp -- fft128.bit.bin fft128.bin
    sha256sum fft128.bin > fft128.bin.sha256
)
printf 'FIRMWARE_READY: %s\n' "$work/fft128.bin"
printf '%s\n' 'Copy as the mounting user to a local Ubuntu folder before sudo install into /nfsroot/opt/fft128/.' \
    'FPGA programming remains a separate board command: sudo fpgautil -b /opt/fft128/fft128.bin'
