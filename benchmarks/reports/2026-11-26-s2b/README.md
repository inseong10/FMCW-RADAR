# S2b — 12.8 ms preliminary continuous-input test

Run 92111, 2026-11-26: PS backend, CPU0, Hann, warmup10,
200 frames, queue4/partial4, diagnostic first-packet probe disabled,
128x128 multi4-noise input, burst chirps and 12.8 ms frame period.
The existing rxfix1 stream receiver and FFTW library were reused.
This follows the selected PL100MHz offline comparison; this PS run does
not execute the FPGA. Current-run board clock and binary identity capture
remain pending with the receiver raw files.

User console reports **91/200 processed**. The remaining 109 frames are
not yet classified: receiver counters, frame trace, detections and resources
have not been collected. No receiver bottleneck or latency is established.

The original sender JSON is retained in `ps_92111_sender.json`.
All 200 schedule IDs, maximum lateness and overrun count were independently
recalculated from its raw timestamps:

- 32 frames finished sending after their scheduled period deadline.
- Maximum start lateness: 14.697306 ms.
- Actual frame-start intervals: 2.263128 to 26.108878 ms.

The offered load fails the existing sender validity criterion (zero overruns
and maximum lateness below 10% of the period). Receiver completion also fails
the zero-drop criterion. Preserve this as a failed preliminary attempt; it
does not establish the PS maximum sustainable frame rate or a fair PS/PL
throughput comparison. Do not derive FPS from 91/200 or from sender duration.

Next: collect the receiver raw directory, classify missing/partial/queue-full
frames and socket errors, inspect both latency anchors and resource samples,
and investigate sender scheduling before accepting another comparison run.
Keep the original run unchanged and use fresh paths/run IDs for subsequent runs.

## Receiver raw follow-up

The five original receiver files (49,040 bytes) have now been collected from
the VMware share, copied into ignored `build/s2b_ps_100mhz_200_01`, checked
byte-for-byte by SHA256, and retained in `ps_92111_raw/`.
The preliminary records above are preserved as the earlier evidence state.
`ps_92111_verified.json` and `ps_92111_trace_summary.json` contain the final
independent analysis for this attempt. Its reproducible verification driver,
original analyzer and NumPy reference sources are retained alongside them.

| Frame status | Count |
|---|---:|
| Processed | 91 |
| Complete frame discarded because processing queue was full | 52 |
| Incomplete frame evicted from partial-frame buffer | 50 |
| Incomplete frame left at termination | 3 |
| No packets observed | 4 |

All 21,794 received packets are accounted for by the frame trace. The recorded
3,806 socket/kernel drops bring the total to exactly 25,600 expected packets.
The effective socket receive buffer is 360,448 bytes. There are no invalid,
decode, metadata, truncation, worker-failure or interruption errors. These
observations establish both queue overflow and receive-buffer loss in this
attempt; sender scheduling irregularity remains a confounding load variable.

All 91 processed frames contain exactly four expected targets and zero false
detections. All 364 peak powers and thresholds match the normalized independent
NumPy FFT/CA-CFAR calculation (maximum relative errors 4.06e-16 and 9.82e-14).
Unprocessed frames are not covered by this accuracy result. No full FFT spectrum
was exported by this production stream run.

| Diagnostic interval for processed frames | Median ms | P99 ms |
|---|---:|---:|
| First kernel packet to CSV flush | 142.090342 | 167.2789714 |
| Completed frame to CSV flush | 131.645827 | 149.4763043 |
| Queue wait | 101.381077 | 117.7805356 |
| Preparation | 2.381610 | 12.2865024 |
| FFT | 12.713731 | 19.8429558 |
| Power/CFAR | 13.284504 | 25.8785065 |
| Worker start to CSV flush | 29.069874 | 40.9852749 |

The worker intervals include preemption and competition with receiving on CPU0;
they are elapsed times, not isolated CPU computation costs. The process used
94.02% of one core across the 13 whole resource intervals overlapping active
frames; two-core system usage was 50.19%. Boundary sample margins are included.
Maximum RSS was 7,335,936 bytes.

Four clock-mapping errors invalidate acceptance based on kernel timestamps.
Their cause cannot be recovered because per-packet clock-calibration samples
were not logged. Retain all timings as diagnostic survivor observations rather
than accepting or correcting their values. Clock/binary identity capture from
this specific run is still absent; the preceding 100MHz offline verification
does not supply a current-run frequency measurement.

Next run: a non-diagnostic PS 200-frame, **50 ms** baseline with the same binary,
CPU affinity, buffers, fixture, Hann and CFAR. Check sender validity, zero drops
and clock counters at this lower load before PL and a period sweep. This is a
diagnostic baseline, not a change to the 12.8 ms S2b acceptance target. Do not
enlarge queues or change core allocation while establishing this baseline.

## User-directed resource policy update

