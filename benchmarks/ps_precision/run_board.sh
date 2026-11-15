#!/bin/sh
# PS01 only. No /dev/mem, FPGA programming or Python on the board.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
results=${1:-"$here/results_$(date +%Y%m%d_%H%M%S)"}
repeat=${FFT128_REPEAT:-100}
warmup=${FFT128_WARMUP:-10}
trials=${FFT128_TRIALS:-3}
for value in "$repeat" "$trials"; do
    case "$value" in ''|*[!0-9]*|0) printf 'Invalid positive repeat/trials\n' >&2; exit 1;; esac
    test "$value" -gt 0 || exit 1
done
case "$warmup" in ''|*[!0-9]*) printf 'Invalid warmup\n' >&2; exit 1;; esac
test "$repeat" -le 1000000 && test "$warmup" -le 100000 && test "$trials" -le 1000 || exit 1
test ! -e "$results" || { printf 'Use a fresh result directory: %s\n' "$results" >&2; exit 1; }
mkdir -p "$results"
last_log=
trap 's=$?; if test "$s" -ne 0; then printf "PS_PRECISION_STOPPED: status=%s\n" "$s" >&2; if test -n "$last_log"; then tail -n 25 "$last_log" >&2; fi; fi' 0
(cd "$here"; sha256sum -c artifacts.sha256) > "$results/artifact_check.txt"
cp "$here/artifacts.sha256" "$here/reference.json" "$results/"
{
    uname -a
    cat /proc/cpuinfo
    printf 'repeat=%s warmup=%s trials=%s\nCPU0 required, single thread; PS only, no FPGA access\n' "$repeat" "$warmup" "$trials"
    for path in /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq; do
        if test -r "$path"; then printf '%s: ' "$path"; cat "$path"; fi
    done
} > "$results/environment.txt"
run_variant() {
    variant=$1; shift
    library=libfftw3f.so.3
    if test "$variant" = double; then library=libfftw3.so.3; fi
    "$here/$variant/bin/receiver" --cpu0 --input "$here/frame.rspb" \
        --window none --q15-input --normalize-output --verify-spectrum "$here/reference.csv" \
        --fftw-lib "$here/$variant/lib/$library" "$@"
}
for variant in double float_scalar float_neon; do
    printf 'PS01 preflight: %s, target wisdom + numerical verification\n' "$variant"
    mkdir -p "$results/$variant"
    cp "$here/$variant/build_environment.txt" "$here/$variant/fftw_build_environment.txt" "$results/$variant/"
    last_log="$results/$variant/preflight.log"
    run_variant "$variant" --measure-plan --plan-time-limit 10 \
        --wisdom-out "$results/$variant/plan.wis" --warmup 0 --repeat 1 > "$last_log" 2>&1
    if test "$variant" = float_neon; then
        sed -n '/^Range plan/,/^FFT:/p' "$last_log" | grep -qi neon || {
            printf 'NEON codelet not selected in FFTW plans; stop before comparison\n' >&2; exit 1;
        }
    fi
done
trial=1
while test "$trial" -le "$trials"; do
    # Rotate variant order to reduce a fixed ordering/temperature bias.
    case $(( (trial - 1) % 3 )) in
        0) order='double float_scalar float_neon';;
        1) order='float_scalar float_neon double';;
        2) order='float_neon double float_scalar';;
    esac
    printf 'trial=%s order=%s\n' "$trial" "$order" >> "$results/order.txt"
    for variant in $order; do
        printf 'PS01 trial %s/%s: %s\n' "$trial" "$trials" "$variant"
        prefix="$results/$variant/trial_$trial"
        last_log="$prefix.log"
        run_variant "$variant" --wisdom-in "$results/$variant/plan.wis" \
            --warmup "$warmup" --repeat "$repeat" --timings "$prefix.timings.csv" \
            --output "$prefix.csv" > "$last_log" 2>&1
        grep -E 'PS_VERIFY_PASS|FFT only:' "$last_log"
    done
    trial=$((trial + 1))
done
printf 'PS_PRECISION_COMPLETE: %s\n' "$results"
printf '%s\n' 'Analyze fft_pipeline, not FFT only. Per-repeat numerical checks are outside timing.'
