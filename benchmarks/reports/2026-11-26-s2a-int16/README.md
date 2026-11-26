# S2a-int16 — ADC-emulated input boundary

Status: implementation and PC validation passed. ADC tests13/13, existing float
regression11/11, and the staged shared-folder ADC tests13/13 passed. Ubuntu host
build/loopback and ARM build subsequently passed independent raw verification;
PS/PL board50ms/20 raw diagnostics also passed independent verification.
The ADC-boundary implementation gates are complete; continuous S2b is pending.
Existing float-input measurements remain unchanged. No commit or push.

System input is fixed-gain ADC-emulated signed16 I/Q. ADC conversion is outside
the timed system. Hann stays inside both receivers; PS int16-to-double is timed.
No frame-peak normalization. Default profile1:16bits, S=1,600,000codes/unit,
round-to-nearest/ties-even and clipping to[-32768,32767]. The four existing
fixtures calibrate the choice once; future frames use the same frozen scale.
Maximum complex calibration amplitude0.009593515132970855 leaves about6.59dB
headroom. Source noise RMS0.00179 corresponds to2864complex LSB. These are
model/input quantities, not board measurements.

E14 ABI8 packs real in bits15:0 and imaginary in31:16. ADC codes map directly
without a shift; one code represents1/32768 in the FFT fixed-point convention.
Each butterfly floors a signed full-width result after right shift16 and
saturates to signed16. Seven stages per axis give normalization1/16384.
PL Hann uses precomputed Q15 coefficient pairs, a combined Q30 product and
one ties-even rounding per component; Python independently models the rule.

Joint changes include input precision/scale, half-sized payload, protocol and
reassembly/storage changes, integer Hann and hoisted backend branching. Keep
these confounders explicit. Use default double/O2 initially, queue4/partial4.
The separate opt1 float/NEON candidate is not the baseline for this experiment.
The working tree also retains opt1's FFTW-aligned PS allocation and omission
of unused PL FFTW buffers. Those differ from the deployed rxfix1 baseline and
can affect plans/cache/memory; record them as additional confounders. Float
precision, MEASURE planning, required NEON and O3/LTO tuning stay disabled in
this initial ADC build. The actual PS plan is saved as `fftw_plan.txt`.
Sender chirp spacing stays0 (frame UDP bursts), as in the existing streaming
baseline. This emulates ADC numeric output; ADC acquisition time is outside
the measured path. Output stays in the existing `/opt/fft128` bundle tree.

Required gates: PC all-bin/model and detection comparison; Ubuntu host smoke
and ARM build with binary SHA; actual PS/PL50ms/20 diagnostic raw validation;
then nondiagnostic12.8ms/200 and10,000-frame S2b. Missing measurements stay empty.

## PC evidence (not board measurements)

Production v3 wire decode/reassembly and PS double FFTW match NumPy across all
16384 complex bins in six cases. The same production integer preparation and
`fft128_process(..., fft128_model, ...)` match independent Python integer
Hann/FFT exactly in all bins. CA-CFAR guard(2,2), train(8,8), Pfa1e-6 and ±1-bin
truth matching are unchanged. Every case has the same ordered peak bins as
the original float baseline:

| Case | Original float hits / false | ADC PS hits / false | ADC PL model hits / false |
|---|---|---|---|
| single_none | 1/1 / 0 | 1/1 / 0 | 1/1 / 0 |
| single_hann | 1/1 / 0 | 1/1 / 0 | 1/1 / 0 |
| multi4_none | 4/4 / 1 | 4/4 / 1 | 4/4 / 1 |
| multi4_hann | 4/4 / 0 | 4/4 / 0 | 4/4 / 0 |
| close_weak_none | 1/3 / 0 | 1/3 / 0 | 1/3 / 0 |
| close_weak_hann | 1/3 / 0 | 1/3 / 0 | 1/3 / 0 |

