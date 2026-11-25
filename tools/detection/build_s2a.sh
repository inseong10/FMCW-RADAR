#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
target=${1:-host}
case "$target" in
    host) cc=${S2A_CC:-gcc}; cxx=${S2A_CXX:-g++} ;;
    arm) cc=${S2A_CC:-arm-linux-gnueabihf-gcc}; cxx=${S2A_CXX:-arm-linux-gnueabihf-g++} ;;
    *) echo 'Usage: build_s2a.sh host|arm NEW_OUTPUT' >&2; exit 1 ;;
esac
out=${2:?Pass a new output directory}
test ! -e "$out" || { echo "Use a fresh output directory: $out" >&2; exit 1; }
if test "$target" = arm; then
    case $("$cxx" -dumpmachine) in arm*linux*gnueabihf*) ;; *) exit 1 ;; esac
fi
mkdir -p "$out"
{
    "$cc" --version
    "$cxx" --version
    printf 'target=%s C=-O2 -std=c11 CXX=-O2 -std=c++17 -Wall -Wextra -Werror -pthread -ldl\n' "$target"
    sha256sum "$root/src/PS/receiver/stream_receiver.cpp" \
        "$root/src/PS/receiver/stream_protocol.hpp" "$root/src/PS/receiver/stream_pipeline.hpp" \
        "$root/src/PS/receiver/stream_timestamp.hpp" \
        "$root/src/PS/receiver/cfar_ca.hpp" "$root/src/PS/fft128/native_core.c" \
        "$root/src/PS/fft128/native_core.h" "$root/src/PS/fft128/dma_frame/fft128_dma_frame_uapi.h"
} > "$out/build_environment.txt"
if ! "$cc" -O2 -std=c11 -Wall -Wextra -Werror -c "$root/src/PS/fft128/native_core.c" -o "$out/native_core.o" > "$out/build.log" 2>&1 ||
   ! "$cxx" -O2 -std=c++17 -Wall -Wextra -Werror -pthread \
        "$root/src/PS/receiver/stream_receiver.cpp" "$out/native_core.o" -ldl -lm \
        -o "$out/stream-receiver" >> "$out/build.log" 2>&1; then
    cat "$out/build.log" >&2
    exit 1
fi
sha256sum "$out/stream-receiver" > "$out/stream-receiver.sha256"
printf 'S2A_BUILD_PASS target=%s executable=%s/stream-receiver\n' "$target" "$out"
