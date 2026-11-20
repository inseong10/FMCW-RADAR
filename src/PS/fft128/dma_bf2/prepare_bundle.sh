#!/usr/bin/env bash
# Assemble E13-bf2 into ignored build/, never overwrite the baseline deployment.
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
root=$(cd -- "$here/../../../.." && pwd)
run=${1:-$(cat "$root/build/fft128_dma_bf2_latest.txt")}
host=${FFT128_DMA_BF2_HOST_OUT:-"$root/build/fft128_dma_bf2_host"}
module="$root/build/fft128_dma_bf2_module"
out=${FFT128_DMA_BF2_BUNDLE_OUT:-"$root/build/fft128_dma_bf2_bundle"}
test ! -e "$out" || { echo 'Preserve existing bundle; move it aside before assembling another.' >&2; exit 1; }
for path in "$run/dma_config.json" "$run/timing.rpt" "$run/bf2_core_check.txt" "$run/bf2_utilization.rpt" "$run/source.sha256" "$host/artifacts.sha256" "$host/source.sha256" "$module/fft128_dma_bf2.ko" "$module/source.sha256"; do
    test -r "$path" || { printf 'Missing prerequisite: %s\n' "$path" >&2; exit 1; }
done
python3 - "$run/dma_config.json" <<'PY'
import json, sys
d=json.load(open(sys.argv[1]))
assert d['experiment']=='E13-bf2' and d['fft_control_base']=='0x43c60000'
assert d['fft_per_request']==128 and d['bytes_per_direction']==65536 and d['register_abi']==6 and d['parallel_cores']==4 and d['butterflies_per_core']==2 and d['total_butterflies']==8 and not d['group_barrier'] and not d['external_ping_pong'] and d['external_buffers'] and d['buffering']=='per_lane_fifos' and d['next_group_prefetch']
assert d['irq_f2p_bits']==[6,7] and d['clock_hz']==50000000 and not d['sg']
PY
(cd "$host"; sha256sum -c artifacts.sha256)
(cd "$module"; sha256sum -c artifacts.sha256)
(cd "$root"; sha256sum -c "$host/source.sha256")
(cd "$here"; sha256sum -c "$module/source.sha256")
sha256sum -c "$run/source.sha256"
bash "$root/src/PL/fft128_ps/prepare_firmware.sh" "$run" > "$run/e13_bf2_firmware_prepare.log"
mkdir -p "$out"
cp "$run/firmware/fft128.bin" "$out/fft128_e13_bf2.bin"
cp "$host/fft128_e13_bf2.dtbo" "$host/fft128_e13_bf2.json" "$module/fft128_dma_bf2.ko" "$out/"
cp "$host/bin/fft128-receiver" "$out/"
cp "$host/bin/test-dma-bf2-client" "$out/"
cp "$root/benchmarks/fixtures/radarsimpy_128x128.rspb" "$out/frame.rspb"
cp "$here/load_board.sh" "$here/profile_board.sh" "$here/run_board.sh" "$out/"
cp "$root/build/fft128_dma_probe/probe_board/kernelrelease.txt" "$out/"
cp "$run/dma_config.json" "$run/build_config.json" "$run/clock_source.txt" "$run/timing.rpt" "$run/utilization.rpt" "$run/bf2_core_check.txt" "$run/bf2_utilization.rpt" "$out/"
cp "$run/source.sha256" "$out/pl_source.sha256"
cp "$host/source.sha256" "$out/host_source.sha256"
cp "$module/source.sha256" "$out/module_source.sha256"
cp "$module/build_environment.txt" "$out/module_build_environment.txt"
python3 - "$out" <<'PY'
import json, pathlib, struct, sys
p=pathlib.Path(sys.argv[1]); d=json.loads((p/'fft128_e13_bf2.json').read_text())
(p/'gic_phandle.bin').write_bytes(struct.pack('>I',d['gic_phandle']))
(p/'gic_path.txt').write_text(d['gic_path']+'\n')
PY
(cd "$out"; sha256sum fft128_e13_bf2.bin fft128_e13_bf2.dtbo fft128_e13_bf2.json fft128_dma_bf2.ko \
    fft128-receiver test-dma-bf2-client frame.rspb kernelrelease.txt gic_phandle.bin gic_path.txt dma_config.json \
    bf2_core_check.txt bf2_utilization.rpt build_config.json clock_source.txt pl_source.sha256 host_source.sha256 module_source.sha256 \
    module_build_environment.txt load_board.sh profile_board.sh run_board.sh > artifacts.sha256)
printf 'DMA_BUNDLE_READY: %s\n' "$out"
printf 'Copy as mounting user to a local folder, then sudo install under /nfsroot/opt/fft128/e13_bf2.\n'
