"""S1a PC reference: Range-Doppler map, 2-D CA-CFAR and ground-truth comparison.

Input is either the committed RSPB recording or a RadarSimPy scenario generated with
the same radar as tools/sender/sender.py. Bins follow the board layout: map[doppler, range],
no fftshift, Doppler index d maps to signed bin d (d < N/2) or d - N.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

import numpy as np

C = 299_792_458.0
F0, F1, CHIRP_S, PRP_S = 24.0e9, 24.1e9, 80e-6, 100e-6
SLOPE = (F1 - F0) / CHIRP_S
LAMBDA = C / ((F0 + F1) / 2)
NOISE_RMS = 1.79e-3
HEADER = struct.Struct("!4sBBHIIId")
ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------- input
def read_rspb(path: Path) -> tuple[np.ndarray, float]:
    with path.open("rb") as f:
        if f.read(8) != b"RSPB0001":
            raise ValueError("not an RSPB0001 record")
        rows, fs, chirps = {}, None, None
        while (size := f.read(4)):
            packet = f.read(struct.unpack("!I", size)[0])
            magic, _, _, _, index, chirps, samples, fs = HEADER.unpack_from(packet)
            if magic != b"RSPY":
                raise ValueError("bad datagram magic")
            iq = np.frombuffer(packet, ">f4", offset=HEADER.size).astype(np.float64)
            rows[index] = iq[0::2] + 1j * iq[1::2]
    if len(rows) != chirps:
        raise ValueError(f"{len(rows)} of {chirps} chirps present")
    return np.stack([rows[i] for i in range(chirps)]), float(fs)


def simulate(targets: list[dict], chirps: int, samples: int, noise: bool) -> tuple[np.ndarray, float]:
    """Sum of single-target runs (free tier allows 2 targets per run; point targets add linearly).

    RadarSimPy returns 'baseband' without receiver noise and 'noise' separately. The committed
    fixture (sender.py) sends 'baseband' only, i.e. it is noise-free. RadarSimPy's 'noise' changed
    between processes despite seed=42 (baseband did not), so noise is generated here with NumPy
    (seed 42) as circular complex Gaussian at NOISE_RMS, the RMS of RadarSimPy's noise output
    for this radar (two runs: 1.7982e-3, 1.7890e-3).
    """
    sys.path.insert(0, str(ROOT / "tools" / "sender"))
    from sender import create_radar, load_radarsimpy  # noqa: E402

    rs = load_radarsimpy()
    radar = create_radar(chirps, rs, samples=samples)
    total, noise_part = 0, None
    for t in targets:
        out = rs.sim_radar(radar, [{"location": [t["range_m"], 0, 0], "speed": [t["speed_mps"], 0, 0],
                                    "rcs": t.get("rcs", 10), "phase": 0}])
        total = total + np.asarray(out["baseband"])[0]
    if noise:
        rng = np.random.default_rng(42)
        total = total + NOISE_RMS / np.sqrt(2) * (rng.standard_normal(total.shape)
                                                  + 1j * rng.standard_normal(total.shape))
    return total, float(radar.receiver.bb_prop["fs"])


def quantize_q15(frame: np.ndarray) -> np.ndarray:
    """Same rule as the board path: one scale so the largest |I| or |Q| maps to 32767."""
    peak = max(np.abs(frame.real).max(), np.abs(frame.imag).max())
    s = 32767.0 / peak
    return (np.clip(np.round(frame.real * s), -32768, 32767)
            + 1j * np.clip(np.round(frame.imag * s), -32768, 32767))


# ---------------------------------------------------------------- processing
def range_doppler_power(frame: np.ndarray, window: str) -> np.ndarray:
    chirps, samples = frame.shape
    if window == "hann":
        frame = frame * np.hanning(chirps)[:, None] * np.hanning(samples)[None, :]
    rd = np.fft.fft(np.fft.fft(frame, axis=1), axis=0)
    return (rd.real ** 2 + rd.imag ** 2)


def ca_cfar_2d(power: np.ndarray, guard: tuple[int, int], train: tuple[int, int],
               pfa: float) -> tuple[np.ndarray, np.ndarray]:
    """Square-law CA-CFAR. Doppler axis wraps (circular), range axis edges use available cells."""
    gd, gr = guard
    td, tr = train
    hd, hr = gd + td, gr + tr
    kernel = np.ones((2 * hd + 1, 2 * hr + 1))
    kernel[td:td + 2 * gd + 1, tr:tr + 2 * gr + 1] = 0
    nd, nr = power.shape
    padded = np.pad(power, ((hd, hd), (0, 0)), mode="wrap")
    padded = np.pad(padded, ((0, 0), (hr, hr)), mode="constant")
    valid = np.pad(np.ones_like(power), ((hd, hd), (0, 0)), mode="wrap")
    valid = np.pad(valid, ((0, 0), (hr, hr)), mode="constant")
    total = np.zeros_like(power)
    count = np.zeros_like(power)
    for i, j in zip(*np.nonzero(kernel)):
        total += padded[i:i + nd, j:j + nr]
        count += valid[i:i + nd, j:j + nr]
    alpha = count * (pfa ** (-1.0 / count) - 1.0)
    threshold = alpha * total / count
    return power > threshold, threshold


def os_alpha(k: int, n: int, pfa: float) -> float:
    """Square-law OS-CFAR scale: Pfa = prod_{i=0}^{k-1} (n-i)/(n-i+T), solved by bisection."""
    def pfa_of(t):
        return np.exp(np.sum(np.log((n - np.arange(k)) / (n - np.arange(k) + t))))
    lo, hi = 0.0, 1e6
    for _ in range(200):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if pfa_of(mid) > pfa else (lo, mid)
    return hi


def os_cfar_2d(power: np.ndarray, guard: tuple[int, int], train: tuple[int, int],
               pfa: float, k_frac: float = 0.75) -> tuple[np.ndarray, np.ndarray]:
    """Square-law OS-CFAR on the same window as ca_cfar_2d; Doppler wraps, range edges are reflected."""
    gd, gr = guard
    td, tr = train
    hd, hr = gd + td, gr + tr
    mask = np.ones((2 * hd + 1, 2 * hr + 1), bool)
    mask[td:td + 2 * gd + 1, tr:tr + 2 * gr + 1] = False
    padded = np.pad(power, ((hd, hd), (0, 0)), mode="wrap")
    padded = np.pad(padded, ((0, 0), (hr, hr)), mode="reflect")
    win = np.lib.stride_tricks.sliding_window_view(padded, mask.shape)[..., mask]
    n = win.shape[-1]
    k = int(round(k_frac * n))
    stat = np.partition(win, k - 1, axis=-1)[..., k - 1]
    threshold = os_alpha(k, n, pfa) * stat
    return power > threshold, threshold


def cluster_peaks(power: np.ndarray, detections: np.ndarray) -> list[tuple[int, int]]:
    """One report per local maximum (3x3, Doppler wraps) among detected cells."""
    peaks = []
    nd, nr = power.shape
    for d, r in zip(*np.nonzero(detections)):
        nb = power[[(d - 1) % nd, d, (d + 1) % nd]][:, max(r - 1, 0):r + 2]
        if power[d, r] >= nb.max():
            peaks.append((int(d), int(r)))
    return sorted(peaks, key=lambda p: -power[p])


# ---------------------------------------------------------------- truth
def expected_bins(t: dict, chirps: int, samples: int, fs: float) -> tuple[float, float]:
    range_bin = 2 * t["range_m"] * SLOPE / C / (fs / samples)
    doppler_bin = (2 * t["speed_mps"] / LAMBDA) * chirps * PRP_S
    return doppler_bin, range_bin


def signed(d: int, n: int) -> int:
    return d if d < n // 2 else d - n


def evaluate(peaks, truths, chirps, samples, fs, tol=1.0):
    rows, used = [], set()
    for t in truths:
        ed, er = expected_bins(t, chirps, samples, fs)
        best = None
        for k, (d, r) in enumerate(peaks):
            dd = signed(d, chirps) - ed
            dd = (dd + chirps / 2) % chirps - chirps / 2
            err = max(abs(dd), abs(r - er))
            if err <= tol and (best is None or err < best[1]):
                best = (k, err)
        if best is not None:
            used.add(best[0])
        d, r = peaks[best[0]] if best else (None, None)
        rows.append({"truth": t, "expected_doppler_bin": round(ed, 3), "expected_range_bin": round(er, 3),
                     "detected": [d, r] if best else None,
                     "range_m": None if best is None else r * (fs / samples) * C / (2 * SLOPE),
                     "speed_mps": None if best is None else signed(d, chirps) / (chirps * PRP_S) * LAMBDA / 2,
                     "hit": best is not None})
    false = [list(p) for k, p in enumerate(peaks) if k not in used]
    return rows, false


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scenarios", type=Path, default=Path(__file__).with_name("s1a_scenarios.json"))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--window", choices=["none", "hann"], nargs="+", default=["none", "hann"])
    ap.add_argument("--guard", type=int, nargs=2, default=[2, 2], metavar=("DOPPLER", "RANGE"))
    ap.add_argument("--train", type=int, nargs=2, default=[8, 8], metavar=("DOPPLER", "RANGE"))
    ap.add_argument("--method", choices=["ca", "os"], nargs="+", default=["ca", "os"])
    ap.add_argument("--pfa", type=float, default=1e-6)
    args = ap.parse_args()
    cfg = json.loads(args.scenarios.read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)
    summary = {"params": {"guard": args.guard, "train": args.train, "pfa": args.pfa,
                          "lambda_m": LAMBDA, "slope_hz_per_s": SLOPE}, "runs": []}
    for sc in cfg["scenarios"]:
        if "rspb" in sc:
            path = ROOT / sc["rspb"]
            frame, fs = read_rspb(path)
            source = {"rspb": sc["rspb"], "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        else:
            frame, fs = simulate(sc["targets"], sc["chirps"], sc["samples"], sc.get("noise", False))
            source = {"simulated": True, "seed": 42, "noise": sc.get("noise", False)}
        chirps, samples = frame.shape
        np.save(args.out / f"{sc['name']}_frame.npy", frame)
        source["frame_sha256"] = hashlib.sha256(np.ascontiguousarray(frame).tobytes()).hexdigest()
        for quant in ("float", "q15_input"):
            data = quantize_q15(frame) if quant == "q15_input" else frame
            for window, method in [(w, m) for w in args.window for m in args.method]:
                power = range_doppler_power(data, window)
                cfar = ca_cfar_2d if method == "ca" else os_cfar_2d
                det, _ = cfar(power, tuple(args.guard), tuple(args.train), args.pfa)
                peaks = cluster_peaks(power, det)
                rows, false = evaluate(peaks, sc["targets"], chirps, samples, fs)
                run = {"scenario": sc["name"], "input": quant, "window": window, "method": method, "source": source,
                       "shape": [chirps, samples], "fs_hz": fs, "detected_cells": int(det.sum()),
                       "peaks": len(peaks), "targets": rows, "false_peaks": false[:50],
                       "false_count": len(false), "all_hit": all(r["hit"] for r in rows)}
                summary["runs"].append(run)
                print(f"{sc['name']:22s} {quant:9s} {window:5s} {method} hit {sum(r['hit'] for r in rows)}/{len(rows)}"
                      f"  peaks {len(peaks):3d}  false {len(false):3d}  cells {int(det.sum())}")
                np.save(args.out / f"{sc['name']}_{quant}_{window}_power.npy", power.astype(np.float32))
    (args.out / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
