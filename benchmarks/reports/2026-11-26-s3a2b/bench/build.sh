#!/bin/sh
# S3a-2b bench build (Ubuntu). Same flags as build_s2a.sh default (-O2, no NEON, no fast-math).
set -eu
cd "$(dirname "$0")"
mkdir out
for v in old new; do
  gcc -O2 -std=c11 -Wall -Wextra -Werror -c $v/fft128/native_core.c -o out/core_${v}_host.o
  arm-linux-gnueabihf-gcc -O2 -std=c11 -Wall -Wextra -Werror -c $v/fft128/native_core.c -o out/core_${v}_arm.o
  g++ -O2 -std=c++17 -Wall -Wextra -Werror -pthread $v/receiver/tests/bench_s3a2.cpp out/core_${v}_host.o -ldl -lm -o out/bench_${v}_host
  arm-linux-gnueabihf-g++ -O2 -std=c++17 -Wall -Wextra -Werror -pthread $v/receiver/tests/bench_s3a2.cpp out/core_${v}_arm.o -ldl -lm -o out/bench_${v}_arm
done
find old new -type f | sort | xargs sha256sum > out/source.sha256
sha256sum out/bench_* > out/binaries.sha256
for v in old new old new; do ./out/bench_${v}_host out/host_$v 20 > out/host_$v.txt 2>&1 || { cat out/host_$v.txt; exit 1; }; done
cmp out/host_old.dump out/host_new.dump && echo S3A2B_HOST_BITEXACT
sha256sum out/host_*.dump
D=/nfsroot/home/petalinux/s3a2b_bench_20261126; mkdir $D; cp out/bench_*_arm $D/; sha256sum $D/*
echo S3A2B_BUILD_PASS
