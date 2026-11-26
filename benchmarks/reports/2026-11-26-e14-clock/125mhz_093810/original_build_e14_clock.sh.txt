#!/usr/bin/env bash
# Build one isolated candidate. No deployment, FPGA programming or ARM rebuild.
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
mhz=${1:?Usage: build_e14_clock.sh MHz}
python3 - "$mhz" <<'PY'
import math, sys
n = float(sys.argv[1])
assert math.isfinite(n) and 50 <= n <= 200, 'MHz must be in [50, 200]'
PY
vivado=${FFT128_VIVADO:-}
if [[ -z "$vivado" ]]; then
    for candidate in vivado /tools/Xilinx/Vivado/2022.1/bin/vivado; do
        if command -v "$candidate" >/dev/null 2>&1; then vivado=$candidate; break; fi
    done
fi
test -n "$vivado" || { echo 'Vivado not found; set FFT128_VIVADO to its executable.' >&2; exit 1; }
mkdir -p "$root/build/e14_clock"
launch=$(mktemp -d "$root/build/e14_clock/launch_XXXXXX")
printf 'requested_mhz=%s\n' "$mhz" > "$launch/request.txt"
cd "$root"
printf 'E14_CLOCK_BUILD_START: %s MHz\nLOG: %s\n' "$mhz" "$launch/console.log"
set +e
"$vivado" -mode batch -notrace \
    -log "$launch/vivado.log" -journal "$launch/vivado.jou" \
    -source "$root/src/PL/fft128_ps/build_dma_frame_clock.tcl" -tclargs "$mhz" \
    > "$launch/console.log" 2>&1
vivado_status=$?
set -e
printf 'vivado_status=%s\n' "$vivado_status" >> "$launch/request.txt"
run=$(sed -n 's/^FFT128_CLOCK_RUN: //p' "$launch/console.log" | tail -n 1)
test -n "$run" && test -d "$run" || {
    tail -n 12 "$launch/console.log" >&2
    printf 'No candidate directory; inspect %s\n' "$launch/console.log" >&2; exit 1;
}
cp "$launch/request.txt" "$run/clock_request.txt"
printf '%s\n' "$launch" > "$run/launcher_path.txt"
if ! python3 "$root/tools/clock/validate_clock.py" "$run" --mhz "$mhz"; then
    printf 'Vivado log tail:\n' >&2
    tail -n 12 "$launch/console.log" >&2
    exit 1
fi
test "$vivado_status" -eq 0 || {
    printf 'Vivado exited with status %s; inspect %s\n' "$vivado_status" "$launch/console.log" >&2
    exit 1
}
printf 'E14_CLOCK_CANDIDATE_READY: %s\n' "$run"
