# E10: pipeline/50 MHz board profile

The user-pasted board console confirms CPU0 affinity, two warmups, 20 measured
128x128 frames, peak (Doppler 107, Range 20), and bit-exact agreement with the
integer model at all 16,384 complex bins. Each FFT reports 861 cycles.
`summary.json` preserves these console measurements and derived ratios.
`console_excerpt.log` preserves the pasted output with wrapped lines joined.

| Average interval | Serial/20 MHz E09 | Pipeline/50 MHz E10 |
|---|---:|---:|
| Host input MMIO | 23.429884 ms | 11.526609 ms |
| Start and completion wait | 39.927098 ms | 5.054848 ms |
| Host output MMIO | 18.370430 ms | 8.850965 ms |
| PS gather/scatter | 0.947203 ms | 0.946476 ms |
| Instrumented total | 83.694257 ms | 27.327809 ms |
| PL internal, overlapping start/wait | 39.334400 ms | 4.408320 ms |

Total mean time improved by 3.063x and the internal PL interval by 8.923x.
New total median/min/max are 27.329907 / 27.291030 / 27.403428 ms.
Input+output MMIO is 20.377574 ms, about 74.6% of the new total. PS transpose
is nearly unchanged. Pipeline and both core/AXI clock frequency changed together;
this is their combined effect, not an isolated pipeline or DMA measurement.

PL internal time includes staging and overlaps start/wait. Do not add it to host
stages. Counter reads and other unlisted host costs account for the remaining
0.948911 ms by subtraction. This instrumented run must not be combined with the
original unprofiled 300-frame PS comparison as a new acceleration measurement.

The original per-frame profile CSV has now been collected and validated. It is
preserved here with its metadata, timing CSV, analyzer summary and
`collected_validation.json`. All 20 frames and cycle bounds validate; the stored
input and full spectrum match the unprofiled benchmark and serial baseline.
The board timestamp is not the client experiment date. Original console summaries
remain unchanged as historical evidence. The unprofiled benchmark has also been
validated; see [E10 final results](../2026-11-15-pipeline50-benchmark/README.md).
