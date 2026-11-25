#!/bin/sh
# Build the standalone S1c CFAR checker. No FPGA/driver changes, no FFTW dependency.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
target=${1:-host}
case "$target" in
    host) compiler=${S1C_CXX:-g++} ;;
    arm) compiler=${S1C_CXX:-arm-linux-gnueabihf-g++} ;;
    *) echo 'Usage: build_s1c.sh host|arm [new-output-directory]' >&2; exit 1 ;;
esac
out=${2:-"$root/build/s1c_$target"}
test ! -e "$out" || { echo "Use a fresh output directory: $out" >&2; exit 1; }
triple=$("$compiler" -dumpmachine)
if test "$target" = arm; then
    case "$triple" in arm*linux*gnueabihf*) ;; *) echo "ARM hard-float compiler required: $triple" >&2; exit 1 ;; esac
fi
mkdir -p "$out"
{
    "$compiler" --version
    printf 'target=%s triple=%s flags=-O2 -std=c++17 -Wall -Wextra -Werror\n' "$target" "$triple"
    sha256sum "$root/tools/detection/cfar_spectrum.cpp" "$root/src/PS/receiver/cfar_ca.hpp"
} > "$out/build_environment.txt"
"$compiler" -O2 -std=c++17 -Wall -Wextra -Werror \
    "$root/tools/detection/cfar_spectrum.cpp" -o "$out/cfar-spectrum" \
    > "$out/build.log" 2>&1 || { cat "$out/build.log" >&2; exit 1; }
sha256sum "$out/cfar-spectrum" > "$out/cfar-spectrum.sha256"
printf 'S1C_BUILD_PASS target=%s executable=%s/cfar-spectrum\n' "$target" "$out"
