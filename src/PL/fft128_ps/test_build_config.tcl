# Host-only regression; no Vivado, synthesis or FPGA access.
set test_here [file dirname [file normalize [info script]]]
# Load Tcl 8.6's clock support before disabling its try command for the test.
clock format [clock seconds] -format %Y%m%d_%H%M%S
if {[llength [info commands try]]} {rename try {}}
set ::fft128_load_only 1
source [file join $test_here build.tcl]
if {$::fft128::core_mode ne "serial" || $::fft128::clock_mhz != 20} {error "Default build changed"}
source [file join $test_here build_fast.tcl]
if {$::fft128::core_mode ne "pipeline" || $::fft128::clock_mhz != 50} {error "Fast configuration wrong"}
if {[info exists ::fft128_build_core] || [info exists ::fft128_build_mhz]} {error "Fast configuration leaked"}
source [file join $test_here build.tcl]
if {$::fft128::core_mode ne "serial" || $::fft128::clock_mhz != 20} {error "Default configuration leaked"}

# Force a build error without invoking Vivado, then verify cleanup and error info.
unset ::fft128_load_only
rename source test_original_source
proc source {path} {
 if {[file tail $path] eq "build.tcl"} {error "EXPECTED_BUILD_FAILURE"}
 uplevel 1 [list test_original_source $path]
}
set code [catch {source [file join $test_here build_fast.tcl]} message options]
rename source {}
rename test_original_source source
if {$code!=1 || $message ne "EXPECTED_BUILD_FAILURE"} {error "Build error was hidden: $message"}
if {![string match *EXPECTED_BUILD_FAILURE* [dict get $options -errorinfo]]} {error "Original error info lost"}
if {[info exists ::fft128_build_core] || [info exists ::fft128_build_mhz]} {error "Failed build configuration leaked"}
puts "TCL_COMPAT_PASS: try unavailable; serial20, pipeline50, default restore, failure cleanup and error propagation"
