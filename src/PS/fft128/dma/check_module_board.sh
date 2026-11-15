#!/bin/sh
# Check real running-kernel CRCs before new firmware or DT. No FPGA register IO.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
test "$(id -u)" = 0 || { echo 'Run with sudo sh' >&2; exit 1; }
(cd "$here"; sha256sum -c artifacts.sha256)
test "$(uname -r)" = "$(cat "$here/kernelrelease.txt")"
test ! -d /sys/module/fft128_dma || { echo 'Module already active; do not probe compatibility now.' >&2; exit 1; }
# Prevent platform probe/AXI access: no matching DT client may exist yet.
(cd /sys/firmware/devicetree/base; find . -type f -name compatible) |
while IFS= read -r path; do
    if grep -q fmcw,fft128-dma-v1 "/sys/firmware/devicetree/base/$path"; then
        echo 'FFT DMA client already exists in DT; use full activation workflow.' >&2; exit 1
    fi
done
insmod "$here/fft128_dma.ko"
rmmod fft128_dma
printf 'DMA_MODULE_CRC_PASS: normal load/unload accepted by running kernel; no FPGA/DT change or DMA transfer\n'
