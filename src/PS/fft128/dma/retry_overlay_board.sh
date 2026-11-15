#!/bin/sh
# One-time recovery from the observed unpopulated nested-bus overlay.
# Refuse to unload a working/new DMA configuration or any active client.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
test "$(id -u)" = 0 || { echo 'Run with sudo sh' >&2; exit 1; }
(cd "$here"; sha256sum -c artifacts.sha256)
test ! -e /dev/fft128-dma || { echo 'DMA client exists; stop recovery.' >&2; exit 1; }
test -d /sys/firmware/devicetree/base/fft128-e11a-bus || { echo 'Expected failed nested-bus overlay is absent.' >&2; exit 1; }
for path in /sys/firmware/devicetree/base/amba_pl/dma@40400000 \
    /sys/firmware/devicetree/base/amba_pl/fft@43c60000 \
    /sys/bus/platform/devices/40400000.dma /sys/bus/platform/devices/43c60000.fft; do
    test ! -e "$path" || { echo "Device already instantiated: $path; stop recovery." >&2; exit 1; }
done
overlay=/sys/kernel/config/device-tree/overlays/fft128_e11a
test -d "$overlay"
if test -d /sys/module/fft128_dma; then rmmod fft128_dma; fi
# Only this failed overlay is removed, with no instantiated DMA/FFT devices.
rmdir "$overlay"
test ! -e /sys/firmware/devicetree/base/fft128-e11a-bus
test ! -e /sys/firmware/devicetree/base/fft128-e11a-clock
exec sh "$here/load_board.sh"
