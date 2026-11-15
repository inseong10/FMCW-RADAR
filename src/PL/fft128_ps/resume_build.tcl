# Resume the open V3 project after the reset-IP simulation source-list repair.
# Does not create a new project or discard existing synthesis/implementation.
set fft128_resume_here [file dirname [file normalize [info script]]]
if {![llength [get_projects -quiet]] || [get_property NAME [current_project]] ne "fft128_ps"} {
 error "Open the existing FFT128 V3 project first"
}
set fft128_resume_out [get_property DIRECTORY [current_project]]
set ::fft128_load_only 1
set fft128_load_status [catch {source [file join $fft128_resume_here build.tcl]} fft128_load_message fft128_load_options]
unset ::fft128_load_only
if {$fft128_load_status} {return -options $fft128_load_options $fft128_load_message}
set ::fft128::out $fft128_resume_out
catch {close_sim}
if {[catch {
 fft128::check_reset
 fft128::finish_build
} fft128_resume_message fft128_resume_options]} {
 set f [open [file join $::fft128::out error.txt] w]
 puts $f [dict get $fft128_resume_options -errorinfo]
 close $f
 puts "FFT128_RESUME_STOPPED: $fft128_resume_message"
 return -options $fft128_resume_options $fft128_resume_message
}
