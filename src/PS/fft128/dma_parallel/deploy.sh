#!/usr/bin/env bash
# Explicit deployment of a complete E13-2core bundle only; baseline paths preserved.
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
root=$(cd -- "$here/../../../.." && pwd)
bundle=${FFT128_DMA_PARALLEL_BUNDLE_OUT:-"$root/build/fft128_dma_parallel_bundle"}
(cd "$bundle"; sha256sum -c artifacts.sha256)
stage=$(mktemp -d "$HOME/fft128_e13_2core_deploy.XXXXXX")
cp -r "$bundle/." "$stage/"
if sudo test -e /nfsroot/opt/fft128/e13_2core/artifacts.sha256; then
    sudo cmp -s "$stage/artifacts.sha256" /nfsroot/opt/fft128/e13_2core/artifacts.sha256 || {
        echo 'A different E13-2core deployment exists; preserve its firmware/results and use a new destination.' >&2
        exit 1
    }
fi
sudo install -d -m 0755 /nfsroot/opt/fft128/e13_2core
for path in "$stage"/*; do
    test -f "$path" || continue
    mode=0644
    case $(basename -- "$path") in fft128-receiver|test-dma-parallel-client) mode=0755;; esac
    sudo install -m "$mode" "$path" /nfsroot/opt/fft128/e13_2core/
done
printf 'DMA_DEPLOY_READY: board /opt/fft128/e13_2core; no FPGA programming performed\n'
