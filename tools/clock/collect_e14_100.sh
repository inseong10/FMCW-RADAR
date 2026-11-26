#!/usr/bin/env bash
# Ubuntu: copy completed raw board results into the Windows/VM shared workspace.
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
source_dir=/nfsroot/opt/fft128/e14_clock_100000000_20261126_095418/compare_100mhz_01
out=${1:-"$root/build/e14_clock_100_results_$(date +%Y%m%d_%H%M%S)"}
test ! -e "$out" || { echo 'Use a fresh collection directory.' >&2; exit 1; }
for name in clock_before.txt clock_after.txt load_board.console.log profile/pl.profile.csv paired/interrupts_after.txt; do
    test -s "$source_dir/$name" || { printf 'Missing board result: %s\n' "$name" >&2; exit 1; }
done
cp -r "$source_dir" "$out"
printf 'E14_100MHZ_COLLECTED: %s\n' "$out"
printf 'Raw copy complete; independent clock, accuracy and paired-timing analysis follows.\n'
