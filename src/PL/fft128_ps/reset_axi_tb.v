`timescale 1ns/1ps
// Integration test uses Vivado's actual generated proc_sys_reset instance.
module reset_axi_tb;
 reg clk=0;
 always #25 clk=~clk;
 reg locked=0;
 reg aux=0;
 reg done=0, passed=0;
 wire interconnect_resetn, peripheral_resetn;
 reg [11:0] araddr=0;
 reg arvalid=0, rready=0;
 wire arready, rvalid;
 wire [31:0] rdata;
 wire [1:0] rresp;
 system_reset_0 reset_ip(
  .slowest_sync_clk(clk), .ext_reset_in(1'b1), .aux_reset_in(aux),
  .mb_debug_sys_rst(1'b0), .dcm_locked(locked),
  .interconnect_aresetn(interconnect_resetn), .peripheral_aresetn(peripheral_resetn),
  .mb_reset(), .bus_struct_reset(), .peripheral_reset());
 fft128_axi fft(
  .aclk(clk), .aresetn(peripheral_resetn),
  .s_axi_awaddr(12'b0), .s_axi_awprot(3'b0), .s_axi_awvalid(1'b0), .s_axi_awready(),
  .s_axi_wdata(32'b0), .s_axi_wstrb(4'b0), .s_axi_wvalid(1'b0), .s_axi_wready(),
  .s_axi_bresp(), .s_axi_bvalid(), .s_axi_bready(1'b0),
  .s_axi_araddr(araddr), .s_axi_arprot(3'b0), .s_axi_arvalid(arvalid), .s_axi_arready(arready),
  .s_axi_rdata(rdata), .s_axi_rresp(rresp), .s_axi_rvalid(rvalid), .s_axi_rready(rready));
 task read_check(input [11:0] address, input [31:0] expected);
  integer cycles;
  begin
   @(negedge clk); araddr=address; arvalid=1;
   cycles=0;
   @(posedge clk);
   while (arready!==1'b1) begin
    cycles=cycles+1; if(cycles>50) $fatal(1,"AXI AR timeout after reset");
    @(posedge clk);
   end
   @(negedge clk); arvalid=0;
   cycles=0;
   while(rvalid!==1'b1) begin
    cycles=cycles+1; if(cycles>50) $fatal(1,"AXI R timeout after reset");
    @(negedge clk);
   end
   if(rresp!==2'b00 || rdata!==expected) $fatal(1,"AXI register %h actual=%h expected=%h resp=%h",address,rdata,expected,rresp);
   rready=1; @(posedge clk); @(negedge clk); rready=0;
  end
 endtask
 task check_released;
  begin
   repeat(200) @(negedge clk);
   if(interconnect_resetn!==1'b1 || peripheral_resetn!==1'b1)
    $fatal(1,"Reset stuck: interconnect=%b peripheral=%b aux=%b",interconnect_resetn,peripheral_resetn,aux);
   read_check(12'h000,32'h46543128);
   read_check(12'h00c,32'd128);
  end
 endtask
 initial begin
  repeat(20) @(negedge clk);
  locked=1;
  // PC-only reproduction against the old generated active-low auxiliary IP.
  // Production Vivado simulation never sets this plusarg.
  if($test$plusargs("REPRO_OLD_AUX")) begin
   repeat(200) @(negedge clk);
   if(interconnect_resetn!==1'b0 || peripheral_resetn!==1'b0)
    $fatal(1,"Old auxiliary reset failure was not reproduced");
   $display("OLD_AUX_BUG_REPRODUCED: locked=1 aux=0 both AXI resets remain asserted");
   aux=1;
  end
  check_released;
  locked=0;
  repeat(100) @(negedge clk);
  if(interconnect_resetn!==1'b0 || peripheral_resetn!==1'b0)
   $fatal(1,"Lock loss did not reset AXI");
  locked=1;
  check_released;
  passed=1; done=1;
  $display("RESET_AXI_PASS: generated reset IP, ID/length reads, lock-loss recovery");
  $finish;
 end
 initial begin #95000; $fatal(1,"Reset/AXI test watchdog"); end
endmodule
