#!/bin/sh
# Paired same-board PS01 double/NEON vs E14-frame. UDP/file IO excluded.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ps=${FFT128_PS01_DIR:-/opt/fft128/ps_precision}
out=${1:-"$here/results_e14_frame_$(date +%Y%m%d_%H%M%S)"}
test ! -e "$out" || { echo 'Use a fresh result directory' >&2; exit 1; }
test -c /dev/fft128-dma-frame
mkdir -p "$out"
last_log=
trap 'ret=$?; if test "$ret" -ne 0 && test -n "$last_log"; then tail -n 30 "$last_log" >&2; fi' 0
(cd "$here"; sha256sum -c artifacts.sha256) > "$out/dma_artifact_check.txt"
(cd "$ps"; sha256sum -c artifacts.sha256) > "$out/ps_artifact_check.txt"
cp "$here/artifacts.sha256" "$out/dma_artifacts.sha256"
cp "$ps/artifacts.sha256" "$out/ps_artifacts.sha256"
cp "$ps/reference.json" "$out/"
cp "$here/dma_config.json" "$here/fft128_e14_frame.json" "$here/pl_source.sha256" \
    "$here/host_source.sha256" "$here/module_source.sha256" "$here/module_build_environment.txt" "$out/"
cmp -s "$here/frame.rspb" "$ps/frame.rspb" || { echo 'PS/PL inputs differ' >&2; exit 1; }
{
    uname -a; cat /proc/sys/kernel/random/boot_id; cat /proc/cpuinfo
    printf 'E14-frame CPU0 warmup=10 repeats=100 trials=3, coherent HP0, 50MHz 1streaming_core 7dedicated_stages, full-frame ioctl, PL transpose/reorder, inplace_matrix\n'
    cat "$here/dma_config.json"
    sha256sum "$here/fft128_e14_frame.bin" "$here/fft128_dma_frame.ko" "$here/fft128-receiver" "$here/frame.rspb"
    for path in /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq; do
        if test -r "$path"; then printf '%s: ' "$path"; cat "$path"; else printf '%s: unavailable\n' "$path"; fi
    done
} > "$out/environment.txt"
cat /proc/interrupts > "$out/interrupts_before.txt"
for path in /proc/irq/*/smp_affinity_list; do
    if test -r "$path"; then printf '%s: ' "$path"; cat "$path"; else printf '%s: unavailable\n' "$path"; fi
done > "$out/irq_affinity.txt"
run_ps() {
    variant=$1; shift
    library=libfftw3f.so.3
    if test "$variant" = double; then library=libfftw3.so.3; fi
    "$ps/$variant/bin/receiver" --cpu0 --input "$here/frame.rspb" \
        --window none --q15-input --normalize-output --verify-spectrum "$ps/reference.csv" \
        --fftw-lib "$ps/$variant/lib/$library" "$@"
}
for variant in double float_neon; do
    mkdir -p "$out/$variant"
    cp "$ps/$variant/build_environment.txt" "$ps/$variant/fftw_build_environment.txt" "$out/$variant/"
    last_log="$out/$variant/preflight.log"
    run_ps "$variant" --measure-plan --plan-time-limit 10 --wisdom-out "$out/$variant/plan.wis" \
        --warmup 0 --repeat 1 > "$last_log" 2>&1
    if test "$variant" = float_neon; then
        sed -n '/^Range plan/,/^FFT:/p' "$last_log" | grep -qi neon || { echo 'NEON plan absent' >&2; exit 1; }
    fi
done
trial=1
while test "$trial" -le 3; do
    case $trial in
        1) order='double float_neon pl';;
        2) order='float_neon pl double';;
        3) order='pl double float_neon';;
    esac
    printf 'trial=%s order=%s\n' "$trial" "$order" >> "$out/order.txt"
    for variant in $order; do
        printf 'E14-frame trial %s/3: %s\n' "$trial" "$variant"
        mkdir -p "$out/$variant"
        prefix="$out/$variant/trial_$trial"; last_log="$prefix.log"
        if test "$variant" = pl; then
            "$here/fft128-receiver" --cpu0 --input "$here/frame.rspb" --warmup 10 --repeat 100 \
                --output "$prefix" > "$last_log" 2>&1
            grep -E 'PIPELINE_TIMING|FRAME_PASS' "$last_log"
        else
            run_ps "$variant" --wisdom-in "$out/$variant/plan.wis" --warmup 10 --repeat 100 \
                --timings "$prefix.timings.csv" --output "$prefix.csv" > "$last_log" 2>&1
            grep PS_VERIFY_PASS "$last_log"
        fi
    done
    trial=$((trial+1))
done
cat /proc/interrupts > "$out/interrupts_after.txt"
printf 'E14_FRAME_BENCHMARK_COMPLETE: %s\n' "$out"
printf 'Compare fft_pipeline wall times; per-repeat validation excluded. No UDP.\n'
