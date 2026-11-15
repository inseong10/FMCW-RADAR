# The testbench instantiates a BD child IP directly. Vivado does not traverse
# the unrelated system BD for this simulation top. Register its generated
# VHDL implementation and dependencies explicitly in the simulation fileset.
namespace eval fft128 {}
proc fft128::attach_reset_sim_sources {out} {
 set gen [file join $out fft128_ps.gen sources_1 bd system]
 set wrapper [file join $gen ip system_reset_0 sim system_reset_0.vhd]
 set reset_files [glob -nocomplain [file join $gen ipshared * hdl proc_sys_reset_v5_0_vh_rfs.vhd]]
 set cdc_files [glob -nocomplain [file join $gen ipshared * hdl lib_cdc_v1_0_rfs.vhd]]
 if {![file exists $wrapper] || [llength $reset_files]!=1 || [llength $cdc_files]!=1} {
  error "Generated reset simulation sources missing in $gen"
 }
 set f [open $wrapper r]; set wrapper_text [read $f]; close $f
 set f [open [lindex $reset_files 0] r]; set reset_text [read $f]; close $f
 if {![regexp -nocase {library\s+(proc_sys_reset_v[0-9_]+)\s*;} $wrapper_text -> reset_lib] ||
     ![regexp -nocase {library\s+(lib_cdc_v[0-9_]+)\s*;} $reset_text -> cdc_lib]} {
  error "Cannot identify generated reset/CDC VHDL libraries"
 }
 if {![regexp {C_AUX_RESET_HIGH\s*=>\s*'1'} $wrapper_text]} {
  error "Generated reset IP still has an active-low auxiliary reset; regenerate V3 first"
 }
 set staging [file join $out reset_sim_sources]
 file mkdir $staging
 foreach source [list [lindex $cdc_files 0] [lindex $reset_files 0] $wrapper] library [list $cdc_lib $reset_lib xil_defaultlib] {
  # Copies prevent conflicts with Vivado's BD-managed file objects.
  set target [file join $staging [file tail $source]]
  file copy -force $source $target
  set registered [get_files -quiet -of_objects [get_filesets sim_1] $target]
  if {![llength $registered]} {add_files -fileset sim_1 -norecurse $target}
  set registered [get_files -quiet -of_objects [get_filesets sim_1] $target]
  set_property library $library $registered
  puts "FFT128_RESET_SIM_SOURCE: $library/[file tail $target]"
 }
 update_compile_order -fileset sim_1
}
