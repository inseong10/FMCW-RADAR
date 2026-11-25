# S2a — Ubuntu loopback smoke and ARM build (2026-11-25)

Evidence: Ubuntu VM raw files, independently recalculated on Windows. No board
execution or FPGA result in this report. CPU affinity was not requested for
these VM tests (`cpu0=0`). The input is multi4 noise, Hann, 20 frames at 50 ms,
128-packet bursts. The actual board test remains pending.

| Case | Processed | Dropped/status | Independent result |
|---|---:|---|---|
| Integer software model | 20 | 0 | trace, resource records, every detection list PASS |
| PS double FFTW | 20 | 0 | trace, resource records, every detection list PASS |
| Model, deliberate missing chirp in frame 2 | 19 | 1 partial_evicted | exact intended loss accounted for, other detections PASS |

All three have zero invalid packets, kernel drops, clock errors, worker errors
and missing kernel timestamps. Six resource intervals were recorded per case.
The original summaries equal independent recalculation. `hardware=false` is
required for these cases. These are instrumentation checks, not S2b acceptance.

`raw/` retains all original frame/resource/detection CSVs, environment/counters,
sender schedules and receiver logs. `independent_summary.json` is recalculated
from the retained raw traces. `identity.json` records all raw hashes, source and
tool identities, executable hashes and ELF machine/class checks.
Host/ARM build logs and compiler/source records are in `host_build/` and
`arm_build/`. Both used Ubuntu GCC/G++ 9.4.0 with the recorded flags.

Seven compiled source hashes and five check/send/build tool identities matched
the local working source. ARM ELF32 machine40 hard-float flags0x5000400,
executable SHA256:
`21548ffb2ed04c89e271f4dd1a952eafabfd58d5c8e64c6cb895d9b855438371`.
Full build directories including binaries are retained in ignored
`build/s2a_host_20261125_201834/`, `build/s2a_arm_20261125_201834/`, and
`build/s2a_smoke_20261125_201834/`.
