#!/bin/sh
set -eu
cd "$(dirname "$0")"
F=../../benchmarks/fixtures/adc16
FX="$F/radarsimpy_128x128_sim_multi4_noise_adc16.rspb $F/radarsimpy_128x128_sim_single_noise_adc16.rspb $F/radarsimpy_128x128_sim_close_weak_noise_adc16.rspb $F/radarsimpy_128x128_adc16.rspb"
mkdir -p res_host
./out_host/adc_window_exhaustive | tee res_host/adc_window_exhaustive.txt
for v in old new; do ./out_host/bench_$v model - res_host/model_$v 200 $FX | tee res_host/model_$v.txt; done
cmp res_host/model_old.dump res_host/model_new.dump && cmp res_host/model_old.peaks.txt res_host/model_new.peaks.txt && echo S3A0_HOST_MODEL_BITEXACT
sha256sum res_host/*.dump res_host/*.peaks.txt
