#!/bin/sh
# S3a-2b iteration 2 (int32 butterfly). Same flags as build_s2a.sh default.
set -eu
cd "$(dirname "$0")"
o=out_new2; mkdir $o
gcc -O2 -std=c11 -Wall -Wextra -Werror -c new2/fft128/native_core.c -o $o/core_host.o
arm-linux-gnueabihf-gcc -O2 -std=c11 -Wall -Wextra -Werror -c new2/fft128/native_core.c -o $o/core_arm.o
g++ -O2 -std=c++17 -Wall -Wextra -Werror -pthread new2/receiver/tests/bench_s3a2.cpp $o/core_host.o -ldl -lm -o $o/bench_host
arm-linux-gnueabihf-g++ -O2 -std=c++17 -Wall -Wextra -Werror -pthread new2/receiver/tests/bench_s3a2.cpp $o/core_arm.o -ldl -lm -o $o/bench_arm 2>/dev/null
for t in micro_s3a2 butterfly_s3a2_equiv; do
  g++ -O2 -std=c++17 -Wall -Wextra -Werror -pthread micro_new2/receiver/tests/$t.cpp $o/core_host.o -ldl -lm -o $o/${t}_host
  arm-linux-gnueabihf-g++ -O2 -std=c++17 -Wall -Wextra -Werror -pthread micro_new2/receiver/tests/$t.cpp $o/core_arm.o -ldl -lm -o $o/${t}_arm 2>/dev/null
done
find new2 micro_new2 -type f | sort | xargs sha256sum > $o/source.sha256
sha256sum $o/*_host $o/*_arm > $o/binaries.sha256
./$o/butterfly_s3a2_equiv_host
./$o/bench_host $o/host_new2 10 > $o/host_new2.txt
cmp $o/host_new2.dump out/host_old.dump && echo S3A2B_HOST_NEW2_BITEXACT_VS_OLD
D=/nfsroot/home/petalinux/s3a2b_bench_20261126/new2; mkdir $D; cp $o/*_arm $D/; sha256sum $D/*
echo S3A2B_BUILD_NEW2_PASS
