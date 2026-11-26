#!/usr/bin/env python3
"""S2a fixed-record replay with RSPY v2 run/frame IDs; standard library only.

Frames use absolute deadlines and record lateness and overruns. Catch-up after
an overrun invalidates an offered-load claim even when the receiver has no drops.
"""
import argparse
import array
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
from adc16_record import ADC_PROFILE, read_adc_frame, row_bytes

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


def packet_v3(row, chirp, fs, run_id, frame_id, sender_ns, pulses=128, samples=128):
    # S3a-1: header pulses/samples carry the frame shape (M chirps x N samples).
    if len(row) != row_bytes(samples) or not 0 <= chirp < pulses or not math.isfinite(fs) or fs <= 0:
        raise ValueError('Invalid ADC16 row')
    return (HEADER.pack(b'RSPY', 3, 2, 0, run_id, frame_id, chirp, pulses, samples, fs, sender_ns)
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
    pulses = len(packets)
    samples = len(packets[0])//4 if adc else 128
    wait_mode = getattr(args, "wait_mode", "sleep")
    destination = (str(ipaddress.IPv4Address(args.ip)), args.port)
    if (not 1 <= args.port <= 65535 or not 1 <= args.frames <= 100000 or
            not 1 <= args.run_id < 2**64 or not math.isfinite(args.period_ms) or args.period_ms <= 0 or
            not math.isfinite(args.chirp_gap_us) or args.chirp_gap_us < 0 or
            args.chirp_gap_us*(pulses-1) >= args.period_ms*1000 or not 0 <= args.drop_frame <= args.frames or
            not math.isfinite(getattr(args, "chirp_late_p99_limit_us", 10)) or
            getattr(args, "chirp_late_p99_limit_us", 10) <= 0 or
            wait_mode not in ("sleep", "spin") or
            getattr(args, "schedule", "absolute") not in ("absolute", "reanchor")):
        raise ValueError("Invalid run, period, packet spacing or drop-frame")
    if args.out.exists():
        raise ValueError("Use a new sender JSON path")
    period = round(args.period_ms*1e6)
    gap = round(args.chirp_gap_us*1000)
    start = time.monotonic_ns()+100000000
    wall_start = time.monotonic_ns()
    cpu_start = time.process_time_ns()
    rows = []
    p99_limit = round(getattr(args, "chirp_late_p99_limit_us", 10)*1000)
    max_limit = period//10  # same 10%-of-period bound as frame-start lateness
    report_ns = 100000      # reported only: chirps at least one PRP-equivalent 100us late
    detail = getattr(args, "chirp_detail", False)
    all_late = array.array("q")
    send_max = 0
    # reanchor schedule (2026-11-26 user decision): a deadline missed by more than the jitter
    # limit moves the schedule to the actual send time instead of catching up, so spacing is
    # never compressed by more than the jitter limit; a stall only inserts a gap.
    reanchor = bool(gap) and getattr(args, "schedule", "absolute") == "reanchor"
    frame_anchor = start
    prev_t0 = None          # previous chirp send time (any frame), for spacing checks
    prev_first = None
    frame_reanchors = 0
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        for frame_id in range(1, args.frames+1):
            intended = frame_anchor+(frame_id-1)*period
            frame_moved = False
            if reanchor and prev_t0 is not None and prev_t0+gap > intended:
                # A stall in the previous frame pushed its last chirp past this frame's slot.
                frame_anchor += prev_t0+gap-intended
                intended = prev_t0+gap
                frame_moved = True
            wait_until(intended, wait_mode)
            first = time.monotonic_ns()
            if reanchor and first-intended > p99_limit:
                frame_anchor += first-intended
                frame_moved = True
            frame_reanchors += frame_moved
            sent = 0
            if not gap:
                # Burst path: unchanged from the S2b/S2a-int16 sender.
                for i, packet in enumerate(packets):
                    # Deliberately omit one chirp, retaining the expected frame ID.
                    if frame_id == args.drop_frame and i == 64:
                        continue
                    wire = (packet_v3(packet, i, rate, args.run_id, frame_id, first, pulses, samples) if adc else
                            packet_v2(packet, args.run_id, frame_id, first))
                    sent += sock.sendto(wire, destination)
                rows.append({"frame_id": frame_id, "intended_ns": intended, "first_send_ns": first,
                             "last_send_ns": time.monotonic_ns(), "bytes": sent})
                continue
            # Paced path: chirp i is due at first+i*gap (absolute, no catch-up shift).
            # The packet is built before its deadline so lateness is wait+clock only.
            late = []
            frame_send_max = 0
            chirp_anchor = first
            chirp_reanchors = 0
            min_spacing = None
            for i, packet in enumerate(packets):
                if frame_id == args.drop_frame and i == 64:
                    continue
                wire = (packet_v3(packet, i, rate, args.run_id, frame_id, first, pulses, samples) if adc else
                        packet_v2(packet, args.run_id, frame_id, first))
                due = chirp_anchor+i*gap
                wait_until(due, wait_mode)
                t0 = time.monotonic_ns()
                sent += sock.sendto(wire, destination)
                t1 = time.monotonic_ns()
                late.append(t0-due)
                frame_send_max = max(frame_send_max, t1-t0)
                if prev_t0 is not None:
                    d = t0-prev_t0
                    min_spacing = d if min_spacing is None else min(min_spacing, d)
                prev_t0 = t0
                if reanchor and t0-due > p99_limit:
                    chirp_anchor = t0-i*gap
                    chirp_reanchors += 1
            last = time.monotonic_ns()
            all_late.extend(late)
            send_max = max(send_max, frame_send_max)
            row = {"frame_id": frame_id, "intended_ns": intended, "first_send_ns": first,
                   "last_send_ns": last, "bytes": sent, "chirps_sent": len(late),
                   "chirp_late_max_ns": max(late),
                   "chirp_late_total_max_ns": first-intended+max(late),
                   "chirp_late_ge_100us": sum(v >= report_ns for v in late),
                   "chirp_send_max_ns": frame_send_max}
            if reanchor:
                row.update({"frame_reanchored": frame_moved, "chirp_reanchors": chirp_reanchors,
                            "stall_max_ns": max(first-intended, max(late)),
                            "min_chirp_spacing_ns": min_spacing,
                            "frame_spacing_ns": None if prev_first is None else first-prev_first})
            prev_first = first
            if detail:
                row["chirp_late_ns"] = late
            rows.append(row)
    cpu_end = time.process_time_ns()
    wall_end = time.monotonic_ns()
    summary = {"schema": 1, "run_id": args.run_id, "destination": list(destination),
               "record": str(args.record), "record_sha256": hashlib.sha256(args.record.read_bytes()).hexdigest(),
               "fs": rate, "frames": args.frames, "period_ms": args.period_ms,
               "chirp_gap_us": args.chirp_gap_us, "drop_frame": args.drop_frame,
               "input_format": "adc16" if adc else "float32", "protocol_version": 3 if adc else 2,
               "adc_profile": adc_profile, "pulses": pulses, "samples": samples,
               "wait_mode": wait_mode,
               "process_cpu_pct_one_core": 100*(cpu_end-cpu_start)/(wall_end-wall_start),
               "python": platform.python_version(),
               "sender_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "max_lateness_ms": max((r["first_send_ns"]-r["intended_ns"])/1e6 for r in rows),
               "overrun_frames": sum(r["last_send_ns"] >= r["intended_ns"]+period for r in rows),
               "schedule": rows}
    if gap:
        ordered = sorted(all_late)
        q = lambda p: ordered[min(len(ordered)-1, max(0, math.ceil(p*len(ordered))-1))]/1e6
        total_max = max(r["chirp_late_total_max_ns"] for r in rows)
        summary["chirp_pacing"] = {
            "definition": "jitter lateness = time.monotonic_ns() just before sendto - (frame first_send_ns + chirp*gap); "
                          "total lateness adds frame start lateness (first_send_ns - intended_ns); "
                          "sender-side only, not wire/board arrival spacing",
            "rule": "valid = jitter P99 < p99 limit and total max < 10% of period (2026-11-26 user decision); "
                    "frame-boundary overrun_frames is reported, not a validity condition in paced mode",
            "gap_us": args.chirp_gap_us, "late_p99_limit_us": p99_limit/1000, "late_max_limit_ms": max_limit/1e6,
            "chirps": len(ordered), "late_median_ms": q(.5), "late_p99_ms": q(.99), "late_p99_9_ms": q(.999),
            "late_max_ms": ordered[-1]/1e6, "late_total_max_ms": total_max/1e6,
            "chirps_ge_100us": sum(r["chirp_late_ge_100us"] for r in rows),
            "frames_with_chirp_ge_100us": sum(r["chirp_late_ge_100us"] > 0 for r in rows),
            "frame_boundary_overruns": summary["overrun_frames"],
            "sendto_max_ms": send_max/1e6, "detail": bool(detail),
            "valid": ordered[min(len(ordered)-1, max(0, math.ceil(.99*len(ordered))-1))] < p99_limit and total_max < max_limit}
        summary["chirp_pacing"]["schedule"] = "reanchor" if reanchor else "absolute"
        if reanchor:
            c = summary["chirp_pacing"]
            p99_ok = ordered[min(len(ordered)-1, max(0, math.ceil(.99*len(ordered))-1))] < p99_limit
            spacings = [r["min_chirp_spacing_ns"] for r in rows if r["min_chirp_spacing_ns"] is not None]
            fsp = [r["frame_spacing_ns"] for r in rows if r["frame_spacing_ns"] is not None]
            stall_frames = sum(r["stall_max_ns"] >= max_limit for r in rows)
            min_chirp = min(spacings) if spacings else None
            min_frame = min(fsp) if fsp else None
            c.update({
                "rule": "reanchor schedule (2026-11-26 user decision): valid = jitter P99 < p99 limit and "
                        "min chirp spacing >= gap - p99 limit and min frame spacing >= period - p99 limit and "
                        "stall frames (lateness >= 10% of period) <= 1% of frames; late_total_max_ms is "
                        "reported only; lateness is measured against the re-anchored schedule",
                "reanchor_threshold_us": p99_limit/1000, "stall_threshold_ms": max_limit/1e6,
                "stall_frames": stall_frames, "stall_frames_limit": args.frames//100,
                "stall_max_ms": max(r["stall_max_ns"] for r in rows)/1e6,
                "chirp_reanchors": sum(r["chirp_reanchors"] for r in rows), "frame_reanchors": frame_reanchors,
                "min_chirp_spacing_us": None if min_chirp is None else min_chirp/1000,
                "min_frame_spacing_ms": None if min_frame is None else min_frame/1e6,
                "effective_period_ms": ((rows[-1]["first_send_ns"]-rows[0]["first_send_ns"])/(len(rows)-1)/1e6
                                        if len(rows) > 1 else None),
                "valid": (p99_ok and (min_chirp is None or min_chirp >= gap-p99_limit) and
                          (min_frame is None or min_frame >= period-p99_limit) and
                          stall_frames <= args.frames//100)})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2)+"\n", encoding="utf-8")
    print(f"S2A_SENT frames={args.frames} run_id={args.run_id} overruns={summary['overrun_frames']} "
          f"wait={wait_mode} max_late_ms={summary['max_lateness_ms']:.3f}")
    if gap:
        c = summary["chirp_pacing"]
        print(f"S2A_CHIRP_PACING gap_us={c['gap_us']} p99_us={c['late_p99_ms']*1e3:.2f}"
              f"(<{c['late_p99_limit_us']:g}) total_max_ms={c['late_total_max_ms']:.4f}(<{c['late_max_limit_ms']:g}) "
              f"ge_100us={c['chirps_ge_100us']} boundary_overruns={c['frame_boundary_overruns']} valid={c['valid']}")
        if c["schedule"] == "reanchor":
            print(f"S2A_REANCHOR stall_frames={c['stall_frames']}(<={c['stall_frames_limit']}) "
                  f"stall_max_ms={c['stall_max_ms']:.3f} min_chirp_us={c['min_chirp_spacing_us']} "
                  f"min_frame_ms={c['min_frame_spacing_ms']} eff_period_ms={c['effective_period_ms']} "
                  f"reanchors={c['chirp_reanchors']}/{c['frame_reanchors']} valid={c['valid']}")


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
    p.add_argument("--chirp-late-p99-limit-us", type=float, default=10,
                   help="paced mode: chirp jitter P99 must be below this; total max must be below 10%% of period")
    p.add_argument("--chirp-detail", action="store_true",
                   help="paced mode: store every chirp lateness in the JSON (large for long runs)")
    p.add_argument("--schedule", choices=["absolute", "reanchor"], default="absolute",
                   help="paced mode: reanchor moves the schedule to the actual time after a miss "
                        "larger than the jitter limit (no catch-up burst)")
    p.add_argument("--drop-frame", type=int, default=0, help="test only: omit chirp 64 of this frame")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    try:
        send(args)
    except (ValueError, OSError) as e:
        p.exit(1, str(e)+"\n")


if __name__ == "__main__":
    main()
