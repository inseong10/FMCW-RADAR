#!/usr/bin/env bash
# Explicit deployment of a complete E13-4core bundle only; baseline paths preserved.
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
root=$(cd -- "$here/../../../.." && pwd)
bundle=${FFT128_DMA_QUAD_BUNDLE_OUT:-"$root/build/fft128_dma_quad_bundle"}
(cd "$bundle"; sha256sum -c artifacts.sha256)
stage=$(mktemp -d "$HOME/fft128_e13_4core_deploy.XXXXXX")
cp -r "$bundle/." "$stage/"
if sudo test -e /nfsroot/opt/fft128/e13_4core/artifacts.sha256; then
    sudo cmp -s "$stage/artifacts.sha256" /nfsroot/opt/fft128/e13_4core/artifacts.sha256 || {
        echo 'A different E13-4core deployment exists; preserve its firmware/results and use a new destination.' >&2
        exit 1
    }
fi
sudo install -d -m 0755 /nfsroot/opt/fft128/e13_4core
for path in "$stage"/*; do
    test -f "$path" || continue
    mode=0644
    case $(basename -- "$path") in fft128-receiver|test-dma-quad-client) mode=0755;; esac
    sudo install -m "$mode" "$path" /nfsroot/opt/fft128/e13_4core/
done
printf 'DMA_DEPLOY_READY: board /opt/fft128/e13_4core; no FPGA programming performed\n'
