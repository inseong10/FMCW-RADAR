#!/bin/sh
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
out=${1:-"$here/profiles_e14_frame_$(date +%Y%m%d_%H%M%S)"}
test ! -e "$out" || { echo 'Use a fresh profile directory' >&2; exit 1; }
mkdir -p "$out"
(cd "$here"; sha256sum -c artifacts.sha256) > "$out/artifact_check.txt"
cp "$here/artifacts.sha256" "$here/dma_config.json" "$here/fft128_e14_frame.json" \
    "$here/pl_source.sha256" "$here/host_source.sha256" "$here/module_source.sha256" \
    "$here/module_build_environment.txt" "$out/"
{
    uname -a; cat /proc/sys/kernel/random/boot_id; cat /proc/cpuinfo
    printf 'E14-frame CPU0 profile warmup=2 repeats=20, full-frame ioctl, PL transpose and output reorder\n'
} > "$out/environment.txt"
cat /proc/interrupts > "$out/interrupts_before.txt"
"$here/fft128-receiver" --cpu0 --input "$here/frame.rspb" \
    --warmup 2 --repeat 20 --profile-dma --pl-clock-hz 50000000 \
    --output "$out/pl" > "$out/profile.log" 2>&1 || { tail -n 30 "$out/profile.log"; exit 1; }
cat "$out/profile.log"
cat /proc/interrupts > "$out/interrupts_after.txt"
printf 'DMA_PROFILE_COMPLETE: %s\n' "$out"
