#!/usr/bin/env bash
# Inspect BSP recipes/configuration without PetaLinux dependency checks.
# No package installation, kernel build, NFS or existing project changes.
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
root=$(cd -- "$here/../../../.." && pwd)
out="$root/build/fft128_dma_kernel_project"
mkdir -p "$out"
python3 - /tools/Xilinx/bsp/Zybo-Z7-10-Petalinux-2022-1.bsp "$out" <<'PY'
import pathlib, sys, tarfile
bsp, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
with tarfile.open(str(bsp)) as archive:
    members = archive.getmembers()
    (out/'bsp_manifest.txt').write_text(''.join(m.name+'\n' for m in members))
    selected = []
    for member in members:
        name = pathlib.PurePosixPath(member.name)
        if not member.isfile() or '..' in name.parts or name.is_absolute():
            continue
        parts = name.parts
        if 'project-spec' not in parts:
            continue
        relative = pathlib.Path(*parts[parts.index('project-spec'):])
        # Configuration/recipes only, never prebuilt bitstreams, SDKs or images.
        if relative.suffix not in ('.bb', '.bbappend', '.conf', '.cfg', '.scc', '.dts', '.dtsi', '.sh') and relative.name not in ('config', 'rootfs_config'):
            continue
        if member.size > 2*1024*1024:
            continue
        target = out/'bsp_config'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(archive.extractfile(member).read())
        selected.append(str(relative))
    if not selected:
        raise SystemExit('No BSP project recipes found; see bsp_manifest.txt')
    print('BSP inspection files:', len(selected))
PY
if command -v apt-get >/dev/null; then
    apt-get -s install gcc-multilib > "$out/gcc_multilib_plan.txt" 2>&1 || true
fi
printf 'DMA_KERNEL_PROJECT_READY: %s\n' "$out"
