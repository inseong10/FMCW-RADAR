"""S1c correctness bundle: unchanged E14 FFT -> shared C++ CA-CFAR.

Hann is applied on the PC before float32 RSPB serialization and board quantization.
The E14 receiver still reports window=none because its input is already windowed.
PL and CFAR are separate processes with CSV between them: component timings only.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import shlex
import shutil
import subprocess

import numpy as np

import cfar_reference as ref
from make_fixture import write_rspb

SPEC = importlib.util.spec_from_file_location("s1c_q15", ref.ROOT / "src/PS/fft128/receiver.py")
model = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(model)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def quantize(frame):
    """Match native_core.c: max complex magnitude -> 16384; ties to even."""
    peak = float(np.max(np.hypot(frame.real, frame.imag)))
    scale = 16384.0 / peak if peak else 1.0
    return np.rint(frame.real * scale) + 1j * np.rint(frame.imag * scale), scale


def integer_spectrum(q):
    rows = [model.fft_q15([model.pack_iq((z.real, z.imag)) for z in row]) for row in q]
    columns = [model.fft_q15([rows[d][r] for d in range(128)]) for r in range(128)]
    return np.array([[complex(*model.unpack_iq(columns[r][d])) for r in range(128)] for d in range(128)])


def detect(power):
    cells, _ = ref.ca_cfar_2d(power, (2, 2), (8, 8), 1e-6)
    return ref.cluster_peaks(power, cells)


def prepare(out, warmup, repeat):
    if out.exists():
        raise ValueError(f"Use a new output directory: {out}")
    out.mkdir(parents=True)
    cases = []
    shell = ["#!/bin/sh", "set -eu", 'cd -- "$(dirname -- "$0")"',
             'pl=${1:?Pass the existing E14 receiver}', 'cfar=${2:?Pass the new S1c CFAR executable}',
             'test -c /dev/fft128-dma-frame',
             'test ! -e environment.txt || { echo "Use a fresh bundle" >&2; exit 1; }',
             'sha256sum -c artifacts.sha256 > artifact_check.txt',
             '{ uname -a; cat /proc/sys/kernel/random/boot_id; cat /proc/cpuinfo; } > environment.txt',
             'sha256sum "$pl" "$cfar" > runtime.sha256',
             'for f in "$(dirname -- "$pl")/fft128_e14_frame.bin" "$(dirname -- "$pl")/fft128_dma_frame.ko"; do',
             '  if test -f "$f"; then sha256sum "$f"; fi', 'done > firmware_module.sha256',
             'last_log=',
             'trap \'ret=$?; if test "$ret" -ne 0 && test -n "$last_log"; then tail -n 30 "$last_log" >&2; fi\' 0']
    for name in ("single", "multi4", "close_weak"):
        source = ref.ROOT / f"benchmarks/fixtures/radarsimpy_128x128_sim_{name}_noise.rspb"
        meta = json.loads(source.with_suffix(".json").read_text(encoding="utf-8"))
        if sha(source) != meta["record_sha256"]:
            raise ValueError(f"Fixture SHA mismatch: {source}")
        original, fs = ref.read_rspb(source)
        for window in ("none", "hann"):
            case_name = f"{name}_{window}"
            weighted = original.copy()
            if window == "hann":
                weighted *= np.hanning(128)[:, None] * np.hanning(128)[None, :]
            path = out / (case_name + ".rspb")
            write_rspb(path, weighted, fs)
            wire, wire_fs = ref.read_rspb(path)
            assert wire_fs == fs
            q, scale = quantize(wire)
            fixed = integer_spectrum(q)
            expected_file = out / (case_name + ".expected.npy")
            np.save(expected_file, fixed)
            baseline = detect(ref.range_doppler_power(original, window))
            float_wire = detect(ref.range_doppler_power(wire, "none"))
            ideal = np.fft.fft2(q) / 16384
            fixed_peaks = detect(np.abs(fixed) ** 2)
            case = {"name": case_name, "window": window, "original_record": source.name,
                    "original_sha256": sha(source), "record": path.name, "record_sha256": sha(path),
                    "expected_file": expected_file.name, "expected_sha256": sha(expected_file),
                    "targets": meta["targets"], "fs_hz": fs, "input_to_q15_scale": scale,
                    "float_baseline_peaks": baseline, "float_wire_peaks": float_wire,
                    "q15_ideal_peaks": detect(np.abs(ideal) ** 2), "integer_model_peaks": fixed_peaks,
                    "integer_vs_ideal_max_q15_lsb": float(np.max(np.abs(fixed - ideal))),
                    "integer_vs_ideal_relative_l2": float(np.linalg.norm(fixed - ideal) / np.linalg.norm(ideal))}
            cases.append(case)
            pl_args = ["--input", path.name, "--output", case_name + ".pl",
                       "--warmup", str(warmup), "--repeat", str(repeat)]
            cfar_args = ["--input", case_name + ".pl.csv", "--output", case_name + ".detections.csv",
                         "--timings", case_name + ".cfar.timings.csv", "--warmup", str(warmup), "--repeat", str(repeat)]
            case["pl_arguments"] = pl_args
            case["cfar_arguments"] = cfar_args
            shell += [f"last_log={case_name}.pl.log",
                      '"$pl" --backend dma_frame --cpu0 ' + shlex.join(pl_args) + ' > "$last_log" 2>&1',
                      'grep FRAME_PASS "$last_log"', f"last_log={case_name}.cfar.log",
                      '"$cfar" --cpu0 ' + shlex.join(cfar_args) + ' > "$last_log" 2>&1',
                      'grep S1C_CFAR_COMPLETE "$last_log"']
            print(f"{case_name}: PC model peaks={len(fixed_peaks)}, matches float={fixed_peaks == baseline}")
    shell += ["echo S1C_RUN_COMPLETE"]
    with (out / "run_board.sh").open("w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(shell) + "\n")
    paths = [Path(__file__).resolve(), ref.ROOT / "tools/detection/cfar_spectrum.cpp",
             ref.ROOT / "tools/detection/cfar_reference.py", ref.ROOT / "tools/detection/make_fixture.py",
             ref.ROOT / "src/PS/receiver/cfar_ca.hpp", ref.ROOT / "src/PS/fft128/receiver.py",
             ref.ROOT / "src/PS/fft128/native_core.c", ref.ROOT / "src/PS/fft128/native_receiver.c"]
    manifest = {"experiment": "S1c", "scope": "E14 exported integer FFT -> separate C++ CFAR; correctness, no end-to-end timing",
                "window_policy": "PC symmetric Hann on original IQ -> float32 RSPB -> board Q15; no additional E14 window",
                "quantization": "max complex magnitude -> 16384, ties to even; per-stage floor/saturation, total 1/16384",
                "warmup": warmup, "repeat": repeat, "numpy": np.__version__,
                "sources": {p.relative_to(ref.ROOT).as_posix(): sha(p) for p in paths}, "cases": cases}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    files = sorted(p for p in out.iterdir() if p.is_file())
    (out / "artifacts.sha256").write_text("".join(f"{sha(p)}  {p.name}\n" for p in files), encoding="utf-8")


def timing(path, stage, repeat):
    with path.open() as f:
        rows = list(csv.DictReader(f))
    values = [float(r["wall_ms"]) for r in rows if r["stage"] == stage]
    if len(values) != repeat or not all(np.isfinite(v) and v > 0 for v in values):
        raise ValueError(f"Invalid time samples: {path}")
    return {"samples": repeat, "median_ms": float(np.median(values)), "max_ms": max(values)}


def check(out, hardware=True):
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    names = [f"{n}_{w}" for n in ("single", "multi4", "close_weak") for w in ("none", "hann")]
    if [c["name"] for c in manifest["cases"]] != names:
        raise ValueError("Expected all six S1c cases in the recorded order")
    runs = []
    for case in manifest["cases"]:
        name = case["name"]
        record = out / case["record"]
        if sha(record) != case["record_sha256"] or sha(out / case["expected_file"]) != case["expected_sha256"]:
            raise ValueError(f"Input/reference SHA mismatch: {name}")
        frame, fs = ref.read_rspb(record)
        q, scale = quantize(frame)
        expected = integer_spectrum(q)
        np.testing.assert_array_equal(expected, np.load(out / case["expected_file"], allow_pickle=False))
        meta = json.loads((out / (name + ".pl.json")).read_text())
        if hardware:
            if not (out / (name + ".pl.batch.json")).is_file():
                raise ValueError(f"Missing E14 hardware metadata; software models cannot pass the board check: {name}")
            batch = json.loads((out / (name + ".pl.batch.json")).read_text())
            if meta["backend"] != "PL_DMA_FRAME" or batch["hardware"] is not True or batch["register_abi"] != 8:
                raise ValueError(f"Expected real E14-frame output: {name}")
            for label in ("pl", "cfar"):
                if "CPU_AFFINITY=0" not in (out / (name + "." + label + ".log")).read_text():
                    raise ValueError(f"CPU0 not confirmed: {name} {label}")
        elif meta["backend"] != "SOFTWARE_MODEL (no FPGA access)":
            raise ValueError("Host check requires explicit SOFTWARE_MODEL")
        if meta["mismatched_complex_bins"] != 0 or meta["repeats"] != manifest["repeat"]:
            raise ValueError(f"Invalid E14 validation metadata: {name}")
        np.testing.assert_allclose(meta["input_to_q15_scale"], scale, rtol=1e-13)
        rows = np.loadtxt(out / (name + ".pl.csv"), delimiter=",", skiprows=1)
        d, r = np.indices((128, 128))
        np.testing.assert_array_equal(rows[:, :2], np.column_stack((d.ravel(), r.ravel())))
        actual = (rows[:, 2] + 1j * rows[:, 3]).reshape(128, 128)
        np.testing.assert_array_equal(actual, expected)
        received = np.loadtxt(out / (name + ".pl.input.csv"), delimiter=",", skiprows=1)
        np.testing.assert_array_equal(received[:, :2], rows[:, :2])
        np.testing.assert_array_equal((received[:, 2] + 1j * received[:, 3]).reshape(128, 128), frame)
        power = actual.real ** 2 + actual.imag ** 2
        cells, threshold = ref.ca_cfar_2d(power, (2, 2), (8, 8), 1e-6)
        expected_peaks = ref.cluster_peaks(power, cells)
        with (out / (name + ".detections.csv")).open() as f:
            detections = list(csv.DictReader(f))
        peaks = [(int(x["doppler_bin_unshifted"]), int(x["range_bin"])) for x in detections]
        if peaks != expected_peaks:
            raise ValueError(f"C++/NumPy CFAR mismatch: {name}")
        for row, peak in zip(detections, peaks):
            np.testing.assert_allclose(float(row["power"]), power[peak], rtol=1e-12)
            np.testing.assert_allclose(float(row["threshold"]), threshold[peak], rtol=1e-10)
        truth, false = ref.evaluate(peaks, case["targets"], 128, 128, fs)
        equivalent = [list(p) for p in peaks] == case["float_baseline_peaks"]
        runs.append({"case": name, "peaks": peaks, "truth": truth, "false_peaks": false,
                     "matches_float_baseline": equivalent,
                     "fft_component": timing(out / (name + ".pl.timings.csv"), "fft_pipeline", manifest["repeat"]),
                     "cfar_component": timing(out / (name + ".cfar.timings.csv"), "cfar", manifest["repeat"])})
        print(f"{name}: integer FFT/CFAR PASS, hit {sum(t['hit'] for t in truth)}/{len(truth)}, false {len(false)}, matches float={equivalent}")
    summary = {"evidence": "board E14 + separate board CFAR" if hardware else "PC SOFTWARE_MODEL + C++ CFAR; no FPGA",
               "scope": manifest["scope"], "end_to_end_timing_measured": False, "runs": runs}
    (out / "checked_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    if not all(r["matches_float_baseline"] for r in runs):
        raise ValueError("S1c detection equivalence failed; summary preserved")
    print("S1C_RECORDED_CHECK_PASS cases=6 hardware=" + str(hardware))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--prepare-only", action="store_true")
    group.add_argument("--check-only", action="store_true")
    group.add_argument("--model-binary", type=Path, help="prepare/run/check on PC; no FPGA")
    ap.add_argument("--cfar-binary", type=Path)
    ap.add_argument("--warmup", type=int, default=10)
    ap.add_argument("--repeat", type=int, default=100)
    args = ap.parse_args()
    if not (0 <= args.warmup <= 100000 and 1 <= args.repeat <= 1000000):
        ap.error("invalid warmup/repeat")
    if args.model_binary and not args.cfar_binary:
        ap.error("--model-binary requires --cfar-binary")
    if not args.check_only:
        prepare(args.out, args.warmup, args.repeat)
    if args.model_binary:
        pl, cfar = args.model_binary.resolve(), args.cfar_binary.resolve()
        manifest = json.loads((args.out / "manifest.json").read_text())
        for case in manifest["cases"]:
            for binary, arguments, label in [(pl, ["--backend", "model", *case["pl_arguments"]], "pl"),
                                              (cfar, case["cfar_arguments"], "cfar")]:
                log_path = args.out / (case["name"] + "." + label + ".log")
                with log_path.open("w") as log:
                    result = subprocess.run([str(binary), *arguments], cwd=args.out,
                                            stdout=log, stderr=subprocess.STDOUT, timeout=120)
                if result.returncode:
                    raise RuntimeError(log_path.read_text())
        check(args.out, hardware=False)
    elif args.check_only:
        check(args.out)


if __name__ == "__main__":
    main()
