#!/bin/sh
# Separate diagnostic run: never mix instrumented samples with baseline timings.
# Usage: sudo sh profile_board.sh 20000000 [output-prefix]
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
hz=${1:?Specify actual PL clock Hz from the programmed build clock_source.txt}
prefix=${2:-"$here/profiles/profile_$(date +%Y%m%d_%H%M%S)"}
case "$hz" in 20000000|50000000) ;; *) echo 'Expected 20000000 or 50000000 Hz matching firmware' >&2; exit 2;; esac
mkdir -p "$(dirname -- "$prefix")"
"$here/bin/fft128-receiver" --input "$here/frame.rspb" --cpu0 \
    --warmup 2 --repeat 20 --profile-mmio --pl-clock-hz "$hz" --output "$prefix"
printf 'PROFILE_COMPLETE: %s.profile.csv\n' "$prefix"
