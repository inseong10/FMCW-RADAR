#!/usr/bin/env bash
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
stage="$HOME/fft128_dma_probe_deploy"
mkdir -p "$stage"
cp "$here/probe_board.sh" "$stage/probe_board.sh"
sudo install -D -m 0755 "$stage/probe_board.sh" /nfsroot/opt/fft128/e11a/probe_board.sh
printf '%s\n' 'DMA_PROBE_DEPLOYED; board: sudo sh /opt/fft128/e11a/probe_board.sh'
