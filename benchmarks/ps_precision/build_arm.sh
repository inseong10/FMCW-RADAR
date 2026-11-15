#!/usr/bin/env bash
# Ubuntu host; isolated PS01 outputs. No FPGA build or programming.
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
root=$(cd -- "$here/../.." && pwd)
out=${FFT128_PS_OUT:-"$root/build/fft128_ps_precision"}
cxx=${FFT128_CXX:-arm-linux-gnueabihf-g++}
python=${FFT128_PYTHON:-python3}
command -v "$cxx" >/dev/null
[[ $("$cxx" -dumpmachine) == arm*linux* ]] || { printf 'Need ARM Linux g++\n' >&2; exit 1; }
mkdir -p "$out"
"$python" "$here/prepare_reference.py" "$out"
for variant in double float_scalar float_neon; do
    FFT128_BENCH_OUT="$out/$variant" FFT128_FFTW_VARIANT="$variant" \
        bash "$root/benchmarks/build_fftw_arm.sh"
    flags=(-O3 -mcpu=cortex-a9 -mfpu=neon -mfloat-abi=hard -std=c++17 -Wall -Wextra)
    definitions=("-DFFT128_VARIANT=\"$variant\"")
    if [[ "$variant" != double ]]; then
        flags+=(-fno-tree-vectorize -fno-tree-slp-vectorize)
        definitions+=(-DFFT128_SINGLE=1)
    fi
    mkdir -p "$out/$variant/bin"
    "$cxx" "${flags[@]}" "${definitions[@]}" "$root/src/PS/receiver/udp_radar_receiver.cpp" \
        -static-libstdc++ -static-libgcc -ldl -o "$out/$variant/bin/receiver"
    {
        "$cxx" --version
        printf 'VARIANT=%s\nCXXFLAGS=%s\nDEFINITIONS=%s\n' "$variant" "${flags[*]}" "${definitions[*]}"
        printf 'source: '; sha256sum "$root/src/PS/receiver/udp_radar_receiver.cpp"
        readelf -h -A -l "$out/$variant/bin/receiver"
    } > "$out/$variant/build_environment.txt"
done
cp "$here/run_board.sh" "$out/run_board.sh"
(
    cd "$out"
    # No result directories are included: only these exact prepared artifacts.
    sha256sum frame.rspb reference.csv reference.json run_board.sh
    for variant in double float_scalar float_neon; do
        sha256sum "$variant/bin/receiver" "$variant"/lib/*.so.3 \
            "$variant/build_environment.txt" "$variant/fftw_build_environment.txt"
    done
) > "$out/artifacts.sha256"
printf 'PS_PRECISION_BUILD_PASS: %s\n' "$out"
printf '%s\n' 'Next: bash benchmarks/ps_precision/deploy.sh (no FPGA changes).'
