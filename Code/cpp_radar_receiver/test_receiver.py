from __future__ import annotations

import argparse
from contextlib import contextmanager
from pathlib import Path
import socket
import struct
import sys
import time

import numpy as np


HEADER = struct.Struct("!4sBBHIIId")
C = 299_792_458.0

PROCESS_STAGES = [
    "range_window",
    "range_fft",
    "doppler_window",
    "doppler_fft",
    "postprocess",
    "axis_calculation",
    "processing_total",
]


class Profiler:
    def __init__(self, thread_cpu=False):
        self.records = {}
        self.samples = {}
        self.cpu_clock = (
            time.thread_time_ns
            if thread_cpu
            else time.process_time_ns
        )

    @contextmanager
    def measure(self, name):
        record = self.records.setdefault(
            name,
            {"wall_ns": 0, "cpu_ns": 0, "calls": 0},
        )

        wall_start = time.perf_counter_ns()
        cpu_start = self.cpu_clock()

        try:
            yield
        finally:
            cpu_ns = self.cpu_clock() - cpu_start
            wall_ns = time.perf_counter_ns() - wall_start

            record["wall_ns"] += wall_ns
            record["cpu_ns"] += cpu_ns
            record["calls"] += 1
            self.samples.setdefault(name, []).append((wall_ns, cpu_ns))

    def print_report(self, names):
        print(
            f"{'Stage':24s}"
            f"{'Wall avg(ms)':>15s}"
            f"{'CPU avg(ms)':>15s}"
            f"{'CPU(%)':>11s}"
            f"{'Calls':>9s}"
        )
        print("-" * 74)

        for name in names:
            if name not in self.records:
                continue

            r = self.records[name]
            calls = r["calls"]
            wall = r["wall_ns"]
            cpu = r["cpu_ns"]
            usage = 100.0 * cpu / wall if wall else 0.0

            print(
                f"{name:24s}"
                f"{wall / calls / 1e6:15.6f}"
                f"{cpu / calls / 1e6:15.6f}"
                f"{usage:11.1f}"
                f"{calls:9d}"
            )

    def print_fft_summary(self):
        r = self.records["range_fft"]
        d = self.records["doppler_fft"]

        wall_ns = r["wall_ns"] + d["wall_ns"]
        cpu_ns = r["cpu_ns"] + d["cpu_ns"]

        # 두 단계는 동일한 횟수만큼 실행됩니다.
        calls = r["calls"]
        usage = 100.0 * cpu_ns / wall_ns if wall_ns else 0.0

        print(
            f"\nFFT only per frame: "
            f"wall={wall_ns / calls / 1e6:.6f} ms, "
            f"CPU={cpu_ns / calls / 1e6:.6f} ms, "
            f"CPU usage={usage:.2f}%"
        )

    def export(self):
        result = {}

        for name, r in self.records.items():
            calls = r["calls"]
            wall = r["wall_ns"]
            cpu = r["cpu_ns"]

            result[f"{name}_wall_avg_ms"] = wall / calls / 1e6
            result[f"{name}_cpu_avg_ms"] = cpu / calls / 1e6
            result[f"{name}_cpu_percent"] = (
                100.0 * cpu / wall if wall else 0.0
            )
            result[f"{name}_calls"] = calls

        return result


