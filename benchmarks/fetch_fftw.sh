#!/usr/bin/env bash
# Download the pinned official source; never install or execute downloaded code.
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
root=$(cd -- "$here/.." && pwd)
archive=${FFT128_FFTW_ARCHIVE:-"$root/build/third_party/fftw-3.3.11.tar.gz"}
url=https://www.fftw.org/fftw-3.3.11.tar.gz
sha=5630c24cdeb33b131612f7eb4b1a9934234754f9f388ff8617458d0be6f239a1
command -v sha256sum >/dev/null
if [[ -f "$archive" ]]; then
    printf '%s  %s\n' "$sha" "$archive" | sha256sum -c -
    exit 0
fi
mkdir -p -- "$(dirname -- "$archive")"
temporary=$(mktemp "${archive}.XXXXXX")
trap 'rm -f -- "$temporary"' EXIT
if command -v curl >/dev/null 2>&1; then
    curl --fail --location --proto '=https' --proto-redir '=https' "$url" --output "$temporary"
elif command -v wget >/dev/null 2>&1; then
    wget --https-only -O "$temporary" "$url"
else
    printf '%s\n' 'Install curl or wget to download the official FFTW source.' >&2
    exit 1
fi
printf '%s  %s\n' "$sha" "$temporary" | sha256sum -c -
mv -- "$temporary" "$archive"
printf 'FFTW_SOURCE_READY: %s\n' "$archive"
