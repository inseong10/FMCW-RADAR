#!/bin/sh
# S3a-0 iteration 2 (separable integer CFAR). Same flags as build_s2a.sh default (-O2, no NEON, no fast-math).
set -eu
cd "$(dirname "$0")"
o=out2; mkdir $o
gcc -O2 -std=c11 -Wall -Wextra -Werror -c new2/fft128/native_core.c -o $o/native_core_host.o
arm-linux-gnueabihf-gcc -O2 -std=c11 -Wall -Wextra -Werror -c new2/fft128/native_core.c -o $o/native_core_arm.o
for t in bench_s3a0 micro_s3a0; do
  g++ -O2 -std=c++17 -Wall -Wextra -Werror -pthread new2/receiver/tests/$t.cpp $o/native_core_host.o -ldl -lm -o $o/${t}_host
  arm-linux-gnueabihf-g++ -O2 -std=c++17 -Wall -Wextra -Werror -pthread new2/receiver/tests/$t.cpp $o/native_core_arm.o -ldl -lm -o $o/${t}_arm 2>/dev/null
done
for t in adc_window_exhaustive cfar_integer_equiv; do
  g++ -O2 -std=c++17 -Wall -Wextra -Werror new2/receiver/tests/$t.cpp -o $o/${t}_host
  arm-linux-gnueabihf-g++ -O2 -std=c++17 -Wall -Wextra -Werror new2/receiver/tests/$t.cpp -o $o/${t}_arm 2>/dev/null
done
find new2 -type f | sort | xargs sha256sum > $o/source.sha256
sha256sum $o/*_host $o/*_arm > $o/binaries.sha256
F=../../benchmarks/fixtures/adc16
FX="$F/radarsimpy_128x128_sim_multi4_noise_adc16.rspb $F/radarsimpy_128x128_sim_single_noise_adc16.rspb $F/radarsimpy_128x128_sim_close_weak_noise_adc16.rspb $F/radarsimpy_128x128_adc16.rspb"
./$o/cfar_integer_equiv_host
./$o/adc_window_exhaustive_host | tail -2
./$o/bench_s3a0_host model - $o/host_model_new2 50 $FX > $o/host_model_new2.txt
cmp $o/host_model_new2.dump res_host/model_old.dump && cmp $o/host_model_new2.peaks.txt res_host/model_old.peaks.txt && echo S3A0_HOST_NEW2_BITEXACT_VS_OLD
D=/nfsroot/home/petalinux/s3a0_bench_20261126/new2; mkdir $D; cp $o/*_arm $D/; sha256sum $D/*
echo S3A0_BUILD2_PASS
