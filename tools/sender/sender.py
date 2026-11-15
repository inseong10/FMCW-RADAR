"""Run a moving-target RadarSimPy simulation and send its baseband over UDP.

Each UDP datagram contains one chirp so that the packet stays below a typical
Ethernet MTU.  The payload is interleaved big-endian float32 I/Q data.
"""

from __future__ import annotations

import argparse
import importlib
import ipaddress
import json
import os
from pathlib import Path
import socket
import struct
import sys
import time

import numpy as np


LOCAL_CONFIG = Path(__file__).with_name("radarsimpy.local.json")
PROJECT_PACKAGE = Path(__file__).resolve().parent.parent / "radarsimpy"
_DLL_HANDLES = []


def load_radarsimpy(package_path: Path | None = None):
    """Load the project-local package, an override, or an installed distribution."""
    selected = package_path or os.environ.get("RADARSIMPY_PATH")
    if not selected and LOCAL_CONFIG.is_file():
        config = json.loads(LOCAL_CONFIG.read_text(encoding="utf-8"))
        selected = config.get("package_root") if isinstance(config, dict) else None
        if not isinstance(selected, str) or not selected.strip():
            raise ValueError(f"Invalid package_root in {LOCAL_CONFIG}")
        selected = Path(selected).expanduser()
        if not selected.is_absolute():
            selected = LOCAL_CONFIG.parent / selected

    if not selected and (PROJECT_PACKAGE / "__init__.py").is_file():
        selected = PROJECT_PACKAGE

    if selected:
        root = Path(selected).expanduser().resolve()
        package = root if root.name == "radarsimpy" and (root / "__init__.py").is_file() else root / "radarsimpy"
        if not (package / "__init__.py").is_file():
            raise ValueError(f"RadarSimPy package not found under {root}")
        loaded = sys.modules.get("radarsimpy")
        if loaded is not None and Path(getattr(loaded, "__file__", "") or ".").resolve() != (package / "__init__.py").resolve():
            raise RuntimeError("Another RadarSimPy package is already loaded; start a fresh Python process.")
        parent = str(package.parent)
        if parent in sys.path:
            sys.path.remove(parent)
        sys.path.insert(0, parent)
        if sys.platform == "win32" and loaded is None:
            for directory in (package, package / "lib"):
                if directory.is_dir():
                    _DLL_HANDLES.append(os.add_dll_directory(str(directory)))

    try:
        simulator = importlib.import_module("radarsimpy")
    except (ImportError, OSError) as exc:
        raise RuntimeError(
            "Cannot load RadarSimPy. Set --radarsimpy-path or RADARSIMPY_PATH to a "
            "distribution matching this OS, Python version and architecture. "
            f"Original error: {exc}"
        ) from exc
    if not all(hasattr(simulator, name) for name in ("Radar", "Transmitter", "Receiver", "sim_radar")):
        raise RuntimeError("The selected radarsimpy folder is not a complete package; check its nesting.")
    return simulator


MAGIC = b"RSPY"
PROTOCOL_VERSION = 1
MESSAGE_TYPE_BASEBAND = 1

# Network byte order:
# magic, version, message type, channel, chirp index, total chirps,
# sample count, sampling rate (Hz)
HEADER = struct.Struct("!4sBBHIIId")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Simulate a moving point target and transmit baseband I/Q data over UDP."
    )
    parser.add_argument("--ip", help="Destination IPv4 address (prompted when omitted)")
    parser.add_argument("--radarsimpy-path", type=Path, help="External distribution root or radarsimpy package directory")
    parser.add_argument("--check-simulator", action="store_true", help="Check simulator loading and exit without sending UDP")
    parser.add_argument(
        "--port", type=int, help="Destination UDP port (prompted when omitted)"
    )
    parser.add_argument(
        "--range",
        dest="target_range",
        type=float,
        default=30.0,
        help="Initial target range in metres (default: 30)",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=-10.0,
        help="Target x-axis speed in m/s; negative approaches the radar (default: -10)",
    )
    parser.add_argument(
        "--pulses",
        type=int,
        default=160,
        help="Number of FMCW chirps (default: 160)",
    )
    parser.add_argument(
        "--samples", type=int, default=160,
        help="Samples per 80 us chirp; sampling rate follows this count (default: 160)",
    )
    parser.add_argument(
        "--packet-delay-ms",
        type=float,
        default=1.0,
        help="Delay between UDP datagrams in milliseconds (default: 1)",
    )
    return parser.parse_args()


