# Usage (on board, in ~/s3a0_bench_20261126): sh board_iter.sh VERSION RESULT_DIR
set -u
V=$1; R=$2; L=/opt/fft128/s2a_int16_20261126_adc01/libfftw3.so.3
FX="radarsimpy_128x128_sim_multi4_noise_adc16.rspb radarsimpy_128x128_sim_single_noise_adc16.rspb radarsimpy_128x128_sim_close_weak_noise_adc16.rspb radarsimpy_128x128_adc16.rspb"
mkdir $R || exit 1
./$V/cfar_integer_equiv_arm | tee $R/cfar_integer_equiv.txt
./$V/adc_window_exhaustive_arm | tee $R/adc_window_exhaustive.txt
for b in model ps; do for v in old $V old_b ${V}_b; do case $v in old*) X=./bench_old;; *) X=./$V/bench_s3a0_arm;; esac
  $X $b $L $R/${b}_$v 500 $FX > $R/${b}_$v.txt 2>&1; echo "exit=$?" >> $R/${b}_$v.txt
  echo "== $b $v $(grep -E 'STAGE (prepare|detect)' $R/${b}_$v.txt | awk '{print $2,$3}' | tr '\n' ' ') $(tail -1 $R/${b}_$v.txt)"; done
  cmp $R/${b}_old.dump $R/${b}_$V.dump && cmp $R/${b}_old.peaks.txt $R/${b}_$V.peaks.txt && cmp $R/${b}_old.dump $R/${b}_${V}_b.dump && echo S3A0_BOARD_${b}_${V}_BITEXACT; done
./$V/micro_s3a0_arm radarsimpy_128x128_sim_multi4_noise_adc16.rspb 300 > $R/micro.txt; grep -E "EXACT|detect_integer|sep_u64" $R/micro.txt
