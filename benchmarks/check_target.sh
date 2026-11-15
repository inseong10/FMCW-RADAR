#!/usr/bin/env bash
# Ubuntu: inspect the NFS rootfs without changing it.
set -euo pipefail
target=${1:-/nfsroot}
printf 'TARGET_ROOTFS: %s\n' "$target"
for dir in "$target/lib" "$target/usr/lib" "$target/lib/arm-linux-gnueabihf" "$target/usr/lib/arm-linux-gnueabihf"; do
    if [[ -d "$dir" ]]; then
        find "$dir" -maxdepth 1 \( -name 'libfftw3.so*' -o -name 'libstdc++.so*' -o -name 'ld-linux*' -o -name 'libc.so*' \) -printf '%p -> %l\n'
    fi
done
if command -v readelf >/dev/null 2>&1 && [[ -r "$target/bin/busybox" ]]; then
    readelf -h "$target/bin/busybox" | sed -n '/Class:/p;/Machine:/p;/Flags:/p'
    readelf -A "$target/bin/busybox" | sed -n '/Tag_CPU_name:/p;/Tag_ABI_VFP_args:/p'
fi
for cc in arm-linux-gnueabihf-gcc arm-linux-gnueabihf-g++; do
    if command -v "$cc" >/dev/null 2>&1; then "$cc" --version | head -n 1; fi
done
