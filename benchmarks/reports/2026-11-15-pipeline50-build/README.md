# E10: pipeline/50 MHz Vivado implementation

The user reported bitstream completion. The shared output files were independently
read from run `fft128_ps_pipeline_20261115_224343` on 2026-11-15.

| Item | Implemented result |
|---|---:|
| Clock | 50 MHz, pipeline core selected |
| Setup WNS | 9.807 ns |
| Hold WHS | 0.034 ns |
| Setup / hold failing endpoints | 0 / 0 |
| Slice LUTs | 1,364 / 17,600 |
| Slice registers | 1,048 / 35,200 |
| DSPs | 4 / 80 |
| BRAM tiles | 2.5 / 60 |

Generated-reset simulation passed ID/length and lock-loss recovery. All specified
timing constraints were met. Original reports are preserved here, along with
`implementation_summary.json` containing original artifact SHA256 hashes.
Bitstream and XSA copies are retained locally under
`build/vivado/fft128_pipeline50_20261115_224343/` and excluded from source control.

This establishes implementation at 50 MHz, not board correctness or latency.
Raw BIN conversion is complete. The user-reported board self-test passed four
vectors / 512 complex bins; see `board_selftest.json` and `.log`. Full-frame
validation and cycle profiling have now passed: 861 cycles/FFT, 4.408320 ms internal,
27.327809 ms instrumented total mean. See [profile results](../2026-11-15-pipeline50-profile/README.md).
The unprofiled PS/PL comparison has now passed: PS median 5.557368 ms, PL median
25.2591725 ms; see [final benchmark](../2026-11-15-pipeline50-benchmark/README.md). See [experiment log](../../../docs/experiment_log.md).

`build_config.json` and `board_selftest.json` retain the status at build/self-test
capture time. The final `implementation_summary.json` and linked later reports
record completed full-frame validation and benchmark results.
