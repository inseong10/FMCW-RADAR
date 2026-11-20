#!/bin/sh
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
out=${1:-"$here/profiles_e12_4core_$(date +%Y%m%d_%H%M%S)"}
test ! -e "$out" || { echo 'Use a fresh profile directory' >&2; exit 1; }
mkdir -p "$out"
(cd "$here"; sha256sum -c artifacts.sha256) > "$out/artifact_check.txt"
cp "$here/artifacts.sha256" "$here/dma_config.json" "$here/fft128_e12_4core.json" "$out/"
"$here/fft128-receiver" --cpu0 --input "$here/frame.rspb" \
    --warmup 2 --repeat 20 --profile-dma --pl-clock-hz 50000000 \
    --output "$out/pl" > "$out/profile.log" 2>&1 || { tail -n 30 "$out/profile.log"; exit 1; }
cat "$out/profile.log"
printf 'DMA_PROFILE_COMPLETE: %s\n' "$out"
