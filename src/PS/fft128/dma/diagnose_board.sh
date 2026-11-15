#!/bin/sh
# Read-only diagnosis after E11a overlay/module activation; no MMIO access.
set -eu
out=${1:-/opt/fft128/e11a/diagnostic_01}
test ! -e "$out" || { echo 'Use a fresh diagnostic directory' >&2; exit 1; }
mkdir -p "$out"
dmesg | tail -n 160 > "$out/dmesg.txt"
cat /proc/interrupts > "$out/interrupts.txt"
cat /proc/modules > "$out/modules.txt"
{
    ls -l /dev/fft128-dma 2>/dev/null || true
    ls -l /sys/bus/platform/drivers/fft128-dma /sys/bus/platform/drivers/xilinx-vdma 2>/dev/null || true
    ls -l /sys/bus/platform/devices | grep -E 'fft128|40400000|43c60000' || true
    for path in /sys/kernel/config/device-tree/overlays/fft128_e11a/status \
        /sys/kernel/debug/devices_deferred /sys/kernel/debug/clk/clk_summary; do
        if test -r "$path"; then printf '\n%s\n' "$path"; cat "$path"; fi
    done
    for node in /sys/bus/platform/devices/*; do
        case "$node" in *fft128*|*40400000*|*43c60000*)
            printf '\nDEVICE %s\n' "$node"
            ls -l "$node/driver" "$node/of_node" 2>/dev/null || true
            cat "$node/modalias" "$node/uevent" 2>/dev/null || true;;
        esac
    done
} > "$out/devices.txt"
if test -d /sys/firmware/devicetree/base; then
    tar -C /sys/firmware/devicetree/base -cf "$out/live_dt.tar" .
fi
chmod a+r "$out"/*
cat "$out/dmesg.txt"
cat "$out/devices.txt"
printf 'DMA_DIAGNOSTIC_READY: %s\n' "$out"
