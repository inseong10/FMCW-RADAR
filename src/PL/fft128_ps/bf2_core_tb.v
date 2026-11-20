`timescale 1ns/1ps
module bf2_core_tb;
 reg clk=0;always #5 clk=~clk;
 reg rst=1,start=0,iv=0,il=0,ready=0,gready=0;
 reg [31:0] idata=0;
 wire busy,done,error,ir,ov,ol,gbusy,gdone,gerror,gir,gov,gol;
 wire di,dr,ca;wire [31:0] od,god;
 fft128_bf2 dut(.clk(clk),.rst(rst),.start(start),.busy(busy),.done(done),.input_error(error),
  .s_axis_tdata(idata),.s_axis_tvalid(iv),.s_axis_tready(ir),.s_axis_tlast(il),
  .m_axis_tdata(od),.m_axis_tvalid(ov),.m_axis_tready(ready),.m_axis_tlast(ol),
  .dual_issue(di),.dual_retire(dr),.calc_active(ca));
 fft128_pipeline baseline(.clk(clk),.rst(rst),.start(start),.busy(gbusy),.done(gdone),.input_error(gerror),
  .s_axis_tdata(idata),.s_axis_tvalid(iv),.s_axis_tready(gir),.s_axis_tlast(il),
  .m_axis_tdata(god),.m_axis_tvalid(gov),.m_axis_tready(gready),.m_axis_tlast(gol));
 reg [31:0] inputs[0:131071],expected[0:131071],held;
 reg held_last,stalled=0;
 integer cases,t,k,received,greceived,rcycle,gcycle;
 integer issue_count=0,retire_count=0,calc_count=0,gcalc_count=0;
 integer stage_issues[0:6],stage_retires[0:6],j;
 always @(posedge clk) begin
  if(rst || start) begin
   issue_count<=0;retire_count<=0;calc_count<=0;gcalc_count<=0;stalled<=0;
   for(j=0;j<7;j=j+1) begin stage_issues[j]<=0;stage_retires[j]<=0;end
  end else begin
   if(di) begin
    issue_count<=issue_count+1;stage_issues[dut.stage]<=stage_issues[dut.stage]+1;
    if(dut.read_ea==dut.read_eb || dut.read_oa==dut.read_ob) $fatal(1,"read bank collision");
    if(dut.addr_a0==dut.addr_a1 || dut.addr_a0==dut.addr_b1 ||
       dut.addr_b0==dut.addr_a1 || dut.addr_b0==dut.addr_b1) $fatal(1,"overlapping butterflies");
   end
   if(dr) begin
    retire_count<=retire_count+1;stage_retires[dut.stage]<=stage_retires[dut.stage]+1;
    if(dut.write_ea==dut.write_eb || dut.write_oa==dut.write_ob) $fatal(1,"write bank collision");
   end
   if(ca) calc_count<=calc_count+1;
   if(baseline.state==2) gcalc_count<=gcalc_count+1;
   if(dut.result_valid0!==dut.result_valid1) $fatal(1,"two arithmetic pipelines lost alignment");
   if(stalled && (!ov || od!==held || ol!==held_last)) $fatal(1,"output hold violation");
   stalled<=ov && !ready;held<=od;held_last<=ol;
  end
 end
 initial begin
  if(!$value$plusargs("CASES=%d",cases)) $fatal(1,"Missing CASES");
  $readmemh("inputs.hex",inputs,0,cases*128-1);
  $readmemh("expected.hex",expected,0,cases*128-1);
  repeat(5) @(negedge clk);rst=0;
  for(t=0;t<cases;t=t+1) begin
   @(negedge clk);start=1;@(negedge clk);start=0;
   fork
    begin
     for(k=0;k<128;k=k+1) begin
      repeat((k+t)%4) @(negedge clk);
      idata=inputs[t*128+k];iv=1;il=t%17==16 ? k==100 : k==127;
      @(posedge clk);while(!ir || !gir) @(posedge clk);
      @(negedge clk);iv=0;
     end
    end
    begin
     received=0;rcycle=0;
     while(received<128) begin
      @(negedge clk);ready=rcycle%7>=3;rcycle=rcycle+1;
      @(posedge clk);
      if(ov && ready) begin
       if(od!==expected[t*128+received] || ol!==(received==127))
        $fatal(1,"bf2 integer mismatch vector=%0d bin=%0d actual=%h expected=%h",t,received,od,expected[t*128+received]);
       received=received+1;
      end
      if(rcycle>4000) $fatal(1,"bf2 timeout");
     end
     @(negedge clk);ready=0;
    end
    begin
     greceived=0;gcycle=0;
     while(greceived<128) begin
      @(negedge clk);gready=gcycle%5>=2;gcycle=gcycle+1;
      @(posedge clk);
      if(gov && gready) begin
       if(god!==expected[t*128+greceived] || gol!==(greceived==127)) $fatal(1,"baseline mismatch");
       greceived=greceived+1;
      end
      if(gcycle>4000) $fatal(1,"baseline timeout");
     end
     @(negedge clk);gready=0;
    end
   join
   if(error!==(t%17==16) || gerror!==error || busy || gbusy) $fatal(1,"TLAST or completion mismatch");
   if(issue_count!=224 || retire_count!=224 || calc_count!=252 || gcalc_count!=476)
    $fatal(1,"arithmetic schedule issue=%0d retire=%0d CALC=%0d baseline_CALC=%0d",issue_count,retire_count,calc_count,gcalc_count);
   for(j=0;j<7;j=j+1) if(stage_issues[j]!=32 || stage_retires[j]!=32) $fatal(1,"stage pair accounting");
  end
  $display("BF2_CORE_PASS vectors=%0d exact_bins=%0d baseline_CALC=476 bf2_CALC=252 issue_pairs=224 retire_pairs=224 bank_conflicts=0 stalled_output malformed_TLAST",cases,cases*128);
  $finish;
 end
 initial begin #20000000;$fatal(1,"bf2 core watchdog");end
endmodule
