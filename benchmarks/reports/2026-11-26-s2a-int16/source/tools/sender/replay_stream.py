#!/usr/bin/env python3
"""S2a fixed-record replay with RSPY v2 run/frame IDs; standard library only.

Frames use absolute deadlines and record lateness and overruns. Catch-up after
an overrun invalidates an offered-load claim even when the receiver has no drops.
"""
import argparse
import hashlib
import ipaddress
import json
import math
from pathlib import Path
import platform
import socket
import struct
import time

from replay_udp import read_frame
from adc16_record import ADC_PROFILE, ROW_BYTES, read_adc_frame

HEADER = struct.Struct("!4sBBHQQIIIdQ")
PROFILE = struct.Struct('!I')


def packet_v2(packet, run_id, frame_id, sender_ns):
    """Reuse the validated v1 payload without an extra float conversion."""
    magic, version, dtype, channel, chirp, pulses, samples, fs = struct.unpack_from("!4sBBHIIId", packet)
    if (magic, version, dtype, channel, pulses, samples) != (b"RSPY", 1, 1, 0, 128, 128):
        raise ValueError("Expected a v1 128x128 channel-0 record")
    if len(packet) != 28+128*8 or not 0 <= chirp < 128 or not math.isfinite(fs) or fs <= 0:
        raise ValueError("Invalid source packet")
    return HEADER.pack(b"RSPY", 2, 1, 0, run_id, frame_id, chirp, 128, 128, fs, sender_ns)+packet[28:]


def packet_v3(row, chirp, fs, run_id, frame_id, sender_ns):
    if len(row) != ROW_BYTES or not 0 <= chirp < 128 or not math.isfinite(fs) or fs <= 0:
        raise ValueError('Invalid ADC16 row')
    return (HEADER.pack(b'RSPY', 3, 2, 0, run_id, frame_id, chirp, 128, 128, fs, sender_ns)
            + PROFILE.pack(ADC_PROFILE) + row)


def wait_until(deadline, mode="sleep", clock=time.monotonic_ns, sleep=time.sleep):
    # Absolute deadlines stay unchanged after an overshoot in either mode.
    if mode == "sleep":
        remaining = (deadline-clock())/1e9
        if remaining > 0:
            sleep(remaining)
    elif mode == "spin":
        while clock() < deadline:
            pass
    else:
        raise ValueError("Invalid wait mode")


def send(args):
    with args.record.open('rb') as stream:
        adc = stream.read(8) == b'RSPB0002'
    if adc:
        packets, rate, adc_profile = read_adc_frame(args.record)
    else:
        packets, rate = read_frame(args.record)
        adc_profile = None
    wait_mode = getattr(args, "wait_mode", "sleep")
    destination = (str(ipaddress.IPv4Address(args.ip)), args.port)
    if (not 1 <= args.port <= 65535 or not 1 <= args.frames <= 100000 or
            not 1 <= args.run_id < 2**64 or not math.isfinite(args.period_ms) or args.period_ms <= 0 or
            not math.isfinite(args.chirp_gap_us) or args.chirp_gap_us < 0 or
            args.chirp_gap_us*127 >= args.period_ms*1000 or not 0 <= args.drop_frame <= args.frames or
            wait_mode not in ("sleep", "spin")):
        raise ValueError("Invalid run, period, packet spacing or drop-frame")
    if args.out.exists():
        raise ValueError("Use a new sender JSON path")
    period = round(args.period_ms*1e6)
    gap = round(args.chirp_gap_us*1000)
    start = time.monotonic_ns()+100000000
    wall_start = time.monotonic_ns()
    cpu_start = time.process_time_ns()
    rows = []
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        for frame_id in range(1, args.frames+1):
            intended = start+(frame_id-1)*period
            wait_until(intended, wait_mode)
            first = time.monotonic_ns()
            sent = 0
            for i, packet in enumerate(packets):
                if gap:
                    wait_until(first+i*gap, wait_mode)
                # Deliberately omit one chirp, retaining the expected frame ID.
                if frame_id == args.drop_frame and i == 64:
                    continue
                wire = (packet_v3(packet, i, rate, args.run_id, frame_id, first) if adc else
                        packet_v2(packet, args.run_id, frame_id, first))
                sent += sock.sendto(wire, destination)
            rows.append({"frame_id": frame_id, "intended_ns": intended, "first_send_ns": first,
                         "last_send_ns": time.monotonic_ns(), "bytes": sent})
    cpu_end = time.process_time_ns()
    wall_end = time.monotonic_ns()
    summary = {"schema": 1, "run_id": args.run_id, "destination": list(destination),
               "record": str(args.record), "record_sha256": hashlib.sha256(args.record.read_bytes()).hexdigest(),
               "fs": rate, "frames": args.frames, "period_ms": args.period_ms,
               "chirp_gap_us": args.chirp_gap_us, "drop_frame": args.drop_frame,
               "input_format": "adc16" if adc else "float32", "protocol_version": 3 if adc else 2,
               "adc_profile": adc_profile,
               "wait_mode": wait_mode,
               "process_cpu_pct_one_core": 100*(cpu_end-cpu_start)/(wall_end-wall_start),
               "python": platform.python_version(),
               "sender_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "max_lateness_ms": max((r["first_send_ns"]-r["intended_ns"])/1e6 for r in rows),
               "overrun_frames": sum(r["last_send_ns"] >= r["intended_ns"]+period for r in rows),
               "schedule": rows}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2)+"\n", encoding="utf-8")
    print(f"S2A_SENT frames={args.frames} run_id={args.run_id} overruns={summary['overrun_frames']} "
          f"wait={wait_mode} max_late_ms={summary['max_lateness_ms']:.3f}")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("record", type=Path)
    p.add_argument("--ip", default="10.0.0.3")
    p.add_argument("--port", type=int, default=5000)
    p.add_argument("--frames", type=int, default=20)
    p.add_argument("--run-id", type=int, required=True)
    p.add_argument("--period-ms", type=float, default=50)
    p.add_argument("--wait-mode", choices=["sleep", "spin"], default="sleep",
                   help="spin uses a sender CPU while waiting; lateness/overrun checks still apply")
    p.add_argument("--chirp-gap-us", type=float, default=0,
                   help="0 sends a burst; 100 approximates the nominal chirp cadence")
    p.add_argument("--drop-frame", type=int, default=0, help="test only: omit chirp 64 of this frame")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    try:
        send(args)
    except (ValueError, OSError) as e:
        p.exit(1, str(e)+"\n")


if __name__ == "__main__":
    main()
