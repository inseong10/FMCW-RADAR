#!/bin/sh
# S3a-0 bench build (Ubuntu). Same flags as build_s2a.sh default (-O2, no NEON, no fast-math).
set -eu
cd "$(dirname "$0")"
for v in old new; do
  for t in host arm; do
    o=out_$t; mkdir -p $o
    if [ $t = host ]; then cc=gcc; cxx=g++; else cc=arm-linux-gnueabihf-gcc; cxx=arm-linux-gnueabihf-g++; fi
    $cc -O2 -std=c11 -Wall -Wextra -Werror -c $v/fft128/native_core.c -o $o/native_core_$v.o
    $cxx -O2 -std=c++17 -Wall -Wextra -Werror -pthread $v/receiver/tests/bench_s3a0.cpp $o/native_core_$v.o -ldl -lm -o $o/bench_$v
  done
done
g++ -O2 -std=c++17 -Wall -Wextra -Werror new/receiver/tests/adc_window_exhaustive.cpp -o out_host/adc_window_exhaustive
arm-linux-gnueabihf-g++ --version | head -1 > toolchain.txt; g++ --version | head -1 >> toolchain.txt
find old new -type f | sort | xargs sha256sum > source.sha256
sha256sum out_host/* out_arm/bench_* > binaries.sha256
echo S3A0_BENCH_BUILD_PASS
