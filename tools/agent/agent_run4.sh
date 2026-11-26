#!/bin/sh
# Usage: agent_run4.sh RUN_ID OUT_NAME nfs|ram SENDER_TAG ps|pl BUNDLE FRAMES RECORD PERIOD_MS  (wrapper v3, S3a)
# One pinned PL 10,000-frame run: Ubuntu snap -> board start -> READY+pin check -> send -> wait -> Ubuntu snap.
set -u
id=$1; name=$2; store=$3; tag=$4; be=$5; bundle=$6; frames=$7; record=$8; period=$9
K=$HOME/.ssh/fmcw_agent
F='post-quantum|store now|openssh.com/pq'
BRD() { timeout "${2:-40}" ssh -i "$K" -o BatchMode=yes -o ConnectTimeout=15 -o "ProxyCommand=ssh -i $K -o BatchMode=yes -W %h:%p user@192.168.25.129" petalinux@10.0.0.3 "$1" 2>&1 | grep -vE "$F"; }
UBU() { timeout "${2:-60}" ssh -i "$K" -o BatchMode=yes user@192.168.25.129 "$1" 2>&1 | grep -vE "$F"; }
P=/home/user/fmcw_share/FMCW-FFT-test
SN="$P/build/s3a_ubuntu_snap_$id"
UBU "test ! -e ${SN}_before.txt && { cat /proc/uptime; grep -E '^(rc|io|th|net|rpc)' /proc/net/rpc/nfsd; grep -E '^cpu' /proc/stat; } > ${SN}_before.txt && echo UBU_SNAP_BEFORE"
BRD "sudo -n /opt/fft128/agent_20261126_03/run_pinned3.sh $bundle $be $id $frames $name $store > /tmp/agent_nohup_$id.txt 2>&1 < /dev/null & echo BOARD_STARTED"
out=$(BRD "L=/opt/fft128/agent_logs_20261126_01; n=0; until grep -qE 'S2A_READY|AGENT_RUN_DONE' \$L/run_$id.log 2>/dev/null; do n=\$((n+1)); [ \$n -lt 300 ] || { echo NO_READY; break; }; sleep 0.1; done; i=0; until grep -qE 'mask=2|PIN_TIMEOUT' \$L/pin_$id.txt 2>/dev/null; do i=\$((i+1)); [ \$i -lt 50 ] || break; sleep 0.1; done; cat \$L/run_$id.log; cat \$L/pin_$id.txt; cat /tmp/agent_nohup_$id.txt" 60)
echo "$out"
if ! echo "$out" | grep -q "S2A_READY backend=$be run_id=$id" || [ "$(echo "$out" | grep -cE 'mask=1$')" -ne 2 ] || ! echo "$out" | grep -qE 'mask=2$'; then
    echo "ABORT_NO_SEND: READY or pin masks not confirmed"; exit 1
fi
UBU "cd $P && test ! -e build/s3a_sender_$tag.json && python3 tools/sender/replay_stream.py $record --ip 10.0.0.3 --run-id $id --frames $frames --period-ms $period --wait-mode spin --chirp-gap-us 100 --schedule reanchor --out build/s3a_sender_$tag.json" 400
BRD "L=/opt/fft128/agent_logs_20261126_01; n=0; until grep -q AGENT_RUN_DONE \$L/run_$id.log; do n=\$((n+1)); [ \$n -lt 900 ] || { echo NOT_DONE; break; }; sleep 0.1; done; cat \$L/run_$id.log; O=/opt/fft128/$bundle/$name; tr '\n' ' ' < \$O/trace/counters.txt; echo; cut -d, -f2 \$O/trace/frames.csv | sort | uniq -c" 120
UBU "test ! -e ${SN}_after.txt && { cat /proc/uptime; grep -E '^(rc|io|th|net|rpc)' /proc/net/rpc/nfsd; grep -E '^cpu' /proc/stat; } > ${SN}_after.txt && echo UBU_SNAP_AFTER"
