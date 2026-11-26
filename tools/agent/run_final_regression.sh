#!/bin/sh
# S3a-final: 10k regression of the final source on all four sizes, no sudo (pinned NOPASSWD wrapper only).
# Runs from the Windows checkout (Git Bash). Per run: AC power check -> agent_run4.sh -> independent check
# (--network-loss-ok) -> stage stats. A run that is invalid is kept as recorded; rerun it with a new ID.
# stdin of every ssh/powershell call is detached: the first version (92441) let ssh read the run list,
# so only run 1 executed.
# Usage: sh tools/agent/run_final_regression.sh LABEL_PREFIX FIRST_RUN_ID [ONLY_INDEX]
set -u
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
prefix=${1:?label prefix used with prepare_final.sh}
first=${2:?first run id}
only=${3:-}
K=$HOME/.ssh/fmcw_agent
F='post-quantum|store now|openssh.com/pq'
UBU() { timeout "${2:-600}" ssh -n -i "$K" -o BatchMode=yes user@192.168.25.129 "$1" 2>&1 | grep -vE "$F"; }
P=/home/user/fmcw_share/FMCW-FFT-test
A=benchmarks/fixtures/adc16; S=benchmarks/fixtures/s3a
# index backend shape record period
runs="1 pl 128x128 $A/radarsimpy_128x128_sim_multi4_noise_adc16.rspb 12.8
2 ps 128x128 $A/radarsimpy_128x128_sim_multi4_noise_adc16.rspb 12.8
3 pl 256x128 $S/radarsimpy_256x128_sim_multi4_noise_adc16.rspb 25.6
4 pl 128x256 $S/radarsimpy_128x256_sim_multi4_noise_adc16.rspb 12.8
5 pl 256x256 $S/radarsimpy_256x256_sim_multi4_noise_adc16.rspb 25.6"
summary="$P/build/s3a_final_${prefix}_summary.txt"
echo "$runs" | while read -r idx be shape record period; do
    test -z "$only" || test "$only" = "$idx" || continue
    id=$((first+idx-1)); m=${shape%x*}; n=${shape#*x}
    bundle="s2a_int16_${prefix}_m${m}n${n}"; name="final_${be}_10k_${id}"; tag="final_${be}_${shape}_${id}"
    ac=$(powershell.exe -NoProfile -Command "(Get-CimInstance Win32_Battery).BatteryStatus" < /dev/null | tr -d '\r')
    echo "=== run $id $be $shape period=$period AC=$ac"
    if test "$ac" != 2; then echo "SKIP_NOT_ON_AC run=$id (BatteryStatus $ac)"; continue; fi
    timeout 1700 sh "$here/agent_run4.sh" "$id" "$name" nfs "$tag" "$be" "$bundle" 10000 "$record" "$period" < /dev/null 2>&1 |
        grep -E "S2A_SENT|PACING|REANCHOR|RECORDED|AGENT_RUN_DONE|invalid=|ABORT|NOT_DONE|rror"
    UBU "cd $P && B=/nfsroot/opt/fft128/$bundle && C=build/s3a_final_check_$id.json && T=build/s3a_final_stats_$id.json &&
        test ! -e \$C && python3 tools/detection/check_adc16_stream.py \$B/$name --sender build/s3a_sender_$tag.json --record $record --network-loss-ok > \$C 2>&1;
        v=\$(head -1 \$C | cut -c1-120); python3 tools/detection/stage_stats.py \$B/$name/trace/frames.csv $period > \$T;
        st=\$(python3 -c \"import json;d=json.load(open('\$T'));print('proc_med=%s c2o_p99=%s over_period=%s'%(d['process_total']['median'],d['complete_to_output']['p99'],d['c2o_over_period']))\");
        cl=\$(grep -h '^clock_errors=\|^offset_resampled=\|^offset_unresolved=' \$B/$name/trace/clock_diag.txt | tr '\n' ' ');
        line=\"run=$id be=$be shape=$shape period=$period \$st \$cl check=\$v\"; echo \"\$line\"; echo \"\$line\" >> $summary"
done
echo "FINAL_REGRESSION_DONE summary=$summary"
