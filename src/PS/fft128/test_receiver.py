"""PC tests of framing and the explicit software backend; no hardware implied."""
import importlib.util
import math
from pathlib import Path
import socket
import struct
import threading
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('fft128', HERE/'receiver.py')
fft = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fft)


def packet(index, fs=1.6e6, channel=0):
    return fft.HEADER.pack(b'RSPY',1,1,channel,index,128,128,fs)+struct.pack('!256f', *([0.25,-0.125]*128))


class ReceiverTests(unittest.TestCase):
    def test_decoder_rejects_wrong_shape_length_and_nonfinite(self):
        good = packet(127)
        self.assertEqual(fft.decode_packet(good)[:3], (0,127,1.6e6))
        bad = [good[:-1], packet(128), packet(0,fs=math.nan),
               good[:28]+struct.pack('!f',math.inf)+good[32:],
               fft.HEADER.pack(b'RSPY',1,1,0,0,256,128,1.6e6)+good[28:]]
        for data in bad:
            with self.assertRaises(ValueError): fft.decode_packet(data)

    def test_quantizer_headroom_and_packing(self):
        frame = [[complex(-3,4),0j]*64]*128
        quantized, scale = fft.quantize(frame)
        self.assertAlmostEqual(scale, 16384/5)
        self.assertEqual(fft.unpack_iq(fft.pack_iq((-32768,32767))),(-32768,32767))
        self.assertLessEqual(abs(complex(*fft.unpack_iq(quantized[0][0]))),16385)

    def test_udp_reordering_duplicates_peer_lock_and_missing_chirp(self):
        # Wait for the receiver's bind instead of relying on a fixed sleep.
        original = fft.socket.socket
        ready = threading.Event()
        received_first = threading.Event()
        class Socket(original):
            def bind(self, addr):
                super().bind(addr)
                self.bound_port = self.getsockname()[1]
                state['port'] = self.bound_port
                ready.set()
            def recvfrom(self, size):
                result = super().recvfrom(size)
                received_first.set()
                return result
        state = {}
        def worker():
            try: state['result'] = fft.receive('127.0.0.1',0,0,2)
            except Exception as exc: state['error'] = exc
        fft.socket.socket = Socket
        try:
            thread = threading.Thread(target=worker)
            thread.start()
            self.assertTrue(ready.wait(2))
            dest = ('127.0.0.1',state['port'])
            with original(socket.AF_INET,socket.SOCK_DGRAM) as sender:
                sender.sendto(packet(127),dest)
                self.assertTrue(received_first.wait(2))
                with original(socket.AF_INET,socket.SOCK_DGRAM) as stranger:
                    stranger.sendto(packet(0,fs=2e6),dest)
                # Duplicate and unrelated channel must not count as new chirps.
                sender.sendto(packet(127),dest)
                sender.sendto(packet(0,channel=1),dest)
                for k in reversed(range(127)):
                    sender.sendto(packet(k),dest)
            thread.join(3)
            self.assertFalse(thread.is_alive())
            self.assertNotIn('error',state)
            frame,fs = state['result']
            self.assertEqual((len(frame),len(frame[0]),fs),(128,128,1.6e6))
            self.assertEqual(frame[0][0],complex(.25,-.125))
        finally:
            fft.socket.socket=original
        with self.assertRaises((TimeoutError,socket.timeout)):
            fft.receive('127.0.0.1',0,0,.05)


if __name__ == '__main__':
    unittest.main()
