#!/bin/sh
# Ubuntu host smoke + ARM build + a separate NFS bundle; keep all old binaries.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
label=${1:-$(date +%Y%m%d_%H%M%S)}
case "$label" in ''|*[!A-Za-z0-9_-]*) echo 'Use an alphanumeric/underscore/hyphen label' >&2; exit 1 ;; esac
out="$root/build/s2a_int16_$label"
dest="/nfsroot/opt/fft128/s2a_int16_$label"
board="/opt/fft128/s2a_int16_$label"
lib=/nfsroot/opt/fft128/s1b_20261125_192718/libfftw3.so.3
test ! -e "$out" && test ! -e "$dest" || { echo 'Use a new label' >&2; exit 1; }
expected=182f6f5317bf1480aeee92d9a93958c5c5cc24fdccf36217d3ce253b01cb3c6b
actual=$(sha256sum "$lib"); actual=${actual%% *}
test "$actual" = "$expected" || { echo 'Existing ARM double FFTW SHA differs' >&2; exit 1; }
mkdir -p "$out"
log="$out/prepare.log"
printf 'ADC16_PREPARE_START\nLOG: %s\n' "$log"
trap 'ret=$?; if test "$ret" -ne 0; then tail -n 18 "$log" >&2; fi' 0
(
    S2A_PRECISION=double S2A_TUNED=0 sh "$root/tools/detection/build_s2a.sh" host "$out/host"
    python3 "$root/tools/detection/smoke_s2a.py" --binary "$out/host/stream-receiver" --out "$out/float_regression"
    python3 "$root/tools/detection/smoke_adc16.py" --binary "$out/host/stream-receiver" --out "$out/adc_smoke"
    S2A_PRECISION=double S2A_TUNED=0 sh "$root/tools/detection/build_s2a.sh" arm "$out/arm"
    mkdir "$out/bundle"
    cp "$out/arm/stream-receiver" "$out/arm/build_environment.txt" "$out/bundle/"
    cp "$lib" "$out/bundle/libfftw3.so.3"
    cp "$root/tools/detection/run_adc16_board.sh" "$out/bundle/run_board.sh"
    (cd "$root"; sha256sum src/PS/receiver/stream_receiver.cpp \
        src/PS/receiver/stream_pipeline.hpp src/PS/receiver/stream_protocol.hpp \
        src/PS/receiver/stream_adc16.hpp src/PS/receiver/stream_timestamp.hpp \
        src/PS/receiver/cfar_ca.hpp src/PS/fft128/native_core.c src/PS/fft128/native_core.h \
        src/PS/fft128/dma_frame/fft128_dma_frame_uapi.h tools/detection/build_s2a.sh \
        tools/detection/prepare_adc16.sh tools/detection/run_adc16_board.sh \
        tools/detection/adc16_reference.py tools/detection/check_adc16_stream.py \
        tools/detection/smoke_adc16.py tools/detection/smoke_s2a.py tools/detection/analyze_stream.py \
        tools/sender/replay_stream.py tools/sender/adc16_record.py) > "$out/bundle/source.sha256"
    (cd "$out/bundle"; sha256sum stream-receiver libfftw3.so.3 build_environment.txt \
        source.sha256 run_board.sh > artifacts.sha256)
) > "$log" 2>&1
sudo -v
sudo mkdir "$dest"
sudo cp "$out/bundle/stream-receiver" "$out/bundle/libfftw3.so.3" \
    "$out/bundle/build_environment.txt" "$out/bundle/source.sha256" \
    "$out/bundle/run_board.sh" "$out/bundle/artifacts.sha256" "$dest/"
sudo sh -c 'cd "$1" && sha256sum -c artifacts.sha256' sh "$dest" >> "$log" 2>&1
printf 'ADC16_DEPLOY_READY: %s\nHost float/ADC smoke and ARM build passed; board checks pending.\n' "$board"
