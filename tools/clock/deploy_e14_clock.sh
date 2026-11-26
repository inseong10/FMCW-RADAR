#!/usr/bin/env bash
# Copy a complete candidate into a new NFS directory. Never program the FPGA here.
set -euo pipefail
bundle=${1:?Usage: deploy_e14_clock.sh BUNDLE}
(cd "$bundle"; sha256sum -c artifacts.sha256)
hz=$(python3 - "$bundle" <<'PY'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1])
d = json.loads((p/'dma_config.json').read_text())
v = json.loads((p/'clock_validation.json').read_text())
assert v['status'] == 'E14_CLOCK_BUILD_PASS' and v['clock_hz'] == d['clock_hz']
assert 50000000 <= d['clock_hz'] <= 200000000
print(d['clock_hz'])
PY
)
stage=$(mktemp -d "$HOME/fft128_e14_clock_deploy.XXXXXX")
cp -r "$bundle/." "$stage/"
dest="/nfsroot/opt/fft128/e14_clock_${hz}_$(date +%Y%m%d_%H%M%S)"
# mkdir (without -p) refuses an existing candidate, preserving all earlier results.
sudo mkdir "$dest"
for path in "$stage"/*; do
    test -f "$path" || continue
    mode=0644
    case $(basename -- "$path") in fft128-receiver|test-dma-frame-client) mode=0755;; esac
    sudo install -m "$mode" "$path" "$dest/"
done
sudo sh -c 'cd "$1" && sha256sum -c artifacts.sha256' sh "$dest"
printf 'E14_CLOCK_DEPLOY_READY: board %s\n' "${dest#/nfsroot}"
printf 'Existing E14 module must be absent before load_board.sh; use a fresh board boot.\n'
