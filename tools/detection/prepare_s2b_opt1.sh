#!/bin/sh
# Build a separate float/NEON candidate, host smoke, reuse verified ARM FFTW.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
label=${1:-$(date +%Y%m%d_%H%M%S)}
case "$label" in ''|*[!A-Za-z0-9_-]*) echo 'Use an alphanumeric/underscore/hyphen label' >&2; exit 1 ;; esac
out="$root/build/s2b_opt1_$label"
dest="/nfsroot/opt/fft128/s2b_opt1_$label"
board="/opt/fft128/s2b_opt1_$label"
lib=/nfsroot/opt/fft128/ps_precision/float_neon/lib/libfftw3f.so.3
test ! -e "$out" && test ! -e "$dest" || { echo 'Use a new label/output path' >&2; exit 1; }
test -f "$lib" || { echo "Missing existing ARM NEON FFTW: $lib" >&2; exit 1; }
expected=9c06dfa6f7e6f686b5eabda0845b75d38c5f05b852234364edfd84c423315653
actual=$(sha256sum "$lib"); actual=${actual%% *}
test "$actual" = "$expected" || { echo 'ARM FFTW differs from verified PS01 NEON library' >&2; exit 1; }
mkdir -p "$out"
log="$out/prepare.log"
printf 'S2B_OPT1_PREPARE_START\nLOG: %s\n' "$log"
trap 'ret=$?; if test "$ret" -ne 0; then tail -n 18 "$log" >&2; fi' 0
(
    S2A_PRECISION=double S2A_TUNED=1 sh "$root/tools/detection/build_s2a.sh" host "$out/host"
    python3 "$root/tools/detection/smoke_s2a.py" --binary "$out/host/stream-receiver" --out "$out/host_smoke"
    S2A_PRECISION=float S2A_TUNED=1 sh "$root/tools/detection/build_s2a.sh" arm "$out/arm"
    mkdir "$out/bundle"
    cp "$out/arm/stream-receiver" "$out/arm/build_environment.txt" "$out/bundle/"
    cp "$lib" "$out/bundle/libfftw3f.so.3"
    cp "$root/tools/detection/run_s2b_opt1.sh" "$out/bundle/run_board.sh"
    (cd "$root"; sha256sum src/PS/receiver/stream_receiver.cpp \
        src/PS/receiver/stream_pipeline.hpp src/PS/receiver/stream_protocol.hpp \
        src/PS/receiver/stream_timestamp.hpp src/PS/receiver/cfar_ca.hpp \
        src/PS/fft128/native_core.c src/PS/fft128/native_core.h \
        src/PS/fft128/dma_frame/fft128_dma_frame_uapi.h \
        tools/detection/build_s2a.sh tools/detection/run_s2b_opt1.sh \
        tools/detection/prepare_s2b_opt1.sh) > "$out/bundle/source.sha256"
    (cd "$out/bundle"; sha256sum stream-receiver libfftw3f.so.3 \
        build_environment.txt source.sha256 run_board.sh > artifacts.sha256)
) > "$log" 2>&1
# Prompt for credentials visibly; keep build output in the log.
sudo -v
sudo mkdir "$dest"
sudo cp "$out/bundle/stream-receiver" "$out/bundle/libfftw3f.so.3" \
    "$out/bundle/build_environment.txt" "$out/bundle/source.sha256" \
    "$out/bundle/run_board.sh" "$out/bundle/artifacts.sha256" "$dest/"
sudo sh -c 'cd "$1" && sha256sum -c artifacts.sha256' sh "$dest" >> "$log" 2>&1
printf 'S2B_OPT1_DEPLOY_READY: %s\nHost smoke/build passed; board NEON/correctness/performance pending.\n' "$board"
