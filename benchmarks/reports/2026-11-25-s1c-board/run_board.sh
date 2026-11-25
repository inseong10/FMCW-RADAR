#!/bin/sh
set -eu
cd -- "$(dirname -- "$0")"
pl=${1:?Pass the existing E14 receiver}
cfar=${2:?Pass the new S1c CFAR executable}
test -c /dev/fft128-dma-frame
test ! -e environment.txt || { echo "Use a fresh bundle" >&2; exit 1; }
sha256sum -c artifacts.sha256 > artifact_check.txt
{ uname -a; cat /proc/sys/kernel/random/boot_id; cat /proc/cpuinfo; } > environment.txt
sha256sum "$pl" "$cfar" > runtime.sha256
for f in "$(dirname -- "$pl")/fft128_e14_frame.bin" "$(dirname -- "$pl")/fft128_dma_frame.ko"; do
  if test -f "$f"; then sha256sum "$f"; fi
done > firmware_module.sha256
last_log=
trap 'ret=$?; if test "$ret" -ne 0 && test -n "$last_log"; then tail -n 30 "$last_log" >&2; fi' 0
last_log=single_none.pl.log
"$pl" --backend dma_frame --cpu0 --input single_none.rspb --output single_none.pl --warmup 10 --repeat 100 > "$last_log" 2>&1
grep FRAME_PASS "$last_log"
last_log=single_none.cfar.log
"$cfar" --cpu0 --input single_none.pl.csv --output single_none.detections.csv --timings single_none.cfar.timings.csv --warmup 10 --repeat 100 > "$last_log" 2>&1
grep S1C_CFAR_COMPLETE "$last_log"
last_log=single_hann.pl.log
"$pl" --backend dma_frame --cpu0 --input single_hann.rspb --output single_hann.pl --warmup 10 --repeat 100 > "$last_log" 2>&1
grep FRAME_PASS "$last_log"
last_log=single_hann.cfar.log
"$cfar" --cpu0 --input single_hann.pl.csv --output single_hann.detections.csv --timings single_hann.cfar.timings.csv --warmup 10 --repeat 100 > "$last_log" 2>&1
grep S1C_CFAR_COMPLETE "$last_log"
last_log=multi4_none.pl.log
"$pl" --backend dma_frame --cpu0 --input multi4_none.rspb --output multi4_none.pl --warmup 10 --repeat 100 > "$last_log" 2>&1
grep FRAME_PASS "$last_log"
last_log=multi4_none.cfar.log
"$cfar" --cpu0 --input multi4_none.pl.csv --output multi4_none.detections.csv --timings multi4_none.cfar.timings.csv --warmup 10 --repeat 100 > "$last_log" 2>&1
grep S1C_CFAR_COMPLETE "$last_log"
last_log=multi4_hann.pl.log
"$pl" --backend dma_frame --cpu0 --input multi4_hann.rspb --output multi4_hann.pl --warmup 10 --repeat 100 > "$last_log" 2>&1
grep FRAME_PASS "$last_log"
last_log=multi4_hann.cfar.log
"$cfar" --cpu0 --input multi4_hann.pl.csv --output multi4_hann.detections.csv --timings multi4_hann.cfar.timings.csv --warmup 10 --repeat 100 > "$last_log" 2>&1
grep S1C_CFAR_COMPLETE "$last_log"
last_log=close_weak_none.pl.log
"$pl" --backend dma_frame --cpu0 --input close_weak_none.rspb --output close_weak_none.pl --warmup 10 --repeat 100 > "$last_log" 2>&1
grep FRAME_PASS "$last_log"
last_log=close_weak_none.cfar.log
"$cfar" --cpu0 --input close_weak_none.pl.csv --output close_weak_none.detections.csv --timings close_weak_none.cfar.timings.csv --warmup 10 --repeat 100 > "$last_log" 2>&1
grep S1C_CFAR_COMPLETE "$last_log"
last_log=close_weak_hann.pl.log
"$pl" --backend dma_frame --cpu0 --input close_weak_hann.rspb --output close_weak_hann.pl --warmup 10 --repeat 100 > "$last_log" 2>&1
grep FRAME_PASS "$last_log"
last_log=close_weak_hann.cfar.log
"$cfar" --cpu0 --input close_weak_hann.pl.csv --output close_weak_hann.detections.csv --timings close_weak_hann.cfar.timings.csv --warmup 10 --repeat 100 > "$last_log" 2>&1
grep S1C_CFAR_COMPLETE "$last_log"
echo S1C_RUN_COMPLETE
