`timescale 1ns/1ps
module dma_frame_ctrl_tb;
 reg clk=0; always #5 clk=~clk;
 reg resetn=0;
 reg [11:0] awaddr=0, araddr=0;
 reg awvalid=0,wvalid=0,bready=0,arvalid=0,rready=0;
 reg [31:0] wdata=0;
 reg [3:0] wstrb=15;
 wire awready,wready,bvalid,arready,rvalid;
 wire [31:0] rdata;
 wire [1:0] bresp,rresp;
 reg [31:0] txdata=0; reg [3:0] txkeep=15;
 reg txvalid=0,txlast=0,rxready=0;
 wire txready,rxvalid,rxlast; wire [31:0] rxdata; wire [3:0] rxkeep;
 fft128_dma_frame_ctrl dut(.aclk(clk),.aresetn(resetn),
  .s_axi_awaddr(awaddr),.s_axi_awprot(3'b0),.s_axi_awvalid(awvalid),.s_axi_awready(awready),
  .s_axi_wdata(wdata),.s_axi_wstrb(wstrb),.s_axi_wvalid(wvalid),.s_axi_wready(wready),
  .s_axi_bresp(bresp),.s_axi_bvalid(bvalid),.s_axi_bready(bready),
  .s_axi_araddr(araddr),.s_axi_arprot(3'b0),.s_axi_arvalid(arvalid),.s_axi_arready(arready),
  .s_axi_rdata(rdata),.s_axi_rresp(rresp),.s_axi_rvalid(rvalid),.s_axi_rready(rready),
  .s_axis_tdata(txdata),.s_axis_tkeep(txkeep),.s_axis_tvalid(txvalid),
  .s_axis_tready(txready),.s_axis_tlast(txlast),
  .m_axis_tdata(rxdata),.m_axis_tkeep(rxkeep),.m_axis_tvalid(rxvalid),
  .m_axis_tready(rxready),.m_axis_tlast(rxlast));
 task write_word(input [11:0] addr,input [31:0] data,input integer mode,input [3:0] strb,input [1:0] response);
  begin
   fork
    begin
     repeat(mode==1 ? 4 : 1) @(negedge clk);
     awaddr=addr; awvalid=1;
     @(posedge clk); while (!awready) @(posedge clk);
     @(negedge clk); awvalid=0;
    end
    begin
     repeat(mode==2 ? 4 : 1) @(negedge clk);
     wdata=data; wstrb=strb; wvalid=1;
     @(posedge clk); while (!wready) @(posedge clk);
     @(negedge clk); wvalid=0;
    end
   join
   while (!bvalid) @(negedge clk);
   repeat(3) begin
    @(negedge clk);
    if (!bvalid || bresp!==response) $fatal(1,"B response/hold addr=%h resp=%h",addr,bresp);
   end
   bready=1; @(posedge clk); @(negedge clk); bready=0;
  end
 endtask
 reg [31:0] inputs[0:98303],expected[0:98303];
 reg [31:0] value,held_data;
 reg held_last,stalled=0;
 reg consumed[0:16383];
 integer k,n,received,cycle,mode=0,active,range_time,doppler_time,drain_time;
 integer checked_frames=0,checked_bins=0,observed_multi=0,observed_vectors=0;
 always @(posedge clk) begin
  if(!resetn || dut.clear_command || dut.soft_reset) begin
   stalled<=0;observed_multi<=0;observed_vectors<=0;
   for(n=0;n<16384;n=n+1) consumed[n]=0;
  end else if(dut.running) begin
   if(stalled && (!rxvalid || rxdata!==held_data || rxlast!==held_last || rxkeep!==15)) $fatal(1,"Stalled external output changed");
   stalled<=rxvalid && !rxready;held_data<=rxdata;held_last<=rxlast;
   if(dut.compute_stages>=2) observed_multi<=observed_multi+1;
   if(dut.inflight_vectors>=2) observed_vectors<=observed_vectors+1;
   if(dut.pipeline_send && dut.phase==2) consumed[{dut.doppler_inputs[6:0],dut.doppler_inputs[13:7]}]=1;
   if(dut.ram_write && dut.phase==2) begin
    if(!consumed[dut.ram_write_address] || !dut.overwrite_safe) $fatal(1,"Unread matrix location overwritten");
    if(dut.ram_read && dut.ram_read_address==dut.ram_write_address) $fatal(1,"RAM read/write collision");
   end
   if(rxvalid && dut.phase!=3) $fatal(1,"Output before row-major drain");
   if(dut.read_requests>16384 || dut.input_count>16384 || dut.output_count>16384) $fatal(1,"Count overflow");
  end else stalled<=0;
 end
 task send_frame(input integer index,input integer malformed);
  integer sample;
  begin
   for(sample=0;sample<16384;sample=sample+1) begin
    repeat(mode==1 ? sample%4 : mode==2 && sample%128==0 ? 700 : 0) @(negedge clk);
    txdata=inputs[index*16384+sample];txvalid=1;
    txlast=(sample==16383 && malformed!=2) || (malformed==1 && sample==3);
    txkeep=malformed==3 && sample==5 ? 7 : 15;
    @(posedge clk);while(!txready) @(posedge clk);
    @(negedge clk);txvalid=0;
   end
   txlast=0;txkeep=15;
  end
 endtask
 task receive_frame(input integer index);
  begin
   received=0;cycle=0;
   while(received<16384) begin
    @(negedge clk);rxready=mode!=1 || (cycle>60000 && cycle%7>=3);cycle=cycle+1;
    @(posedge clk);
    if(rxvalid && rxready) begin
     if(rxdata!==expected[index*16384+received] || rxkeep!==15 || rxlast!==(received==16383))
      $fatal(1,"2D mismatch frame=%0d bin=%0d actual=%h expected=%h",index,received,rxdata,expected[index*16384+received]);
     received=received+1;checked_bins=checked_bins+1;
    end
    if(cycle>300000) $fatal(1,"Full frame timeout");
   end
   @(negedge clk);rxready=0;
  end
 endtask
 task check_reg(input [11:0] address,input [31:0] expected_value);
  begin read_word(address,value,0);if(value!==expected_value) $fatal(1,"Reg %h actual=%0d expected=%0d",address,value,expected_value);end
 endtask
 task run_frame(input integer index,input integer malformed);
  begin
   // Repeated requests deliberately start without a separate abort/reset write.
   fork
    begin write_word(4,1,index%3,15,0);write_word(40,16384,1,15,2);write_word(4,1,2,15,2);end
    send_frame(index,malformed);
    receive_frame(index);
   join
   check_reg(8,malformed ? 6 : 2);
   check_reg(24,16384);check_reg(28,16384);check_reg(44,256);check_reg(48,1);
   check_reg(64,32768);check_reg(68,32768);check_reg(72,16384);check_reg(76,16384);check_reg(80,16384);
   check_reg(84,0);check_reg(88,0);check_reg(92,0);check_reg(96,16384);check_reg(108,7);
   check_reg(112,256*7*68);check_reg(116,observed_multi);check_reg(120,observed_vectors);
   if(!observed_multi || !observed_vectors) $fatal(1,"Missing inter-vector pipeline overlap");
   for(k=0;k<7;k=k+1) begin check_reg(128+k*4,16384);check_reg(160+k*4,16384);end
   read_word(16,value,0);active=value;
   read_word(52,value,0);range_time=value;read_word(56,value,0);doppler_time=value;read_word(60,value,0);drain_time=value;
   if(active!=range_time+doppler_time+drain_time || drain_time<16385) $fatal(1,"Phase counter accounting");
   if(!mode) begin
    check_reg(32,0);check_reg(36,0);
    if(active!=51927 || range_time!=17771 || doppler_time!=17771 || drain_time!=16385) $fatal(1,"Zero-stall E14 schedule changed");
   end
   checked_frames=checked_frames+1;
   $display("FRAME_PACKET_PASS index=%0d mode=%0d malformed=%0d cycles=%0d range=%0d doppler=%0d drain=%0d",index,mode,malformed,active,range_time,doppler_time,drain_time);
  end
 endtask
 task abort_phase(input integer target,input integer hard_reset);
  begin
   write_word(4,1,0,15,0);
   if(target==1) begin
    for(k=0;k<333;k=k+1) begin
     @(negedge clk);txdata=inputs[k];txvalid=1;
     @(posedge clk);while(!txready) @(posedge clk);
    end
    @(negedge clk);txvalid=0;
   end else begin
    send_frame(0,0);
    while(dut.phase!=target) @(negedge clk);
    repeat(700) @(negedge clk);
    if(target==3 && !rxvalid) $fatal(1,"Missing blocked drain output");
   end
   if(hard_reset) begin @(negedge clk);resetn=0;repeat(5) @(negedge clk);resetn=1;end
   else write_word(4,2,2,15,0);
   repeat(5) @(negedge clk);
   check_reg(8,0);check_reg(16,0);check_reg(24,0);check_reg(28,0);check_reg(84,0);
   if(rxvalid || dut.pipeline_busy || dut.inflight_vectors || dut.rd_valid) $fatal(1,"Abort failed to clear valid state");
   $display("FRAME_ABORT_PASS phase=%0d hard_reset=%0d",target,hard_reset);
   mode=0;run_frame(2,0);
  end
 endtask
 initial begin
  $readmemh("frames.hex",inputs);$readmemh("frames_expected.hex",expected);
  repeat(5) @(negedge clk);resetn=1;
  check_reg(0,32'h46545088);check_reg(20,8);check_reg(40,16384);
  write_word(40,0,0,15,2);write_word(40,128,1,15,2);write_word(40,16384,2,15,0);
  write_word(5,1,2,15,2);write_word(4,1,0,3,2);write_word(40,0,0,0,0);
  read_word(1,value,2);read_word(12'h100,value,2);write_word(12'h100,123,0,15,2);
  run_frame(0,0);run_frame(1,0);run_frame(2,0);run_frame(3,0);run_frame(4,0);run_frame(5,0);
  mode=1;run_frame(2,0);mode=2;run_frame(3,0);mode=0;
  run_frame(1,1);run_frame(4,2);run_frame(5,3);run_frame(0,0);
  // Inject a broken-core early result: the live overwrite guard must both
  // block the write and record the violation, not expose a constant-zero flag.
  write_word(4,1,0,15,0);send_frame(0,0);
  while(dut.phase!=2) @(negedge clk);
  force dut.pipeline_valid=1;force dut.doppler_inputs=0;
  repeat(3) begin @(posedge clk);if(dut.ram_write) $fatal(1,"Guard allowed unread overwrite");end
  @(negedge clk);release dut.pipeline_valid;release dut.doppler_inputs;
  read_word(88,value,0);if(value<3) $fatal(1,"Guard violations not counted");
  read_word(8,value,0);if(!value[2]) $fatal(1,"Guard failed to set error");
  write_word(4,2,1,15,0);repeat(5) @(negedge clk);
  $display("FRAME_OVERWRITE_GUARD_PASS premature_result_blocked_and_counted");
  abort_phase(1,0);abort_phase(2,0);abort_phase(3,0);abort_phase(1,1);abort_phase(2,1);abort_phase(3,1);
  $display("DMA_FRAME_CTRL_PASS frames=%0d exact_bins=%0d all_phases_abort in_place_read_before_write row_major independent_AW_W held_responses malformed_TLAST_TKEEP backpressure starvation",checked_frames,checked_bins);$finish;
 end
 initial begin #60000000;$fatal(1,"Global E14 watchdog");end
 task read_word(input [11:0] addr, output [31:0] data,input [1:0] response);
  reg [31:0] held;
  begin
   @(negedge clk); araddr=addr; arvalid=1;
   @(posedge clk); while (!arready) @(posedge clk);
   @(negedge clk); arvalid=0;
   while (!rvalid) @(negedge clk);
   held=rdata;
   repeat(3) begin
    @(negedge clk);
    if (!rvalid || rresp!==response || rdata!==held) $fatal(1,"R response/hold addr=%h",addr);
   end
   data=rdata; rready=1; @(posedge clk); @(negedge clk); rready=0;
  end
 endtask
endmodule
