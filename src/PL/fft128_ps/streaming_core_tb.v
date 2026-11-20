`timescale 1ns/1ps
module streaming_core_tb;
 reg clk=0;always #10 clk=!clk;
 reg rst=1,s_valid=0,s_last=0,m_ready=0;
 reg [31:0] s_data=0;
 wire s_ready,m_valid,m_last,busy,input_error;wire [31:0] m_data;
 wire [6:0] stage_issue,stage_retire,stage_calc;wire [7:0] inflight;
 fft128_streaming dut(.clk(clk),.rst(rst),.s_data(s_data),.s_valid(s_valid),.s_ready(s_ready),.s_last(s_last),
  .m_data(m_data),.m_valid(m_valid),.m_ready(m_ready),.m_last(m_last),.busy(busy),.input_error(input_error),
  .stage_issue(stage_issue),.stage_retire(stage_retire),.stage_calc(stage_calc),.inflight_vectors(inflight));
 reg [31:0] inputs[0:34815],expected[0:34815];
 integer issued[0:6],retired[0:6],calc[0:6];
 integer cycle=0,received=0,mode=0,count=0,first_output=0,last_frame=0,interval_errors=0;
 integer multi_stage=0,multi_vector=0,active_stages=0,stall_left=0;reg active=0,held=0;
 reg [31:0] held_data;reg held_last;
 genvar g,h;
 generate for(g=0;g<7;g=g+1) begin: checks
  for(h=0;h<2;h=h+1) begin: banks
   always @(posedge clk) if(active && !rst) begin
    if(dut.stage[g].unit.slot[h].load_here && dut.stage[g].unit.slot[h].compute_read) $fatal(1,"Input slot collision");
    if(dut.stage[g].unit.slot[h].compute_write && dut.stage[g].unit.slot[h].output_read) $fatal(1,"Output slot collision");
    if(dut.stage[g].unit.slot[h].compute_read && dut.stage[g].unit.addr_a==dut.stage[g].unit.addr_b) $fatal(1,"Same butterfly read address");
    if(dut.stage[g].unit.slot[h].compute_write && dut.stage[g].unit.pipe_a[3]==dut.stage[g].unit.pipe_b[3]) $fatal(1,"Same butterfly write address");
   end
  end
 end endgenerate
 integer j;
 always @(negedge clk) if(active && !rst) begin
  if(mode==1 && received==32 && stall_left==0) stall_left=8000;
  if(stall_left>0) begin m_ready=0;stall_left=stall_left-1;if(stall_left==0) stall_left=-1;end
  else m_ready=mode==0 || cycle%11>2;
 end
 always @(posedge clk) if(active && !rst) begin
  cycle=cycle+1;active_stages=0;
  for(j=0;j<7;j=j+1) begin
   if(stage_issue[j]) issued[j]=issued[j]+1;
   if(stage_retire[j]) retired[j]=retired[j]+1;
   if(stage_calc[j]) begin calc[j]=calc[j]+1;active_stages=active_stages+1;end
  end
  if(active_stages>=2) multi_stage=multi_stage+1;
  if(inflight>=2) multi_vector=multi_vector+1;
  if(held && (!m_valid || m_data!==held_data || m_last!==held_last)) $fatal(1,"Unstable stalled output");
  held=m_valid && !m_ready;held_data=m_data;held_last=m_last;
  if(m_valid && m_ready) begin
   if(received>=count*128 || m_data!==expected[received]) $fatal(1,"Numeric index=%0d actual=%h expected=%h",received,m_data,expected[received]);
   if(m_last!==(received%128==127)) $fatal(1,"Output vector TLAST");
   if(received==0) first_output=cycle;
   if(received%128==127) begin
    if(mode==0 && received>127 && cycle-last_frame!=128) interval_errors=interval_errors+1;
    last_frame=cycle;
   end
   received=received+1;
  end
  if(cycle>200000) $fatal(1,"Core watchdog received=%0d",received);
 end
 task run_case(input integer n,input integer slow,input integer malformed);
 integer i;
 begin
  @(negedge clk);active=0;rst=1;s_valid=0;m_ready=0;held=0;
  repeat(5) @(negedge clk);
  count=n;mode=slow;cycle=0;received=0;first_output=0;last_frame=0;interval_errors=0;
  multi_stage=0;multi_vector=0;stall_left=0;
  for(i=0;i<7;i=i+1) begin issued[i]=0;retired[i]=0;calc[i]=0;end
  rst=0;active=1;
  fork
   begin
    for(i=0;i<n*128;i=i+1) begin
     @(negedge clk);s_valid=0;
     if(slow && i%13==0) repeat(3) @(negedge clk);
     s_data=inputs[i];s_last=(i%128==127) ^ (malformed && i==17);s_valid=1;
     @(posedge clk);while(!s_ready) @(posedge clk);
    end
    @(negedge clk);s_valid=0;
   end
   begin wait(received==n*128);end
  join
  @(negedge clk);
  if(input_error!==malformed[0]) $fatal(1,"Input TLAST error flag");
  for(i=0;i<7;i=i+1) if(issued[i]!=n*64 || retired[i]!=n*64 || calc[i]!=n*68)
   $fatal(1,"Stage%0d counts issue=%0d retire=%0d calc=%0d n=%0d",i,issued[i],retired[i],calc[i],n);
  if(n>1 && slow==0 && (interval_errors!=0 || multi_stage==0 || multi_vector==0)) $fatal(1,"No sustained streaming interval=%0d overlap=%0d",interval_errors,multi_stage);
  $display("STREAM_CORE_CASE_PASS count=%0d mode=%0d cycles=%0d first_output=%0d frame_II=128 multi_stage=%0d multi_vector=%0d stage_CALC_per_FFT=68",n,slow,cycle,first_output,multi_stage,multi_vector);
  repeat(5) @(negedge clk);if(busy || inflight!=0) $fatal(1,"Pipeline not empty");active=0;
 end
 endtask
 initial begin
  $readmemh("inputs.hex",inputs);$readmemh("expected.hex",expected);
  run_case(272,0,0);run_case(128,1,0);run_case(1,0,1);
  // Discard a partially filled and active multi-frame pipeline; all slot
  // ownership and pending RAM results must reset before the next exact run.
  @(negedge clk);rst=1;repeat(4) @(negedge clk);rst=0;
  s_valid=1;s_last=0;s_data=32'h12345678;m_ready=0;
  repeat(500) @(negedge clk);s_valid=0;
  run_case(5,0,0);
  $display("STREAMING_CORE_PASS numeric_vectors=272 exact_bins=34816 stages=7 frame_II=128 bank_conflicts=0 stalls malformed_TLAST reset_recovery");$finish;
 end
 initial begin #20000000;$fatal(1,"Global watchdog");end
endmodule
