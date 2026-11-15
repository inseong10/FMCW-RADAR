#!/usr/bin/env bash
# Stage a module-only compatibility check before asking for a Vivado build.
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
root=$(cd -- "$here/../../../.." && pwd)
module="$root/build/fft128_dma_module"
(cd "$module"; sha256sum -c artifacts.sha256)
stage=$(mktemp -d "$HOME/fft128_module_probe.XXXXXX")
cp "$module/fft128_dma.ko" "$here/check_module_board.sh" "$stage/"
cp "$root/build/fft128_dma_probe/probe_board/kernelrelease.txt" "$stage/"
(cd "$stage"; sha256sum fft128_dma.ko check_module_board.sh kernelrelease.txt > artifacts.sha256)
sudo install -d -m 0755 /nfsroot/opt/fft128/e11a/module_probe
for path in "$stage"/*; do sudo install -m 0644 "$path" /nfsroot/opt/fft128/e11a/module_probe/; done
printf 'MODULE_PROBE_DEPLOY_READY: sudo sh /opt/fft128/e11a/module_probe/check_module_board.sh\n'
