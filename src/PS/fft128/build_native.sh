#!/usr/bin/env bash
# Run on Ubuntu. Build only; NFS/TFTP contents and FPGA are not modified.
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
root=$(cd -- "$here/../../.." && pwd)
backend=${FFT128_IO_BACKEND:-mmio}
extra=()
case $backend in
    mmio) transport="$here/mmio.c"; default_out="$root/build/fft128_native";;
    dma) transport="$here/dma/dma_backend.c"; extra=(-DFFT128_DMA_BACKEND); default_out="$root/build/fft128_dma_native";;
    *) echo 'FFT128_IO_BACKEND must be mmio or dma' >&2; exit 1;;
esac
out=${FFT128_OUT:-"$default_out"}
compiler=()
is_arm_linux() {
    local triple
    triple=$("$@" -dumpmachine 2>/dev/null) || return 1
    [[ "$triple" == arm*linux* ]]
}
if [[ -n ${FFT128_CC:-} ]]; then
    compiler=("$FFT128_CC")
elif [[ -n ${CC:-} ]]; then
    # SDK CC contains the compiler plus architecture/sysroot arguments.
    read -r -a candidate <<< "$CC"
    if is_arm_linux "${candidate[@]}"; then compiler=("${candidate[@]}"); fi
fi
if ((${#compiler[@]}==0)); then
    for candidate in arm-linux-gnueabihf-gcc arm-xilinx-linux-gnueabi-gcc \
        /tools/Xilinx/Vitis/2022.1/gnu/aarch32/lin/*/bin/arm*linux*gcc; do
        if command -v "$candidate" >/dev/null 2>&1 && is_arm_linux "$candidate"; then
            compiler=("$candidate"); break
        fi
    done
fi
if ((${#compiler[@]}==0)) || ! is_arm_linux "${compiler[@]}"; then
    printf '%s\n' 'No ARM32 Linux compiler found. Source the matching PetaLinux SDK environment,' \
        'or set FFT128_CC to the Vitis arm-linux-gnueabihf-gcc executable.' >&2
    exit 1
fi
read -r -a cflags <<< "${CFLAGS:-}"
read -r -a ldflags <<< "${LDFLAGS:-}"
linkmode=()
case ${FFT128_STATIC:-1} in
    1) linkmode=(-static);;
    0) ;;
    *) printf '%s\n' 'FFT128_STATIC must be 0 or 1' >&2; exit 1;;
esac
mkdir -p -- "$out"
printf 'COMPILER: %s\n' "${compiler[*]}"
"${compiler[@]}" -O2 -std=c11 -Wall -Wextra "${cflags[@]}" \
    "${extra[@]}" "$here/native_core.c" "$here/native_receiver.c" "$transport" \
    "${linkmode[@]}" "${ldflags[@]}" -lm -o "$out/fft128-receiver"
if command -v file >/dev/null 2>&1; then file "$out/fft128-receiver"; fi
printf 'NATIVE_BUILD_PASS: %s\n' "$out/fft128-receiver"
if [[ $backend == dma ]]; then
    printf '%s\n' 'E11a build only. Use dma/prepare_bundle.sh and dma/deploy.sh; baseline deployment stays intact.' \
        'DMA requires the E11a bitstream, DT overlay and matching fft128_dma module.'
else
    printf '%s\n' 'Copy this ARM32 Linux executable into /nfsroot/opt/fft128 on Ubuntu.' \
        'On the board it will appear at /opt/fft128/fft128-receiver. Python is not required.' \
        'The new FFT bitstream and clock/reset must be ready before using the default MMIO backend.'
fi
