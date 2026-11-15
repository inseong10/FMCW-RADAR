# Vivado Tcl Console: pipelined butterfly + ping-pong stage RAM at 50 MHz.
# Actual routed setup/hold and clock period must pass before bitstream output.
set ::fft128_build_core pipeline
set ::fft128_build_mhz 50.0
# Use catch/return-options rather than Tcl 8.6 try: the target Vivado rejects try.
set fft128_fast_status [catch {
 source [file join [file dirname [info script]] build.tcl]
} fft128_fast_message fft128_fast_options]
unset -nocomplain ::fft128_build_core ::fft128_build_mhz
if {$fft128_fast_status} {
 return -options $fft128_fast_options $fft128_fast_message
}
unset fft128_fast_status fft128_fast_message fft128_fast_options
