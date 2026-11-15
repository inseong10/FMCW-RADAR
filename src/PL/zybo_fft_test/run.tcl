# Vivado 2022.1. Default: simulate, implement, program Zybo Z7-10, read VIO.
# Override with: set ::FFT_TEST_STAGE sim (or build) before sourcing this file.
namespace eval fft_smoke {
    variable here [file dirname [file normalize [info script]]]
    variable root [file normalize [file join $here ../../..]]
    variable result_root [file join $root build vivado]
    file mkdir $result_root
    variable stage all
    if {[info exists ::FFT_TEST_STAGE]} {set stage $::FFT_TEST_STAGE}
    if {$stage ni {sim build all}} {error "FFT_TEST_STAGE must be sim, build or all"}
    variable run_dir [file join $result_root fft32_zybo_[clock format [clock seconds] -format %Y%m%d_%H%M%S]]
    if {[file exists $run_dir]} {error "Run directory already exists: $run_dir"}
    file mkdir $run_dir
    variable log_file [file join $result_root fft32_latest.log]
    set channel [open $log_file w]
    puts $channel "Run directory: $run_dir"
    puts $channel "Stage: $stage"
    close $channel
}

proc fft_smoke::note {message} {
    variable log_file
    puts "FFT_TEST: $message"
    set channel [open $log_file a]
    puts $channel "[clock format [clock seconds] -format {%H:%M:%S}] $message"
    close $channel
}

proc fft_smoke::save_text {path text} {
    set channel [open $path w]
    puts $channel $text
    close $channel
}

proc fft_smoke::check_run {name step tag} {
    variable run_dir
    set run [get_runs $name]
    set status [get_property STATUS $run]
    if {[string match "$step Complete*" $status]} {return}
    set logfile [file join [get_property DIRECTORY $run] runme.log]
    set details {}
    if {[file isfile $logfile]} {
        set channel [open $logfile r]
        set contents [read $channel]
        close $channel
        foreach line [split $contents \n] {
            if {[regexp {^(ERROR:|CRITICAL WARNING:)} $line]} {lappend details $line}
        }
        save_text [file join $run_dir ${name}_failure.txt] [join $details \n]
    }
    error "$tag: $status\n[join [lrange $details 0 4] \n]\nLog: $logfile"
}

proc fft_smoke::simulate_fft {label} {
    variable run_dir
    set_property top fft_selftest_tb [get_filesets sim_1]
    update_compile_order -fileset sim_1
    note "START_SIMULATION: $label RTL, five vectors / 160 bins"
    launch_simulation
    run 100 us
    set done [get_value -radix unsigned /fft_selftest_tb/done]
    set mask [get_value -radix unsigned /fft_selftest_tb/passed]
    set errors [get_value -radix unsigned /fft_selftest_tb/error_count]
    set first [get_value -radix hex /fft_selftest_tb/first_error_index]
    set actual [get_value -radix hex /fft_selftest_tb/first_actual]
    set expected [get_value -radix hex /fft_selftest_tb/first_expected]
    save_text [file join $run_dir simulation_${label}.txt] "done=$done passed=$mask errors=$errors first=$first actual=$actual expected=$expected"
    if {$done ne "1" || $mask ne "31" || $errors ne "0"} {
        error "SIMULATION_FAIL ($label): done=$done passed=$mask errors=$errors first=$first actual=$actual expected=$expected"
    }
    close_sim
    set csv [file join $run_dir fft32_zybo.sim sim_1 behav xsim fft_selftest_results.csv]
    if {[file isfile $csv]} {file copy -force $csv [file join $run_dir fft_${label}.csv]}
    note "SIMULATION_PASS ($label): all five vectors / 160 bins within documented tolerances"
}

proc fft_smoke::simulate_board {mode type} {
    variable run_dir
    set_property top fft_board_tb [get_filesets sim_1]
    update_compile_order -fileset sim_1
    note "START_NETLIST_SIMULATION: $mode $type"
    launch_simulation -mode $mode -type $type
    run 200 us
    set done [get_value -radix unsigned /fft_board_tb/done]
    set mask [get_value -radix unsigned /fft_board_tb/passed]
    set errors [get_value -radix unsigned /fft_board_tb/error_count]
    set first [get_value -radix hex /fft_board_tb/first_error_index]
    set actual [get_value -radix hex /fft_board_tb/first_actual]
    set expected [get_value -radix hex /fft_board_tb/first_expected]
    save_text [file join $run_dir netlist_${mode}_${type}.txt] "done=$done passed=$mask errors=$errors first=$first actual=$actual expected=$expected"
    if {$done ne "1" || $mask ne "31" || $errors ne "0"} {
        error "NETLIST_SIMULATION_FAIL ($mode $type): done=$done passed=$mask errors=$errors first=$first actual=$actual expected=$expected"
    }
    close_sim
    set_property top fft_selftest_tb [get_filesets sim_1]
    note "NETLIST_SIMULATION_PASS: $mode $type, all five vectors / 160 bins"
}