def read_destination(ip_value: str | None, port_value: int | None) -> tuple[str, int]:
    ip_text = ip_value or input("Destination IP: ").strip()
    try:
        destination_ip = str(ipaddress.IPv4Address(ip_text))
    except ipaddress.AddressValueError as exc:
        raise ValueError(f"Invalid IPv4 address: {ip_text}") from exc

    if port_value is None:
        port_text = input("Destination UDP port: ").strip()
        try:
            destination_port = int(port_text)
        except ValueError as exc:
            raise ValueError(f"Invalid UDP port: {port_text}") from exc
    else:
        destination_port = port_value

    if not 1 <= destination_port <= 65535:
        raise ValueError("UDP port must be between 1 and 65535")

    return destination_ip, destination_port


def create_radar(pulses: int, simulator=None, samples: int = 160):
    if pulses < 1:
        raise ValueError("pulses must be at least 1")
    if not 1 <= samples <= 8184:
        raise ValueError("samples must be between 1 and 8184 (UDP payload limit)")

    rs = simulator if simulator is not None else load_radarsimpy()
    transmitter = rs.Transmitter(
        f=[24e9, 24.1e9],
        t=80e-6,
        tx_power=10,
        pulses=pulses,
        prp=100e-6,
    )
    receiver = rs.Receiver(
        fs=samples * 12_500.0,  # Exactly samples / (80 us), without rate roundoff.
        noise_figure=10,
        rf_gain=20,
        load_resistor=500,
        baseband_gain=30,
    )
    return rs.Radar(transmitter=transmitter, receiver=receiver, seed=42)


def simulate(pulses: int, target_range: float, target_speed: float, package_path: Path | None = None,
             samples: int = 160) -> tuple[np.ndarray, float]:
    rs = load_radarsimpy(package_path)
    radar = create_radar(pulses, rs, samples=samples)
    targets = [
        {
            "location": [target_range, 0, 0],
            "speed": [target_speed, 0, 0],
            "rcs": 10,
            "phase": 0,
        }
    ]
    result = rs.sim_radar(radar, targets)
    baseband = np.asarray(result["baseband"])
    if baseband.ndim != 3 or baseband.shape[1:] != (pulses, samples):
        raise RuntimeError(f"Simulator returned {baseband.shape}, expected (*, {pulses}, {samples})")
    sample_rate_hz = float(radar.receiver.bb_prop["fs"])
    return baseband, sample_rate_hz


def build_packet(
    samples: np.ndarray,
    channel: int,
    chirp_index: int,
    total_chirps: int,
    sample_rate_hz: float,
) -> bytes:
    iq = np.column_stack((samples.real, samples.imag)).astype(">f4", copy=False)
    header = HEADER.pack(
        MAGIC,
        PROTOCOL_VERSION,
        MESSAGE_TYPE_BASEBAND,
        channel,
        chirp_index,
        total_chirps,
        samples.size,
        sample_rate_hz,
    )
    return header + iq.tobytes()


def send_baseband(
    baseband: np.ndarray,
    sample_rate_hz: float,
    destination: tuple[str, int],
    packet_delay_ms: float,
) -> tuple[int, int]:
    if baseband.ndim != 3:
        raise ValueError(f"Expected 3-D baseband data, got shape {baseband.shape}")
    if packet_delay_ms < 0:
        raise ValueError("packet-delay-ms cannot be negative")

    sent_packets = 0
    sent_bytes = 0
    delay_seconds = packet_delay_ms / 1000.0
    channel_count, chirp_count, _ = baseband.shape

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
        for channel in range(channel_count):
            for chirp_index in range(chirp_count):
                packet = build_packet(
                    baseband[channel, chirp_index],
                    channel,
                    chirp_index,
                    chirp_count,
                    sample_rate_hz,
                )
                sent_bytes += udp_socket.sendto(packet, destination)
                sent_packets += 1
                if delay_seconds and chirp_index + 1 < chirp_count:
                    time.sleep(delay_seconds)

    return sent_packets, sent_bytes


def main() -> int:
    args = parse_args()
    try:
        if args.check_simulator:
            simulator = load_radarsimpy(args.radarsimpy_path)
            print(f"RadarSimPy {getattr(simulator, '__version__', 'unknown')}: {simulator.__file__}")
            return 0
        destination = read_destination(args.ip, args.port)
        print(
            f"Simulating target: range={args.target_range:g} m, "
            f"speed={args.speed:g} m/s, chirps={args.pulses}"
        )
        baseband, sample_rate_hz = simulate(
            args.pulses, args.target_range, args.speed, args.radarsimpy_path, args.samples
        )
        print(f"Baseband shape: {baseband.shape}")

        packet_count, byte_count = send_baseband(
            baseband,
            sample_rate_hz,
            destination,
            args.packet_delay_ms,
        )
        print(
            f"Sent {packet_count} UDP packets ({byte_count} bytes) "
            f"to {destination[0]}:{destination[1]}"
        )
        return 0
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
