#!/usr/bin/env bash
# Ubuntu: collect named completed NFS results and independently validate them.
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
root=$(cd -- "$here/../../../.." && pwd)
source_dir=${1:-/nfsroot/opt/fft128/e13_bf2}
out="$root/build/fft128_dma_bf2_measurements"
test ! -e "$out" || { echo 'Preserve existing collected measurements; use a fresh collection directory.' >&2; exit 1; }
test -s "$source_dir/results_e13_bf2_01/interrupts_after.txt"
test -s "$source_dir/profile_e13_bf2_01/pl.profile.csv"
mkdir -p "$out"
cp -r "$source_dir/results_e13_bf2_01" "$source_dir/profile_e13_bf2_01" "$out/"
python3 "$root/benchmarks/compare_dma_bf2_board.py" "$out/results_e13_bf2_01" > "$out/comparison_console.json"
python3 "$here/analyze_profile.py" "$out/profile_e13_bf2_01/pl.profile.csv" > "$out/profile_console.json"
printf 'E13_BF2_COLLECTED_VALIDATED: %s\n' "$out"