def parse_args():
    parser = argparse.ArgumentParser(
        description="UDP radar receiver and NumPy FFT benchmark"
    )

    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--channel", type=int, default=0)
    parser.add_argument("--source-ip")
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--max-frame-mb", type=float, default=128.0)

    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--repeat", type=int, default=100)
    parser.add_argument("--thread-cpu", action="store_true")
    parser.add_argument(
        "--window",
        choices=["hann", "none"],
        default="hann",
    )

    # 송신 헤더에 포함되지 않는 레이더 설정값입니다.
    parser.add_argument("--bandwidth-mhz", type=float, default=100.0)
    parser.add_argument("--chirp-us", type=float, default=80.0)
    parser.add_argument("--prp-us", type=float, default=100.0)
    parser.add_argument("--fc-ghz", type=float, default=24.05)

    parser.add_argument("--output", type=Path)
    parser.add_argument("--plot", action="store_true")


    args = parser.parse_args()

    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")

    if not 0 <= args.channel <= 65535:
        parser.error("channel must be between 0 and 65535")

    if args.warmup < 0:
        parser.error("warmup must be nonnegative")

    if args.repeat < 1:
        parser.error("repeat must be at least 1")

    for name in (
        "timeout",
        "max_frame_mb",
        "bandwidth_mhz",
        "chirp_us",
        "prp_us",
        "fc_ghz",
    ):
        value = getattr(args, name)

        if not np.isfinite(value) or value <= 0:
            parser.error(f"{name} must be positive and finite")

    return args


def decode_packet(packet):
    if len(packet) < HEADER.size:
        raise ValueError("Short header")

    (
        magic,
        version,
        message_type,
        channel,
        chirp_index,
        chirp_count,
        sample_count,
        sample_rate_hz,
    ) = HEADER.unpack_from(packet)

    if (magic, version, message_type) != (b"RSPY", 1, 1):
        raise ValueError("Unsupported protocol")

    if not (
        1 <= chirp_count <= 100_000
        and 1 <= sample_count <= 8184
        and chirp_index < chirp_count
    ):
        raise ValueError("Invalid dimensions/index")

    if not np.isfinite(sample_rate_hz) or sample_rate_hz <= 0:
        raise ValueError("Invalid sampling rate")

    if len(packet) != HEADER.size + sample_count * 8:
        raise ValueError("Invalid payload length")

    # I0, Q0, I1, Q1, ... 순서의 big-endian float32입니다.
    iq = np.frombuffer(
        packet,
        dtype=">f4",
        offset=HEADER.size,
    ).reshape(sample_count, 2)

    samples = (
        iq[:, 0].astype(np.float32)
        + 1j * iq[:, 1].astype(np.float32)
    )

    if not np.isfinite(samples).all():
        raise ValueError("Nonfinite I/Q")

    return (
        channel,
        chirp_index,
        chirp_count,
        sample_count,
        sample_rate_hz,
        samples,
    )


def receive_frame(args, profiler):
    frame = None
    seen = None
    sender = None
    metadata = None

    received = 0
    duplicates = 0
    invalid = 0
    ignored = 0

    first_arrival_ns = None
    last_arrival_ns = None

    def incomplete_error():
        if seen is None:
            return TimeoutError("No valid frame received")

        missing = np.flatnonzero(~seen)

        return TimeoutError(
            f"Incomplete frame: received {received}/{seen.size}; "
            f"first missing indices={missing[:20].tolist()}"
        )

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_RCVBUF,
            4 * 1024 * 1024,
        )
        sock.bind((args.bind, args.port))

        print(
            f"Listening on {args.bind}:{args.port}, "
            f"channel={args.channel}",
            flush=True,
        )

        deadline = time.monotonic() + args.timeout

        with profiler.measure("receive_total"):
            while True:
                remaining = deadline - time.monotonic()

                if remaining <= 0:
                    raise incomplete_error()

                sock.settimeout(remaining)

                try:
                    with profiler.measure("socket_wait"):
                        packet, address = sock.recvfrom(65535)
                except socket.timeout:
                    raise incomplete_error() from None

                arrival_ns = time.perf_counter_ns()

                if args.source_ip and address[0] != args.source_ip:
                    ignored += 1
                    continue

                if sender is not None and address != sender:
                    ignored += 1
                    continue

                try:
                    with profiler.measure("decode"):
                        (
                            channel,
                            index,
                            chirp_count,
                            sample_count,
                            sample_rate_hz,
                            samples,
                        ) = decode_packet(packet)
                except ValueError:
                    invalid += 1
                    continue

                if channel != args.channel:
                    ignored += 1
                    continue

                with profiler.measure("reassembly"):
                    current_metadata = (
                        chirp_count,
                        sample_count,
                        sample_rate_hz,
                    )

                    if frame is None:
                        # C++과 동일하게 complex128 프레임을 보관합니다.
                        frame_bytes = chirp_count * sample_count * 16

                        if frame_bytes > args.max_frame_mb * 1024**2:
                            raise ValueError(
                                "Frame exceeds --max-frame-mb"
                            )

                        frame = np.empty(
                            (chirp_count, sample_count),
                            dtype=np.complex128,
                        )
                        seen = np.zeros(chirp_count, dtype=bool)

                        metadata = current_metadata
                        sender = address
                        first_arrival_ns = arrival_ns

                    elif metadata != current_metadata:
                        raise ValueError(
                            "Frame metadata changed; restart both programs"
                        )

                    if seen[index]:
                        duplicates += 1
                        continue

                    frame[index] = samples
                    seen[index] = True

                    received += 1
                    last_arrival_ns = arrival_ns

                if received == chirp_count:
                    break

    span_ms = (last_arrival_ns - first_arrival_ns) / 1e6

    print(f"Sender: {sender}")
    print(
        f"Frame shape: {frame.shape}, "
        f"dtype={frame.dtype}, fs={sample_rate_hz:g} Hz"
    )
    print(
        f"Duplicates={duplicates}, invalid={invalid}, ignored={ignored}"
    )
    print(f"First-to-last packet: {span_ms:.6f} ms")

    return frame, sample_rate_hz, span_ms


