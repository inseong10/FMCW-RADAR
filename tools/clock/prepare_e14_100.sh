#!/usr/bin/env bash
# Package/deploy the selected, already built 100 MHz candidate. Never program PL.
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
run=${1:-"$root/build/vivado/fft128_dma_e14_clock_100p000mhz_20261126_092439_245"}
python3 - "$run/clock_validation.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
assert d['status'] == 'E14_CLOCK_BUILD_PASS' and d['clock_hz'] == 100000000, 'Require validated 100 MHz build'
PY
mkdir -p "$root/build/e14_clock"
work=$(mktemp -d "$root/build/e14_clock/prepare_100mhz_XXXXXX")
log="$work/prepare.log"
printf 'E14_100MHZ_PREPARE_START\nLOG: %s\n' "$log"
if ! bash "$root/tools/clock/prepare_e14_clock_bundle.sh" "$run" "$work/bundle" > "$log" 2>&1; then
    tail -n 15 "$log" >&2
    exit 1
fi
# Keep any password prompt visible; all detailed copy/hash output stays in the log.
sudo -v
if ! bash "$root/tools/clock/deploy_e14_clock.sh" "$work/bundle" >> "$log" 2>&1; then
    tail -n 15 "$log" >&2
    exit 1
fi
board=$(sed -n 's/^E14_CLOCK_DEPLOY_READY: board //p' "$log" | tail -n 1)
test -n "$board" || { echo 'Missing deployment result; inspect log.' >&2; exit 1; }
printf '%s\n' "$board" > "$root/build/e14_clock_100mhz_deployed_path.txt"
printf 'E14_100MHZ_DEPLOY_READY: %s\n' "$board"
printf 'After a fresh board boot: sudo sh %s/load_board.sh\n' "$board"