proc fft_smoke::main {} {
    variable here
    variable root
    variable run_dir
    variable stage
    set upstream [file join $root src PL fft32-dit-butterfly FPGA RTL]
    set names {adder3_n.v butterfly2_n.v clk_div.v control_unit.v get_negative_n.v
               m_ram.v multiplier_n.v mux_n.v pipling_stage_n.v s_ram.v top_n.v
               twiddle_rom_imag_n.v twiddle_rom_real_n.v fft_wrapper.v}
    set sources {}
    foreach name $names {
        set path [file join $upstream $name]
        if {![file isfile $path]} {error "Missing upstream source: $path"}
        lappend sources $path
    }
    if {[llength [get_projects -quiet]]} {
        catch {close_sim}
        close_project
    }
    create_project fft32_zybo $run_dir -part xc7z010clg400-1
    set_property target_language Verilog [current_project]
    add_files -norecurse $sources
    add_files -norecurse [list [file join $here fft_selftest.v] [file join $here zybo_fft_test_top.v]]
    set_property include_dirs [list $here] [get_filesets sources_1]
    add_files -fileset sim_1 -norecurse [list [file join $here fft_selftest_tb.v] [file join $here fft_board_tb.v]]
    set_property include_dirs [list $here] [get_filesets sim_1]
    set_property top fft_selftest_tb [get_filesets sim_1]
    set_property xsim.simulate.runtime 0ns [get_filesets sim_1]
    update_compile_order -fileset sources_1
    update_compile_order -fileset sim_1
    simulate_fft upstream

    # Keep the Git submodule unchanged. Substitute the shared multiplier and
    # separate the divider capture edge from the adder's calculation edge.
    # Compare against the actual original multiplier before synthesis.
    set original_multiplier [file join $upstream multiplier_n.v]
    set channel [open $original_multiplier r]
    set original_text [read $channel]
    close $channel
    if {[regsub {module\s+multiplier\s*#} $original_text {module multiplier_reference #} reference_text] != 1} {
        error "Cannot create renamed upstream multiplier reference"
    }
    set reference_file [file join $run_dir multiplier_reference.v]
    save_text $reference_file $reference_text
    remove_files [get_files $original_multiplier]
    remove_files [get_files [file join $upstream adder3_n.v]]
    remove_files [get_files [file join $upstream clk_div.v]]
    add_files -norecurse [list [file join $here multiplier_zybo.v] \
        [file join $here adder3_zybo.v] [file join $here clk_div_zybo.v]]
    add_files -fileset sim_1 -norecurse [list $reference_file [file join $here multiplier_equivalence_tb.v]]
    set_property top multiplier_equivalence_tb [get_filesets sim_1]
    update_compile_order -fileset sources_1
    update_compile_order -fileset sim_1
    note "START_MULTIPLIER_EQUIVALENCE: upstream versus single-product Q8 implementation"
    launch_simulation
    run 3 ms
    set done [get_value -radix unsigned /multiplier_equivalence_tb/done]
    set passed [get_value -radix unsigned /multiplier_equivalence_tb/passed]
    set checks [get_value -radix unsigned /multiplier_equivalence_tb/checks]
    save_text [file join $run_dir multiplier_equivalence.txt] "done=$done passed=$passed comparisons=$checks"
    if {$done ne "1" || $passed ne "1" || $checks ne "589825"} {
        error "MULTIPLIER_EQUIVALENCE_FAIL: done=$done passed=$passed checks=$checks"
    }
    close_sim
    note "MULTIPLIER_EQUIVALENCE_PASS: $checks input pairs and asynchronous reset"
    simulate_fft zybo
    if {$stage eq "sim"} {return}

    create_ip -name clk_wiz -vendor xilinx.com -library ip -version 6.0 -module_name fft_test_clk
    # The first 50 MHz route failed setup by 5.605 ns on the half-cycle
    # multiplier path. Use a real 20 MHz clock (25 ns per half-cycle) for the
    # initial functional board test; keep every internal timing check enabled.
    set_property -dict [list CONFIG.PRIM_IN_FREQ {125.000} CONFIG.CLKOUT1_REQUESTED_OUT_FREQ {20.000} \
        CONFIG.USE_LOCKED {true} CONFIG.USE_RESET {true} CONFIG.RESET_TYPE {ACTIVE_HIGH}] [get_ips fft_test_clk]
    create_ip -name vio -vendor xilinx.com -library ip -version 3.0 -module_name fft_test_vio
    set_property -dict [list CONFIG.C_NUM_PROBE_IN {6} CONFIG.C_NUM_PROBE_OUT {1} \
        CONFIG.C_PROBE_IN0_WIDTH {1} CONFIG.C_PROBE_IN1_WIDTH {5} CONFIG.C_PROBE_IN2_WIDTH {8} \
        CONFIG.C_PROBE_IN3_WIDTH {8} CONFIG.C_PROBE_IN4_WIDTH {32} CONFIG.C_PROBE_IN5_WIDTH {32} \
        CONFIG.C_PROBE_OUT0_WIDTH {1} CONFIG.C_PROBE_OUT0_INIT_VAL {0x0}] [get_ips fft_test_vio]
    generate_target all [get_ips {fft_test_clk fft_test_vio}]
    add_files -fileset constrs_1 -norecurse [file join $here zybo_z7_10.xdc]
    set_property top zybo_fft_test_top [get_filesets sources_1]
    update_compile_order -fileset sources_1
    note "START_SYNTHESIS: xc7z010clg400-1, 20 MHz test clock / 4 MHz divided clock"
    launch_runs synth_1 -jobs 2
    wait_on_run synth_1
    check_run synth_1 synth_design SYNTHESIS_FAIL
    open_run synth_1
    report_utilization -file [file join $run_dir utilization_synth.rpt]
    set dsps [llength [get_cells -hier -filter {REF_NAME == DSP48E1}]]
    note "SYNTHESIS_DSP: $dsps / 80 (before linking out-of-context IP)"
    if {$dsps > 80} {error "RESOURCE_FAIL: $dsps DSP48E1 cells exceed the XC7Z010 limit of 80"}
    close_design
    simulate_board post-synthesis functional
    note "START_IMPLEMENTATION"
    launch_runs impl_1 -to_step route_design -jobs 2
    wait_on_run impl_1
    check_run impl_1 route_design IMPLEMENTATION_FAIL
    open_run impl_1
    report_utilization -file [file join $run_dir utilization.rpt]
    report_timing_summary -file [file join $run_dir timing.rpt]
    foreach type {max min} {
        set paths [get_timing_paths -delay_type $type -max_paths 1]
        if {[llength $paths] == 0} {error "No $type timing path found"}
        set slack [get_property SLACK [lindex $paths 0]]
        note "TIMING_$type: slack=$slack ns"
        if {$slack < 0} {error "TIMING_FAIL: $type slack=$slack ns"}
    }
    close_design
    simulate_board post-implementation timing
    launch_runs impl_1 -to_step write_bitstream -jobs 2
    wait_on_run impl_1
    check_run impl_1 write_bitstream BITSTREAM_FAIL
    set bitstream [file join $run_dir fft32_zybo.runs impl_1 zybo_fft_test_top.bit]
    if {![file isfile $bitstream]} {error "BITSTREAM_FAIL: [get_property STATUS [get_runs impl_1]]"}
    open_run impl_1
    set probes [file join $run_dir zybo_fft_test_top.ltx]
    write_debug_probes -force $probes
    close_design
    note "BUILD_PASS: $bitstream"
    if {$stage eq "build"} {return}

    note "CONNECTING_JTAG"
    open_hw_manager
    if {![llength [get_hw_servers -quiet]]} {connect_hw_server}
    if {[llength [get_hw_targets -quiet]] == 0} {error "NO_JTAG_TARGET: attach Zybo USB-JTAG to this Ubuntu VM"}
    if {[llength [get_hw_targets]] != 1} {error "Multiple JTAG targets found; select the Zybo target explicitly"}
    current_hw_target [lindex [get_hw_targets] 0]
    # The previous test may have left this same target open after readback.
    close_hw_target -quiet [current_hw_target]
    # Keep JTAG below one 2.5th of the 20 MHz debug core/hub clock.
    set_property PARAM.FREQUENCY 3000000 [current_hw_target]
    open_hw_target
    set devices [get_hw_devices -filter {PART =~ xc7z010*}]
    if {[llength $devices] != 1} {error "Expected one XC7Z010: [get_hw_devices]"}
    set device [lindex $devices 0]
    current_hw_device $device
    set_property PROGRAM.FILE $bitstream $device
    set_property PROBES.FILE $probes $device
    note "PROGRAMMING_JTAG: $bitstream"
    program_hw_devices $device
    refresh_hw_device $device
    note "JTAG_PROGRAMMED: reading FFT test result"
    source [file join $here check_hardware.tcl]
}

if {[catch {fft_smoke::main} fft_message fft_options]} {
    fft_smoke::note "STOPPED: $fft_message"
    fft_smoke::save_text [file join $fft_smoke::run_dir error.txt] [dict get $fft_options -errorinfo]
    return -options $fft_options $fft_message
}
fft_smoke::note "COMPLETED stage=$fft_smoke::stage"
