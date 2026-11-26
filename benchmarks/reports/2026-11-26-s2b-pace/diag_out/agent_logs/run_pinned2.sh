#!/bin/sh
# v2 of run_pinned.sh for the S2b-diag output-location A/B (2026-11-26).
# Usage (board): sudo /opt/fft128/agent_20261126_02/run_pinned2.sh ps|pl RUN_ID FRAMES OUT_NAME nfs|ram
#   nfs: receiver writes to $B/OUT_NAME (NFS root, as in all runs up to 92348)
#   ram: receiver writes to tmpfs /var/volatile/fft128_agent/OUT_NAME; copied to $B/OUT_NAME after exit
# Same as v1 otherwise: pin main+sampler -> CPU0, worker -> CPU1 once, then run_board.sh ... measure.
# Adds one-shot network/NFS counter snapshots before and after the run (no sampling during it).
set -eu
PATH=/usr/sbin:/usr/bin:/sbin:/bin; export PATH
B=/opt/fft128/s2a_int16_20261126_adc01
T=/opt/fft128/pin_tid_20261126_01/pin-tid
L=/opt/fft128/agent_logs_20261126_01
R=/var/volatile/fft128_agent
[ $# -eq 5 ] || { echo 'usage: run_pinned2.sh ps|pl RUN_ID FRAMES OUT_NAME nfs|ram' >&2; exit 2; }
backend=$1; id=$2; frames=$3; name=$4; store=$5
case $backend in ps|pl) ;; *) echo 'bad backend' >&2; exit 2 ;; esac
case $id in ''|*[!0-9]*) echo 'bad run id' >&2; exit 2 ;; esac
case $frames in ''|*[!0-9]*) echo 'bad frames' >&2; exit 2 ;; esac
case $name in ''|*[!A-Za-z0-9_]*) echo 'bad output name' >&2; exit 2 ;; esac
case $store in nfs) out=$B/$name ;; ram) out=$R/$name ;; *) echo 'bad store' >&2; exit 2 ;; esac
log=$L/run_$id.log; pin=$L/pin_$id.txt
test ! -e "$B/$name" || { echo 'output exists; use a new name' >&2; exit 2; }
test ! -e "$out" || { echo 'output exists; use a new name' >&2; exit 2; }
test ! -e "$log" && test ! -e "$pin" || { echo 'run id already used' >&2; exit 2; }
if pidof stream-receiver >/dev/null 2>&1; then echo 'another stream-receiver is running' >&2; exit 2; fi
mkdir -p "$L"; chmod 755 "$L"
if test "$store" = ram; then mkdir -p "$R"; chmod 755 "$R"; fi
: > "$log"; : > "$pin"; chmod 644 "$log" "$pin"
snap() {
    printf 'uptime '; cut -d' ' -f1 /proc/uptime
    grep '^Udp' /proc/net/snmp
    grep -E 'eth0' /proc/net/dev
    grep -E '^(net|rpc)' /proc/net/rpc/nfs
    grep -E '^cpu[01]? ' /proc/stat
    grep -E '^(nr_dirty|nr_writeback) ' /proc/vmstat
}
echo "store=$store out=$out" >> "$log"
snap > "$L/snap_${id}_before.txt" 2>&1; chmod 644 "$L/snap_${id}_before.txt"
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
snap > "$L/snap_${id}_after.txt" 2>&1; chmod 644 "$L/snap_${id}_after.txt"
wait "$pinner" || true
if test "$store" = ram && test -d "$out"; then
    (cd "$out" && find . -type f -exec sha256sum {} + | sort -k2) > "$L/ram_${id}.sha256"
    cp -r "$out" "$B/$name"
    if (cd "$B/$name" && sha256sum -c -s "$L/ram_${id}.sha256"); then
        echo "RAM_COPY_OK files=$(wc -l < "$L/ram_${id}.sha256")" >> "$log"; rm -rf "$out"
    else
        echo "RAM_COPY_MISMATCH; tmpfs copy kept at $out" >> "$log"; status=3
    fi
    chmod 644 "$L/ram_${id}.sha256"
fi
cp "$pin" "$B/pin_$name.txt"
echo "AGENT_RUN_DONE run_id=$id status=$status" >> "$log"
exit "$status"
