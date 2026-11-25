"""S1b recorded-input checks, usable with a Linux host or a Python-free board.

Prepare on the PC, copy the bundle to the board, run run_board.sh with the new
receiver and its FFTW library, copy results back, then use --check-only.
This is single-frame validation; it does not measure continuous UDP throughput.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys

import numpy as np

import cfar_reference as ref


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def repository_commit():
    # Shared source copies may deliberately omit .git; source SHA256 stays mandatory.
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ref.ROOT,
                                capture_output=True, text=True, check=False)
        return result.stdout.strip() if result.returncode == 0 else None
    except FileNotFoundError:
        return None


def prepare(out, warmup, repeat):
    if out.exists():
        raise ValueError(f"Use a new bundle directory: {out}")
    out.mkdir(parents=True)
    cases = []
    shell = ["#!/bin/sh", "set -eu", 'cd -- "$(dirname -- "$0")"',
             'receiver=${1:?Pass the S1b receiver executable}',
             'library=${2:-libfftw3.so.3}',
             'test ! -e environment.txt || { echo "Use a fresh bundle" >&2; exit 1; }',
             'sha256sum -c artifacts.sha256 > artifact_check.txt',
             '{ uname -a; cat /proc/cpuinfo; } > environment.txt',
             'sha256sum "$receiver" > receiver.sha256',
             'if test -f "$library"; then sha256sum "$library" > fftw.sha256; fi',
             'for f in /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq; do',
             '  if test -r "$f"; then printf "%s: " "$f"; cat "$f"; fi',
             'done >> environment.txt']
    for name in ("single", "multi4", "close_weak"):
        filename = f"radarsimpy_128x128_sim_{name}_noise.rspb"
        source = ref.ROOT / "benchmarks/fixtures" / filename
        meta = json.loads(source.with_suffix(".json").read_text(encoding="utf-8"))
        if sha(source) != meta["record_sha256"]:
            raise ValueError(f"Fixture SHA mismatch: {source}")
        shutil.copyfile(source, out / filename)
        frame, fs = ref.read_rspb(source)
        for window in ("none", "hann"):
            case = {"name": f"{name}_{window}", "record": filename, "sha256": sha(source),
                    "window": window, "shape": list(frame.shape), "fs_hz": fs,
                    "targets": meta["targets"]}
            cases.append(case)
            arguments = ["--input", filename, "--window", window, "--cfar", "ca",
                         "--warmup", str(warmup), "--repeat", str(repeat),
                         "--output", case["name"]+".spectrum.csv",
                         "--detections", case["name"]+".detections.csv",
                         "--timings", case["name"]+".timings.csv"]
            case["arguments"] = arguments
            shell += ['"$receiver" --cpu0 --fftw-lib "$library" '+shlex.join(arguments)+
                      f' > {case["name"]}.log 2>&1']
    shell += ['echo S1B_RUN_COMPLETE']
    with (out / "run_board.sh").open("w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(shell)+"\n")
    sources = {str(p.relative_to(ref.ROOT)).replace("\\", "/"): sha(p) for p in [
        ref.ROOT / "src/PS/receiver/udp_radar_receiver.cpp",
        ref.ROOT / "src/PS/receiver/cfar_ca.hpp",
        Path(__file__).resolve(), ref.ROOT / "tools/detection/cfar_reference.py"]}
    (out / "manifest.json").write_text(json.dumps({"scope": "S1b offline recorded frames, original IQ, double FFTW",
        "base_commit": repository_commit(),
        "sources": sources, "preparation_python": sys.version, "numpy": np.__version__,
        "repeat": repeat, "warmup": warmup, "cases": cases}, indent=2)+"\n", encoding="utf-8")
    files = sorted(p for p in out.iterdir() if p.is_file())
    (out / "artifacts.sha256").write_text("".join(f"{sha(p)}  {p.name}\n" for p in files), encoding="utf-8")


def check(out):
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    runs = []
    for case in manifest["cases"]:
        record = out / case["record"]
        if sha(record) != case["sha256"]:
            raise ValueError(f"Changed fixture: {record}")
        frame, fs = ref.read_rspb(record)
        weighted = frame.copy()
        if case["window"] == "hann":
            weighted *= np.hanning(frame.shape[0])[:, None]*np.hanning(frame.shape[1])[None, :]
        spectrum = np.fft.fft2(weighted)
        actual = np.loadtxt(out / (case["name"]+".spectrum.csv"), delimiter=",", skiprows=1)
        d, r = np.indices(frame.shape)
        np.testing.assert_array_equal(actual[:, :2], np.column_stack((d.ravel(), r.ravel())))
        np.testing.assert_allclose((actual[:, 2]+1j*actual[:, 3]).reshape(frame.shape), spectrum,
                                   rtol=1e-10, atol=float(np.abs(spectrum).max())*1e-12)
        power = ref.range_doppler_power(frame, case["window"])
        det, threshold = ref.ca_cfar_2d(power, (2, 2), (8, 8), 1e-6)
        expected = ref.cluster_peaks(power, det)
        with (out / (case["name"]+".detections.csv")).open() as f:
            rows = list(csv.DictReader(f))
        found = [(int(p["doppler_bin_unshifted"]), int(p["range_bin"])) for p in rows]
        if found != expected:
            raise AssertionError(f"{case['name']}: detections {found} != {expected}")
        for row, peak in zip(rows, expected):
            np.testing.assert_allclose(float(row["power"]), power[peak], rtol=1e-9)
            np.testing.assert_allclose(float(row["threshold"]), threshold[peak], rtol=1e-8)
        with (out / (case["name"]+".timings.csv")).open() as f:
            timings = list(csv.DictReader(f))
        stages = {}
        for stage in ("fft_pipeline", "cfar", "processing_total"):
            values = [float(t["wall_ms"]) for t in timings if t["stage"] == stage]
            if len(values) != manifest["repeat"] or not all(np.isfinite(x) and x > 0 for x in values):
                raise AssertionError(f"{case['name']}: invalid {stage} timing samples")
            stages[stage] = {"samples": len(values), "median_ms": float(np.median(values)),
                             "p99_ms": float(np.percentile(values, 99)), "max_ms": max(values)}
        truth, false = ref.evaluate(found, case["targets"], *frame.shape, fs)
        runs.append({"case": case["name"], "peaks": [list(p) for p in found],
                     "truth": truth, "false_peaks": false, "timings": stages})
        print(f"{case['name']}: FFT/CFAR PASS, hit {sum(t['hit'] for t in truth)}/{len(truth)}, false {len(false)}")
    summary = {"scope": manifest["scope"], "timing_scope": "same-frame repeats; not continuous UDP/P99 acceptance",
               "checked_on": platform.platform(), "runs": runs}
    (out / "checked_summary.json").write_text(json.dumps(summary, indent=2)+"\n", encoding="utf-8")
    print("S1B_RECORDED_CHECK_PASS cases="+str(len(runs)))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, type=Path)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare-only", action="store_true")
    mode.add_argument("--check-only", action="store_true")
    mode.add_argument("--binary", type=Path, help="prepare, run locally, then check")
    ap.add_argument("--fftw-lib", type=Path)
    ap.add_argument("--warmup", type=int, default=2)
    ap.add_argument("--repeat", type=int, default=3)
    args = ap.parse_args()
    if not (0 <= args.warmup <= 100000 and 1 <= args.repeat <= 1000000):
        ap.error("invalid warmup/repeat")
    if not args.check_only:
        prepare(args.out, args.warmup, args.repeat)
    if args.binary:
        binary = args.binary.resolve()
        lib = ["--fftw-lib", str(args.fftw_lib.resolve())] if args.fftw_lib else []
        manifest = json.loads((args.out / "manifest.json").read_text(encoding="utf-8"))
        for case in manifest["cases"]:
            with (args.out / (case["name"]+".log")).open("w") as log:
                subprocess.run([str(binary), *lib, *case["arguments"]], cwd=args.out,
                               stdout=log, stderr=subprocess.STDOUT, check=True, timeout=600)
    if not args.prepare_only:
        check(args.out)


if __name__ == "__main__":
    main()
