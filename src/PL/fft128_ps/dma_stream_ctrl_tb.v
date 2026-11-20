`timescale 1ns/1ps
module dma_stream_ctrl_tb;
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
 fft128_dma_stream_ctrl dut(.aclk(clk),.aresetn(resetn),
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
 reg [31:0] inputs[0:34815],expected[0:34815];
 reg [31:0] value,held_data;reg held_last,stalled=0;
 integer cases=272,txk,received,cycle,batch_count=1,inject_stalls=0,active,k;
 integer observed_multi=0,observed_vectors=0,observed_busy=0;
 always @(posedge clk) begin
  if(!resetn || dut.soft_reset) stalled<=0;
  else begin
   if(stalled && (!rxvalid || rxdata!==held_data || rxlast!==held_last || rxkeep!==15)) $fatal(1,"Stalled AXIS payload");
   stalled<=rxvalid && !rxready;held_data<=rxdata;held_last<=rxlast;
  end
  if(!resetn || dut.soft_reset || (!dut.running && dut.aw_pending && dut.w_pending && dut.awaddr==4 && dut.wdata==1)) begin
   observed_multi<=0;observed_vectors<=0;observed_busy<=0;
  end else if(dut.running) begin
   if(dut.compute_stages>=2) observed_multi<=observed_multi+1;
   if(dut.inflight_vectors>=2) observed_vectors<=observed_vectors+1;
   observed_busy<=observed_busy+dut.compute_stages;
  end
 end
 task send_vector(input integer index,input integer malformed);
  begin
   for(txk=0;txk<batch_count*128;txk=txk+1) begin
    repeat(inject_stalls==2 && txk>0 && txk%128==0 ? 700 : inject_stalls==1 ? txk%4 : 0) @(negedge clk);
    txdata=inputs[((index+txk/128)%cases)*128+txk%128];txvalid=1;
    txlast=((txk==batch_count*128-1) && malformed!=2) || (malformed==1 && txk==3);
    txkeep=(malformed==3 && txk==5) ? 7 : 15;
    @(posedge clk);while(!txready) @(posedge clk);
    @(negedge clk);txvalid=0;
   end
   txlast=0;txkeep=15;
  end
 endtask
 task receive_vector(input integer index);
  begin
   received=0;cycle=0;
   while(received<batch_count*128) begin
    @(negedge clk);rxready=inject_stalls!=1 || (cycle>8000 && cycle%7>=3);cycle=cycle+1;
    @(posedge clk);
    if(rxvalid && rxready) begin
     if(rxdata!==expected[((index+received/128)%cases)*128+received%128] || rxkeep!==15 || rxlast!==(received==batch_count*128-1))
      $fatal(1,"DMA mismatch vector=%0d bin=%0d actual=%h expected=%h",index,received,rxdata,expected[((index+received/128)%cases)*128+received%128]);
     received=received+1;
    end
    if(cycle>batch_count*5000) $fatal(1,"DMA receive timeout");
   end
   @(negedge clk);rxready=0;
  end
 endtask
 task run_vector(input integer index,input integer malformed);
  begin
   write_word(4,2,0,15,0);repeat(3) @(negedge clk);
   write_word(40,batch_count,index%3,15,0);
   fork
    begin write_word(4,1,index%3,15,0);write_word(40,1,1,15,2);write_word(4,1,0,15,2);end
    send_vector(index,malformed);
    receive_vector(index);
   join
   read_word(8,value,0);if(value!==(malformed ? 6 : 2)) $fatal(1,"Status %h",value);
   read_word(24,value,0);if(value!==batch_count*128) $fatal(1,"Input count");
   read_word(28,value,0);if(value!==batch_count*128) $fatal(1,"Output count");
   read_word(44,value,0);if(value!==batch_count) $fatal(1,"Completed FFTs");
   read_word(48,value,0);if(value!==1) $fatal(1,"Streaming core count");
   read_word(108,value,0);if(value!==7) $fatal(1,"Stage count");
   for(k=0;k<7;k=k+1) begin
    read_word(128+k*4,value,0);if(value!==batch_count*64) $fatal(1,"Stage issue %0d %0d",k,value);
    read_word(160+k*4,value,0);if(value!==batch_count*64) $fatal(1,"Stage retire %0d %0d",k,value);
   end
   read_word(112,value,0);if(value!==batch_count*7*68 || value!==observed_busy) $fatal(1,"Stage busy sum %0d",value);
   read_word(116,value,0);if(value!==observed_multi) $fatal(1,"Multi-stage counter");
   if(batch_count>=16 && !inject_stalls && value==0) $fatal(1,"No stage arithmetic concurrency");
   read_word(120,value,0);if(value!==observed_vectors) $fatal(1,"Multi-vector counter");
   if(batch_count>1 && !inject_stalls && value==0) $fatal(1,"No inter-frame overlap");
   read_word(32,value,0);if(!inject_stalls && value!=0) $fatal(1,"Unexpected external input starvation");
   read_word(36,value,0);if(!inject_stalls && value!=0) $fatal(1,"Unexpected external output stall");
   read_word(16,value,0);active=value;
   if(!inject_stalls && batch_count==128 && active!=17770) $fatal(1,"Zero-stall schedule changed");
   if(!inject_stalls && batch_count==128 && active>=20930) $fatal(1,"No improvement over bf2");
   if(!inject_stalls && batch_count==128) $display("STREAM_ZERO_STALL_AXIS cycles=%0d frame_cycles=%0d",active,active*2);
   $display("STREAM_PACKET_PASS count=%0d mode=%0d malformed=%0d cycles=%0d multi_stage=%0d multi_vector=%0d",batch_count,inject_stalls,malformed,active,observed_multi,observed_vectors);
  end
 endtask
 initial begin
  $readmemh("inputs.hex",inputs);$readmemh("expected.hex",expected);
  repeat(5) @(negedge clk);resetn=1;
  read_word(0,value,0);if(value!==32'h46545087) $fatal(1,"ID");
  read_word(20,value,0);if(value!==7) $fatal(1,"ABI");
  write_word(40,0,0,15,2);write_word(40,129,1,15,2);
  write_word(5,1,2,15,2);write_word(4,1,0,3,2);write_word(40,0,0,0,0);
  read_word(1,value,2);read_word(12'h100,value,2);write_word(12'h100,123,0,15,2);
  batch_count=128;run_vector(0,0);run_vector(128,0);batch_count=16;run_vector(256,0);
  batch_count=1;run_vector(5,0);batch_count=2;run_vector(4,0);batch_count=3;run_vector(3,0);
  batch_count=4;run_vector(2,0);batch_count=5;run_vector(1,0);batch_count=127;run_vector(0,0);
  batch_count=128;inject_stalls=1;run_vector(3,0);inject_stalls=2;run_vector(7,0);
  batch_count=2;inject_stalls=0;run_vector(0,1);run_vector(0,2);run_vector(0,3);
  // Abort a blocked pipeline with partial input and pending output.
  write_word(4,2,0,15,0);repeat(3) @(negedge clk);write_word(40,128,0,15,0);write_word(4,1,0,15,0);
  rxready=0;
  for(k=0;k<1000;k=k+1) begin
   @(negedge clk);txdata=inputs[k];txvalid=1;txlast=0;
   @(posedge clk);while(!txready) @(posedge clk);
  end
  @(negedge clk);txvalid=0;repeat(9000) @(negedge clk);
  if(!rxvalid) $fatal(1,"Missing blocked output for abort");
  write_word(4,2,2,15,0);repeat(5) @(negedge clk);
  read_word(8,value,0);if(value!==0) $fatal(1,"Abort status");
  if(rxvalid || dut.pipeline.busy || dut.inflight_vectors!=0) $fatal(1,"Abort not cleared");
  batch_count=5;run_vector(9,0);
  $display("DMA_STREAM_CTRL_PASS numeric_vectors=272 full_partial_repeated_axis independent_AW_W response_stalls TLAST_TKEEP backpressure abort_recovery stage_counters inter_frame_overlap");$finish;
 end
 initial begin #30000000;$fatal(1,"Global DMA stream watchdog");end
endmodule
