# Zybo Z7-10 FFT board test

This test uses the FFT submodule at commit
`42b13489e5382a013e77b4b057f93c56ce0955ae`. Its files remain unchanged. The
board build substitutes `multiplier_zybo.v` for `multiplier_n.v` to share one
magnitude product across the four sign cases. It also uses `adder3_zybo.v`
for simultaneous registered updates and `clk_div_zybo.v` to capture the final
FFT stage half a master-clock cycle after its calculation. The remaining core
RTL and all submodule files are original.
It targets **Zybo Z7-10 / XC7Z010-1CLG400C**, using the onboard 125 MHz clock,
Clocking Wizard at 20 MHz (4 MHz after the core divider), four LEDs and JTAG
VIO. It is a standalone PL test;
PS Linux, UDP and DMA are not part of this test.

## Verified board result — 2026-11-13

The corrected revision completed on **Zybo Z7-10 / Vivado 2022.1** at
18:00:39 KST. JTAG programmed the FPGA and VIO read back:

```text
done=1 passed=31 errors=0 first=0 actual=0 expected=0
HARDWARE_PASS: JTAG VIO confirms five vectors / 160 FFT output bins
```

Original/revised RTL simulation, 589825 multiplier comparisons,
post-synthesis functional simulation, post-implementation timing simulation,
static timing, bitstream generation and board readback all passed. Final
setup slack was **5.156 ns**, hold slack **0.043 ns**, with **64/80 DSPs**,
**7691/17600 LUTs** and **6996/35200 registers**. The test clock was 20 MHz.

The complete run took approximately 28 minutes; post-route timing simulation
including elaboration took approximately 13 minutes. That simulation emitted
many MMCM model period warnings for CLKOUT1–CLKOUT6 while the test checker
passed; the positive static timing report and actual VIO readback are retained
separately. This verifies the five documented real-input 32-point FFT cases,
not the full radar/PS/UDP data path or a maximum operating frequency.

The successful bitstream, LTX, result files and reports are saved locally under
`build/vivado/validated_20261113_173240/`. The bitstream SHA256 is
`c18fdd8840f5e4733caeae3c1b08767d10282ddc184afcf63b04a31da8c444bd`.

## Test cases

| Index | Real input, 32 samples | Per-component tolerance (raw Q8 units) |
|---|---|---:|
| 0 | all zero | 0 |
| 1 | impulse at sample 0 | 0 |
| 2 | all one | 0 |
| 3 | impulse at sample 1 | 4 (0.015625) |
| 4 | upstream `in_ram.txt` pattern | 32 (0.125) |

`test_vectors.vh` contains independent NumPy FFT references rounded to Q8. The
tolerances accommodate the upstream coefficient quantization/truncation; they
are not a claim of exact agreement with floating-point FFT. All 32 complex bins
are checked for each vector. The first failing test/bin and actual/reference
values are retained. Simulation also writes a per-bin CSV.

## Run with Vivado 2022.1

Open Vivado's Tcl Console and source this file using the checkout's Linux path:

```tcl
source {/path/to/FMCW-RADAR/src/PL/zybo_fft_test/run.tcl}
```

By default, this creates a separate timestamped project, simulates the original
FFT, compares both multipliers on 589825 input pairs and asynchronous reset,
then simulates the FFT with the replacement multiplier. Only after these checks
pass does it run synthesis, post-synthesis functional simulation of the board
netlist, implementation, static timing checks, post-implementation timing
simulation and bitstream generation, then connect to the local hardware server, verify XC7Z010,
program the FPGA and read the
VIO result. A failed stage stops the flow. The existing `fmcw_zynq` project is
closed; it is not overwritten. This does not write boot flash or SD images.

For simulation only:

```tcl
set ::FFT_TEST_STAGE sim
source {/path/to/FMCW-RADAR/src/PL/zybo_fft_test/run.tcl}
```

Use `build` instead of `sim` to stop after bitstream generation. Use `all` to
include JTAG programming. Generated projects, reports and results are under
`build/vivado/`; `fft32_latest.log` records the latest stage. Only an actual
`HARDWARE_PASS` record establishes a successful board test. Source preparation
or a successful simulation does not establish that hardware was tested.

## Board connection and results

