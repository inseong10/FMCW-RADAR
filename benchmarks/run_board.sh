#!/bin/sh
# Run on the Zybo after deployment. Does not program/rebuild the FPGA.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repeat=${FFT128_REPEAT:-100}
warmup=${FFT128_WARMUP:-10}
trials=${FFT128_TRIALS:-3}
results="$here/results"
mkdir -p "$results"
last_log=
trap 'status=$?; if test "$status" -ne 0; then printf "BOARD_BENCHMARK_STOPPED: status=%s\n" "$status" >&2; if test -n "$last_log" && test -r "$last_log"; then tail -n 35 "$last_log" >&2; fi; fi' 0
test -r "$here/frame.rspb"
test -x "$here/bin/udp_radar_receiver"
test -x "$here/bin/fft128-receiver"
{
    uname -a
    cat /proc/cpuinfo
    for path in /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor \
        /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq; do
        if test -r "$path"; then printf '%s: ' "$path"; cat "$path"; fi
    done
    printf 'repeat=%s warmup=%s trials=%s\n' "$repeat" "$warmup" "$trials"
    if command -v sha256sum >/dev/null 2>&1; then sha256sum "$here/frame.rspb"; fi
} > "$results/environment.txt"
printf 'cpu0_affinity=required; both programs use sched_setaffinity via --cpu0\n' >> "$results/environment.txt"
run_cpu() {
    "$@" --cpu0
}
fftw="$here/lib/libfftw3.so.3"
test -r "$fftw"
# Check CPU runtime first; a missing FFTW/loader stops before any PL MMIO.
printf '%s\n' 'PS preflight: prepare target-specific 128x128 FFTW MEASURE wisdom (excluded from timing)'
last_log="$results/ps_preflight.log"
run_cpu "$here/bin/udp_radar_receiver" --input "$here/frame.rspb" \
    --window none --q15-input --normalize-output --measure-plan --plan-time-limit 10 --fftw-lib "$fftw" \
    --wisdom-out "$results/ps_128x128.wis" --warmup 0 --repeat 1 > "$results/ps_preflight.log" 2>&1
trial=1
while test "$trial" -le "$trials"; do
    printf 'Trial %s/%s: PS optimized C++/FFTW\n' "$trial" "$trials"
    last_log="$results/ps_$trial.log"
    run_cpu "$here/bin/udp_radar_receiver" --input "$here/frame.rspb" \
        --window none --q15-input --normalize-output --warmup "$warmup" --repeat "$repeat" \
        --wisdom-in "$results/ps_128x128.wis" \
        --fftw-lib "$fftw" \
        --timings "$results/ps_$trial.timings.csv" --output "$results/ps_$trial.csv" \
        > "$results/ps_$trial.log" 2>&1
    printf 'Trial %s/%s: PL FFT + AXI4-Lite + PS transpose\n' "$trial" "$trials"
    last_log="$results/pl_$trial.log"
    run_cpu "$here/bin/fft128-receiver" --input "$here/frame.rspb" \
        --warmup "$warmup" --repeat "$repeat" --output "$results/pl_$trial" \
        > "$results/pl_$trial.log" 2>&1
    tail -n 2 "$results/pl_$trial.log"
    trial=$((trial + 1))
done
printf 'BOARD_BENCHMARK_COMPLETE: %s\n' "$results"
printf '%s\n' 'Same recorded frame, same board. No UDP, no DMA. Compare fft_pipeline stage only.'