The user subsequently required use of the board's available resources for the
final comparison. The CPU0-only 50ms follow-up above is therefore superseded
as the next planned run; its execution status is unknown. Preserve any result
under its original identity rather than relabeling it as a two-core run.

S2b-2core next: PS run92121, 200 frames at12.8ms, remove `--cpu0`, retain the
same binary, Hann/CFAR, warmup10, queue4/partial4 and burst sender. Confirm both
CPUs online and inherited allowed CPUs0-1. The PL follow-up must also permit
both CPU cores, with the selected100MHz FPGA configuration. This is still an
unmeasured preliminary experiment. Sender-load and clock validity checks stay
in force; unpinning is not assumed to repair either earlier error.

The existing receiver already has receive, processing and sampling threads;
removing affinity restriction permits concurrency but does not parallelize
the FFT/CFAR worker internally or establish an optimal CPU implementation.
The final system comparison must also consider measured PS bottlenecks and
validated NEON/FFTW/CFAR improvements under the same resource budget. Do not
call the unoptimized double-FFTW stream path the maximum possible PS result.

## Run92121 user console and sender verification

The user reports `processed=150 expected=200` after omitting `--cpu0` with
otherwise unchanged12.8ms/200-frame PS settings. Online-CPU/allowed-affinity
output was not supplied. Receiver raw counters, traces and resources are not
yet collected, so neither actual core utilization nor the missing-frame cause
has been established for this run.

The original sender schedule in `ps_92121_sender.json` was independently checked:
200 ordered IDs,35 overruns, maximum start lateness16.692511ms. Sending duration
median3.0403965ms/max6.881976ms; frame-start interval median14.425804ms,
min2.588512ms/max28.919078ms. Offered load is invalid. The completed-frame count
is greater than91 in run92111, but differing invalid load means150/91 is not a
validated speedup and neither run establishes sustainable FPS.

Next: collect the receiver raw directory, and run `tools/sender/check_pacing.py`
on Ubuntu to compare sleep and spin deadline wakeups without sending packets.
This diagnostic tests a timer/scheduling hypothesis; its outcome cannot certify
actual network offered load. It writes both raw schedules, CPU consumption and
the same10%-of-period wakeup threshold. A spin test uses one VM CPU for about
2.56s at200x12.8ms; it does not run on the board. Default production sender
behavior has not changed. PC deterministic-clock checks passed3tests; VM
execution and any improvement remain unverified.

## Run92121 raw verification and VM pacing result

Five original receiver files,66,353 bytes, are now retained in `ps_92121_raw/`.
Their shared/local SHA256 values match. `ps_92121_verified.json` and the saved
driver `verify_s2b_92121.py.txt` independently account for all200 frame IDs:
processed150, queue_full35, partial_evicted11, partial4. All150 processed
frames contain4/4 targets and zero false detections; all600 peak powers and
thresholds match the normalized NumPy reference. Unprocessed frames and full
FFT spectra are not covered by this correctness result.

The trace accounts for all25,393 received packets. Against25,600 expected
packets,207 were unreceived;192 are reported by the recorded kernel-drop
counter and15 remain unlocalized. Do not silently equate192 with all packet
loss. Decode/truncation/metadata/kernel-missing/clock/worker error counts are0.
The inherited allowed-CPU mask was not captured, but process CPU consumption
above one core demonstrates multi-core execution: duration-weighted active
process CPU134.6725% of one core, system CPU68.6313%, maximum RSS7,380,992bytes.
The14 overlapping whole sample intervals include boundary margins.

| Diagnostic survivor timing | Median ms | P99 ms |
|---|---:|---:|
| First kernel packet to CSV flush |81.847453|95.54649946|
| Completed frame to CSV flush |75.547510|88.44221914|
| Queue wait |57.5811215|71.8969684|
| Preparation |2.429157|7.96000734|
| FFT |5.409438|11.5735578|
| Power/CFAR |5.570661|11.84762527|
| Worker start to CSV flush |16.389597|22.96997638|

This attempt still fails both loss and offered-load requirements. These values
are not a sustainable-throughput acceptance result or isolated affinity speedup.

The Ubuntu pacing raw file is retained in `pacing_12p8ms_01.json`; both200-row
schedules and thresholds were independently recomputed, and its embedded source
SHA matches `check_pacing_at_vm_probe.py.txt`. On Ubuntu Python3.8.10,4 VM CPUs:

| Deadline-only mode | Median lateness ms | Max lateness ms | >=1.28ms | Process CPU % |
|---|---:|---:|---:|---:|
| sleep |4.881992|15.732412|169|0.3784|
| spin |0.000404|0.010425|0|99.9727|

Waiting policy materially affects deadline wakeups in this VM. The result does
not identify the hypervisor/host root cause or prove actual UDP offered load.

## S2b-spin: actual sender option prepared

