#!/usr/bin/env bash
# Assemble E11a into ignored build/, never overwrite the baseline deployment.
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
root=$(cd -- "$here/../../../.." && pwd)
run=${1:-$(cat "$root/build/fft128_dma_latest.txt")}
host=${FFT128_DMA_HOST_OUT:-"$root/build/fft128_dma_host"}
module="$root/build/fft128_dma_module"
out=${FFT128_DMA_BUNDLE_OUT:-"$root/build/fft128_dma_bundle"}
test ! -e "$out" || { echo 'Preserve existing bundle; move it aside before assembling another.' >&2; exit 1; }
for path in "$run/dma_config.json" "$run/timing.rpt" "$run/source.sha256" "$host/artifacts.sha256" "$host/source.sha256" "$module/fft128_dma.ko" "$module/source.sha256"; do
    test -r "$path" || { printf 'Missing prerequisite: %s\n' "$path" >&2; exit 1; }
done
python3 - "$run/dma_config.json" <<'PY'
import json, sys
d=json.load(open(sys.argv[1]))
assert d['experiment']=='E11a' and d['fft_control_base']=='0x43c60000'
assert d['irq_f2p_bits']==[6,7] and d['clock_hz']==50000000 and not d['sg']
PY
(cd "$host"; sha256sum -c artifacts.sha256)
(cd "$module"; sha256sum -c artifacts.sha256)
(cd "$root"; sha256sum -c "$host/source.sha256")
(cd "$here"; sha256sum -c "$module/source.sha256")
sha256sum -c "$run/source.sha256"
bash "$root/src/PL/fft128_ps/prepare_firmware.sh" "$run" > "$run/e11a_firmware_prepare.log"
mkdir -p "$out"
cp "$run/firmware/fft128.bin" "$out/fft128_e11a.bin"
cp "$host/fft128_e11a.dtbo" "$host/fft128_e11a.json" "$module/fft128_dma.ko" "$out/"
cp "$host/bin/fft128-receiver" "$out/"
cp "$host/bin/test-dma-client" "$out/"
cp "$root/benchmarks/fixtures/radarsimpy_128x128.rspb" "$out/frame.rspb"
cp "$here/load_board.sh" "$here/profile_board.sh" "$here/run_board.sh" "$here/retry_overlay_board.sh" "$out/"
cp "$root/build/fft128_dma_probe/probe_board/kernelrelease.txt" "$out/"
cp "$run/dma_config.json" "$run/build_config.json" "$run/clock_source.txt" "$run/timing.rpt" "$run/utilization.rpt" "$out/"
cp "$run/source.sha256" "$out/pl_source.sha256"
cp "$host/source.sha256" "$out/host_source.sha256"
cp "$module/source.sha256" "$out/module_source.sha256"
cp "$module/build_environment.txt" "$out/module_build_environment.txt"
python3 - "$out" <<'PY'
import json, pathlib, struct, sys
p=pathlib.Path(sys.argv[1]); d=json.loads((p/'fft128_e11a.json').read_text())
(p/'gic_phandle.bin').write_bytes(struct.pack('>I',d['gic_phandle']))
(p/'gic_path.txt').write_text(d['gic_path']+'\n')
PY
(cd "$out"; sha256sum fft128_e11a.bin fft128_e11a.dtbo fft128_e11a.json fft128_dma.ko \
    fft128-receiver test-dma-client frame.rspb kernelrelease.txt gic_phandle.bin gic_path.txt dma_config.json \
    build_config.json clock_source.txt pl_source.sha256 host_source.sha256 module_source.sha256 \
    module_build_environment.txt load_board.sh profile_board.sh run_board.sh retry_overlay_board.sh > artifacts.sha256)
printf 'DMA_BUNDLE_READY: %s\n' "$out"
printf 'Copy as mounting user to a local folder, then sudo install under /nfsroot/opt/fft128/e11a.\n'
