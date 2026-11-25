#!/bin/sh
set -eu
cd -- "$(dirname -- "$0")"
receiver=${1:?Pass the S1b receiver executable}
library=${2:-libfftw3.so.3}
test ! -e environment.txt || { echo "Use a fresh bundle" >&2; exit 1; }
sha256sum -c artifacts.sha256 > artifact_check.txt
{ uname -a; cat /proc/cpuinfo; } > environment.txt
sha256sum "$receiver" > receiver.sha256
if test -f "$library"; then sha256sum "$library" > fftw.sha256; fi
for f in /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq; do
  if test -r "$f"; then printf "%s: " "$f"; cat "$f"; fi
done >> environment.txt
"$receiver" --cpu0 --fftw-lib "$library" --input radarsimpy_128x128_sim_single_noise.rspb --window none --cfar ca --warmup 10 --repeat 100 --output single_none.spectrum.csv --detections single_none.detections.csv --timings single_none.timings.csv > single_none.log 2>&1
"$receiver" --cpu0 --fftw-lib "$library" --input radarsimpy_128x128_sim_single_noise.rspb --window hann --cfar ca --warmup 10 --repeat 100 --output single_hann.spectrum.csv --detections single_hann.detections.csv --timings single_hann.timings.csv > single_hann.log 2>&1
"$receiver" --cpu0 --fftw-lib "$library" --input radarsimpy_128x128_sim_multi4_noise.rspb --window none --cfar ca --warmup 10 --repeat 100 --output multi4_none.spectrum.csv --detections multi4_none.detections.csv --timings multi4_none.timings.csv > multi4_none.log 2>&1
"$receiver" --cpu0 --fftw-lib "$library" --input radarsimpy_128x128_sim_multi4_noise.rspb --window hann --cfar ca --warmup 10 --repeat 100 --output multi4_hann.spectrum.csv --detections multi4_hann.detections.csv --timings multi4_hann.timings.csv > multi4_hann.log 2>&1
"$receiver" --cpu0 --fftw-lib "$library" --input radarsimpy_128x128_sim_close_weak_noise.rspb --window none --cfar ca --warmup 10 --repeat 100 --output close_weak_none.spectrum.csv --detections close_weak_none.detections.csv --timings close_weak_none.timings.csv > close_weak_none.log 2>&1
"$receiver" --cpu0 --fftw-lib "$library" --input radarsimpy_128x128_sim_close_weak_noise.rspb --window hann --cfar ca --warmup 10 --repeat 100 --output close_weak_hann.spectrum.csv --detections close_weak_hann.detections.csv --timings close_weak_hann.timings.csv > close_weak_hann.log 2>&1
echo S1B_RUN_COMPLETE
