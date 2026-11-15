#!/usr/bin/env bash
# Preserve the initial bundle; update DT layout without a Vivado/kernel rebuild.
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
root=$(cd -- "$here/../../../.." && pwd)
export FFT128_DMA_HOST_OUT="$root/build/fft128_dma_host_dt_v2"
export FFT128_DMA_BUNDLE_OUT="$root/build/fft128_dma_bundle_dt_v2"
bash "$here/prepare_host.sh"
bash "$here/prepare_bundle.sh"
# The raw FPGA firmware must be identical to the first successful implementation.
cmp "$root/build/fft128_dma_bundle/fft128_e11a.bin" "$FFT128_DMA_BUNDLE_OUT/fft128_e11a.bin"
bash "$here/deploy.sh"
printf 'DMA_OVERLAY_REPAIR_READY: board sudo sh /opt/fft128/e11a/retry_overlay_board.sh\n'
