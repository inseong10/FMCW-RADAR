#!/usr/bin/env python3
"""Send one recorded 128x128 RSPY frame over UDP; standard library only.

Run on the Ubuntu NFS host when RadarSimPy runs on the Windows host.
The record contains original RSPY datagrams, not precomputed FFT results.
"""
import argparse
import ipaddress
import math
from pathlib import Path
import socket
import struct
import time

HEADER = struct.Struct('!4sBBHIIId')


def read_frame(path):
    packets = []
    seen = set()
    rate = None
    with path.open('rb') as stream:
        if stream.read(8) != b'RSPB0001':
            raise ValueError('Invalid RSPB record header')
        while True:
            size = stream.read(4)
            if not size:
                break
            if len(size) != 4 or struct.unpack('!I', size)[0] != HEADER.size + 128 * 8:
                raise ValueError('Expected a complete 128-sample RSPY packet')
            packet = stream.read(HEADER.size + 128 * 8)
            if len(packet) != HEADER.size + 128 * 8:
                raise ValueError('Truncated RSPY packet')
            magic, version, dtype, channel, index, chirps, samples, fs = HEADER.unpack_from(packet)
            if (magic, version, dtype, channel, chirps, samples) != (b'RSPY', 1, 1, 0, 128, 128):
                raise ValueError('Expected channel 0, protocol 1 float32 IQ, shape 128x128')
            if index >= 128 or index in seen or not math.isfinite(fs) or fs <= 0:
                raise ValueError('Invalid/duplicate chirp or sample rate')
            if rate is not None and rate != fs:
                raise ValueError('Sample rate changed within the frame')
            seen.add(index)
            rate = fs
            packets.append(packet)
    if len(packets) != 128:
        raise ValueError('Expected exactly 128 chirps')
    return packets, rate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('record', type=Path)
    parser.add_argument('--ip', default='10.0.0.3')
    parser.add_argument('--port', type=int, default=5000)
    parser.add_argument('--packet-delay-ms', type=float, default=2.0)
    args = parser.parse_args()
    try:
        destination = (str(ipaddress.IPv4Address(args.ip)), args.port)
        if not 1 <= args.port <= 65535 or not math.isfinite(args.packet_delay_ms) or args.packet_delay_ms < 0:
            raise ValueError('Invalid port or packet delay')
        packets, rate = read_frame(args.record)
        total = 0
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            for index, packet in enumerate(packets):
                total += sock.sendto(packet, destination)
                if index + 1 < len(packets):
                    time.sleep(args.packet_delay_ms / 1000)
        print(f'Sent {len(packets)} UDP packets ({total} bytes), fs={rate:g}, to {destination[0]}:{destination[1]}')
        print('UDP transmission completed; confirm FRAME_PASS on the board.')
    except (OSError, ValueError) as exc:
        parser.exit(1, f'Error: {exc}\n')


if __name__ == '__main__':
    main()
