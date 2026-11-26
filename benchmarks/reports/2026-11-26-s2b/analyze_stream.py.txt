#!/usr/bin/env python3
"""Validate S2a trace integrity and summarize observed latency, never infer throughput."""
import argparse
from collections import Counter
import csv
import json
import math
from pathlib import Path


def fields(path):
    return dict(line.split("=", 1) for line in path.read_text(encoding="utf-8").splitlines() if "=" in line)


def percentile(values, p):
    ordered = sorted(values)
    i = (len(ordered)-1)*p
    lo = int(i)
    return ordered[lo]+(ordered[min(lo+1, len(ordered)-1)]-ordered[lo])*(i-lo)


def statistics(values):
    return {"count": len(values), "median_ms": percentile(values, .5),
            "p99_ms": percentile(values, .99), "max_ms": max(values)} if values else None


def analyze(out, sender=None):
    env = fields(out/"environment.txt")
    counters = fields(out/"counters.txt")
    expected = int(env["frames"])
    with (out/"frames.csv").open(newline="") as f:
        rows = list(csv.DictReader(f))
    if [int(r["frame_id"]) for r in rows] != list(range(1, expected+1)):
        raise ValueError("Frame trace must account for every expected ID exactly once")
    status = Counter(r["status"] for r in rows)
    known = {"processed", "missing", "partial", "partial_evicted", "queue_full", "queued"}
    if set(status)-known:
        raise ValueError("Unknown frame status")
    processed = [r for r in rows if r["status"] == "processed"]
    stages = ["first_rx_ns", "complete_ns", "process_start_ns", "prepared_ns",
              "fft_done_ns", "cfar_done_ns", "output_done_ns"]
    for r in processed:
        ticks = [int(r[k]) for k in stages]
        kernel = int(r["first_kernel_ns"])
        if int(r["packets"]) != 128 or min(ticks) <= 0 or ticks != sorted(ticks) or kernel <= 0:
            raise ValueError("Invalid processed-frame timestamps/count")
        if kernel > ticks[0]+1000000 or kernel > ticks[-1]:
            raise ValueError("Kernel clock mapping is inconsistent")
    with (out/"detections.csv").open(newline="") as f:
        detections = list(csv.DictReader(f))
    by_id = {}
    for d in detections:
        frame_id = int(d["frame_id"])
        if int(d["run_id"]) != int(env["run_id"]):
            raise ValueError("Wrong run ID in detections")
        if not all(math.isfinite(float(d[k])) and float(d[k]) >= 0 for k in ("power", "threshold")):
            raise ValueError("Invalid detection power")
        by_id.setdefault(frame_id, []).append(d)
    if set(by_id) != {int(r["frame_id"]) for r in processed}:
        raise ValueError("Output frame IDs do not match processed frames")
    for r in processed:
        ds = by_id[int(r["frame_id"])]
        actual = [(int(d["doppler_bin"]), int(d["range_bin"])) for d in ds]
        if int(r["peaks"]) == 0:
            if actual != [(-1, -1)]:
                raise ValueError("Missing empty-output sentinel")
        elif len(ds) != int(r["peaks"]) or len(set(actual)) != len(actual) or any(
                not (0 <= d < 128 and 0 <= b < 128) for d, b in actual):
            raise ValueError("Invalid detection count/bins")
    intervals = {
        "first_kernel_to_output": ("first_kernel_ns", "output_done_ns"),
        "complete_to_output": ("complete_ns", "output_done_ns"),
        "queue_wait": ("complete_ns", "process_start_ns"),
        "preparation": ("process_start_ns", "prepared_ns"),
        "fft_transfer": ("prepared_ns", "fft_done_ns"),
        "power_cfar": ("fft_done_ns", "cfar_done_ns"),
        "output_flush": ("cfar_done_ns", "output_done_ns"),
    }
    metrics = {k: statistics([(int(r[b])-int(r[a]))/1e6 for r in processed])
               for k, (a, b) in intervals.items()}
    with (out/"resources.csv").open(newline="") as f:
        resources = list(csv.DictReader(f))
    for r in resources:
        if int(r["start_ns"]) >= int(r["end_ns"]) or int(r["rss_bytes"]) <= 0 or any(
                not math.isfinite(float(r[k])) or float(r[k]) < 0 for k in
                ("process_cpu_pct_one_core", "system_cpu_pct")):
            raise ValueError("Invalid resource sample")
    if not resources:
        raise ValueError("Missing resource samples")
    active = [r for r in resources if processed and int(r["end_ns"]) > min(int(x["first_rx_ns"]) for x in processed)
              and int(r["start_ns"]) < max(int(x["output_done_ns"]) for x in processed)]
    invalidating = [k for k in ("invalid", "metadata_errors", "kernel_drops", "kernel_missing", "clock_errors",
                               "failed", "interrupted") if int(counters[k])]
    result = {"schema": 1, "backend": env["backend"], "hardware": env["hardware"] == "1",
              "diagnostic_probe": env.get("diagnostic_probe", "0") == "1",
              "expected": expected, "status_counts": dict(status), "counters": counters,
              "trace_valid": not invalidating, "invalidating_counters": invalidating,
              "zero_drops": len(processed) == expected, "metrics": metrics,
              "resource_samples": len(resources), "active_resource_samples": len(active),
              "max_rss_bytes": max(int(r["rss_bytes"]) for r in resources),
              "scope": "kernel first-packet -> per-frame CSV flush; includes acquisition/queue/preparation; no fsync",
              "continuous_acceptance": "not evaluated by S2a"}
    if sender:
        sent = json.loads(sender.read_text(encoding="utf-8"))
        if sent["run_id"] != int(env["run_id"]) or sent["frames"] != expected:
            raise ValueError("Sender/receiver identity mismatch")
        result["sender"] = {k: sent[k] for k in ("period_ms", "chirp_gap_us", "max_lateness_ms", "overrun_frames", "drop_frame")}
        result["offered_load_valid"] = not sent["overrun_frames"] and sent["max_lateness_ms"] < sent["period_ms"]*.1
    (out/"summary.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("out", type=Path)
    p.add_argument("--sender", type=Path)
    a = p.parse_args()
    r = analyze(a.out, a.sender)
    print(json.dumps(r, indent=2))
    if not r["trace_valid"] or not r["zero_drops"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
