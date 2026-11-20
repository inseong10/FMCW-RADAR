# E13-2core only: two unchanged pipelined FFTs/50 MHz, pair barrier, one shared axis packet.
# Source from Vivado 2022.1 Tcl console. Does not program hardware.
set ::fft128_load_only 1
set ::fft128_build_core pipeline
set ::fft128_build_mhz 50.0
set fft_dma_code [catch {source [file join [file dirname [info script]] build.tcl]} fft_dma_msg fft_dma_opts]
unset ::fft128_load_only ::fft128_build_core ::fft128_build_mhz
if {$fft_dma_code} {return -options $fft_dma_opts $fft_dma_msg}
set ::fft128::out [file join $::fft128::root build vivado fft128_dma_e13_2core_[clock format [clock seconds] -format %Y%m%d_%H%M%S]]
set ::fft128::latest_file fft128_dma_parallel_latest.txt
# Build independent ARM userspace/module prerequisites while Vivado implements
# this design. This never installs a kernel, deploys or programs the FPGA.
set fft_batch_host_dir [file join $::fft128::root build fft128_dma_parallel_preparation]
file mkdir $fft_batch_host_dir
set fft_batch_host_pid [exec bash [file join $::fft128::root src PS fft128 dma_parallel prepare_all.sh] >[file join $fft_batch_host_dir launcher.log] 2>@1 &]
puts "E13_2CORE_ARM_BUILD_STARTED: pid=$fft_batch_host_pid log=$fft_batch_host_dir/arm_build.log"
proc fft128::dma_main {} {
 variable here; variable root; variable out
 file mkdir $out
 if {[llength [get_projects -quiet]]} {close_project}
 set_param board.repoPaths [concat [list [file join $here board_files]] [get_param board.repoPaths]]
 create_project fft128_ps $out -part xc7z010clg400-1 -force
 set boards [get_board_parts -quiet digilentinc.com:zybo-z7-10:part0:1.2]
 if {[llength $boards]!=1} {error "Bundled Zybo Z7-10 board files unavailable"}
 set_property board_part [lindex $boards 0] [current_project]
 set_property target_language Verilog [current_project]
 foreach name {fft128_dma_parallel_ctrl.v fft128_pipeline.v fft128_twiddle.v butterfly_pipeline.v fft_working_ram.v address_generator.v} {
  add_files [file join $here $name]
 }
 add_files -fileset constrs_1 [file join $here zybo_sysclk.xdc]
 update_compile_order -fileset sources_1
 create_bd_design system
 set ps [create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:5.5 ps7]
 apply_bd_automation -rule xilinx.com:bd_rule:processing_system7 -config {make_external "FIXED_IO, DDR" apply_board_preset "1" Master "Disable" Slave "Disable"} $ps
 set_property -dict [list CONFIG.PCW_USE_M_AXI_GP0 {1} CONFIG.PCW_USE_S_AXI_HP0 {1} CONFIG.PCW_S_AXI_HP0_DATA_WIDTH {64} CONFIG.PCW_USE_FABRIC_INTERRUPT {1} CONFIG.PCW_IRQ_F2P_INTR {1} CONFIG.PCW_EN_CLK0_PORT {0} CONFIG.PCW_EN_RST0_PORT {0}] $ps
 set clk [create_bd_cell -type ip -vlnv xilinx.com:ip:clk_wiz:6.0 clock_gen]
 set_property -dict [list CONFIG.PRIM_IN_FREQ {125.000} CONFIG.CLKOUT1_REQUESTED_OUT_FREQ {50.000} CONFIG.USE_LOCKED {true} CONFIG.USE_RESET {true} CONFIG.RESET_TYPE {ACTIVE_HIGH}] $clk
 set sysclk [create_bd_port -dir I -type clk sysclk]
 set_property CONFIG.FREQ_HZ {125000000} $sysclk
 connect_bd_net $sysclk [get_bd_pins clock_gen/clk_in1]
 create_bd_cell -type module -reference fft128_dma_parallel_ctrl fft
 set dma [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_dma:7.1 dma]
 set_property -dict [list CONFIG.c_include_sg {0} CONFIG.c_include_mm2s {1} CONFIG.c_include_s2mm {1} CONFIG.c_include_mm2s_dre {0} CONFIG.c_include_s2mm_dre {0} CONFIG.c_m_axi_mm2s_data_width {64} CONFIG.c_m_axi_s2mm_data_width {64} CONFIG.c_m_axis_mm2s_tdata_width {32} CONFIG.c_s_axis_s2mm_tdata_width {32} CONFIG.c_mm2s_burst_size {16} CONFIG.c_s2mm_burst_size {16} CONFIG.c_sg_length_width {17}] $dma
 set axi [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:2.1 axi]
 set_property -dict [list CONFIG.NUM_SI {1} CONFIG.NUM_MI {2}] $axi
 set mem [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:2.1 mem]
 set_property -dict [list CONFIG.NUM_SI {2} CONFIG.NUM_MI {1}] $mem
 set rst [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 reset]
 set_property -dict [list CONFIG.C_EXT_RESET_HIGH {0} CONFIG.C_AUX_RESET_HIGH {1}] $rst
 set zero [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 zero]
 set_property CONFIG.CONST_VAL {0} $zero
 set one [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 one]
 set_property CONFIG.CONST_VAL {1} $one
 set irq [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconcat:2.1 irq]
 set_property CONFIG.NUM_PORTS {16} $irq
 # Live BSP DT already reserves SPI29..34 (IRQ_F2P[0..5]) for video/XADC.
 # Use F2P[6]/[7] = GIC IRQ67/68 = DT SPI35/36 instead.
 for {set i 0} {$i<16} {incr i} {
  if {$i==6} {connect_bd_net [get_bd_pins dma/mm2s_introut] [get_bd_pins irq/In$i]} elseif {$i==7} {
   connect_bd_net [get_bd_pins dma/s2mm_introut] [get_bd_pins irq/In$i]
  } else {connect_bd_net [get_bd_pins zero/dout] [get_bd_pins irq/In$i]}
 }
 connect_bd_net [get_bd_pins irq/dout] [get_bd_pins ps7/IRQ_F2P]
 foreach pair {{ps7/M_AXI_GP0 axi/S00_AXI} {axi/M00_AXI fft/S_AXI} {axi/M01_AXI dma/S_AXI_LITE} {dma/M_AXI_MM2S mem/S00_AXI} {dma/M_AXI_S2MM mem/S01_AXI} {mem/M00_AXI ps7/S_AXI_HP0} {dma/M_AXIS_MM2S fft/S_AXIS} {fft/M_AXIS dma/S_AXIS_S2MM}} {
  connect_bd_intf_net [get_bd_intf_pins [lindex $pair 0]] [get_bd_intf_pins [lindex $pair 1]]
 }
 set clock_pins {ps7/M_AXI_GP0_ACLK ps7/S_AXI_HP0_ACLK axi/ACLK axi/S00_ACLK axi/M00_ACLK axi/M01_ACLK mem/ACLK mem/S00_ACLK mem/S01_ACLK mem/M00_ACLK fft/aclk reset/slowest_sync_clk dma/s_axi_lite_aclk dma/m_axi_mm2s_aclk dma/m_axi_s2mm_aclk}
 foreach pin $clock_pins {connect_bd_net [get_bd_pins clock_gen/clk_out1] [get_bd_pins $pin]}
 connect_bd_net [get_bd_pins one/dout] [get_bd_pins reset/ext_reset_in]
 connect_bd_net [get_bd_pins clock_gen/locked] [get_bd_pins reset/dcm_locked]
 connect_bd_net [get_bd_pins zero/dout] [get_bd_pins reset/aux_reset_in] [get_bd_pins reset/mb_debug_sys_rst] [get_bd_pins clock_gen/reset]
 foreach pin {axi/ARESETN axi/S00_ARESETN axi/M00_ARESETN axi/M01_ARESETN mem/ARESETN mem/S00_ARESETN mem/S01_ARESETN mem/M00_ARESETN} {
  connect_bd_net [get_bd_pins reset/interconnect_aresetn] [get_bd_pins $pin]
 }
 connect_bd_net [get_bd_pins reset/peripheral_aresetn] [get_bd_pins fft/aresetn] [get_bd_pins dma/axi_resetn]
 # Keep old 0x43c00000 MMIO firmware/software intact. BSP has a VTC at that address.
 assign_bd_address -offset 0x43C60000 -range 0x00001000 -target_address_space [get_bd_addr_spaces ps7/Data] [get_bd_addr_segs -of_objects [get_bd_intf_pins fft/S_AXI]] -force
 assign_bd_address -offset 0x40400000 -range 0x00010000 -target_address_space [get_bd_addr_spaces ps7/Data] [get_bd_addr_segs dma/S_AXI_LITE/Reg] -force
 foreach space {Data_MM2S Data_S2MM} {
  assign_bd_address -offset 0x00000000 -range 0x40000000 -target_address_space [get_bd_addr_spaces dma/$space] [get_bd_addr_segs ps7/S_AXI_HP0/HP0_DDR_LOWOCM] -force
 }
 validate_bd_design
 if {[llength [get_bd_pins -quiet ps7/FCLK_RESET0_N]]} {error "Unexpected PS FCLK reset dependency"}
 save_bd_design
 set bd [get_files system.bd]
 generate_target all $bd
 add_files -norecurse [make_wrapper -files $bd -top]
 set_property top system_wrapper [current_fileset]
 update_compile_order -fileset sources_1
 check_reset reset_dma_parallel_tb
 set sources {}
 foreach name {build_dma_parallel.tcl build.tcl reset_dma_parallel_tb.v reset_sim_sources.tcl zybo_sysclk.xdc fft128_dma_parallel_ctrl.v fft128_pipeline.v fft128_twiddle.v butterfly_pipeline.v fft_working_ram.v address_generator.v} {
  lappend sources [file join $here $name]
 }
 set f [open [file join $out source.sha256] w]; puts $f [exec sha256sum {*}$sources]; close $f
 finish_build
 report_utilization -hierarchical -file [file join $out parallel_utilization.rpt]
 set dsp_cells [get_cells -hierarchical -filter {REF_NAME == DSP48E1}]
 if {[llength $dsp_cells]!=8} {error "Expected 8 DSP48E1 primitives for two unchanged arithmetic cores"}
 set f [open [file join $out parallel_core_check.txt] w]
 puts $f "core_instances=2; DSP48E1=[llength $dsp_cells]; arithmetic core sources unchanged; board overlap counters pending"
 close $f
 set f [open [file join $out dma_config.json] w]
 puts $f {{"experiment":"E13-2core","core":"pipeline","clock_hz":50000000,"fft_control_base":"0x43c60000","dma_base":"0x40400000","irq_f2p_bits":[6,7],"dt_spi":[35,36],"memory_port":"HP0","memory_width":64,"stream_width":32,"sg":false,"dre":false,"burst":16,"length_width":17,"register_abi":3,"parallel_cores":2,"pair_barrier":true,"next_pair_prefetch":false,"external_ping_pong":false,"fft_per_request":128,"bytes_per_direction":65536,"board_verified":false}}
 close $f
 puts "FFT128_DMA_PARALLEL_BUILD_PASS: $out"
}
if {[catch {fft128::dma_main} fft_dma_msg fft_dma_opts]} {
 file mkdir $::fft128::out
 set f [open [file join $::fft128::out error.txt] w]; puts $f [dict get $fft_dma_opts -errorinfo]; close $f
 puts "FFT128_DMA_PARALLEL_BUILD_STOPPED: $fft_dma_msg"
 return -options $fft_dma_opts $fft_dma_msg
}
