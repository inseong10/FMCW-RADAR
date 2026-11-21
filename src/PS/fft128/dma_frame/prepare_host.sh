#!/usr/bin/env bash
# Ubuntu-only userspace/overlay build; no kernel/FPGA/NFS changes.
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
root=$(cd -- "$here/../../../.." && pwd)
out=${FFT128_DMA_FRAME_HOST_OUT:-"$root/build/fft128_dma_frame_host"}
mkdir -p "$out"
FFT128_IO_BACKEND=dma_frame FFT128_OUT="$out/bin" bash "$here/../build_native.sh" | tee "$out/receiver_build.log"
arm-linux-gnueabihf-gcc -O2 -std=c11 -Wall -Wextra -Werror -static \
    "$here/test_dma_frame_client.c" "$here/../native_core.c" -lm -o "$out/bin/test-dma-frame-client"
python3 "$here/make_overlay.py" "$root/build/fft128_dma_probe/probe_board/live_dt.tar" "$out/fft128_e14_frame.dts"
dtc -@ -I dts -O dtb -o "$out/fft128_e14_frame.dtbo" "$out/fft128_e14_frame.dts" 2> "$out/dtc.log"
# Verify local phandle fixups against the captured base tree before deployment.
fdtoverlay -i "$root/build/fft128_dma_probe/probe_board/running.dtb" \
    -o "$out/merged_validation.dtb" "$out/fft128_e14_frame.dtbo"
test "$(fdtget "$out/merged_validation.dtb" /amba_pl/dma@40400000 compatible)" = xlnx,axi-dma-1.00.a
test "$(fdtget "$out/merged_validation.dtb" /amba_pl/fft@43c60000 compatible)" = fmcw,fft128-dma-frame-v8
{
    uname -a
    arm-linux-gnueabihf-gcc --version | head -n 1
    sha256sum "$here/dma_frame_backend.c" "$here/fft128_dma_frame_uapi.h" \
        "$here/../native_receiver.c" "$here/../native_core.c" "$here/../native_core.h"
    printf 'Overlay validation is offline only; kernel DMA transfer/IRQ and Vivado integration remain unverified.\n'
} > "$out/build_environment.txt"
(cd "$root"; sha256sum src/PS/fft128/native_receiver.c src/PS/fft128/native_core.c \
    src/PS/fft128/native_core.h src/PS/fft128/build_native.sh src/PS/fft128/dma_frame/dma_frame_backend.c \
    src/PS/fft128/dma_frame/fft128_dma_frame_uapi.h src/PS/fft128/dma_frame/test_dma_frame_client.c \
    src/PS/fft128/dma_frame/make_overlay.py src/PS/fft128/dma/make_overlay.py \
    src/PS/fft128/dma_frame/frame_process.c src/PS/fft128/dma_frame/frame_process.h src/PS/fft128/dma_batch/make_overlay.py > "$out/source.sha256")
(cd "$out"; sha256sum bin/fft128-receiver bin/test-dma-frame-client fft128_e14_frame.dtbo fft128_e14_frame.dts > artifacts.sha256)
printf 'DMA_HOST_BUILD_READY: %s\n' "$out"
