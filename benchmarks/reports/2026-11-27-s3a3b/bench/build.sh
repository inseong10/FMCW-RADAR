#!/bin/sh
# S3a-3b bench: old = S3a-2b header (2ba1c7f5, access opened), new = S3a-3b header. Same flags as S3a-2b.
set -eu
cd "$(dirname "$0")"
o=out; mkdir $o
for v in old new; do
  gcc -O2 -std=c11 -Wall -Wextra -Werror -c $v/fft128/native_core.c -o $o/core_${v}_host.o
  arm-linux-gnueabihf-gcc -O2 -std=c11 -Wall -Wextra -Werror -c $v/fft128/native_core.c -o $o/core_${v}_arm.o
  for t in bench_s3a2 micro_s3a3b; do
    g++ -O2 -std=c++17 -Wall -Wextra -Werror -pthread $v/receiver/tests/$t.cpp $o/core_${v}_host.o -ldl -lm -o $o/${t}_${v}_host
    arm-linux-gnueabihf-g++ -O2 -std=c++17 -Wall -Wextra -Werror -pthread $v/receiver/tests/$t.cpp $o/core_${v}_arm.o -ldl -lm -o $o/${t}_${v}_arm 2>/dev/null
  done
done
find old new -type f | sort | xargs sha256sum > $o/source.sha256
sha256sum $o/*_host $o/*_arm > $o/binaries.sha256
for v in old new; do ./$o/bench_s3a2_${v}_host $o/host_$v 5 > $o/host_$v.txt; done
sha256sum $o/host_old.dump $o/host_new.dump ../s3a2b_bench_20261126/out/host_old.dump
cmp $o/host_new.dump ../s3a2b_bench_20261126/out/host_old.dump && echo S3A3B_HOST_NEW_BITEXACT_VS_S3A2_OLD
cmp $o/host_old.dump ../s3a2b_bench_20261126/out/host_old.dump && echo S3A3B_HOST_OLD_BITEXACT_VS_S3A2_OLD
D=/nfsroot/home/petalinux/s3a3b_bench_20261127; mkdir $D; cp $o/*_arm $D/; (cd $D && sha256sum *)
echo S3A3B_BUILD_PASS
