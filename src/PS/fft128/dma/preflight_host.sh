#!/usr/bin/env bash
# Final small builds + module-only NFS staging. No full kernel/Vivado rebuild.
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
root=$(cd -- "$here/../../../.." && pwd)
kernel=$(cat "$root/build/fft128_dma_kernel_reference/kernel_build_path.txt")
bash "$here/prepare_host.sh"
bash "$here/build_module.sh" "$kernel"
bash "$here/deploy_module_probe.sh"
