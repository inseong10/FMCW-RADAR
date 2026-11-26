#!/usr/bin/env bash
# Reuse verified E14 ARM binaries; replace only PL image/clock declaration/scripts.
# Does not deploy or program hardware.
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
run=${1:?Usage: prepare_e14_clock_bundle.sh VIVADO_RUN NEW_BUNDLE [BASELINE_BUNDLE]}
out=${2:?Pass a fresh bundle directory}
baseline=${3:-/nfsroot/opt/fft128/e14_frame}
test ! -e "$out" || { echo 'Preserve existing bundle; use a fresh directory.' >&2; exit 1; }
run=$(cd -- "$run" && pwd)
out=$(python3 -c 'import os,sys; print(os.path.abspath(sys.argv[1]))' "$out")
(cd "$baseline"; sha256sum -c artifacts.sha256)
python3 - "$root" "$run" <<'PY'
import importlib.util, json, pathlib, sys
root, run = map(pathlib.Path, sys.argv[1:])
spec = importlib.util.spec_from_file_location('clock_gate', root/'tools/clock/validate_clock.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
recorded = json.loads((run/'clock_validation.json').read_text())
current = m.validate_build(run, recorded['clock_hz'])
assert current == recorded, 'Candidate validation/artifacts changed'
PY
probe="$root/build/fft128_dma_probe/probe_board"
test -r "$probe/live_dt.tar" && test -r "$probe/running.dtb"
bash "$root/src/PL/fft128_ps/prepare_firmware.sh" "$run"
mkdir -p "$out"
python3 - "$baseline" "$out" <<'PY'
from pathlib import Path
import shutil, sys
source, dest = map(Path, sys.argv[1:])
for line in (source/'artifacts.sha256').read_text().splitlines():
    _, name = line.split(maxsplit=1); name = name.lstrip('*')
    assert Path(name).name == name and name not in ('.', '..'), 'Unexpected baseline path'
    shutil.copy2(source/name, dest/name)
shutil.copy2(source/'artifacts.sha256', dest/'baseline_artifacts.sha256')
PY
cp "$run/firmware/fft128.bin" "$out/fft128_e14_frame.bin"
cp "$run/dma_config.json" "$run/build_config.json" "$run/clock_source.txt" \
    "$run/clock_validation.json" "$run/timing.rpt" "$run/utilization.rpt" \
    "$run/frame_core_check.txt" "$run/frame_utilization.rpt" "$out/"
cp "$run/source.sha256" "$out/pl_source.sha256"
cp "$root/src/PS/fft128/dma_frame/profile_board.sh" \
    "$root/src/PS/fft128/dma_frame/run_board.sh" "$out/"
python3 - "$root" "$probe/live_dt.tar" "$out" <<'PY'
import importlib.util, json, pathlib, sys
root, archive, out = map(pathlib.Path, sys.argv[1:])
spec = importlib.util.spec_from_file_location('overlay', root/'src/PS/fft128/dma_frame/make_overlay.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
text, meta = m.make_overlay(archive)
hz = json.loads((out/'dma_config.json').read_text())['clock_hz']
assert text.count('clock-frequency = <50000000>;') == 1
text = text.replace('clock-frequency = <50000000>;', 'clock-frequency = <%d>;' % hz)
meta['clock_hz'] = hz
(out/'fft128_e14_frame.dts').write_text(text)
(out/'fft128_e14_frame.json').write_text(json.dumps(meta, indent=2)+'\n')
PY
dtc -@ -I dts -O dtb -o "$out/fft128_e14_frame.dtbo" "$out/fft128_e14_frame.dts" 2> "$out/dtc.log"
fdtoverlay -i "$probe/running.dtb" -o "$out/merged_validation.dtb" "$out/fft128_e14_frame.dtbo"
hz=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["clock_hz"])' "$out/dma_config.json")
test "$(fdtget "$out/merged_validation.dtb" /fft128-e14_frame-clock clock-frequency)" = "$hz"
test "$(fdtget "$out/merged_validation.dtb" /amba_pl/fft@43c60000 compatible)" = fmcw,fft128-dma-frame-v8
test "$(fdtget "$out/merged_validation.dtb" /amba_pl/dma@40400000 compatible)" = xlnx,axi-dma-1.00.a
(cd "$root"; sha256sum tools/clock/prepare_e14_clock_bundle.sh tools/clock/build_e14_clock.sh \
    tools/clock/validate_clock.py tools/clock/prepare_e14_100.sh src/PS/fft128/dma_frame/make_overlay.py \
    src/PS/fft128/dma_batch/make_overlay.py src/PS/fft128/dma/make_overlay.py \
    src/PL/fft128_ps/prepare_firmware.sh > "$out/clock_tools.sha256")
python3 - "$out" <<'PY'
import hashlib, pathlib, sys
p = pathlib.Path(sys.argv[1])
lines = ['%s  %s' % (hashlib.sha256(f.read_bytes()).hexdigest(), f.name)
         for f in sorted(p.iterdir()) if f.is_file() and f.name != 'artifacts.sha256']
(p/'artifacts.sha256').write_text('\n'.join(lines)+'\n')
PY
(cd "$out"; sha256sum -c artifacts.sha256)
printf 'E14_CLOCK_BUNDLE_READY clock_hz=%s bundle=%s\n' "$hz" "$out"
printf 'Offline overlay validation only; board activation/self-test still required.\n'
