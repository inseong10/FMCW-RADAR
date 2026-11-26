#!/bin/sh
# v3 of run_pinned.sh (2026-11-26, S3a-0): the bundle is an argument instead of a fixed path.
# Usage (board): sudo /opt/fft128/agent_20261126_03/run_pinned3.sh BUNDLE ps|pl RUN_ID FRAMES OUT_NAME nfs|ram
#   BUNDLE: a directory name s2a_int16_<label> under /opt/fft128. It runs only if the directory and its
#   run_board.sh, stream-receiver, libfftw3.so.3 and artifacts.sha256 are root-owned, not group/other
#   writable, and artifacts.sha256 verifies (so only bundles deployed with sudo can run as root).
#   nfs: receiver writes to $B/OUT_NAME (NFS root, as in all runs up to 92348)
#   ram: receiver writes to tmpfs /var/volatile/fft128_agent/OUT_NAME; copied to $B/OUT_NAME after exit
# Same as v1 otherwise: pin main+sampler -> CPU0, worker -> CPU1 once, then run_board.sh ... measure.
# Adds one-shot network/NFS counter snapshots before and after the run (no sampling during it).
set -eu
PATH=/usr/sbin:/usr/bin:/sbin:/bin; export PATH
T=/opt/fft128/pin_tid_20261126_01/pin-tid
L=/opt/fft128/agent_logs_20261126_01
R=/var/volatile/fft128_agent
[ $# -eq 6 ] || { echo 'usage: run_pinned3.sh BUNDLE ps|pl RUN_ID FRAMES OUT_NAME nfs|ram' >&2; exit 2; }
bundle=$1; backend=$2; id=$3; frames=$4; name=$5; store=$6
case $bundle in s2a_int16_*) ;; *) echo 'bad bundle' >&2; exit 2 ;; esac
case ${bundle#s2a_int16_} in ''|*[!A-Za-z0-9_]*) echo 'bad bundle' >&2; exit 2 ;; esac
B=/opt/fft128/$bundle
test -d "$B" && ! test -L "$B" || { echo 'bundle missing' >&2; exit 2; }
for f in "$B" "$B/run_board.sh" "$B/stream-receiver" "$B/libfftw3.so.3" "$B/artifacts.sha256"; do
    test -e "$f" && ! test -L "$f" || { echo "bundle file missing: $f" >&2; exit 2; }
    [ "$(stat -c %u "$f")" = 0 ] || { echo "not root-owned: $f" >&2; exit 2; }
    m=$(stat -c %a "$f"); [ $(( 0$m & 022 )) -eq 0 ] || { echo "group/other writable: $f" >&2; exit 2; }
done
(cd "$B" && sha256sum -c -s artifacts.sha256) || { echo 'bundle artifacts.sha256 mismatch' >&2; exit 2; }
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
echo "bundle=$B store=$store out=$out" >> "$log"
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
