#!/bin/sh
# S3a-3b iteration 3: NEON combine rows + NEON prepare (split shapes) (fpu=neon pragma on the kernels only). Same flags as S3a-2b.
set -eu
cd "$(dirname "$0")"
o=out_new3; mkdir $o
gcc -O2 -std=c11 -Wall -Wextra -Werror -c new3/fft128/native_core.c -o $o/core_host.o
arm-linux-gnueabihf-gcc -O2 -std=c11 -Wall -Wextra -Werror -c new3/fft128/native_core.c -o $o/core_arm.o
for t in bench_s3a2 micro_s3a3b butterfly_s3a3b_neon_equiv; do
  g++ -O2 -std=c++17 -Wall -Wextra -Werror -pthread new3/receiver/tests/$t.cpp $o/core_host.o -ldl -lm -o $o/${t}_host
  arm-linux-gnueabihf-g++ -O2 -std=c++17 -Wall -Wextra -Werror -pthread new3/receiver/tests/$t.cpp $o/core_arm.o -ldl -lm -o $o/${t}_arm
done
# window equiv calls NEON intrinsics from main, so only this test is built with -mfpu=neon
g++ -O2 -std=c++17 -Wall -Wextra -Werror -pthread new3/receiver/tests/window_s3a3b_neon_equiv.cpp $o/core_host.o -ldl -lm -o $o/window_s3a3b_neon_equiv_host
arm-linux-gnueabihf-g++ -O2 -mfpu=neon -std=c++17 -Wall -Wextra -Werror -pthread new3/receiver/tests/window_s3a3b_neon_equiv.cpp $o/core_arm.o -ldl -lm -o $o/window_s3a3b_neon_equiv_arm
find new3 -type f | sort | xargs sha256sum > $o/source.sha256
sha256sum $o/*_host $o/*_arm > $o/binaries.sha256
arm-linux-gnueabihf-objdump -d $o/bench_s3a2_arm | grep -cE "vmull.(s16|u32)" > $o/arm_vmull_count.txt
./$o/bench_s3a2_host $o/host_new3 3 > $o/host_new3.txt
cmp $o/host_new3.dump ../s3a2b_bench_20261126/out/host_old.dump && echo S3A3B_HOST_NEW3_BITEXACT_VS_S3A2_OLD
D=/nfsroot/home/petalinux/s3a3b_bench_20261127/new3; mkdir $D; cp $o/*_arm $D/; (cd $D && sha256sum *)
echo S3A3B_BUILD_NEW3_PASS
