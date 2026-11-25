"""Independent numerical/wire tests plus trace-integrity rejection checks."""
import argparse
from contextlib import redirect_stdout
import csv
import io
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import unittest

import numpy as np

import analyze_stream
import verify_s1c as s1c

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tools/sender"))
import replay_stream as sender

CXX = os.environ.get("CXX") or shutil.which("g++")
CC = os.environ.get("CC") or shutil.which("gcc")
FFTW = os.environ.get("S2A_FFTW")


class SenderTests(unittest.TestCase):
    def test_local_udp_frame_ids_and_deliberate_packet_loss(self):
        received = []
        import socket
        with tempfile.TemporaryDirectory() as temp, socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024*1024)
            listener.bind(("127.0.0.1", 0))
            listener.settimeout(2)
            errors = []
            def collect():
                try:
                    while len(received) < 383:
                        received.append(listener.recvfrom(2048)[0])
                except OSError as e:
                    errors.append(str(e))
            thread = threading.Thread(target=collect)
            thread.start()
            try:
                a = argparse.Namespace(record=ROOT/"benchmarks/fixtures/radarsimpy_128x128_sim_multi4_noise.rspb",
                                       ip="127.0.0.1", port=listener.getsockname()[1], frames=3,
                                       run_id=9, period_ms=50, chirp_gap_us=0, drop_frame=2,
                                       out=Path(temp)/"sender.json")
                with redirect_stdout(io.StringIO()):
                    sender.send(a)
            finally:
                thread.join(timeout=3)
            self.assertFalse(errors, errors)
            self.assertEqual(len(received), 383)
            decoded = [sender.HEADER.unpack_from(p) for p in received]
            self.assertEqual({h[4] for h in decoded}, {9})
            for frame_id in (1, 2, 3):
                selected = [h for h in decoded if h[5] == frame_id]
                self.assertEqual(len(selected), 127 if frame_id == 2 else 128)
                self.assertEqual(len({h[-1] for h in selected}), 1)
            self.assertNotIn(64, [h[6] for h in decoded if h[5] == 2])


