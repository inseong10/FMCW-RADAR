#!/bin/sh
# Build only. No deployment, FPGA programming, packages or service changes.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
target=${1:-host}
case "$target" in
    host) compiler=${S1B_CXX:-g++} ;;
    arm) compiler=${S1B_CXX:-arm-linux-gnueabihf-g++} ;;
    *) echo 'Usage: build_s1b.sh host|arm [new-output-directory]' >&2; exit 1 ;;
esac
out=${2:-"$root/build/s1b_$target"}
test ! -e "$out" || { echo "Use a fresh output directory: $out" >&2; exit 1; }
triple=$("$compiler" -dumpmachine)
if test "$target" = arm; then
    case "$triple" in arm*linux*gnueabihf*) ;; *) echo "ARM hard-float Linux compiler required: $triple" >&2; exit 1 ;; esac
fi
mkdir -p "$out"
{
    "$compiler" --version
    printf 'target=%s triple=%s flags=-O2 -std=c++17 -Wall -Wextra -Werror\n' "$target" "$triple"
    sha256sum "$root/src/PS/receiver/udp_radar_receiver.cpp" "$root/src/PS/receiver/cfar_ca.hpp"
} > "$out/build_environment.txt"
"$compiler" -O2 -std=c++17 -Wall -Wextra -Werror \
    "$root/src/PS/receiver/udp_radar_receiver.cpp" -ldl -o "$out/receiver" \
    > "$out/build.log" 2>&1 || { cat "$out/build.log" >&2; exit 1; }
sha256sum "$out/receiver" > "$out/receiver.sha256"
printf 'S1B_BUILD_PASS target=%s executable=%s/receiver\n' "$target" "$out"
printf '%s\n' 'Dynamic FFTW3 and matching C++/glibc runtime are required on the target.'
