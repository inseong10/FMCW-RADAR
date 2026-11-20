#!/usr/bin/env bash
# Kernel build only; never installs modules or replaces the running kernel.
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
root=$(cd -- "$here/../../../.." && pwd)
probe="$root/build/fft128_dma_probe/probe_board"
kernel=${1:?Usage: build_module.sh /absolute/path/to/prepared-ARM-kernel-build}
kernel=$(cd -- "$kernel" && pwd)
out=${FFT128_BF2_MODULE_OUT:-"$root/build/fft128_dma_bf2_module"}
target=$(cat "$probe/kernelrelease.txt")
test -s "$kernel/Module.symvers" && test -r "$kernel/include/config/kernel.release" || {
    echo 'A full target kernel build is required (modules_prepare alone does not generate symbol CRCs).' >&2; exit 1;
}
test "$(cat "$kernel/include/config/kernel.release")" = "$target" || {
    printf 'Kernel release mismatch; expected %s. Do not force vermagic.\n' "$target" >&2; exit 1;
}
for flag in CONFIG_ARM=y CONFIG_MODULES=y CONFIG_MODVERSIONS=y CONFIG_DMA_ENGINE=y CONFIG_XILINX_DMA=y; do
    grep -qx "$flag" "$kernel/.config" || { printf 'Missing %s\n' "$flag" >&2; exit 1; }
done
cross=${CROSS_COMPILE:-arm-linux-gnueabihf-}
case $("${cross}gcc" -dumpmachine) in arm*linux*) ;; *) echo 'ARM Linux compiler required' >&2; exit 1;; esac
# Build in a local directory: some kernel build tools cannot run on VMware HGFS.
stage=$(mktemp -d "$HOME/fft128_dma_bf2_module.XXXXXX")
cp "$here/fft128_dma_bf2.c" "$here/fft128_dma_bf2_uapi.h" "$here/Makefile" "$stage/"
make -C "$kernel" ARCH=arm LOCALVERSION= CROSS_COMPILE="$cross" M="$stage" modules
mkdir -p "$out"
cp "$stage/fft128_dma_bf2.ko" "$out/"
(cd "$stage"; sha256sum fft128_dma_bf2.c fft128_dma_bf2_uapi.h Makefile > "$out/source.sha256")
{
    printf 'kernel_build=%s\nmodule_build=%s\n' "$kernel" "$stage"
    "${cross}gcc" --version | head -n 1
    sha256sum "$kernel/.config" "$kernel/Module.symvers" "$probe/kernel.config"
    sha256sum "$here/fft128_dma_bf2.c" "$here/fft128_dma_bf2_uapi.h"
    if command -v modinfo >/dev/null; then modinfo "$out/fft128_dma_bf2.ko"; fi
    printf 'Matching release is necessary, not sufficient. Board insmod must accept all MODVERSIONS CRCs. Never use --force.\n'
} > "$out/build_environment.txt"
(cd "$out"; sha256sum fft128_dma_bf2.ko > artifacts.sha256)
printf 'DMA_MODULE_BUILD_READY: %s\n' "$out"
