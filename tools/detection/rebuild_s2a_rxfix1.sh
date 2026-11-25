#!/bin/bash
# User-run Ubuntu workflow: retain failure, host smoke, ARM build, fresh deploy.
set -euo pipefail
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$root"
tag=${1:-20261125_rxfix1}
case "$tag" in ''|*[!a-zA-Z0-9_-]*) echo 'Invalid tag' >&2; exit 1 ;; esac
failed_src=/nfsroot/opt/fft128/s2a_20261125_201834/ps_02
failed_out=build/s2a_failed_ps02_20261125_201834
if test -d "$failed_src" && test ! -e "$failed_out"; then
    cp -r "$failed_src" "$failed_out"
fi
host="build/s2a_host_$tag"
arm="build/s2a_arm_$tag"
smoke="build/s2a_smoke_$tag"
deploy="/nfsroot/opt/fft128/s2a_$tag"
bash tools/detection/build_s2a.sh host "$host"
python3 tools/detection/smoke_s2a.py --binary "$host/stream-receiver" --out "$smoke"
bash tools/detection/build_s2a.sh arm "$arm"
sha256sum -c "$arm/stream-receiver.sha256"
stage=$(mktemp -d "$HOME/s2a-stage.XXXXXX")
cp "$arm/stream-receiver" "$arm/build_environment.txt" "$stage/"
(cd "$stage" && sha256sum stream-receiver > artifacts.sha256)
sudo test ! -e "$deploy"
sudo mkdir "$deploy"
sudo cp -r "$stage/." "$deploy/"
sudo chmod 755 "$deploy/stream-receiver"
echo "S2A_DEPLOY_READY $deploy"
