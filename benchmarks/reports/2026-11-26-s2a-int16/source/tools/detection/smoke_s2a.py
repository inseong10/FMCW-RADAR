#!/usr/bin/env python3
"""Ubuntu loopback smoke: PS/model correctness, deliberate loss, receiver trace.

This is an instrumentation smoke test, not a throughput/board acceptance test.
All raw output is retained in a fresh output folder, including failed runs.
"""
import argparse
import csv
import json
from pathlib import Path
import queue
import socket
import subprocess
import sys
import threading
import time

import analyze_stream

ROOT = Path(__file__).resolve().parents[2]


def port():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def check_peaks(folder):
    expected = [(10, 10), (107, 20), (4, 37), (87, 53)]
    with (folder/"detections.csv").open(newline="") as f:
        rows = list(csv.DictReader(f))
    grouped = {}
    for r in rows:
        grouped.setdefault(int(r["frame_id"]), []).append((int(r["doppler_bin"]), int(r["range_bin"])))
    if any(peaks != expected for peaks in grouped.values()):
        raise ValueError("Loopback detections differ from S1b/S1c multi4 Hann baseline")


def case(binary, out, backend, run_id, loss=False, diagnostic=False, adc16=False):
    chosen = port()
    result = out/f"{backend}_{'loss' if loss else 'normal'}"
    sender_log = out/f"{result.name}_sender.json"
    command = [str(binary), "--backend", backend, "--run-id", str(run_id), "--frames", "20",
               "--bind", "127.0.0.1", "--port", str(chosen), "--out", str(result),
               "--partial", "1" if loss and not adc16 else "4", "--idle-ms", "500", "--start-ms", "10000"]
    if adc16:
        command += ["--input-format", "adc16", "--queue", "4"]
    if diagnostic:
        command.append("--diagnose-first-packet")
        if adc16:command.append("--diagnostic-spectrum")
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, bufsize=1)
    lines = []
    messages = queue.Queue()

    def read():
        for line in process.stdout:
            lines.append(line)
            messages.put(line)
        messages.put(None)

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    try:
        deadline = time.monotonic()+15
        while True:
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Receiver did not become ready")
            line = messages.get(timeout=remaining)
            if line is None:
                raise RuntimeError("Receiver exited before ready: "+"".join(lines))
            if line.startswith("S2A_READY"):
                break
        send_command = [sys.executable, str(ROOT/"tools/sender/replay_stream.py"),
                        str(ROOT/("benchmarks/fixtures/adc16/radarsimpy_128x128_sim_multi4_noise_adc16.rspb" if adc16 else
                                  "benchmarks/fixtures/radarsimpy_128x128_sim_multi4_noise.rspb")),
                        "--ip", "127.0.0.1", "--port", str(chosen), "--frames", "20",
                        "--run-id", str(run_id), "--period-ms", "50", "--out", str(sender_log)]
        if loss:
            send_command += ["--drop-frame", "2"]
        sent = subprocess.run(send_command, capture_output=True, text=True, timeout=10)
        (out/f"{result.name}_sender.log").write_text(sent.stdout+sent.stderr, encoding="utf-8")
        if sent.returncode:
            raise RuntimeError("Sender failed: "+sent.stderr)
        status = process.wait(timeout=10)
        reader.join(timeout=1)
        summary = analyze_stream.analyze(result, sender_log)
        if diagnostic and (not summary["diagnostic_probe"] or
                           not any(line.startswith("S2A_LEGACY_PROBE") for line in lines)):
            raise ValueError("First-packet compatibility probe did not run")
        check_peaks(result)
        if not summary["trace_valid"]:
            raise ValueError("Invalid monitor counters")
        if loss:
            loss_status = "partial" if adc16 else "partial_evicted"
            if status != 2 or summary["status_counts"] != {"processed": 19, loss_status: 1}:
                raise ValueError("Intentional loss was not accounted for exactly")
        elif status != 0 or not summary["zero_drops"]:
            raise ValueError("Normal loopback dropped frames")
        return summary
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill();process.wait(timeout=3)
        reader.join(timeout=1)
        (out/f"{result.name}_receiver.log").write_text("".join(lines), encoding="utf-8")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--binary", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    if a.out.exists():
        p.error("Use a fresh output directory")
    a.out.mkdir(parents=True)
    results = []
    for backend, run_id, loss in (("model", 91001, False), ("ps", 91002, False), ("model", 91003, True)):
        results.append(case(a.binary.resolve(), a.out, backend, run_id, loss,
                            diagnostic=backend == "model" and not loss))
        print(f"S2A_SMOKE_CASE_PASS backend={backend} deliberate_loss={loss}", flush=True)
    (a.out/"smoke_summary.json").write_text(json.dumps(results, indent=2)+"\n", encoding="utf-8")
    print("S2A_HOST_SMOKE_PASS cases=3 (no board/throughput claim)")


if __name__ == "__main__":
    main()
