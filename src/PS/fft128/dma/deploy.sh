#!/usr/bin/env bash
# Explicit deployment of a complete E11a bundle only; baseline paths preserved.
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
root=$(cd -- "$here/../../../.." && pwd)
bundle=${FFT128_DMA_BUNDLE_OUT:-"$root/build/fft128_dma_bundle"}
(cd "$bundle"; sha256sum -c artifacts.sha256)
stage=$(mktemp -d "$HOME/fft128_e11a_deploy.XXXXXX")
cp -r "$bundle/." "$stage/"
sudo install -d -m 0755 /nfsroot/opt/fft128/e11a
for path in "$stage"/*; do
    test -f "$path" || continue
    mode=0644
    case $(basename -- "$path") in fft128-receiver|test-dma-client) mode=0755;; esac
    sudo install -m "$mode" "$path" /nfsroot/opt/fft128/e11a/
done
printf 'DMA_DEPLOY_READY: board /opt/fft128/e11a; no FPGA programming performed\n'
