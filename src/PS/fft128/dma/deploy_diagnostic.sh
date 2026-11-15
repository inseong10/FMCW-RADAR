#!/usr/bin/env bash
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
stage=$(mktemp -d "$HOME/fft128_diag.XXXXXX")
cp "$here/diagnose_board.sh" "$stage/"
sudo install -m 0644 "$stage/diagnose_board.sh" /nfsroot/opt/fft128/e11a/diagnose_board.sh
printf 'Run on board: sudo sh /opt/fft128/e11a/diagnose_board.sh\n'
