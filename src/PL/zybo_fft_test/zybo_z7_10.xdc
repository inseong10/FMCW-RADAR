# Zybo Z7 Rev. B: Digilent's official Zybo-Z7-Master.xdc pin assignments.
# https://github.com/Digilent/digilent-xdc/blob/master/Zybo-Z7-Master.xdc
set_property -dict {PACKAGE_PIN K17 IOSTANDARD LVCMOS33} [get_ports sysclk]
create_clock -name sysclk -period 8.000 [get_ports sysclk]
set_property -dict {PACKAGE_PIN K18 IOSTANDARD LVCMOS33} [get_ports btn_reset]
set_property -dict {PACKAGE_PIN M14 IOSTANDARD LVCMOS33} [get_ports {led[0]}]
set_property -dict {PACKAGE_PIN M15 IOSTANDARD LVCMOS33} [get_ports {led[1]}]
set_property -dict {PACKAGE_PIN G14 IOSTANDARD LVCMOS33} [get_ports {led[2]}]
set_property -dict {PACKAGE_PIN D18 IOSTANDARD LVCMOS33} [get_ports {led[3]}]
# The upstream core intentionally uses a registered divide-by-five clock.
# Preserve its 40% duty cycle rather than assuming a 50% clock waveform.
# The board divider is driven by falling edges and skips the first edge after
# reset release: rise at 75 ns, fall at 175 ns, next rise at 325 ns relative to
# the release rising edge of a 20 MHz master. The adder updates 25 ns earlier.
# Hierarchical module input pins disappear during synthesis flattening. Use
# the divider flip-flop's actual clock pin, which survives flattening.
create_generated_clock -name fft_slow -source [get_pins tester/dut/fft_block/clkk/clock_out_reg/C] -edges {4 8 14} [get_pins tester/dut/fft_block/clkk/clock_out_reg/Q]
set_false_path -from [get_ports btn_reset] -to [get_cells reset_sync_reg*]
