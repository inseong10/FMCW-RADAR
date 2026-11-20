#!/bin/sh
# E13-2core activation only. Never run a baseline MMIO receiver on this firmware.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
test "$(id -u)" = 0 || { echo 'Run with sudo sh' >&2; exit 1; }
(cd "$here"; sha256sum -c artifacts.sha256)
test "$(uname -r)" = "$(cat "$here/kernelrelease.txt")" || { echo 'Kernel release changed; rebuild and reprobe.' >&2; exit 1; }
gic=$(cat "$here/gic_path.txt")
cmp -s "/sys/firmware/devicetree/base$gic/phandle" "$here/gic_phandle.bin" || { echo 'Live GIC phandle changed; regenerate overlay.' >&2; exit 1; }
test ! -d /sys/module/fft128_dma || { echo 'E11a module is active: reboot before switching firmware.' >&2; exit 1; }
test ! -d /sys/module/fft128_dma_batch || { echo 'E11b module is active: reboot before switching firmware.' >&2; exit 1; }
test ! -d /sys/module/fft128_dma_parallel || { echo 'E13-2core module already loaded; keep current firmware while in use.' >&2; exit 1; }
test ! -d /sys/firmware/devicetree/base/fft128-e13_2core-bus || { echo 'E13-2core overlay already present.' >&2; exit 1; }
test ! -d /sys/firmware/devicetree/base/amba_pl/fft@43c60000 || { echo 'E13-2core client already present.' >&2; exit 1; }
test ! -d /sys/firmware/devicetree/base/amba_pl/dma@40400000 || { echo 'E13-2core DMA node already present.' >&2; exit 1; }
grep -q '"overlay_layout": "existing_amba_pl_v2"' "$here/fft128_e13_2core.json" || { echo 'Use corrected /amba_pl overlay bundle.' >&2; exit 1; }
# Do not change HP width in a live Linux system. Bitstream alone does not apply
# PS7 init settings: ensure the existing boot configured HP0 as 64 bit.
rd=$(devmem 0xF8008000 32)
wr=$(devmem 0xF8008014 32)
test $((rd & 1)) = 0 && test $((wr & 1)) = 0 || { echo 'HP0 is 32-bit; stop and review boot PS7 initialization.' >&2; exit 1; }
printf 'HP0 read/write control before activation: %s %s\n' "$rd" "$wr"
if ! grep -qs ' /sys/kernel/config configfs ' /proc/mounts; then
    mount -t configfs none /sys/kernel/config
fi
overlays=/sys/kernel/config/device-tree/overlays
test -d "$overlays" || { echo 'CONFIG_OF_CONFIGFS overlay interface unavailable.' >&2; exit 1; }
test ! -e "$overlays/fft128_e13_2core" || { echo 'E13-2core overlay instance already exists.' >&2; exit 1; }
fpgautil -b "$here/fft128_e13_2core.bin"
test "$(cat /sys/class/fpga_manager/fpga0/state)" = operating
# No firmware-name property in the overlay: fpgautil above handles programming.
mkdir "$overlays/fft128_e13_2core"
cat "$here/fft128_e13_2core.dtbo" > "$overlays/fft128_e13_2core/dtbo"
if test -r "$overlays/fft128_e13_2core/status"; then
    test "$(cat "$overlays/fft128_e13_2core/status")" = applied
fi
# Normal module loading enforces symbol CRCs. No --force or vermagic overrides.
insmod "$here/fft128_dma_parallel.ko"
test -c /dev/fft128-dma-parallel || { echo 'DMA client did not bind; inspect dmesg. Do not start a benchmark.' >&2; exit 1; }
"$here/test-dma-parallel-client"
"$here/fft128-receiver" --self-test
printf 'DMA_E13_2CORE_SELFTEST_READY: next run full frame/profile before benchmarking\n'
