# S2a — board PS/PL stream instrumentation (2026-11-25)

Final status: PS and PL correctness/instrumentation checks have passed.
S2b sustained-input acceptance remains unmeasured. Earlier steps and follow-ups
below preserve the verification history.

Evidence: actual board raw traces, independently recalculated on Windows.
CPU0, run92004, 128x128 multi4 noise/Hann, 20 frames at50ms, burst input,
warmup10, queue4/partial4. Output storage is the board NFS-root deployment.
Diagnostic first-packet peek/console logging is enabled; this run is excluded
from throughput acceptance and is not a12.8ms sustained-input result.

Independent result:20/20 processed,2560 received packets, zero drops and all
invalid/truncation/decode/kernel/clock/worker counters0. Every frame contains
exactly the expected four peaks (10,10),(107,20),(4,37),(87,53),4/4 ground-truth
hits and0 false detections. All80 peak powers and thresholds match the independent
NumPy FFT/CA-CFAR reference (rtol1e-9/1e-8). Production stream spectra are not
exported, so this check does not claim an additional all-bin board comparison.

| Recorded scope | Median ms | P99 ms |
|---|---:|---:|
| First kernel packet to CSV flush |22.4006925|24.7878909|
| Completed frame to CSV flush |13.662444|14.19137802|
| Queue wait |0.125175|0.16362786|

These are diagnostic-run observations, not performance acceptance. Resource
records contain22 intervals,6 intersecting active frames; maximum RSS5410816
bytes. Initial manual waiting is visible in the raw resource timestamps.

The ARM32 control-buffer cause is now confirmed from retained raw console:
old36-byte MSG_PEEK has flags8/control_truncated1; the same datagram received
with512 bytes has flags0/controllen48 and timestamp cmsgs35/20bytes and64/28bytes.
Environment records time_t4bytes/timespec8bytes, cpu0=1 and diagnostic_probe=1.

`ps_diagnostic/` retains the original Ubuntu-checked raw CSVs, counters and
environment; `independent_ps_summary.json` exactly reproduces its summary.
`startup_no_input/` and `ps_01.console.log` preserve the prior run92003 with
zero received packets. Sender schedule/input identity is in
`ps_diagnostic_sender.json`; `ps_identity_and_correctness.json` records binary,
all8 compiled source hashes, correctness and complete raw-file hashes.
The ARM executable SHA matches both the deployed artifacts manifest and build:
`e221f04d232780c9193ca7f8c03df253e9fdba533d2bf7305e0da7c5cd508387`.
Full deployment including the binary is retained in ignored
`build/s2a_board_results_20261125_rxfix1_ps_02/`.

PS stream correctness and instrumentation smoke have passed. PL stream smoke
and later non-diagnostic sustained-input acceptance remain pending.

PL follow-up: user-reported run92005 console now shows20/20 processed frames
with the same successful expanded-buffer receive. See `pl_user_console.txt`.
The sender record is retained when available; complete PL raw verification
remains pending collection. This report does not yet declare PL correctness.

Final follow-up: PL raw files have now been collected in `pl_diagnostic/` and
independently checked in `independent_pl_summary.json` and
`pl_identity_and_correctness.json`. All20 frames/2560 packets processed with
zero drops and all invalid/kernel/clock/error counters0. Every frame has4/4
targets and0 false detections. All80 peak powers match the independent Python
Q15 model exactly; thresholds match NumPy. CPU0/hardware=true, all8 compiled
sources, deployed binary/artifact hashes and original input identity match.
This numerical check covers exported detections, not an unexported full spectrum.

| Diagnostic median, ms | PS | PL |
|---|---:|---:|
| Preparation |2.350314|10.150683|
| FFT / transfer |5.221950|1.756872|
| Power / CFAR |5.756982|6.251232|
| Completed frame to CSV flush |13.662444|18.5183285|
| First kernel packet to CSV flush |22.4006925|27.2200115|

PL completed-frame P99 is18.65466576ms and first-kernel-packet P99 is29.70428982ms.
PL has27 resource intervals,5 intersecting active frames, max RSS4149248bytes.
The integrated PL path currently has substantially more preparation cost despite
faster FFT/transfer. This motivates later bottleneck investigation; it does not
establish sustainable frame rate, and component medians are never summed as an
end-to-end statistic. Both runs used the diagnostic probe/console setting.

S2a instrumentation/correctness smoke is complete for PS and PL. S2b will use
the same binary with diagnostics disabled and12.8ms offered period; an initial
200-frame load check precedes the10,000-frame acceptance run. No S2b measurement
has yet been made.
