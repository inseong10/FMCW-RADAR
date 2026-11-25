"""Write RSPB0001 recordings (same datagrams as tools/sender/sender.py) for S1 scenarios.

Frames come from cfar_reference.simulate(): per-target RadarSimPy baseband summed, plus
optional NumPy seed-42 noise. Output is deterministic; see benchmarks/fixtures/README.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cfar_reference as ref  # noqa: E402

sys.path.insert(0, str(ref.ROOT / "tools" / "sender"))
from sender import build_packet  # noqa: E402


def write_rspb(path: Path, frame: np.ndarray, fs: float) -> str:
    chirps = frame.shape[0]
    with path.open("wb") as f:
        f.write(b"RSPB0001")
        for i in range(chirps):
            packet = build_packet(frame[i], 0, i, chirps, fs)
            f.write(struct.pack("!I", len(packet)) + packet)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scenarios", type=Path, default=Path(__file__).with_name("s1a_scenarios.json"))
    ap.add_argument("--names", nargs="+", required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()
    cfg = {s["name"]: s for s in json.loads(args.scenarios.read_text(encoding="utf-8"))["scenarios"]}
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for name in args.names:
        sc = cfg[name]
        frame, fs = ref.simulate(sc["targets"], sc["chirps"], sc["samples"], sc.get("noise", False))
        path = args.out_dir / f"radarsimpy_{sc['chirps']}x{sc['samples']}_{name}.rspb"
        sha = write_rspb(path, frame, fs)
        meta = {"source": "RadarSimPy 15.5.0 per-target baseband sum (tools/detection/make_fixture.py)",
                "scenario": name, "shape": [1, sc["chirps"], sc["samples"]], "sample_rate_hz": fs,
                "targets": sc["targets"], "noise": sc.get("noise", False),
                "noise_model": "NumPy default_rng(42) circular complex Gaussian, RMS 1.79e-3" if sc.get("noise") else None,
                "record_sha256": sha}
        path.with_suffix(".json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        print(name, path.name, sha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
