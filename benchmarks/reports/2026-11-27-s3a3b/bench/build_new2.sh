#!/bin/sh
# S3a-3b iteration 2: NEON combine rows (fpu=neon pragma on the kernels only). Same flags as S3a-2b.
set -eu
cd "$(dirname "$0")"
o=out_new2; mkdir $o
gcc -O2 -std=c11 -Wall -Wextra -Werror -c new2/fft128/native_core.c -o $o/core_host.o
arm-linux-gnueabihf-gcc -O2 -std=c11 -Wall -Wextra -Werror -c new2/fft128/native_core.c -o $o/core_arm.o
for t in bench_s3a2 micro_s3a3b butterfly_s3a3b_neon_equiv; do
  g++ -O2 -std=c++17 -Wall -Wextra -Werror -pthread new2/receiver/tests/$t.cpp $o/core_host.o -ldl -lm -o $o/${t}_host
  arm-linux-gnueabihf-g++ -O2 -std=c++17 -Wall -Wextra -Werror -pthread new2/receiver/tests/$t.cpp $o/core_arm.o -ldl -lm -o $o/${t}_arm
done
find new2 -type f | sort | xargs sha256sum > $o/source.sha256
sha256sum $o/*_host $o/*_arm > $o/binaries.sha256
arm-linux-gnueabihf-objdump -d $o/bench_s3a2_arm | grep -c "vmull.s16" > $o/arm_vmull_count.txt
./$o/bench_s3a2_host $o/host_new2 3 > $o/host_new2.txt
cmp $o/host_new2.dump ../s3a2b_bench_20261126/out/host_old.dump && echo S3A3B_HOST_NEW2_BITEXACT_VS_S3A2_OLD
D=/nfsroot/home/petalinux/s3a3b_bench_20261127/new2; mkdir $D; cp $o/*_arm $D/; (cd $D && sha256sum *)
echo S3A3B_BUILD_NEW2_PASS
