#!/bin/sh
# S3a-final: build and deploy the four final bundles from one source tree with a single sudo prompt.
# Runs on the Ubuntu host from the shared checkout. Each size goes through prepare_adc16.sh unchanged
# (host build, float/ADC/S3a smokes, ARM build, NFS copy, sha256 check). Existing bundles are never reused.
# Usage: sh tools/detection/prepare_final.sh LABEL_PREFIX [--dry-run]
#   bundles: /nfsroot/opt/fft128/s2a_int16_<LABEL_PREFIX>_m<M>n<N>
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
prefix=${1:?Pass a label prefix, e.g. final_20261127}
dry=${2:-}
case "$prefix" in ''|*[!A-Za-z0-9_]*) echo 'Use letters, digits and underscores only (run_pinned3.sh rule)' >&2; exit 1 ;; esac
shapes="128x128 256x128 128x256 256x256"
for s in $shapes; do
    m=${s%x*}; n=${s#*x}; label="${prefix}_m${m}n${n}"
    test ! -e "$root/build/s2a_int16_$label" && test ! -e "/nfsroot/opt/fft128/s2a_int16_$label" ||
        { echo "Label already used: $label" >&2; exit 1; }
done
if test "$dry" = "--dry-run"; then
    for s in $shapes; do m=${s%x*}; n=${s#*x}; echo "sh $root/tools/detection/prepare_adc16.sh ${prefix}_m${m}n${n} $s"; done
    echo FINAL_PREPARE_DRY_RUN_OK; exit 0
fi
# One password prompt: refresh the sudo timestamp until this script exits (host builds take several minutes).
sudo -v
( while true; do sleep 60; sudo -n true 2>/dev/null || exit; done ) &
keep=$!
trap 'kill "$keep" 2>/dev/null || true' 0 INT TERM
for s in $shapes; do
    m=${s%x*}; n=${s#*x}; label="${prefix}_m${m}n${n}"
    echo "== $label ($s)"
    sh "$root/tools/detection/prepare_adc16.sh" "$label" "$s"
done
echo "FINAL_DEPLOY_READY prefix=$prefix bundles:"
for s in $shapes; do
    m=${s%x*}; n=${s#*x}; d="/nfsroot/opt/fft128/s2a_int16_${prefix}_m${m}n${n}"
    printf '%s %s\n' "$(sha256sum "$d/stream-receiver" | cut -c1-16)" "$d"
done