The ADC boundary preserves the known weak-target limitation; it does not solve
CA masking. Quantized input/window and fixed-point FFT are not numerically
identical to floating point. Their model errors are recorded separately.

Coverage includes all four fixture input/output SHAs, fixed gain and zero
clipping, actual localhost v3 transmission without Hann, signed full-scale
packing, positive/negative ties-even window rounding, reordered/duplicate rows,
mixed float/int16 and unknown-profile rejection, truncation, and rejection of
a corrupted full-bin diagnostic. Existing float32 wire PS double/float/model,
timestamp ABI, trace integrity and deliberate-loss tests also pass.

- [PC configuration, exact source/runtime/binary SHAs and numeric errors](pc_validation.json)
- [ADC tests](test_adc16.txt), [legacy regression](test_float_regression.txt), [staged shared-folder tests](shared_adc_tests.txt)
- [PS accuracy](ps_accuracy.json), [PL model accuracy](model_accuracy.json)
- [Exact tested source snapshot](source/), [shared staging SHA manifest](staging_manifest.json)
- Generated input manifests: [profile1](../../fixtures/adc16/adc16_profile.json).
- Retained PC binaries: `build/adc16_pc_20261126_final/binaries/`; binary SHAs above.
- Previous float/opt1 working sources: `build/pre_adc_float_20261126/`.

Windows GCC16.1.0/Python3.13.13/NumPy2.5.0 produced this evidence. Portable
tests exercise the production numeric and protocol headers; they do not compile
the Linux socket receiver or establish Ubuntu/ARM/NEON/hardware performance.

## Board and build gates

The new source/fixtures/runbook were copied into the existing VMware shared
folder with exact-byte checks. The29-file staging backup is
`build/adc16_source_backup_20261126_adc01` in the shared folder. Its independently
edited `tools/detection/test_s2a.py` was preserved. Existing build directories,
deployed float executables and user dashboard files were not overwritten.

Run [the Ubuntu/board runbook](../../../docs/adc16_runbook.md). The preparation
script uses double/O2, runs legacy and ADC loopback smoke, builds ARM, records
binary/build SHA and creates a fresh NFS deployment. The board wrapper captures
online/allowed CPUs, binary/library identities, before/after clocks and IRQs,
receiver exit code, first-frame all-bin output in diagnostic runs and per-frame
timing/counters. First-packet→CSV flush is the principal latency scope; PS
conversion and both windows are inside preparation. The first diagnostic
spectrum copy occurs after its output timestamp and can affect later frames;
diagnostic results never establish continuous acceptance.

| Gate | Evidence/status |
|---|---|
| Ubuntu host build + float/ADC loopback | PASS; recovered raw, 3 float + 3 ADC cases independently rechecked |
| ARM build + binary SHA | PASS; ARM32 ELF, double/O2, exact bundle/source hashes verified |
| PS 50ms/20 raw independent check | PASS92301:20/20,4/4 targets,false0, first-frame all bins verified |
| PL 100MHz 50ms/20 raw independent check | PASS92302:20/20,4/4 targets,false0, first-frame all bins bit-exact |
| Nondiagnostic12.8ms/200 preliminary | Commands prepared; run after diagnostic validation |
| 10,000-frame S2b | Not run, no acceptance claim |

All six diagnostic-scenario PC results are model evidence. Only recovered board
raw files can fill the board rows or establish PS/PL preparation-time changes.

Ubuntu follow-up: [raw build/smoke verification](ubuntu_build_validation.json),
[prepare log](ubuntu_prepare.log), [ARM build environment](ubuntu_arm_build_environment.txt),
[bundle SHA](ubuntu_bundle_artifacts.sha256). Raw copy:
`build/s2a_int16_ubuntu_20261126_adc01`. Source19 files match the tested local
sources. Normal ADC PS/model each processed20/20 and all first-frame complex
bins match; intentional loss is19 processed/1 partial with queue4/partial4.
ARM binary SHA256:
`72396cb0c1abcf6f831d5d00a0fc7d75618c2e8333d2ff99402b3163ca8d28f0`.
Deployment path is `/opt/fft128/s2a_int16_20261126_adc01` per user console;
at that build-validation stage, no board execution had yet been observed.

