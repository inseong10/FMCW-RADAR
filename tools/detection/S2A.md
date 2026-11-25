# S2a integrated stream instrumentation

Status: S2a is complete. PC pipeline checks, Ubuntu three-case smoke, ARM build,
and board PS/PL raw verification have passed. Each board backend processed20
frames at50ms with4/4 detections per frame,0 false detections and0 drops;
timestamps and CPU/RSS records were independently checked.

ARM32 ancillary buffer truncation was reproduced and fixed with512 bytes plus
time32/time64 parsing. The failure, diagnostic probe and exact source/build
identities are preserved in the experiment journal and
`benchmarks/reports/2026-11-25-s2a-rxfix1/`. Board evidence is in
`benchmarks/reports/2026-11-25-s2a-board/`.

The20-frame board runs used diagnostic probing and are not throughput
acceptance. S2b will disable diagnostics and begin with200 frames at12.8ms,
before the10,000-frame acceptance run. Those load tests have not yet run.
S1b/S1c binaries and historical results are preserved.

The new Linux `stream-receiver` keeps one PS double FFTW 2D ESTIMATE plan or one
E14 ABI8 full-frame device open. `model` explicitly uses the software integer
reference and never claims FPGA access. Input/window/quantization, FFT, power,
the shared CA-CFAR and flushed detection output run in one worker process.
The PS implementation uses a direct 2D FFTW plan; it is a new baseline and does
not substitute for the later optimized NEON comparison in S2c.

RSPY **v2** carries channel 0, run ID, frame ID 1..N and a sender timestamp.
It has a 52-byte network-order header (`!4sBBHQQIIIdQ`) and the unchanged 128
complex float32 IQ samples per chirp. Only 128x128 is supported here. The v1
sender and single-frame receivers retain their existing protocol.
All 128 chirps in a frame must share run/frame ID, sample rate and sender time.
PS applies symmetric Hann in double; PL/model applies it then rounds to float32
before the existing magnitude-to-16384 ties-to-even quantizer, matching S1c.
Preparation is now measured on the receiver. PL uses the existing firmware and
driver; no bitstream reload or module replacement is required.

The receive thread has bounded partial frames (default 4, evicts the lowest ID)
and a bounded completed queue (default 4, drops a newly completed frame if full).
Worker processing continues independently. Every expected frame appears in
`frames.csv`, including never-seen, partial, evicted and queue-full frames.
Late packets of finalized frames cannot restart them. All threads inherit CPU0
when `--cpu0` is given. IRQ affinity and network stack placement are not changed.

`SO_TIMESTAMPNS` records first-packet kernel receive time, mapped from realtime
to monotonic per packet; clock-offset changes >2 ms invalidate the run.
Both first-kernel-packet-to-output and completed-frame-to-output are reported.
The former includes acquisition, socket delay, assembly and queueing. Remote
sender timestamps are identifiers only: unsynchronized host clocks are never
subtracted. `SO_RXQ_OVFL` plus expected frame IDs account for observed loss.
The final cumulative overflow notification may lag a final lost packet; missing
frame IDs remain the primary end-to-end loss check.
The control buffer now holds 512 bytes, including room for time32/time64
conversion and overflow messages. With `--diagnose-first-packet`, one MSG_PEEK
using the original small buffer records its truncation flags before normal
receive. This flag adds diagnostic overhead and excludes the run from throughput
acceptance. Invalid payload/control/decode counts are separate. Any datagram,
including an invalid one, starts/resets the idle deadline; no datagrams use the
initial start deadline.

`detections.csv` is flushed once per frame before output completion is timed.
It uses a -1/-1 sentinel for frames without peaks. Flush does not include fsync,
consumer display, or downstream network delivery. Choose and record the output
storage path: NFS and local storage are different measurement conditions.
Frame trace writing happens after draining; resource sampling and detection
output IO happen during processing. Samples every 200 ms record process CPU
(one core = 100%), whole-system CPU, and RSS from `/proc`. Resource intervals
may straddle the active frame window and must not be treated as exact per-frame
CPU values. Initial manual waiting is visible in resource timestamps.

On Ubuntu, build and run the localhost correctness/loss smoke before ARM:

```sh
tag=$(date +%Y%m%d_%H%M%S)
bash tools/detection/build_s2a.sh host "build/s2a_host_$tag" &&
python3 tools/detection/smoke_s2a.py \
  --binary "build/s2a_host_$tag/stream-receiver" --out "build/s2a_smoke_$tag" &&
bash tools/detection/build_s2a.sh arm "build/s2a_arm_$tag"
```

The smoke checks normal PS/model runs (20 frames, 50 ms, multi4 Hann), all
per-frame peak lists and trace consistency. It deliberately omits a chirp in
frame 2 with partial capacity 1 and requires exactly 19 processed frames and one
evicted partial frame. These are VM tests, not board measurements.

Initial board smoke, after copying the new ARM binary to a fresh deployment:

```sh
sudo /opt/fft128/NEW_S2A/stream-receiver --cpu0 \
  --backend ps --fftw-lib /opt/fft128/s1b_20261125_192718/libfftw3.so.3 \
  --run-id 92001 --frames 20 --out /opt/fft128/NEW_S2A/ps_01
```

Wait for `S2A_READY`, then Ubuntu sends:

```sh
python3 tools/sender/replay_stream.py \
  benchmarks/fixtures/radarsimpy_128x128_sim_multi4_noise.rspb \
  --ip 10.0.0.3 --run-id 92001 --frames 20 --period-ms 50 \
  --out build/s2a_sender_ps_01.json
```

Repeat with a fresh directory/run ID and `--backend pl` for E14. The output
directory must not already exist. Copy results from NFS into a new shared build
directory and run `python3 tools/detection/analyze_stream.py RESULT --sender JSON`.
No component timing sums are used. The initial sender uses bursts of 128
packets; `--chirp-gap-us 100` is a different acquisition pattern that must be
recorded. Sender deadline lateness and overruns invalidate an offered-load
claim; neither the smoke nor the analyzer declares S2b/S2c acceptance.
