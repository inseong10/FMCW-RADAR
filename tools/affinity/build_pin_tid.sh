#!/bin/sh
# Build pin-tid for Ubuntu host (self-test) and ARM board; deploy to a NEW NFS path.
# Usage: sh tools/affinity/build_pin_tid.sh NEW_OUTPUT_DIR NEW_NFS_DIR
set -eu
out=${1:?Pass a new output directory}
nfs=${2:?Pass a new /nfsroot/opt/fft128/... directory}
test ! -e "$out" || { echo 'Use a fresh output directory' >&2; exit 1; }
test ! -e "$nfs" || { echo 'Use a fresh NFS directory' >&2; exit 1; }
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
mkdir -p "$out/host" "$out/arm"
flags='-std=c11 -O2 -Wall -Wextra -Werror'
gcc $flags -o "$out/host/pin-tid" "$here/pin_tid.c"
# Host self-test: pin a child to CPU0 then back to all online CPUs.
sleep 3 & child=$!
"$out/host/pin-tid" 1 "$child" | tee "$out/host/selftest.txt"
grep -q "tid=$child mask=1" "$out/host/selftest.txt"
"$out/host/pin-tid" -q "$child" >> "$out/host/selftest.txt"
kill "$child" 2>/dev/null || true
arm-linux-gnueabihf-gcc $flags -static -o "$out/arm/pin-tid" "$here/pin_tid.c"
case $(file -b "$out/arm/pin-tid") in *ARM*) ;; *) echo 'Not an ARM binary' >&2; exit 1 ;; esac
{
    arm-linux-gnueabihf-gcc --version | head -1
    file -b "$out/arm/pin-tid"
    printf 'flags=%s -static\n' "$flags"
} > "$out/arm/build_environment.txt"
(cd "$here" && sha256sum pin_tid.c build_pin_tid.sh) > "$out/source.sha256"
(cd "$out/arm" && sha256sum pin-tid) > "$out/arm/pin-tid.sha256"
mkdir -p "$nfs"
cp "$out/arm/pin-tid" "$out/arm/pin-tid.sha256" "$out/arm/build_environment.txt" "$out/source.sha256" "$nfs/"
(cd "$nfs" && sha256sum -c pin-tid.sha256)
cat "$out/source.sha256" "$out/arm/pin-tid.sha256"
echo PIN_TID_DEPLOY_READY