@unittest.skipUnless(CXX and CC, "C/C++ compilers required")
class IntegratedPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.folder = Path(cls.tmp.name)
        cls.binary = cls.folder/("stream.exe" if os.name == "nt" else "stream")
        obj = cls.folder/"core.o"
        subprocess.run([CC, "-O2", "-std=c11", "-Wall", "-Wextra", "-Werror", "-c",
                        str(ROOT/"src/PS/fft128/native_core.c"), "-o", str(obj)], check=True, capture_output=True)
        subprocess.run([CXX, "-O2", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                        str(ROOT/"src/PS/receiver/tests/stream_driver.cpp"), str(obj),
                        *([] if os.name == "nt" else ["-ldl"]), "-o", str(cls.binary)], check=True, capture_output=True)
        cls.timestamp_binary = cls.folder/("timestamp.exe" if os.name == "nt" else "timestamp")
        subprocess.run([CXX, "-O2", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                        str(ROOT/"src/PS/receiver/tests/timestamp_driver.cpp"), "-o", str(cls.timestamp_binary)],
                       check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_wire(self, packets, backend="model", window="hann"):
        path = self.folder/"wire"
        path.write_bytes(b"".join(packets))
        return subprocess.run([str(self.binary), str(path), backend, window, FFTW or "",
                               str(self.folder/"out")], capture_output=True, text=True, timeout=30)

    def load(self, name):
        packets, _ = sender.read_frame(ROOT/"benchmarks/fixtures"/f"radarsimpy_128x128_sim_{name}_noise.rspb")
        frame = np.empty((128, 128), dtype=complex)
        wire = []
        for p in packets:
            i = struct.unpack_from("!I", p, 8)[0]
            values = np.frombuffer(p, dtype=">f4", offset=28).reshape(128, 2)
            frame[i] = values[:, 0]+1j*values[:, 1]
            wire.append(sender.packet_v2(p, 9, 1, 123456789))
        return frame, wire

    def compare(self, backend):
        for name in ("single", "multi4", "close_weak"):
            frame, wire = self.load(name)
            for window in ("none", "hann"):
                with self.subTest(name=name, window=window, backend=backend):
                    run = self.run_wire(wire[::-1]+wire[:1], backend, window)
                    self.assertEqual(run.returncode, 0, run.stderr)
                    weighted = frame*(np.hanning(128)[:, None]*np.hanning(128)[None, :] if window == "hann" else 1)
                    if backend == "model":
                        weighted = weighted.astype(np.complex64).astype(complex)
                        q, _ = s1c.quantize(weighted)
                        spectrum = s1c.integer_spectrum(q)
                    else:
                        spectrum = np.fft.fft2(weighted)/16384
                    expected = spectrum.real**2+spectrum.imag**2
                    bins = np.loadtxt(self.folder/"out.bins.csv", delimiter=",")
                    bins = (bins[:, 0]+1j*bins[:, 1]).reshape(128, 128)
                    actual = np.loadtxt(self.folder/"out.power.csv").reshape(128, 128)
                    if backend == "model":
                        np.testing.assert_array_equal(bins, spectrum)
                        np.testing.assert_array_equal(actual, expected)
                    else:
                        np.testing.assert_allclose(bins, spectrum, atol=1e-15, rtol=1e-10)
                        np.testing.assert_allclose(actual, expected, atol=1e-18, rtol=1e-10)
                    with (self.folder/"out.peaks.csv").open(newline="") as f:
                        peaks = list(csv.DictReader(f))
                    reference = s1c.detect(expected)
                    self.assertEqual([(int(p["doppler"]), int(p["range"])) for p in peaks],
                                     [(int(p[0]), int(p[1])) for p in reference])

    def test_integer_pipeline_six_cases_reordered_and_duplicate(self):
        self.compare("model")

    def test_timestamp_time32_time64_layout_and_capacity(self):
        result = subprocess.run([str(self.timestamp_binary)], check=True, capture_output=True, text=True)
        self.assertIn("TIMESTAMP_ABI_PASS", result.stdout)

    @unittest.skipUnless(FFTW, "Set S2A_FFTW to a double FFTW runtime")
    def test_ps_pipeline_six_cases_reordered_and_duplicate(self):
        self.compare("ps")

    def test_rejects_missing_truncated_nonfinite_and_mixed_metadata(self):
        _, wire = self.load("single")
        mixed = bytearray(wire[1]);struct.pack_into("!Q", mixed, 44, 555)
        nan = bytearray(wire[1]);struct.pack_into("!f", nan, 52, float("nan"))
        old = bytearray(wire[0]);old[4] = 1
        for packets in (wire[:-1], wire[:-1]+[wire[-1][:-1]], [wire[0], mixed]+wire[2:],
                        [wire[0], nan]+wire[2:], [old]+wire[1:]):
            self.assertNotEqual(self.run_wire(packets).returncode, 0)


class TraceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        (self.folder/"environment.txt").write_text("frames=1\nrun_id=9\nbackend=model\nhardware=0\n")
        self.counters = {k: "0" for k in ("invalid", "metadata_errors", "kernel_drops", "kernel_missing",
                                        "clock_errors", "failed", "interrupted")}
        (self.folder/"resources.csv").write_text("start_ns,end_ns,process_cpu_pct_one_core,system_cpu_pct,rss_bytes\n1,20,10,5,4096\n")
        (self.folder/"detections.csv").write_text("run_id,frame_id,doppler_bin,range_bin,power,threshold\n9,1,-1,-1,0,0\n")
        self.row = dict(zip(("frame_id,status,packets,first_rx_ns,first_kernel_ns,complete_ns,process_start_ns,"
                            "prepared_ns,fft_done_ns,cfar_done_ns,output_done_ns,sender_ns,queue_depth,peaks").split(","),
                           ("1", "processed", "128", "3", "2", "4", "5", "6", "7", "8", "9", "123", "0", "0")))

    def write(self, rows=None):
        (self.folder/"counters.txt").write_text("\n".join(f"{k}={v}" for k, v in self.counters.items()))
        with (self.folder/"frames.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(self.row));w.writeheader();w.writerows([self.row] if rows is None else rows)

    def test_valid_trace_and_kernel_drop_invalidation(self):
        self.write();r = analyze_stream.analyze(self.folder)
        self.assertTrue(r["trace_valid"] and r["zero_drops"])
        self.assertFalse(r["hardware"])
        self.counters["kernel_drops"] = "1";self.write()
        self.assertFalse(analyze_stream.analyze(self.folder)["trace_valid"])

    def test_missing_id_and_reversed_timestamps_rejected(self):
        self.write([])
        with self.assertRaises(ValueError):
            analyze_stream.analyze(self.folder)
        self.row["fft_done_ns"] = "100";self.write()
        with self.assertRaises(ValueError):
            analyze_stream.analyze(self.folder)

    def test_partial_frame_counted_as_drop(self):
        self.row.update(status="partial", packets="127");self.write()
        (self.folder/"detections.csv").write_text("run_id,frame_id,doppler_bin,range_bin,power,threshold\n")
        self.assertFalse(analyze_stream.analyze(self.folder)["zero_drops"])


if __name__ == "__main__":
    unittest.main()
