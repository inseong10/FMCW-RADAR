"""Create a synthetic complex-tone RSPB0001 frame for offline benchmarks."""
import argparse
import importlib.util
from pathlib import Path
import struct

import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pulses", type=int, default=160)
    parser.add_argument("--samples", type=int, default=160)
    parser.add_argument("--output", type=Path, default=Path("benchmarks/data/frame.bin"))
    args = parser.parse_args()
    if not 1 <= args.pulses <= 100_000 or not 1 <= args.samples <= 8184:
        parser.error("pulses must be 1..100000 and samples must be 1..8184")
    source = Path(__file__).resolve().parents[1] / "tools/sender/sender.py"
    spec = importlib.util.spec_from_file_location("radar_sender", source)
    sender = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sender)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("wb") as stream:
        stream.write(b"RSPB0001")
        for chirp in range(args.pulses):
            tone = np.exp(2j*np.pi*(3*np.arange(args.samples)/args.samples-2*chirp/args.pulses))
            packet = sender.build_packet(tone, 0, chirp, args.pulses, 2e6)
            stream.write(struct.pack("!I", len(packet)))
            stream.write(packet)
    print(f"Saved synthetic {args.pulses}x{args.samples} frame: {args.output}")


if __name__ == "__main__":
    main()
