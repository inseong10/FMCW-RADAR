#!/usr/bin/env bash
# Ubuntu mounting user: stage out of owner-only HGFS before sudo install.
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
root=$(cd -- "$here/.." && pwd)
out=${FFT128_BENCH_OUT:-"$root/build/fft128_board_benchmark"}
stage="$HOME/fft128_bench_deploy"
target=/nfsroot/opt/fft128/benchmark
mkdir -p "$stage"
cp "$out/udp_radar_receiver" "$stage/udp_radar_receiver"
cp "$out/fft128-receiver" "$stage/fft128-receiver"
cp "$root/benchmarks/fixtures/radarsimpy_128x128.rspb" "$stage/frame.rspb"
cp "$here/run_board.sh" "$stage/run_board.sh"
cp "$here/profile_board.sh" "$stage/profile_board.sh"
cp "$out/build_environment.txt" "$stage/build_environment.txt"
cp "$out/lib/libfftw3.so.3" "$stage/libfftw3.so.3"
cp "$out/fftw_build_environment.txt" "$stage/fftw_build_environment.txt"
sudo install -D -m 0755 "$stage/udp_radar_receiver" "$target/bin/udp_radar_receiver"
sudo install -D -m 0755 "$stage/fft128-receiver" "$target/bin/fft128-receiver"
sudo install -D -m 0755 "$stage/run_board.sh" "$target/run_board.sh"
sudo install -D -m 0755 "$stage/profile_board.sh" "$target/profile_board.sh"
sudo install -D -m 0644 "$stage/frame.rspb" "$target/frame.rspb"
sudo install -D -m 0644 "$stage/build_environment.txt" "$target/build_environment.txt"
sudo install -D -m 0755 "$stage/libfftw3.so.3" "$target/lib/libfftw3.so.3"
sudo install -D -m 0644 "$stage/fftw_build_environment.txt" "$target/fftw_build_environment.txt"
for name in udp_radar_receiver fft128-receiver; do
    sudo cmp "$stage/$name" "$target/bin/$name"
done
sudo cmp "$stage/frame.rspb" "$target/frame.rspb"
sudo cmp "$stage/libfftw3.so.3" "$target/lib/libfftw3.so.3"
printf 'BENCHMARK_DEPLOY_PASS: %s\n' "$target"
printf '%s\n' 'Known-good /opt/fft128/fft128-receiver and FPGA firmware are preserved.'
