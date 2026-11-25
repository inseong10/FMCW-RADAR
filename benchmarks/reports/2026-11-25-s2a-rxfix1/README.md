# S2a-rxfix1 — ARM receive failure, compatibility fix and diagnostics

Initial board PS run failed: user reported 2560 invalid datagrams, no decoded
frame and only a CSV header. The sender recorded 20*128 packets to 10.0.0.3:5000
with run92002 and no schedule overrun. Ping/routing worked. See
`initial_console_evidence.txt` and the original sender JSON. Complete board raw
files have not yet been collected. This is not a successful board measurement.

The original code rejected MSG_TRUNC, MSG_CTRUNC and all decode errors together.
On ARM32 it allocated 36 bytes for ancillary data: 20-byte old timestamp plus
16-byte overflow space. An appended 28-byte time64 timestamp needs more room.
[The glibc maintainers documented this conversion/truncation problem](https://sourceware.org/pipermail/glibc-cvs/2022q1/076544.html).
This is a plausible explanation, not a diagnosis proven by the old counter.

The fix allocates 512 aligned control bytes, handles both 8-byte time32 and
16-byte time64 timestamp payloads, preserves rejection on truncation, and splits
payload/control/decode error counters. The first rejection is logged promptly.
Idle timeout now follows any received datagram, so an all-invalid burst exits
after idle timeout instead of waiting the full initial five minutes.

`--diagnose-first-packet` peeks once with the old buffer before receiving the
same datagram with the enlarged buffer. It prints original buffer flags and
then actual receive flags, control types/lengths and first valid run/frame.
This may confirm/refute the hypothesis without changing the wire payload.
The flag and sizeof(time_t/timespec) are recorded in environment.txt and
summary.json. Diagnostic runs include console/probe overhead in the first
frame and must not be used for throughput acceptance.

PC result: 8 unittest methods PASS in `pc_tests.log`, including unchanged
PS/model six-case bin/CFAR comparisons and new time32/time64, post-2038,
malformed timestamp and ARM32 dual-control capacity checks. These tests do not
execute Linux recvmsg. Updated Ubuntu smoke now exercises the peek on its
normal model case; host/ARM rebuild and board execution remain pending.

The exact original seven compiled sources are preserved under ignored
`build/s2a_arm_20261125_201834/source_snapshot/`; the old ARM binary and build
identities remain unchanged. New source/config hashes are in `pc_identity.json`.
`rebuild_s2a_rxfix1.sh` retains the failed board directory when present, builds
and smokes on Ubuntu, cross-builds ARM, and deploys to a fresh path. No existing
board deployment is overwritten.

Follow-up: updated Ubuntu3 smoke and ARM build have passed independent raw-file
checks, retained under `ubuntu/`. Eight compiled source hashes match the local
source. New ARM SHA is
`e221f04d232780c9193ca7f8c03df253e9fdba533d2bf7305e0da7c5cd508387`.
Original failed board raw files are now retained under `failed_ps02_raw/` and
independently confirm 2560 invalid datagrams and20 missing frame IDs.
The later board run92003 was reported as READY then processed0, without any
first-packet log. The specified sender completion JSON is absent from the
shared build directory. That run's raw counters have not been collected;
receive start timeout is plausible but not proven. The ARM32 buffer hypothesis
still awaits a synchronized board input/probe result.

Subsequent reported board probe (run92004, ps_02) confirms the old-buffer
capacity failure: MSG_PEEK with36 bytes sets control_truncated=1, while the same
packet with the expanded buffer has flags0 and48 bytes of control records
(time32 type35/length20 and time64 type64/length28). The receiver then reports
20/20 processed frames. `board_probe_console.txt` retains this user-reported
evidence and `board_ps02_sender.json` records the50ms sender with no overruns.
Full board traces/counters/detections/resources remain pending collection.
The preceding run92003 counters were also supplied: received_packets0 and
failed0/interrupted0 confirm that earlier run received no datagrams.
