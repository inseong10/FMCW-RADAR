#!/bin/sh
# Read-only hardware/kernel inspection. Writes only a fresh evidence directory.
set -eu
out=${1:-/opt/fft128/e11a/probe_board}
test ! -e "$out" || { echo 'Use a fresh probe directory' >&2; exit 1; }
mkdir -p "$out"
uname -a > "$out/uname.txt"
uname -r > "$out/kernelrelease.txt"
cat /proc/cmdline > "$out/cmdline.txt"
if test -r /proc/config.gz; then zcat /proc/config.gz > "$out/kernel.config"; fi
cat /proc/iomem > "$out/iomem.txt"
cat /proc/interrupts > "$out/interrupts.txt"
cat /proc/modules > "$out/modules.txt"
grep -E 'Cma|MemTotal' /proc/meminfo > "$out/memory.txt" || true
if test -r /sys/firmware/fdt; then cp /sys/firmware/fdt "$out/running.dtb"; fi
if test -d /sys/firmware/devicetree/base; then
    tar -C /sys/firmware/devicetree/base -cf "$out/live_dt.tar" .
fi
{
    ls -ld /lib/modules/* /lib/modules/*/build /lib/modules/*/source 2>/dev/null || true
    ls /sys/bus/platform/drivers | grep -E 'dma|xilinx' || true
    ls /sys/kernel/config/device-tree/overlays 2>/dev/null || true
    grep -E 'CONFIG_(MODULES|MODVERSIONS|MODULE_UNLOAD|CONFIGFS_FS|OF_CONFIGFS|OF_OVERLAY|DMA_ENGINE|XILINX_DMA|CMA|DMA_CMA|FPGA)' "$out/kernel.config" || true
} > "$out/capabilities.txt"
# sysfs fdt may be mode 0400; these inspection artifacts must be readable by
# the Ubuntu mounting user through NFS. They contain no credentials.
chmod a+r "$out"/*
echo "DMA_BOARD_PROBE_READY: $out"
cat "$out/capabilities.txt"
