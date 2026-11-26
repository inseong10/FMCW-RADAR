#!/bin/sh
# Root-owned wrapper so the agent can run one pinned receiver without a sudo password.
# Usage (board): sudo /opt/fft128/agent_20261126_01/run_pinned.sh ps|pl RUN_ID FRAMES OUT_NAME
# Does exactly: pin main+sampler -> CPU0, worker -> CPU1 once (no sampling loop during the run),
# then run_board.sh ... measure. Logs go to a root-owned directory, readable by everyone.
set -eu
B=/opt/fft128/s2a_int16_20261126_adc01
T=/opt/fft128/pin_tid_20261126_01/pin-tid
L=/opt/fft128/agent_logs_20261126_01
[ $# -eq 4 ] || { echo 'usage: run_pinned.sh ps|pl RUN_ID FRAMES OUT_NAME' >&2; exit 2; }
backend=$1; id=$2; frames=$3; name=$4
case $backend in ps|pl) ;; *) echo 'bad backend' >&2; exit 2 ;; esac
case $id in ''|*[!0-9]*) echo 'bad run id' >&2; exit 2 ;; esac
case $frames in ''|*[!0-9]*) echo 'bad frames' >&2; exit 2 ;; esac
case $name in ''|*[!A-Za-z0-9_]*) echo 'bad output name' >&2; exit 2 ;; esac
out=$B/$name; log=$L/run_$id.log; pin=$L/pin_$id.txt
test ! -e "$out" || { echo 'output exists; use a new name' >&2; exit 2; }
test ! -e "$log" && test ! -e "$pin" || { echo 'run id already used' >&2; exit 2; }
if pidof stream-receiver >/dev/null 2>&1; then echo 'another stream-receiver is running' >&2; exit 2; fi
mkdir -p "$L"; chmod 755 "$L"
: > "$log"; : > "$pin"; chmod 644 "$log" "$pin"
(
    n=0
    until P=$(pidof stream-receiver) && [ "$(ls /proc/$P/task | wc -l)" -ge 3 ]; do
        n=$((n+1)); [ "$n" -lt 1500 ] || { echo 'PIN_TIMEOUT no receiver with 3 tasks in 30s'; exit 1; }
        sleep 0.02
    done
    set -- $(ls /proc/$P/task | sort -n)
    echo "pid=$P tasks=$*"
    "$T" 1 "$1" "$2"; "$T" 2 "$3"
    echo "T $(cut -d' ' -f1 /proc/uptime)"; grep '^cpu[01] ' /proc/stat
) >> "$pin" 2>&1 &
pinner=$!
status=0
sh "$B/run_board.sh" "$backend" "$id" "$frames" "$out" measure >> "$log" 2>&1 || status=$?
wait "$pinner" || true
cp "$pin" "$B/pin_$name.txt"
echo "AGENT_RUN_DONE run_id=$id status=$status" >> "$log"
exit "$status"
