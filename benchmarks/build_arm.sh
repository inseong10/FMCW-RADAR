#!/usr/bin/env bash
# Ubuntu host: build the existing optimized C++ receiver and native PL receiver.
# Does not install into NFS or change the FPGA.
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
root=$(cd -- "$here/.." && pwd)
out=${FFT128_BENCH_OUT:-"$root/build/fft128_board_benchmark"}
cxx=()
is_arm_linux() {
    local triple
    triple=$("$@" -dumpmachine 2>/dev/null) || return 1
    [[ "$triple" == arm*linux* ]]
}
if [[ -n ${FFT128_CXX:-} ]]; then
    cxx=("$FFT128_CXX")
elif [[ -n ${CXX:-} ]]; then
    read -r -a candidate <<< "$CXX"
    if is_arm_linux "${candidate[@]}"; then cxx=("${candidate[@]}"); fi
fi
if ((${#cxx[@]}==0)); then
    for candidate in arm-linux-gnueabihf-g++ arm-xilinx-linux-gnueabi-g++ \
        /tools/Xilinx/Vitis/2022.1/gnu/aarch32/lin/*/bin/arm*linux*g++; do
        if command -v "$candidate" >/dev/null 2>&1 && is_arm_linux "$candidate"; then
            cxx=("$candidate"); break
        fi
    done
fi
if ((${#cxx[@]}==0)) || ! is_arm_linux "${cxx[@]}"; then
    printf '%s\n' 'ARM32 Linux C++ compiler not found. On Ubuntu: sudo apt install g++-arm-linux-gnueabihf make' >&2
    exit 1
fi
mkdir -p -- "$out"
read -r -a cxxflags <<< "${CXXFLAGS:-}"
read -r -a ldflags <<< "${LDFLAGS:-}"
printf 'CXX: %s\n' "${cxx[*]}"
bash "$here/build_fftw_arm.sh"
# Keep the target libc/loader ABI; avoid requiring a matching libstdc++ runtime.
# FFTW is dynamically loaded from the benchmark's private ARM libfftw3.so.3.
"${cxx[@]}" -O3 -mcpu=cortex-a9 -mfpu=neon -mfloat-abi=hard -std=c++17 -Wall -Wextra "${cxxflags[@]}" \
    "$root/src/PS/receiver/udp_radar_receiver.cpp" \
    -static-libstdc++ -static-libgcc "${ldflags[@]}" -ldl -o "$out/udp_radar_receiver"
CFLAGS="${CFLAGS:--O3 -mcpu=cortex-a9 -mfpu=neon -mfloat-abi=hard}" FFT128_OUT="$out" bash "$root/src/PS/fft128/build_native.sh"
{
    "${cxx[@]}" --version
    printf 'CXXFLAGS=%s\nCFLAGS=%s\n' "-O3 -mcpu=cortex-a9 -mfpu=neon -mfloat-abi=hard -std=c++17 ${CXXFLAGS:-}" "${CFLAGS:--O3 -mcpu=cortex-a9 -mfpu=neon -mfloat-abi=hard}"
    if command -v readelf >/dev/null 2>&1; then readelf -l "$out/udp_radar_receiver"; fi
} > "$out/build_environment.txt"
if command -v file >/dev/null 2>&1; then file "$out/udp_radar_receiver"; fi
printf 'BOARD_BENCH_BUILD_PASS: %s\n' "$out"
printf '%s\n' 'PS baseline: optimized udp_radar_receiver + private lib/libfftw3.so.3.' \
    'PL path: fft128-receiver --input frame.rspb --warmup 10 --repeat 100.' \
    'Stage files locally as the HGFS mounting user before sudo install into NFS.'