PS diagnostic follow-up (run92301): the user subsequently reported20/20 and
exit0 from the ADC bundle, actual568-byte packets with flags0. The legacy
timestamp-buffer probe flags8 belongs to the diagnostic peek, not the actual
receive. [Recovered sender JSON](ps_diag_01_sender.json) confirms matching frozen
input SHA, v3/profile1,20 frames,72704 bytes/frame and zero sender overruns.
Receiver raw files have not been collected yet: board accuracy, full bins,
counters and preparation time remain unverified. The earlier92122/92123 lines
in the same pasted console are historical float results, not ADC runs.

## Board diagnostic raw validation completed (92301 / 92302)

The pending statements above describe the earlier console-only stage. Both
receiver bundles and sender JSONs have now been recovered and independently
recomputed: [validation and raw SHA manifest](board_diag_validation.json).
Exact original raw copy, including the full diagnostic spectra and binaries:
`build/s2a_int16_board_diag_20261126_adc01/`. Compact per-frame traces, runtime,
counters and checked results are retained in [PS](ps_diag_01/) and [PL](pl_diag_01/).

Both have20/20 processed frames,2560 packets, zero drop/error/duplicate/foreign/
late counters, exit0, zero sender overruns and valid offered load. Every
processed frame has4/4 targets and false0; bins, powers and CA thresholds match
the independent reference. The first frame's16384 complex bins match NumPy for
PS and the independent integer Hann/FFT model exactly for PL. All repeated
frames use the same frozen multi4 ADC record. This board run does not establish
board correctness for every other scenario; those six cases have PC evidence.

| Timed stage (ms) | PS median | PS P99 | PL median | PL P99 |
|---|---:|---:|---:|---:|
| Preparation | 0.556071 | 0.58497822 | 2.460540 | 2.68009422 |
| FFT / transfer | 5.259570 | 5.38718490 | 1.197597 | 1.25885730 |
| Power / CA-CFAR | 5.095404 | 5.16172632 | 6.098832 | 6.20870952 |
| Queue wait | 0.085116 | 0.11843652 | 0.088131 | 0.11438652 |
| Output CSV flush | 0.228591 | 0.27332994 | 0.211929 | 0.23191566 |
| Frame complete → output | 11.243868 | 11.38683954 | 10.086009 | 10.17951474 |
| First kernel packet → output | 15.873876 | 24.20294763 | 14.696664 | 16.88978187 |

These are measured20-frame diagnostic distributions, not projections. Medians
of different stages need not add up. PS conversion to double and float Hann,
PL fixed integer Hann/packing are inside preparation. Relative to historical
float runs, precision/scale, payload/storage, normalization, branch hoisting,
FFTW allocation and possibly affinity/clock conditions differ; do not attribute
the change to normalization removal alone. Historical values stay unchanged.

The [clock context](board_clock_context.json) matches before/after and across
both runs: CPU register-derived setting666,666,660Hz, PL device-tree declaration
100,000,000Hz, same boot ID as the validated100MHz session. This is configuration
evidence, not a frequency-counter measurement or maximum-frequency claim.
Both CPUs are online and allowed; this does not imply two FFT workers or full
CPU saturation. Defaultdouble/O2/ESTIMATE and queue4/partial4 were confirmed.

**Next gate:** nondiagnostic12.8ms/200 preliminary runs92311/92312 in the
[runbook](../../../docs/adc16_runbook.md), followed by review before10,000-frame
S2b. The50ms diagnostic first-packet P99 values do not establish acceptance at
12.8ms. No continuous-throughput acceptance is claimed here.
