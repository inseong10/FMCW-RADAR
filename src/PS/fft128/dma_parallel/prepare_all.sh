#!/usr/bin/env bash
# Ubuntu E13-2core userspace + module builds only; no FPGA programming/kernel replacement.
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
root=$(cd -- "$here/../../../.." && pwd)
out="$root/build/fft128_dma_parallel_preparation"
mkdir -p "$out"
{
    bash "$here/prepare_host.sh"
    kernel=$(cat "$root/build/fft128_dma_kernel_reference/kernel_build_path.txt")
    bash "$here/build_module.sh" "$kernel"
    printf 'E13_2CORE_ARM_BUILD_PASS\n'
} 2>&1 | tee "$out/arm_build.log"
