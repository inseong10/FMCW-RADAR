# Recheck the already programmed FFT test without rebuilding/reprogramming.
# Source after run.tcl has opened the JTAG target and loaded the test design.
# VIO uses INPUT_VALUE_RADIX; DISPLAY_RADIX is an ILA probe property.
if {![llength [info commands ::fft_smoke::note]] ||
    ![info exists ::fft_smoke::run_dir]} {
    error "Run run.tcl first to initialize the FFT test project and JTAG connection"
}

proc ::fft_smoke::read_probe {vio port} {
    set probes [get_hw_probes -of_objects $vio -filter "TYPE == vio_input && PROBE_PORT == $port"]
    if {[llength $probes] != 1} {error "Expected one VIO input at port $port: $probes"}
    set probe [lindex $probes 0]
    set_property INPUT_VALUE_RADIX HEX $probe
    set text [string trim [get_property INPUT_VALUE $probe]]
    if {![regexp {^(0[xX])?[0-9a-fA-F]+$} $text] || ![scan $text %x value]} {
        error "Invalid VIO value for port $port: $text"
    }
    return $value
}

proc ::fft_smoke::verify_hardware {} {
    variable run_dir
    set device [current_hw_device]
    if {![string match xc7z010* [get_property PART $device]]} {
        error "Expected the programmed XC7Z010 test device"
    }
    set vios [get_hw_vios -of_objects $device]
    if {[llength $vios] != 1} {error "Expected one test VIO: $vios"}
    set vio [lindex $vios 0]
    set resets [get_hw_probes -of_objects $vio -filter {TYPE == vio_output}]
    if {[llength $resets] != 1} {error "Expected one VIO reset output"}
    note "CHECKING_HARDWARE: reset test and refresh VIO inputs"
    set_property OUTPUT_VALUE_RADIX HEX $resets
    set_property OUTPUT_VALUE 1 $resets
    commit_hw_vio $vio
    after 10
    set_property OUTPUT_VALUE 0 $resets
    commit_hw_vio $vio
    set done 0
    for {set attempt 0} {$attempt < 10} {incr attempt} {
        after 100
        refresh_hw_vio $vio
        set done [read_probe $vio 0]
        if {$done == 1} {break}
    }
    set mask [read_probe $vio 1]
    set errors [read_probe $vio 2]
    set first [read_probe $vio 3]
    set actual [read_probe $vio 4]
    set expected [read_probe $vio 5]
    set result "done=$done passed=$mask errors=$errors first=$first actual=$actual expected=$expected"
    save_text [file join $run_dir hardware.txt] $result
    note "HARDWARE_VALUES: $result"
    if {$done != 1 || $mask != 31 || $errors != 0} {
        error "HARDWARE_FAIL: $result"
    }
    note "HARDWARE_PASS: JTAG VIO confirms five vectors / 160 FFT output bins"
}

if {[catch {::fft_smoke::verify_hardware} fft_hw_message fft_hw_options]} {
    ::fft_smoke::note "HARDWARE_CHECK_STOPPED: $fft_hw_message"
    ::fft_smoke::save_text [file join $::fft_smoke::run_dir hardware_error.txt] [dict get $fft_hw_options -errorinfo]
    return -options $fft_hw_options $fft_hw_message
}
