"""Packet/reference checks; optional C++/FFTW integration via offline replay."""
import argparse
import csv
from contextlib import redirect_stdout
import importlib.util
import io
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[4]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sender = load_module("radar_sender", ROOT / "tools/sender/sender.py")
reference = load_module("receiver_numpy", ROOT / "src/PS/receiver/reference/receiver_numpy.py")
BINARY = Path(os.environ.get("RADAR_RECEIVER_BINARY", ROOT / "build/udp_radar_receiver"))


def options(window="none"):
    return argparse.Namespace(window=window, warmup=0, repeat=1,
                              chirp_us=80, prp_us=100, bandwidth_mhz=100, fc_ghz=24.05)


def process(frame, window="none"):
    with redirect_stdout(io.StringIO()):
        return reference.process_frame(frame, 2e6, options(window), reference.Profiler())


def write_packets(path, frame, indices=None):
    pulses = frame.shape[0]
    with path.open("wb") as stream:
        stream.write(b"RSPB0001")
        for index in range(pulses) if indices is None else indices:
            packet = sender.build_packet(frame[index], 0, index, pulses, 2e6)
            stream.write(struct.pack("!I", len(packet)))
            stream.write(packet)


class PacketAndReferenceTests(unittest.TestCase):
    def test_sender_sample_count_sets_rate_without_truncation(self):
        class Simulator:
            Transmitter = staticmethod(lambda **kwargs: kwargs)
            Receiver = staticmethod(lambda **kwargs: kwargs)
            Radar = staticmethod(lambda **kwargs: kwargs)
        for count, rate in ((128, 1.6e6), (160, 2e6)):
            radar = sender.create_radar(128, Simulator, samples=count)
            self.assertEqual(radar['receiver']['fs'], rate)
            self.assertEqual(radar['transmitter']['t'], 80e-6)
            self.assertEqual(radar['transmitter']['pulses'], 128)
        with self.assertRaises(ValueError):
            sender.create_radar(128, Simulator, samples=0)

    def test_packet_round_trip(self):
        samples = np.array([1.25-2.5j, -3+4j, 0j], dtype=np.complex64)
        packet = sender.build_packet(samples, 7, 2, 5, 2e6)
        self.assertEqual(packet[28:36], struct.pack("!ff", 1.25, -2.5))
        channel, index, pulses, count, fs, decoded = reference.decode_packet(packet)
        self.assertEqual((channel, index, pulses, count, fs), (7, 2, 5, 3, 2e6))
        np.testing.assert_array_equal(decoded, samples)

    def test_invalid_packets(self):
        packet = sender.build_packet(np.ones(3), 0, 0, 2, 2e6)
        bad_packets = [packet[:20], packet[:-1], b"FAIL"+packet[4:],
                       packet[:4]+bytes([2])+packet[5:],
                       sender.build_packet(np.array([complex(np.nan, 0)]), 0, 0, 1, 2e6),
                       sender.build_packet(np.ones(3), 0, 2, 2, 2e6),
                       sender.build_packet(np.ones(3), 0, 0, 2, 0)]
        for bad in bad_packets:
            with self.subTest(packet=bad[:28]), self.assertRaises(ValueError):
                reference.decode_packet(bad)

    def test_known_tone_bins_and_axes(self):
        pulses, samples, doppler_bin, range_bin = 7, 9, -2, 3
        frame = np.exp(2j*np.pi*(doppler_bin*np.arange(pulses)[:, None]/pulses
                                + range_bin*np.arange(samples)[None, :]/samples))
        result = process(frame)
        peak = np.unravel_index(np.argmax(abs(result["range_doppler"])), frame.shape)
        self.assertEqual(peak, ((doppler_bin % pulses+pulses//2) % pulses, range_bin))
        self.assertAlmostEqual(abs(result["range_doppler"][peak]), pulses*samples)
        self.assertAlmostEqual(result["range_m"][peak[1]],
                               range_bin*2e6/samples*reference.C/(2*(100e6/80e-6)))
        self.assertAlmostEqual(result["velocity_mps"][peak[0]],
                               doppler_bin/(pulses*100e-6)*reference.C/(2*24.05e9))

    def test_reference_against_direct_dft(self):
        rng = np.random.default_rng(42)
        frame = rng.normal(size=(5, 7))+1j*rng.normal(size=(5, 7))
        p, s = frame.shape
        dp = np.exp(-2j*np.pi*np.outer(np.arange(p), np.arange(p))/p)
        ds = np.exp(-2j*np.pi*np.outer(np.arange(s), np.arange(s))/s)
        for window in ("none", "hann"):
            with self.subTest(window=window):
                weighted = frame.copy()
                if window == "hann":
                    weighted *= np.hanning(p)[:, None]*np.hanning(s)[None, :]
                expected = np.fft.fftshift(dp @ weighted @ ds.T, axes=0)
                np.testing.assert_allclose(process(frame, window)["range_doppler"], expected,
                                           rtol=1e-12, atol=1e-12)

    def test_explicit_missing_simulator_does_not_fall_back(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "package not found"):
                sender.load_radarsimpy(Path(directory))

    def test_help_does_not_load_simulator(self):
        env = dict(os.environ, RADARSIMPY_PATH=str(ROOT / "missing-simulator"))
        result = subprocess.run([sys.executable, "-B", str(ROOT / "tools/sender/sender.py"), "--help"],
                                capture_output=True, text=True, env=env, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--check-simulator", result.stdout)

    def test_external_package_root_and_package_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "radarsimpy"
            package.mkdir()
            (package / "__init__.py").write_text(
                "Radar = Transmitter = Receiver = sim_radar = object\n__version__ = 'test-external'\n",
                encoding="utf-8")
            env = dict(os.environ, RADARSIMPY_PATH=str(root / "missing"))
            for selected in (root, package):
                with self.subTest(path=selected):
                    result = subprocess.run(
                        [sys.executable, "-B", str(ROOT / "tools/sender/sender.py"),
                         "--check-simulator", "--radarsimpy-path", str(selected)],
                        capture_output=True, text=True, env=env, timeout=15)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("test-external", result.stdout)
                    self.assertIn(str(package), result.stdout)


@unittest.skipUnless(BINARY.is_file(), "Build build/udp_radar_receiver for C++/FFTW checks")
class CppReceiverTests(unittest.TestCase):
    def test_q15_normalized_pipeline_matches_numpy(self):
        with tempfile.TemporaryDirectory() as directory:
            directory=Path(directory)
            rng=np.random.default_rng(128)
            frame=(rng.normal(size=(128,128))+1j*rng.normal(size=(128,128))).astype(np.complex64)
            packets=directory/'frame.bin'; output=directory/'spectrum.csv'; timings=directory/'timings.csv'
            write_packets(packets,frame)
            result=subprocess.run([str(BINARY.resolve()),'--input',str(packets),'--output',str(output),
                '--timings',str(timings),'--window','none','--q15-input','--normalize-output',
                '--warmup','2','--repeat','3'],capture_output=True,text=True,timeout=60)
            self.assertEqual(result.returncode,0,result.stderr)
            values=frame.astype(np.complex128)
            scale=16384/np.max(np.hypot(values.real,values.imag))
            q=np.rint(values.real*scale)+1j*np.rint(values.imag*scale)
            rows=np.loadtxt(output,delimiter=',',skiprows=1)
            actual=(rows[:,2]+1j*rows[:,3]).reshape(128,128)
            np.testing.assert_allclose(actual,np.fft.fft2(q)/16384,rtol=1e-10,atol=1e-9)
            with timings.open() as stream:
                core=[r for r in csv.DictReader(stream) if r['stage']=='fft_pipeline']
            self.assertEqual(len(core),3)
            self.assertTrue(all(float(r['wall_ms'])>0 for r in core))

    def test_offline_spectrum_matches_numpy(self):
        rng = np.random.default_rng(42)
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            for shape in ((160, 160), (5, 7)):
                frame = (rng.normal(size=shape)+1j*rng.normal(size=shape)).astype(np.complex64)
                packets, output = directory / "frame.bin", directory / "spectrum.csv"
                write_packets(packets, frame, list(reversed(range(shape[0]))))
                for window in ("none", "hann"):
                    for measure in (False, True):
                        with self.subTest(shape=shape, window=window, measure=measure):
                            command = [str(BINARY.resolve()), "--input", str(packets), "--output", str(output),
                                       "--warmup", "0", "--repeat", "1", "--window", window]
                            if measure:
                                command.append("--measure-plan")
                            result = subprocess.run(command, capture_output=True, text=True, timeout=60)
                            self.assertEqual(result.returncode, 0, result.stderr)
                            rows = np.loadtxt(output, delimiter=",", skiprows=1)
                            actual = (rows[:, 2]+1j*rows[:, 3]).reshape(shape)
                            weighted = frame.astype(np.complex128)
                            if window == "hann":
                                weighted *= np.hanning(shape[0])[:, None]*np.hanning(shape[1])[None, :]
                            np.testing.assert_allclose(actual, np.fft.fft2(weighted), rtol=1e-10, atol=1e-9)

    def test_incomplete_replay_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            packets = Path(directory) / "missing.bin"
            write_packets(packets, np.ones((5, 7), dtype=np.complex64), [0, 1, 3, 4])
            result = subprocess.run([str(BINARY.resolve()), "--input", str(packets), "--warmup", "0"],
                                    capture_output=True, text=True, timeout=15)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Missing chirp", result.stderr)


if __name__ == "__main__":
    unittest.main()