def make_windows(shape, window):
    chirp_count, sample_count = shape

    if window == "hann":
        if chirp_count < 3 or sample_count < 3:
            raise ValueError(
                "Hann requires >=3 chirps and samples; "
                "use --window none"
            )

        return (
            np.hanning(sample_count),
            np.hanning(chirp_count),
        )

    return (
        np.ones(sample_count),
        np.ones(chirp_count),
    )


def signed_bin(index, size):
    return index if index <= (size - 1) // 2 else index - size


def process_frame(frame, fs, args, profiler):
    chirp_count, sample_count = frame.shape

    range_window, doppler_window = make_windows(
        frame.shape,
        args.window,
    )

    chirp_s = args.chirp_us * 1e-6
    prp_s = args.prp_us * 1e-6
    bandwidth_hz = args.bandwidth_mhz * 1e6
    fc_hz = args.fc_ghz * 1e9

    # 실제 프레임으로 FFT 워밍업을 수행합니다.
    # 워밍업은 측정 시간에서 제외합니다.
    for _ in range(args.warmup):
        range_input = frame * range_window[None, :]
        range_fft = np.fft.fft(range_input, axis=1)

        doppler_input = range_fft * doppler_window[:, None]
        np.fft.fft(doppler_input, axis=0)

    print(
        f"Warmup: {args.warmup}, "
        f"repeats of SAME frame: {args.repeat}"
    )

    for _ in range(args.repeat):
        with profiler.measure("processing_total"):
            with profiler.measure("range_window"):
                range_input = frame * range_window[None, :]

            with profiler.measure("range_fft"):
                range_fft = np.fft.fft(range_input, axis=1)

            with profiler.measure("doppler_window"):
                doppler_input = range_fft * doppler_window[:, None]

            with profiler.measure("doppler_fft"):
                doppler_fft = np.fft.fft(doppler_input, axis=0)

            with profiler.measure("postprocess"):
                # fftshift 복사 및 제곱근 계산 없이 피크를 찾습니다.
                power = (
                    doppler_fft.real * doppler_fft.real
                    + doppler_fft.imag * doppler_fft.imag
                )

                peak_doppler, peak_range = np.unravel_index(
                    np.argmax(power),
                    power.shape,
                )

            with profiler.measure("axis_calculation"):
                peak_beat_hz = (
                    signed_bin(peak_range, sample_count)
                    * fs
                    / sample_count
                )

                peak_doppler_hz = (
                    signed_bin(peak_doppler, chirp_count)
                    / (chirp_count * prp_s)
                )

                peak_range_m = (
                    peak_beat_hz
                    * C
                    / (2.0 * (bandwidth_hz / chirp_s))
                )

                peak_velocity_mps = (
                    peak_doppler_hz * C / (2.0 * fc_hz)
                )

    shifted_peak = (
        peak_doppler + chirp_count // 2
    ) % chirp_count

    print(
        f"Peak bins: range={peak_range}, "
        f"doppler_unshifted={peak_doppler}, "
        f"doppler_shifted={shifted_peak}"
    )
    print(
        f"Beat={peak_beat_hz:.3f} Hz, "
        f"Doppler={peak_doppler_hz:.3f} Hz"
    )
    print(
        f"Apparent signed range={peak_range_m:.3f} m, "
        f"signed velocity={peak_velocity_mps:.3f} m/s"
    )

    # 저장·그래프용 축과 fftshift는 측정 종료 후 생성합니다.
    beat_hz = np.fft.fftfreq(sample_count, d=1.0 / fs)
    doppler_hz = np.fft.fftshift(
        np.fft.fftfreq(chirp_count, d=prp_s)
    )

    return {
        "baseband": frame,
        "range_fft": range_fft,
        "range_doppler": np.fft.fftshift(doppler_fft, axes=0),
        "beat_hz": beat_hz,
        "doppler_hz": doppler_hz,
        "range_m": beat_hz * C / (2.0 * (bandwidth_hz / chirp_s)),
        "velocity_mps": doppler_hz * C / (2.0 * fc_hz),
        "sample_rate_hz": fs,
        "prp_s": prp_s,
        "chirp_s": chirp_s,
        "bandwidth_hz": bandwidth_hz,
        "fc_hz": fc_hz,
    }


