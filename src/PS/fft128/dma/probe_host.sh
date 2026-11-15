#!/usr/bin/env bash
# Locate matching target build artifacts without changing toolchains/projects.
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
root=$(cd -- "$here/../../../.." && pwd)
out="$root/build/fft128_dma_probe"
mkdir -p "$out"
test -r /nfsroot/opt/fft128/e11a/probe_board/kernel.config || {
    printf '%s\n' 'Run probe_board.sh on PetaLinux first.' >&2; exit 1;
}
# Existing probes can include root-only sysfs copies. Read via sudo but extract
# as the mounting user: root cannot write to the VMware shared folder.
mkdir -p "$out/probe_board"
sudo tar -C /nfsroot/opt/fft128/e11a/probe_board -cf - . |
    tar --no-same-owner -C "$out/probe_board" -xf -
chmod -R u+rX "$out/probe_board"
{
    uname -a
    for item in /tools/Xilinx/petalinux/settings.sh /tools/Xilinx/bsp/*.bsp; do
        if test -e "$item"; then ls -l "$item"; fi
    done
    for command in petalinux-create petalinux-build arm-linux-gnueabihf-gcc dtc; do
        command -v "$command" || true
    done
    for dir in "$HOME/FMCW" "$HOME/fmcw_zynq" "$HOME/practice" "$HOME/test" /tools/Xilinx/petalinux/components; do
        if test -d "$dir"; then
            find "$dir" -maxdepth 8 -type f \( -name Module.symvers -o -name kernel.release -o -path '*/project-spec/configs/config' \) -print 2>/dev/null || true
        fi
    done
} > "$out/host.txt"
printf 'DMA_HOST_PROBE_READY: %s\n' "$out"
cat "$out/host.txt"
