`timescale 1ns/1ps
module dma_quad_ctrl_tb;
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
 fft128_dma_quad_ctrl dut(.aclk(clk),.aresetn(resetn),
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
 reg [31:0] inputs[0:131071], expected[0:131071];
 reg [31:0] value, held_data;
 reg held_last, stalled=0;
 integer cases,testno,k,received,cycle,txk;
 integer batch_count=1;
 integer active,c0,c1,c2,c3,any_busy,multi_busy,all_busy,multi_work,all_work,arbitration;
 integer actual_multi=0,actual_all=0,max_calc_lanes=0;
 wire [3:0] calc_mask={dut.core3.state==2,dut.core2.state==2,dut.core1.state==2,dut.core0.state==2};
 wire [2:0] calc_lanes={2'b0,calc_mask[0]}+{2'b0,calc_mask[1]}+{2'b0,calc_mask[2]}+{2'b0,calc_mask[3]};
 integer inject_stalls=1, input_stall_count, output_stall_count, nonstall_cycles=-1;
 // AXIS payload must remain stable until the receiver accepts it.
 always @(posedge clk) begin
  if(!resetn || dut.soft_reset) stalled<=0;
  else begin
   if(stalled && (!rxvalid || rxdata!==held_data || rxlast!==held_last || rxkeep!==15))
    $fatal(1,"AXIS payload changed under backpressure");
   stalled<=rxvalid && !rxready;
   held_data<=rxdata;held_last<=rxlast;
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
    @(negedge clk);rxready=inject_stalls!=1 || (cycle%7>=3);cycle=cycle+1;
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
   write_word(40,batch_count,index%3,15,0);
   write_word(4,1,index%3,15,0);
   write_word(40,1,1,15,2); // immutable batch size while busy
   // A second start must not corrupt in-flight state.
   write_word(4,1,0,15,2);
   fork send_vector(index,malformed);receive_vector(index);join
   read_word(8,value,0);
   if(value!==(malformed ? 6 : 2)) $fatal(1,"DMA status %h malformed=%0d",value,malformed);
   read_word(24,value,0);if(value!==batch_count*128) $fatal(1,"input count");
   read_word(28,value,0);if(value!==batch_count*128) $fatal(1,"output count");
   read_word(44,value,0);if(value!==batch_count) $fatal(1,"completed FFT count");
   read_word(32,value,0);input_stall_count=value;
   if(inject_stalls && value==0) $fatal(1,"missing starvation accounting");
   read_word(36,value,0);output_stall_count=value;
   if(inject_stalls==1 && value==0) $fatal(1,"missing backpressure accounting");
   read_word(16,value,0);active=value;
   read_word(48,value,0);if(value!==4) $fatal(1,"quad core count");
   read_word(52,value,0);c0=value;
   read_word(56,value,0);c1=value;
   read_word(60,value,0);c2=value;
   read_word(64,value,0);c3=value;
   read_word(68,value,0);any_busy=value;
   read_word(72,value,0);multi_busy=value;
   read_word(76,value,0);all_busy=value;
   read_word(80,value,0);multi_work=value;
   read_word(84,value,0);all_work=value;
   read_word(88,value,0);arbitration=value;
   if(c0<=0 || c0>any_busy || c1>any_busy || c2>any_busy || c3>any_busy ||
      all_busy>multi_busy || multi_busy>any_busy || any_busy>active ||
      all_work>multi_work || all_work>all_busy || multi_work>multi_busy ||
      c0+c1+c2+c3<any_busy || input_stall_count>active || output_stall_count>active || arbitration>active)
    $fatal(1,"quad counter hierarchy");
   if(active-any_busy!=(batch_count+3)/4 || multi_work<actual_multi || multi_work>actual_multi+batch_count ||
      all_work<actual_all || all_work>actual_all+batch_count/4)
    $fatal(1,"group boundary or work-window disagrees with actual core states");
   if((batch_count<4 && (c3!=0 || all_busy!=0 || all_work!=0 || actual_all!=0)) ||
      (batch_count<3 && c2!=0) || (batch_count<2 && (c1!=0 || multi_work!=0 || actual_multi!=0)))
    $fatal(1,"inactive arithmetic lane did work");
   if(inject_stalls!=2 && batch_count>1 && actual_multi<=0) $fatal(1,"no concurrent CALC");
   if(!inject_stalls && max_calc_lanes!=(batch_count<4 ? batch_count : 4)) $fatal(1,"expected simultaneous arithmetic lanes");
   if(!inject_stalls && batch_count>=4 && (all_work<=batch_count/4 || actual_all<=0)) $fatal(1,"four cores never calculated concurrently");
   if(inject_stalls==2 && (actual_multi!=0 || multi_work!=0 || actual_all!=0)) $fatal(1,"source-starved fixture unexpectedly overlapped CALC");
   if(!inject_stalls && batch_count>=4 && active>=1116*((batch_count+1)/2)) $fatal(1,"four cores did not improve two-core interval");
   $display("QUAD_COUNTER_PASS count=%0d stall_mode=%0d active=%0d c0=%0d c1=%0d c2=%0d c3=%0d any_busy=%0d multi_busy=%0d all_busy=%0d multi_work=%0d all_work=%0d actual_multi_CALC=%0d actual_all_CALC=%0d max_CALC_lanes=%0d arbitration=%0d input_stalls=%0d output_stalls=%0d",batch_count,inject_stalls,active,c0,c1,c2,c3,any_busy,multi_busy,all_busy,multi_work,all_work,actual_multi,actual_all,max_calc_lanes,arbitration,input_stall_count,output_stall_count);
  end
 endtask
 // Cores within a group overlap, but no next-group prefetch is permitted.
 always @(posedge clk) if(resetn && dut.running && txvalid && txready) begin
  if(dut.input_count/512 != dut.output_count/512) $fatal(1,"next-group input crossed barrier");
 end
 // Independent assertion on the actual unchanged core states, not the exported counter.
 always @(posedge clk) begin
  if(!resetn || dut.soft_reset || (dut.start_pulse[0] && dut.input_count==0)) begin
   actual_multi<=0;actual_all<=0;max_calc_lanes<=0;
  end else if(dut.running) begin
   if(calc_lanes>=2) actual_multi<=actual_multi+1;
   if(&calc_mask) actual_all<=actual_all+1;
   if(calc_lanes>max_calc_lanes) max_calc_lanes<=calc_lanes;
  end
 end

 initial begin
  if(!$value$plusargs("CASES=%d",cases)) $fatal(1,"Missing CASES");
  $readmemh("inputs.hex",inputs,0,cases*128-1);
  $readmemh("expected.hex",expected,0,cases*128-1);
  repeat(5) @(negedge clk);resetn=1;
  read_word(0,value,0);if(value!==32'h46545084) $fatal(1,"batch ID");
  read_word(12,value,0);if(value!==128) $fatal(1,"FFT size");
  read_word(20,value,0);if(value!==4) $fatal(1,"quad ABI");
  read_word(40,value,0);if(value!==128) $fatal(1,"default batch size");
  write_word(40,0,0,15,2);write_word(40,129,1,15,2);
  write_word(4,1,1,0,0);read_word(8,value,0);if(value!==0) $fatal(1,"zero strobe started core");
  write_word(4,1,2,1,2);write_word(5,1,1,15,2);
  write_word(12'h100,1,0,15,2);read_word(12'h800,value,2);
  batch_count=1;inject_stalls=0;run_vector(0,0);
  batch_count=2;run_vector(1,0);
  batch_count=3;run_vector(2,0);
  batch_count=4;run_vector(3,0);
  batch_count=5;run_vector(4,0);
  batch_count=6;run_vector(5,0);
  batch_count=7;run_vector(6,0);
  batch_count=127;run_vector(3,0);
  batch_count=128;run_vector(0,0);
  batch_count=4;inject_stalls=2;run_vector(0,0);
  batch_count=128;inject_stalls=1;
  // Cover all 272 independent numeric vectors across three complete DMA packets.
  run_vector(0,0);run_vector(128,0);run_vector(256,0);
  run_vector(2,1);run_vector(3,2);run_vector(4,3);
  // Abort during first partial load, then during calculation of a later FFT.
  write_word(4,1,0,15,0);
  @(negedge clk);txvalid=1;txdata=32'hdeadbeef;txlast=0;
  repeat(13) @(negedge clk);txvalid=0;
  write_word(4,2,2,15,0);repeat(5) @(negedge clk);
  read_word(8,value,0);if(value!==0) $fatal(1,"abort status");
  run_vector(5,0);
  write_word(40,1,0,15,0);write_word(4,1,1,15,0);
  batch_count=1;send_vector(3,0);
  repeat(20) @(negedge clk);write_word(4,2,0,15,0);
  repeat(5) @(negedge clk);batch_count=128;run_vector(6,0);
  // Abort after all four cores are calculating, then restart a full axis.
  write_word(40,4,0,15,0);write_word(4,1,0,15,0);
  batch_count=4;inject_stalls=0;send_vector(8,0);
  if(calc_lanes!=4) $fatal(1,"abort fixture did not reach four concurrent CALC lanes");
  repeat(10) @(negedge clk);write_word(4,2,1,15,0);
  repeat(5) @(negedge clk);batch_count=128;inject_stalls=1;run_vector(8,0);
  // Abort stalled final output: no stale TLAST/data may leak into the next packet.
  write_word(40,1,0,15,0);write_word(4,1,0,15,0);
  batch_count=1;send_vector(4,0);
  wait(rxvalid);repeat(10) @(negedge clk);
  write_word(4,2,0,15,0);repeat(5) @(negedge clk);
  batch_count=128;run_vector(7,0);
  // Abort during lane2's partial load; all four lane state machines must reset.
  write_word(40,4,0,15,0);write_word(4,1,0,15,0);
  for(k=0;k<269;k=k+1) begin
   @(negedge clk);txvalid=1;txdata=inputs[k];txlast=0;
   @(posedge clk);while(!txready) @(posedge clk);
  end
  @(negedge clk);txvalid=0;
  write_word(4,2,0,15,0);repeat(5) @(negedge clk);
  batch_count=128;run_vector(10,0);
  // Drain lanes0..2, then abort a valid stalled lane3 output.
  write_word(40,4,0,15,0);write_word(4,1,0,15,0);
  batch_count=4;inject_stalls=0;
  fork
   send_vector(9,0);
   begin
    received=0;
    while(received<384) begin
     @(negedge clk);rxready=1;
     @(posedge clk);
     if(rxvalid && rxready) begin
      if(rxdata!==expected[((9+received/128)%cases)*128+received%128] || rxlast || rxkeep!==15)
       $fatal(1,"prefix drain mismatch before lane3 abort");
      received=received+1;
     end
    end
    @(negedge clk);rxready=0;
   end
  join
  wait(rxvalid);if(dut.output_lane!=3) $fatal(1,"lane3 abort fixture");
  repeat(10) @(negedge clk);write_word(4,2,0,15,0);repeat(5) @(negedge clk);
  batch_count=128;inject_stalls=1;run_vector(11,0);
  $display("DMA_QUAD_CTRL_PASS numeric_vectors=%0d full_axis_packets malformed_TLAST_TKEEP abort_recovery lane2_partial_abort lane3_stalled_abort actual_four_CALC_overlap group_barrier partial_group source_starved",cases);
  $finish;
 end
 initial begin #50000000;$fatal(1,"batch TB watchdog");end
endmodule