def plot_result(result):
    import matplotlib.pyplot as plt

    amplitude = np.abs(result["range_doppler"])
    db = 20.0 * np.log10(np.maximum(amplitude, 1e-30))
    db -= db.max()

    plt.pcolormesh(
        np.fft.fftshift(result["range_m"]),
        result["velocity_mps"],
        np.fft.fftshift(db, axes=1),
        shading="auto",
        vmin=-60,
        vmax=0,
    )
    plt.xlabel("Signed apparent range (m)")
    plt.ylabel("Signed velocity (m/s)")
    plt.colorbar(label="Relative amplitude (dB)")
    plt.title("Range-Doppler")
    plt.tight_layout()
    plt.show()


def main():
    args = parse_args()
    profiler = Profiler(thread_cpu=args.thread_cpu)

    try:
        print(f"NumPy version: {np.__version__}")

        frame, fs, receive_span_ms = receive_frame(args, profiler)
        result = process_frame(frame, fs, args, profiler)

        print("\nReceive timing (per-call averages)")
        profiler.print_report(
            [
                "receive_total",
                "socket_wait",
                "decode",
                "reassembly",
            ]
        )

        print("\nProcessing timing (per-frame averages)")
        profiler.print_report(PROCESS_STAGES)
        profiler.print_fft_summary()

        scope = (
            "calling thread"
            if args.thread_cpu
            else "whole receiver process"
        )

        print(
            f"\nCPU scope: {scope}."
            "\n100% = one logical core."
            "\nTotal rows overlap child rows."
            "\nWindow creation, warmup, printing, saving and plotting "
            "are excluded from processing_total."
            "\nRepeated-frame measurements reflect warm-cache processing."
        )

        if args.output:
            np.savez(
                args.output,
                **result,
                **profiler.export(),
                first_to_last_packet_ms=receive_span_ms,
            )
            print(f"\nSaved: {args.output}")

        if args.plot:
            plot_result(result)

        return 0

    except (OSError, ValueError, TimeoutError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())