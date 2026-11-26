# Vivado batch entry point: -source this_file -tclargs MHz
# A candidate changes the E14 MMCM output and connected FFT/AXI/DMA clocks only.
if {$argc!=1} {error "Usage: build_dma_frame_clock.tcl MHz"}
set ::fft128_frame_clock_mhz [lindex $argv 0]
set fft_clock_code [catch {
 source [file join [file dirname [info script]] build_dma_frame.tcl]
} fft_clock_msg fft_clock_opts]
unset ::fft128_frame_clock_mhz
if {$fft_clock_code} {return -options $fft_clock_opts $fft_clock_msg}