Connect the board's USB-JTAG port and attach the USB device to the Ubuntu VM.
The script stops if no target or multiple targets are found. Other FPGA
variants are rejected. Ensure the board is a Zybo Z7-10 matching the official
[Zybo Z7 pin constraints](https://github.com/Digilent/digilent-xdc/blob/master/Zybo-Z7-Master.xdc).

- LED0: 20 MHz clock locked.
- LED1: all five tests passed.
- LED2: test completed with errors.
- LED3: heartbeat.
- BTN0: rerun the test.

VIO input ports 0–5 are `done`, `passed[4:0]`, `error_count`, first failing
`{test[2:0],bin[4:0]}`, first actual value and first expected value. Complex words
are packed `{real[15:0],imag[15:0]}`. VIO output 0 resets/reruns the checker.

This flow retains a registered divide-by-five clock with a 40% duty cycle,
shifted to the master falling edge with an explicit generated-clock constraint.
Resource fit, actual timing closure and upstream
RTL correctness must be demonstrated by running the flow; they are not assumed.

## XC7Z010 resource correction

The first Vivado 2022.1 run passed all original RTL FFT vectors, but synthesis
used 166 DSP48E1 cells versus 80 available on this board, stopping placement
with `DRC UTLZ-1`. The upstream multiplier places a separate multiplication
expression in each sign branch. The replacement computes unsigned magnitudes
once, truncates the product, and then restores the sign. This preserves the
upstream rounding toward zero, wraparound and minimum-negative-input behavior;
a signed multiplication followed by an arithmetic shift would change rounding.
It retains the falling-edge output register and asynchronous reset. The
`use_dsp` attribute guides mapping of the single product; actual DSP usage is
reported and checked after synthesis and final implementation.

The divider constraint now uses the `clock_out_reg/C` source pin instead of a
module input pin that disappeared when synthesis flattened the hierarchy.
Failed build runs copy their underlying Vivado error messages to
`synth_1_failure.txt` or `impl_1_failure.txt` so the stop message includes the
actual cause.

The replacement passed all 589825 HDL multiplier comparisons and both FFT
simulations in Vivado 2022.1. The routed design used 64/80 DSPs and 7935/17600
LUTs. At 50 MHz, however, timing failed with WNS -5.605 ns: the path from the
divided-clock twiddle ROM through the magnitude multiplier had only a 10 ns
half-cycle, including adverse clock skew. The control-to-multiplier path also
failed by 3.490 ns. The functional test therefore now requests a real 20 MHz
Clocking Wizard output and simulates at that period, giving a 25 ns half-cycle.
No false-path or multicycle exception hides these paths. JTAG is set to 3 MHz
to satisfy the debug-clock ratio requirement in
[AMD UG908](https://docs.amd.com/r/2023.2-English/ug908-vivado-programming-debugging/Debug-Cores-Clocking-Guidelines).
The slower configuration must still pass routing, timing checks and
`HARDWARE_PASS`; the frequency change is not itself proof of timing closure.

The 20 MHz run subsequently passed setup (6.387 ns slack), hold (0.057 ns),
and bitstream generation. Its JTAG result-read stage then stopped because
`DISPLAY_RADIX` is not a VIO input property. The readback now uses
`INPUT_VALUE_RADIX`. If this happens after programming, keep the Hardware
Manager connection open and run the following in the same Vivado session to
reset/recheck the loaded design without rebuilding:

```tcl
source {/path/to/FMCW-RADAR/src/PL/zybo_fft_test/check_hardware.tcl}
```

This reuses the initialized run directory and writes `hardware.txt`. A pass
requires `done=1 passed=31 errors=0`; bitstream generation alone is not a board
test pass.

## Correct final-stage capture

The first board readback was `done=1 passed=1 errors=81 first=40 actual=0
expected=16777216`. Only the all-zero vector passed. `first=40` means test 1,
bin 8; the expected word is Q8 real 1.0 and imaginary 0.0.

`verify_capture_schedule.py` parses all 96 muxes and 16 butterflies from the
actual upstream source, then models their stage arithmetic against the test
references. Capturing the fourth of five stages reproduces **every summary
field** of that board failure: mask 1, 81 errors, first bin 40, actual 0 and
expected 16777216. Capturing the fifth stage gives mask 31 and zero errors.
Run this diagnostic model with Python 3:

```text
python src/PL/zybo_fft_test/verify_capture_schedule.py
```

The upstream divider updates on the same rising master-clock edge as the
registered adders. Physical registers capture pre-edge values, so the result
register can retain the preceding FFT stage. Zero-delay RTL simulation can
instead observe the updated adder output, hiding the error. The board divider
now updates on falling edges, giving the final adder output a real half-cycle
to settle before capture. Adders use nonblocking assignments to model
simultaneous flip-flop updates. The divider also skips the first falling edge
after reset release to align its first frame with the control-unit counter.
The generated clock uses edges `{4 8 14}`: rise 75 ns, fall 175 ns, next rise
325 ns relative to the reset-release rising edge at the 20 MHz master clock.

`fft_board_tb.v` checks the actual board netlist through the preserved tester
ports connected to VIO, driving only the board clock, reset button and the
configured default VIO reset value. Both the post-synthesis functional and
post-route timing simulations must pass before programming. The cycle model
diagnoses the observed failure; it is not proof that the revised board build
passes until the simulations, timing checks and hardware readback succeed.

### Reset-release alignment correction

The first falling-edge-divider revision still failed the Vivado RTL test with
the same 81 errors. The checker releases the core reset just after a rising
edge, so `control_unit` cannot start until the next rising edge. A divider
reset to zero starts at the intervening falling edge, leading the control
counter by one full cycle. Falling-edge capture alone therefore still saves
stage four.

`clk_div_zybo.v` now resets its counter to `DIVISOR-1`. Its first falling edge
wraps the counter to zero without creating a pulse; the following falling edge
starts the aligned frame. The cycle-only arithmetic model above did not cover
reset-release scheduling and was insufficient to validate the first revision.
The current correction was checked with **actual HDL simulation** on Windows
using Icarus Verilog 13.0: the previous RTL reproduced the exact 81-error
signature, the corrected RTL passed all five vectors / 160 bins, and three
successive resets with different release phases each gave mask 31 and zero
errors. Local logs and per-bin CSVs are under `build/rtl_debug/`.
The subsequent verified run reported above passed Vivado netlist simulation,
physical timing closure and actual board readback for this correction.
