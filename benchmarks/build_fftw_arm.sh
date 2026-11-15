#!/usr/bin/env bash
# Ubuntu host: build private ARMv7 hard-float FFTW double shared runtime.
# No sudo, rootfs updates or FPGA operations.
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
root=$(cd -- "$here/.." && pwd)
out=${FFT128_BENCH_OUT:-"$root/build/fft128_board_benchmark"}
archive=${FFT128_FFTW_ARCHIVE:-"$root/build/third_party/fftw-3.3.11.tar.gz"}
sha=5630c24cdeb33b131612f7eb4b1a9934234754f9f388ff8617458d0be6f239a1
cc=${FFT128_FFTW_CC:-arm-linux-gnueabihf-gcc}
for tool in "$cc" make tar sha256sum readelf; do
    command -v "$tool" >/dev/null 2>&1 || { printf 'Missing tool: %s\n' "$tool" >&2; exit 1; }
done
triple=$("$cc" -dumpmachine)
[[ "$triple" == arm*linux* ]] || { printf 'Not an ARM Linux compiler: %s\n' "$triple" >&2; exit 1; }
if [[ ! -f "$archive" ]]; then bash "$here/fetch_fftw.sh"; fi
printf '%s  %s\n' "$sha" "$archive" | sha256sum -c -
flags='-O3 -mcpu=cortex-a9 -mfpu=neon -mfloat-abi=hard -fPIC'
# A private local build avoids executable-bit, symlink and latency issues on HGFS.
work="$HOME/fft128_fftw_arm"
signature=$(printf '%s\n' "$sha" "$flags" "$cc" "$("$cc" --version)" 'shared,double,single-thread,slow-planner-timer' | sha256sum)
signature=${signature%% *}
prefix="$work/install-${signature:0:16}"
build="$work/build-${signature:0:16}"
src="$work/fftw-3.3.11"
mkdir -p "$work" "$build" "$out/lib"
if [[ ! -f "$prefix/.complete" ]]; then
    tar -xzf "$archive" -C "$work"
    build_triple=$(sh "$src/config.guess")
    printf 'FFTW_CONFIGURE: ARMv7 hard-float, double precision, single thread\n'
    if ! (cd "$build"; CC="$cc" CFLAGS="$flags" "$src/configure" \
        --build="$build_triple" --host="$triple" --prefix="$prefix" \
        --enable-shared --disable-static --disable-fortran --disable-doc \
        --disable-threads --disable-openmp --disable-mpi --with-slow-timer) \
        > "$build/configure.log" 2>&1; then
        tail -n 35 "$build/configure.log" >&2; exit 1
    fi
    printf 'FFTW_COMPILE: log=%s/make.log\n' "$build"
    if ! make -C "$build" -j "${FFT128_BUILD_JOBS:-2}" > "$build/make.log" 2>&1; then
        tail -n 35 "$build/make.log" >&2; exit 1
    fi
    if ! make -C "$build" install > "$build/install.log" 2>&1; then
        tail -n 35 "$build/install.log" >&2; exit 1
    fi
    test -s "$prefix/lib/libfftw3.so.3"
    touch "$prefix/.complete"
fi
cp -L "$prefix/lib/libfftw3.so.3" "$out/lib/libfftw3.so.3"
readelf -h -A -d "$out/lib/libfftw3.so.3" > "$out/fftw_abi.txt"
grep -q 'Machine:.*ARM' "$out/fftw_abi.txt"
grep -q 'hard-float ABI' "$out/fftw_abi.txt"
readelf -Ws "$out/lib/libfftw3.so.3" > "$out/fftw_symbols.txt"
for symbol in fftw_malloc fftw_free fftw_plan_many_dft fftw_execute fftw_destroy_plan \
    fftw_print_plan fftw_import_wisdom_from_filename fftw_export_wisdom_to_filename fftw_set_timelimit; do
    grep -Eq "[[:space:]]$symbol$" "$out/fftw_symbols.txt" || { printf 'Missing FFTW symbol: %s\n' "$symbol" >&2; exit 1; }
done
{
    printf 'SOURCE=https://www.fftw.org/fftw-3.3.11.tar.gz\nSOURCE_SHA256=%s\nCC=%s\nCFLAGS=%s\n' "$sha" "$cc" "$flags"
    "$cc" --version
    printf '%s\n' 'Double precision; no FFTW threads/OpenMP/MPI.' \
        'ARMv7 NEON has no double-precision SIMD; FFTW --enable-neon is not used.' \
        'Slow timer is used only for planning measurements; no privileged ARM PMU instructions.'
    sha256sum "$out/lib/libfftw3.so.3"
} > "$out/fftw_build_environment.txt"
printf 'FFTW_ARM_READY: %s/lib/libfftw3.so.3\n' "$out"
