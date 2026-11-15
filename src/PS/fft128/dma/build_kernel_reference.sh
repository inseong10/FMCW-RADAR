#!/usr/bin/env bash
# Reconstruct a candidate kernel build tree from the BSP's pinned Digilent source.
# Full build for MODVERSIONS. No PetaLinux dependency checker, install or boot change.
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
root=$(cd -- "$here/../../../.." && pwd)
probe="$root/build/fft128_dma_probe/probe_board"
out="$root/build/fft128_dma_kernel_reference"
work=${FFT128_KERNEL_WORK:-"$HOME/fft128_kernel_e11a"}
source_dir="$work/source"
kernel="$work/build"
revision=5e8c35eccbabeb08a63f55f18fec677a685c30b3
cross=${CROSS_COMPILE:-arm-linux-gnueabihf-}
jobs=${FFT128_KERNEL_JOBS:-2}
case $jobs in ''|*[!0-9]*|0) echo 'Invalid FFT128_KERNEL_JOBS' >&2; exit 1;; esac
for tool in git make bison flex "${cross}gcc"; do
    command -v "$tool" >/dev/null || { printf 'Required host tool missing: %s\n' "$tool" >&2; exit 1; }
done
test -r "$probe/kernel.config" && test "$(cat "$probe/kernelrelease.txt")" = 5.15.19-xilinx
mkdir -p "$out" "$work"
if ! test -d "$source_dir"; then
    mkdir "$source_dir"
    git -C "$source_dir" init
    git -C "$source_dir" remote add origin https://github.com/Digilent/linux-digilent.git
    git -C "$source_dir" fetch --depth 1 origin "$revision"
    git -C "$source_dir" checkout --detach FETCH_HEAD
fi
test "$(git -C "$source_dir" rev-parse HEAD)" = "$revision" || { echo 'Unexpected kernel source revision' >&2; exit 1; }
test -z "$(git -C "$source_dir" status --porcelain)" || { echo 'Kernel source has local edits; stop.' >&2; exit 1; }
mkdir -p "$kernel"
if ! test -e "$kernel/.config"; then
    cp "$probe/kernel.config" "$kernel/.config"
    # The captured PetaLinux kernel release has no Git suffix. This switch only
    # controls release naming; the original config and resulting delta are saved.
    "$source_dir/scripts/config" --file "$kernel/.config" --disable LOCALVERSION_AUTO
fi
make -C "$source_dir" O="$kernel" ARCH=arm LOCALVERSION= CROSS_COMPILE="$cross" olddefconfig > "$out/configure.log" 2>&1
diff -u "$probe/kernel.config" "$kernel/.config" > "$out/config_delta.txt" || test $? = 1
release=$(make -s -C "$source_dir" O="$kernel" ARCH=arm LOCALVERSION= CROSS_COMPILE="$cross" kernelrelease)
test "$release" = "$(cat "$probe/kernelrelease.txt")" || { printf 'Kernel release mismatch: %s\n' "$release" >&2; exit 1; }
printf 'Building reference kernel and symbol CRCs (not FPGA synthesis). Log: %s\n' "$out/build.log"
make -C "$source_dir" O="$kernel" ARCH=arm LOCALVERSION= CROSS_COMPILE="$cross" -j"$jobs" zImage modules > "$out/build.log" 2>&1 || {
    tail -n 60 "$out/build.log" >&2; exit 1;
}
test -s "$kernel/Module.symvers"
printf '%s\n' "$kernel" > "$out/kernel_build_path.txt"
{
    printf 'source=%s\nrevision=%s\nbranch=digilent_rebase_v5.15_LTS_2022.1\nrelease=%s\n' "$source_dir" "$revision" "$release"
    "${cross}gcc" --version | head -n 1
    sha256sum "$probe/kernel.config" "$kernel/.config" "$kernel/Module.symvers"
    printf 'Candidate build only: original BSP used AUTOREV; exact boot-kernel provenance unavailable. Module CRC acceptance on the board is still required.\n'
} > "$out/build_environment.txt"
CROSS_COMPILE="$cross" bash "$here/build_module.sh" "$kernel" | tee "$out/module_build.log"
printf 'DMA_KERNEL_REFERENCE_READY: %s\n' "$out"
printf 'No kernel was installed; board module CRC acceptance remains unverified.\n'
