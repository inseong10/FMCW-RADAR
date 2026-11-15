# Vivado 2022.1: source this file from Tcl Console. Builds only; no JTAG or SD writes.
namespace eval fft128 {
 variable here [file dirname [file normalize [info script]]]
 variable root [file normalize [file join $here .. .. ..]]
 variable out [file join $root build vivado fft128_ps_[clock format [clock seconds] -format %Y%m%d_%H%M%S]]
}
proc fft128::main {} {
 variable here; variable root; variable out
 file mkdir $out
 if {[llength [get_projects -quiet]]} {close_project}
 set_param board.repoPaths [concat [list [file join $here board_files]] [get_param board.repoPaths]]
 create_project fft128_ps $out -part xc7z010clg400-1 -force
 set boards [get_board_parts -quiet digilentinc.com:zybo-z7-10:part0:1.2]
 if {[llength $boards]!=1} {error "Bundled Digilent Zybo Z7-10 board files were not loaded"}
 set_property board_part [lindex $boards 0] [current_project]
 set_property target_language Verilog [current_project]
 foreach name {fft128_axi.v fft128_stream.v fft128_twiddle.v butterfly_engine.v fft_working_ram.v address_generator.v} {
  add_files [file join $here $name]
 }
 add_files -fileset constrs_1 [file join $here zybo_sysclk.xdc]
 update_compile_order -fileset sources_1
 create_bd_design system
 set ps [create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:5.5 ps7]
 apply_bd_automation -rule xilinx.com:bd_rule:processing_system7 -config {make_external "FIXED_IO, DDR" apply_board_preset "1" Master "Disable" Slave "Disable"} $ps
 # FCLK_RESET0_N also requires FCLK0 to propagate inside the PS (UG585).
 # Use the board clock and MMCM lock for both clock and reset independence.
 set_property -dict [list CONFIG.PCW_USE_M_AXI_GP0 {1} CONFIG.PCW_EN_CLK0_PORT {0} CONFIG.PCW_EN_RST0_PORT {0}] $ps
 set clk [create_bd_cell -type ip -vlnv xilinx.com:ip:clk_wiz:6.0 clock_gen]
 set_property -dict [list CONFIG.PRIM_IN_FREQ {125.000} CONFIG.CLKOUT1_REQUESTED_OUT_FREQ {20.000} CONFIG.USE_LOCKED {true} CONFIG.USE_RESET {true} CONFIG.RESET_TYPE {ACTIVE_HIGH}] $clk
 set sysclk [create_bd_port -dir I -type clk sysclk]
 set_property CONFIG.FREQ_HZ {125000000} $sysclk
 connect_bd_net $sysclk [get_bd_pins clock_gen/clk_in1]
 set fft [create_bd_cell -type module -reference fft128_axi fft]
 set axi [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:2.1 axi]
 set_property -dict [list CONFIG.NUM_SI {1} CONFIG.NUM_MI {1}] $axi
 set rst [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 reset]
 # Never rely on the IP default: its auxiliary reset defaults to active LOW.
 # We tie aux_reset_in to zero, so explicitly configure it active HIGH.
 set_property -dict [list CONFIG.C_EXT_RESET_HIGH {0} CONFIG.C_AUX_RESET_HIGH {1}] $rst
 set zero [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 zero]
 set_property CONFIG.CONST_VAL {0} $zero
 set one [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 one]
 set_property CONFIG.CONST_VAL {1} $one
 connect_bd_intf_net [get_bd_intf_pins ps7/M_AXI_GP0] [get_bd_intf_pins axi/S00_AXI]
 connect_bd_intf_net [get_bd_intf_pins axi/M00_AXI] [get_bd_intf_pins fft/S_AXI]
 connect_bd_net [get_bd_pins clock_gen/clk_out1] [get_bd_pins ps7/M_AXI_GP0_ACLK] [get_bd_pins axi/ACLK] [get_bd_pins axi/S00_ACLK] [get_bd_pins axi/M00_ACLK] [get_bd_pins fft/aclk] [get_bd_pins reset/slowest_sync_clk]
 # ext_reset_in is active low. proc_sys_reset provides power-up reset and
 # holds all AXI/FFT resets until the external-clock MMCM locks.
 connect_bd_net [get_bd_pins one/dout] [get_bd_pins reset/ext_reset_in]
 connect_bd_net [get_bd_pins clock_gen/locked] [get_bd_pins reset/dcm_locked]
 connect_bd_net [get_bd_pins zero/dout] [get_bd_pins reset/aux_reset_in] [get_bd_pins reset/mb_debug_sys_rst] [get_bd_pins clock_gen/reset]
 connect_bd_net [get_bd_pins reset/interconnect_aresetn] [get_bd_pins axi/ARESETN] [get_bd_pins axi/S00_ARESETN] [get_bd_pins axi/M00_ARESETN]
 connect_bd_net [get_bd_pins reset/peripheral_aresetn] [get_bd_pins fft/aresetn]
 set segments [get_bd_addr_segs -of_objects [get_bd_intf_pins fft/S_AXI]]
 if {[llength $segments]!=1} {error "Expected one FFT AXI register segment: $segments"}
 assign_bd_address -offset 0x43C00000 -range 0x00001000 -target_address_space [get_bd_addr_spaces ps7/Data] $segments -force
 validate_bd_design
 if {[llength [get_bd_pins -quiet ps7/FCLK_RESET0_N]]} {error "Unexpected PS FCLK reset dependency"}
 if {[get_property CONFIG.C_AUX_RESET_HIGH $rst] != 1} {error "Auxiliary reset tied low must be active HIGH"}
 save_bd_design
 set bd [get_files system.bd]
 generate_target all $bd
 set wrapper [make_wrapper -files $bd -top]
 add_files -norecurse $wrapper
 set_property top system_wrapper [current_fileset]
 update_compile_order -fileset sources_1
 fft128::check_reset
 fft128::finish_build
}
proc fft128::check_reset {} {
 variable here; variable out
 source [file join $here reset_sim_sources.tcl]
 fft128::attach_reset_sim_sources $out
 # Exercise the real generated reset IP, not a hand-written reset model.
 # Fail before synthesis if either AXI reset remains asserted after MMCM lock.
 add_files -fileset sim_1 -norecurse [file join $here reset_axi_tb.v]
 set_property top reset_axi_tb [get_filesets sim_1]
 set_property xsim.simulate.runtime 0ns [get_filesets sim_1]
 update_compile_order -fileset sim_1
 puts "FFT128_RESET_SIM_START: generated reset IP, AXI ID and lock-loss recovery"
 launch_simulation
 run 100 us
 set done [get_value -radix unsigned /reset_axi_tb/done]
 set passed [get_value -radix unsigned /reset_axi_tb/passed]
 set f [open [file join $out reset_simulation.txt] w]
 puts $f "done=$done passed=$passed; generated reset IP; AXI ID/length; lock-loss recovery"
 close $f
 close_sim
 if {$done ne "1" || $passed ne "1"} {error "RESET_SIMULATION_FAIL: done=$done passed=$passed"}
 puts "FFT128_RESET_SIM_PASS: AXI ID responds after reset release and lock-loss recovery"
}
proc fft128::finish_build {} {
 variable out; variable root
 launch_runs synth_1 -jobs 2
 wait_on_run synth_1
 if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {error "Synthesis failed: [get_property STATUS [get_runs synth_1]]"}
 launch_runs impl_1 -to_step route_design -jobs 2
 wait_on_run impl_1
 if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {error "Implementation failed: [get_property STATUS [get_runs impl_1]]"}
 open_run impl_1
 report_utilization -file [file join $out utilization.rpt]
 report_timing_summary -delay_type min_max -check_timing_verbose -file [file join $out timing.rpt]
 set setup [get_timing_paths -delay_type max -max_paths 1]
 set hold [get_timing_paths -delay_type min -max_paths 1]
 if {![llength $setup] || ![llength $hold]} {error "No constrained setup/hold path; inspect timing.rpt"}
 if {[get_property SLACK $setup]<0 || [get_property SLACK $hold]<0} {error "Timing violation; inspect timing.rpt"}
 launch_runs impl_1 -to_step write_bitstream -jobs 2
 wait_on_run impl_1
 if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {error "Bitstream failed"}
 write_hw_platform -fixed -include_bit -force -file [file join $out system.xsa]
 set f [open [file join $out clock_source.txt] w]
 puts $f "board K17 125 MHz -> Clocking Wizard 20 MHz -> PS GP0 ACLK, AXI and FFT; FCLK0 not used"
 puts $f "RESET_SCHEME=BOARD_MMCM_LOCK_V3_AUX_HIGH; FCLK_RESET0_N not used; ext_reset_in=1 active-low; aux_reset_in=0 active-high"
 close $f
 set f [open [file join $root build fft128_latest.txt] w]; puts $f $out; close $f
 puts "FFT128_BUILD_PASS: $out"
 puts "Next: prepare_firmware.sh converts this bitstream for the existing NFS/fpgautil workflow."
}
if {![info exists ::fft128_load_only] && [catch {fft128::main} message options]} {
 file mkdir $fft128::out
 set f [open [file join $fft128::out error.txt] w]; puts $f [dict get $options -errorinfo]; close $f
 puts "FFT128_BUILD_STOPPED: $message"
 return -options $options $message
}
