#!/bin/sh
# Run from an opt1 bundle on Zybo; preserve exit status and clock/identity context.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
backend=${1:?Usage: run_board.sh ps|pl RUN_ID FRAMES NEW_OUTPUT}
run_id=${2:?Pass a new run ID}
frames=${3:?Pass the expected frame count}
out=${4:?Pass a new output directory}
case "$backend" in ps|pl) ;; *) echo 'backend must be ps or pl' >&2; exit 1 ;; esac
test ! -e "$out" || { echo 'Use a fresh output directory' >&2; exit 1; }
online=$(cat /sys/devices/system/cpu/online)
allowed=$(sed -n 's/^Cpus_allowed_list:[[:space:]]*//p' /proc/self/status)
test "$online" = 0-1 && test "$allowed" = 0-1 || {
    echo "Two online/allowed CPUs required: online=$online allowed=$allowed" >&2; exit 1;
}
if test "$backend" = pl; then test -c /dev/fft128-dma-frame; fi
mkdir -p "$out"
(cd "$here"; sha256sum -c artifacts.sha256) > "$out/artifact_check.txt"
cp "$here/artifacts.sha256" "$here/source.sha256" "$here/build_environment.txt" "$out/"
{
    uname -a
    printf 'cpu_online=%s\nallowed_cpus=%s\n' "$online" "$allowed"
    cat /proc/cpuinfo
    sha256sum "$here/stream-receiver" "$here/libfftw3f.so.3"
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
set -- --backend "$backend" --window hann --warmup 10 \
    --start-ms 120000 --idle-ms 2000 --run-id "$run_id" --frames "$frames" \
    --out "$out/trace"
if test "$backend" = ps; then
    set -- "$@" --fftw-lib "$here/libfftw3f.so.3" --measure-plan --require-neon
fi
set +e
"$here/stream-receiver" "$@"
status=$?
set -e
printf '%s\n' "$status" > "$out/receiver_exit.txt"
clock_context > "$out/clock_after.txt"
cat /proc/interrupts > "$out/interrupts_after.txt"
printf 'S2B_OPT1_RECORDED backend=%s receiver_exit=%s out=%s\n' "$backend" "$status" "$out"
exit "$status"
