# E10: pipeline/50 MHz unprofiled board benchmark — validated results

The user ran `run_board.sh /opt/fft128/benchmark/results_pipeline50` and reported
completion of three PS/PL trial pairs, each with ten warmups and 100 measured
frames. All three PL trials matched the integer model at all 16,384 complex bins.
`console_excerpt.log` joins wrapped lines from the supplied console;
`console_summary.json` preserves its statistics and explicitly missing results.

| PL trial | Mean, ms | Median, ms | Min, ms | Max, ms |
|---|---:|---:|---:|---:|
| 1 | 25.260099 | 25.256604 | 25.222806 | 25.429465 |
| 2 | 25.260553 | 25.259575 | 25.224594 | 25.392523 |
| 3 | 25.263327 | 25.260438 | 25.236121 | 25.425432 |

Because each trial has 100 samples, the mean of the displayed trial means is
approximately 25.261326 ms, versus the earlier serial/20 MHz pooled mean
81.525070 ms: about 3.227x shorter. Pipeline and core/AXI clocks changed together.
This comparison uses unprofiled PL runs, separate from diagnostic profile times.

The complete raw results have now been collected and validated with
`compare_board.py`. The historical console summary is retained alongside the
final `comparison.json` and `accuracy_and_progression.json`.

| 300 measured frames per path | PS double FFTW | PL pipeline/50 MHz |
|---|---:|---:|
| Mean, ms | 5.547365 | 25.261326 |
| Median, ms | 5.557368 | 25.259173 |
| 5th–95th percentile, ms | 5.493119–5.605255 | 25.237126–25.284137 |
| Sample coefficient of variation, percent | 0.765931 | 0.092542 |

PL median improved by **3.224977x** from the serial/20 MHz 81.460246 ms,
but remains **4.545168x slower than the PS** measured in this same new run.
Both paths exclude network/IO/quantization/allocation/planning/verification.
The PS retains its stage timer bookkeeping. No DMA or continuous throughput claim.

All three PL stored spectra are bit-identical to the serial baseline, and the
recorded inputs have the same SHA256. NumPy validation passes: maximum PL complex
error 8.749842 Q15 integer units, RMS 1.734691, relative L2 error 1.361021%.
PS maximum error is 1.833e-12. Both peak at (107,20). Every measured PL iteration
was checked against the integer model outside the timer by the board program.
PS uses double arithmetic; PL uses fixed-point Q15.

Individual timing CSVs, console logs, environment, comparison and accuracy summaries
are retained here. `artifact_sha256.json` identifies the complete original artifacts;
Git text newline normalization may change byte hashes of tracked copies. Repeated
full spectra/input CSVs are retained under local ignored
`build/fft128_board_benchmark/results_pipeline50/`. They are needed to rerun the
full accuracy analyzer; compact report files alone reproduce timing statistics.

The raw 20-frame profiles were collected separately and confirm internal time
4.408320 ms and input+output MMIO 20.377574 ms (~74.6% of diagnostic total).
Keep those samples separate from unprofiled timings. The next performance target
is data transfer; DMA and overlap designs have not yet been implemented or timed.
See [experiment log](../../../docs/experiment_log.md).