`replay_stream.py --wait-mode spin` now permits CPU-based waiting on the sender
VM for both frame and optional chirp deadlines. Sleep remains the default.
Wire format, fixture, frame IDs, absolute schedule, burst spacing and original
overrun/lateness criteria are preserved. No receiver, FPGA, core policy or
buffer change is included. Sender JSON adds wait mode, process CPU, Python and
source SHA; console prints maximum lateness. Late frames are still recorded.

PC validation passed8checks:6 deterministic clock checks and2 real loopback
wire/ID/deliberate-loss checks covering default sleep and selected spin.
Python3.8 grammar passed for the4 changed/relevant Python files. Exact current
source identities and the sender copy are retained in `sender_spin_pc_checks.json`
and `replay_stream_spin.py.txt`. Runtime sender files were staged with backups;
the shared independently modified receiver test file was preserved.

Next actual run is PS92122,200frames/12.8ms, unpinned receiver, same Hann/CFAR,
warmup10 and queue4/partial4, sender spin. Actual network performance is still
pending. Require valid sender schedule, complete accounting, clock/error checks
and independent detection validation before proceeding to PL or optimizing the
observed worker bottleneck. Retain all earlier invalid-load attempts unchanged.

## Run92122: actual UDP sender validity established

The user reports PS `processed=179 expected=200` with the unpinned receiver
and explicit sender spin mode. Its original sender JSON is retained in
`ps_92122_sender.json`; all200 IDs,128*1076 bytes per frame, source SHA,
absolute deadlines, zero overruns and maximum lateness were independently
checked. Maximum lateness0.051748ms is below1.28ms. Actual frame-start gaps
min12.749686ms/median12.800001ms/max12.850493ms, send-duration median2.700363ms.
Sender CPU99.4241% of one VM core. This is a valid offered load under the
existing criteria, unlike runs92111 and92121.

The receiver's21 unprocessed frames still fail the zero-drop requirement.
Receiver raw counters, loss categories, timings, resource records and detection
validation are pending collection. The console does not establish whether the
loss happened in the kernel, partial-frame buffers or processing queue. Do not
infer a maximum sustainable FPS, a final PS limit or an affinity speedup.

Next: collect the run92122 receiver raw files, and run PL92123 with the same
12.8ms/200-frame spin sender, fixture/Hann/CFAR, unpinned receiver, warmup10,
queue4/partial4 and NFS output. Retain the selected100MHz E14 configuration;
do not rebuild or reprogram. Validate both sender and receiver evidence before
changing the observed processing bottleneck. These are unoptimized integrated
PS/PL baseline attempts, not the final maximum-resource comparison.

## Valid-spin PS92122 and PL92123 raw verification complete

The five original receiver files for each run are retained in `ps_92122_raw/`
and `pl_92123_raw/`, with exact shared/local SHA checks and reproduced trace
summaries. The two saved verification drivers independently validate packet
accounting, all reported detections and the NumPy/double or Q15 integer model.
Both sender schedules satisfy zero overruns and maximum lateness<1.28ms;
PS max0.051748ms, PL max0.041537ms. Both receive all25,600 packets, with all
invalid/decode/truncation/kernel-drop/kernel-missing/clock/worker counters0.

| Result / processed-frame interval | PS double92122 | PL92123 |
|---|---:|---:|
| Processed frames |179/200|123/200|
| Complete frames discarded by full queue |21|77|
| Preparation median ms |2.413164|12.114900|
| FFT/transfer median ms |5.751816|1.265694|
| Power/CFAR median ms |6.014754|8.596980|
| Worker start-to-output median ms |14.463708|22.209787|
| Queue wait median ms |50.525185|79.073491|
| First kernel packet-to-output P99 ms |81.90911946|114.00777688|
| Completed frame-to-output P99 ms |73.21141944|107.04353932|
| Process CPU, % of one core |141.5339|135.4104|
| Max RSS bytes |6656000|5357568|

Each median is computed for its own interval; do not add medians or infer FPS
from the processed counts. CPU figures are duration-weighted whole intervals
overlapping active frames and include boundary margins. Source/clock identity
capture from these specific runs remains absent; selected100MHz context comes
from the preceding verified deployment, not a new frequency measurement.

Every processed frame contains4/4 targets with0false detections:716 PS peaks
match the normalized NumPy calculation;492 PL peak powers match the Q15 integer
model exactly and thresholds match the independent CA model. No full production
FFT spectra are exported. Missing outputs are processing-queue drops in both
runs, not packet-receive loss. Both fail the12.8ms zero-drop/P99 target.

The PL FFT is faster, but its CPU preparation and power/CFAR costs dominate
this integrated implementation. The next [S2b-opt1 CPU candidate](../2026-11-26-s2b-opt1/README.md)
adds validated float FFT selection, aligned FFTW buffers, explicit measured/NEON
planning and Cortex-A9/LTO build options. PC tests passed; ARM/board execution
is pending. PL preparation/Q15 changes are deferred until separately validated.
