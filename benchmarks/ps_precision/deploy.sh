#!/usr/bin/env bash
# Copy as HGFS mounting user, then sudo install to the NFS root.
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
root=$(cd -- "$here/../.." && pwd)
out=${FFT128_PS_OUT:-"$root/build/fft128_ps_precision"}
stage="$HOME/fft128_ps_precision_deploy"
target=/nfsroot/opt/fft128/ps_precision
mkdir -p "$stage"
for file in frame.rspb reference.csv reference.json run_board.sh artifacts.sha256; do
    cp "$out/$file" "$stage/$file"
done
for variant in double float_scalar float_neon; do
    mkdir -p "$stage/$variant/bin" "$stage/$variant/lib"
    cp "$out/$variant/bin/receiver" "$stage/$variant/bin/receiver"
    cp "$out/$variant"/lib/*.so.3 "$stage/$variant/lib/"
    cp "$out/$variant/build_environment.txt" "$out/$variant/fftw_build_environment.txt" "$stage/$variant/"
done
(cd "$stage"; sha256sum -c artifacts.sha256)
# File names come from the generated, checksum-verified artifact list.
for file in frame.rspb reference.csv reference.json run_board.sh artifacts.sha256; do
    sudo install -D -m 0644 "$stage/$file" "$target/$file"
done
for variant in double float_scalar float_neon; do
    library=libfftw3f.so.3
    if [[ "$variant" == double ]]; then library=libfftw3.so.3; fi
    sudo install -D -m 0755 "$stage/$variant/bin/receiver" "$target/$variant/bin/receiver"
    sudo install -D -m 0755 "$stage/$variant/lib/$library" "$target/$variant/lib/$library"
    for file in build_environment.txt fftw_build_environment.txt; do
        sudo install -D -m 0644 "$stage/$variant/$file" "$target/$variant/$file"
    done
done
(cd "$target"; sudo sha256sum -c artifacts.sha256)
printf 'PS_PRECISION_DEPLOY_PASS: %s\n' "$target"
