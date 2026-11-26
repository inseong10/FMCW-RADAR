#!/bin/sh
# S2a-int16: default double/O2, two CPUs, fixed queue4/partial4.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
backend=${1:?Usage: run_board.sh ps|pl RUN_ID FRAMES NEW_OUTPUT diag|measure}
run_id=${2:?Pass a new run ID}
frames=${3:?Pass expected frame count}
out=${4:?Pass a new output directory}
mode=${5:?Pass diag or measure}
case "$backend" in ps|pl) ;; *) exit 1 ;; esac
case "$mode" in diag) test "$frames" = 20 ;; measure) ;; *) exit 1 ;; esac
test ! -e "$out" || { echo 'Use a fresh output directory' >&2; exit 1; }
online=$(cat /sys/devices/system/cpu/online)
allowed=$(sed -n 's/^Cpus_allowed_list:[[:space:]]*//p' /proc/self/status)
test "$online" = 0-1 && test "$allowed" = 0-1 || {
    echo "Two online/allowed CPUs required: $online / $allowed" >&2; exit 1;
}
if test "$backend" = pl; then test -c /dev/fft128-dma-frame; fi
mkdir -p "$out"
(cd "$here"; sha256sum -c artifacts.sha256) > "$out/artifact_check.txt"
cp "$here/artifacts.sha256" "$here/source.sha256" "$here/build_environment.txt" "$out/"
{
    uname -a
    printf 'experiment=S2a-int16\ncpu_online=%s\nallowed_cpus=%s\nmode=%s\n' "$online" "$allowed" "$mode"
    cat /proc/cpuinfo
    sha256sum "$here/stream-receiver" "$here/libfftw3.so.3"
    if test "$backend" = pl; then
        ls -l /dev/fft128-dma-frame
        ls -d /sys/module/fft128*
    fi
} > "$out/runtime.txt"
clock_context() {
    printf 'boot_id='; cat /proc/sys/kernel/random/boot_id
    for addr in 0xF8000100 0xF8000104 0xF8000108 0xF800010C 0xF8000120; do
        printf '%s: ' "$addr"; devmem "$addr" 32
    done
    find /sys/firmware/devicetree/base -name ps-clk-frequency \
        -exec sh -c 'printf "%s\n" "$1"; od -b "$1"' sh {} \;
    find /sys/firmware/devicetree/base -name clock-frequency \
        -exec sh -c 'printf "%s\n" "$1"; od -b "$1"' sh {} \;
}
clock_context > "$out/clock_before.txt"
cat /proc/interrupts > "$out/interrupts_before.txt"
set -- --backend "$backend" --input-format adc16 --window hann --warmup 10 \
    --queue 4 --partial 4 --start-ms 120000 --idle-ms 2000 \
    --run-id "$run_id" --frames "$frames" --out "$out/trace"
if test "$backend" = ps; then set -- "$@" --fftw-lib "$here/libfftw3.so.3"; fi
if test "$mode" = diag; then set -- "$@" --diagnose-first-packet --diagnostic-spectrum; fi
set +e
"$here/stream-receiver" "$@"
status=$?
set -e
printf '%s\n' "$status" > "$out/receiver_exit.txt"
clock_context > "$out/clock_after.txt"
cat /proc/interrupts > "$out/interrupts_after.txt"
printf 'ADC16_RECORDED backend=%s exit=%s out=%s\n' "$backend" "$status" "$out"
exit "$status"
