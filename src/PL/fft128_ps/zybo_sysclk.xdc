# Digilent Zybo Z7-10 SYSCLK, same pin used by the verified 32-point test.
# https://github.com/Digilent/digilent-xdc/blob/master/Zybo-Z7-Master.xdc
set_property -dict {PACKAGE_PIN K17 IOSTANDARD LVCMOS33} [get_ports sysclk]
create_clock -name sysclk -period 8.000 [get_ports sysclk]
