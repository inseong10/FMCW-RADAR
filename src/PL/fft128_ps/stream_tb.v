`timescale 1ns/1ps
module stream_tb;
 reg clk=0; always #5 clk=~clk;
 reg rst=1,start=0,iv=0,il=0,ready=0;
 reg [31:0] idata=0;
 wire busy,done,error,ir,ov,ol;
 wire [31:0] od;
 `ifdef FFT128_PIPELINE
 fft128_pipeline dut(
 `else
 fft128_stream dut(
 `endif
  .clk(clk),.rst(rst),.start(start),.busy(busy),.done(done),.input_error(error),
  .s_axis_tdata(idata),.s_axis_tvalid(iv),.s_axis_tready(ir),.s_axis_tlast(il),
  .m_axis_tdata(od),.m_axis_tvalid(ov),.m_axis_tready(ready),.m_axis_tlast(ol));
 reg [31:0] inputs[0:2047],expected[0:2047],held;
 integer t,k,j,seed=179,received;
 reg stalled,held_last;
 initial begin
  $readmemh("inputs_stream.hex",inputs,0,2047);
  $readmemh("expected_stream.hex",expected,0,2047);
  repeat(5) @(negedge clk); rst=0;
  for(t=0;t<16;t=t+1) begin
   @(negedge clk); start=1; @(negedge clk); start=0;
   for(k=0;k<128;k=k+1) begin
    repeat($urandom(seed)%4) @(negedge clk);
    idata=inputs[t*128+k]; iv=1; il=(k==127);
    if(t==15) il=(k==100); // malformed TLAST must raise error, no hang
    @(posedge clk); while(!ir) @(posedge clk);
    @(negedge clk); iv=0;
   end
   received=0; stalled=0;
   while(received<128) begin
    @(negedge clk); ready=($urandom(seed)%4==0);
    @(posedge clk);
    if(stalled && (!ov || od!==held || ol!==held_last)) $fatal(1,"AXIS hold violation");
    stalled=ov&&!ready; held=od; held_last=ol;
    if(ov&&ready) begin
     if(od!==expected[t*128+received] || ol!==(received==127)) $fatal(1,"AXIS output bin %0d",received);
     received=received+1;
    end
   end
   @(negedge clk); ready=0;
   if(error!==(t==15)) $fatal(1,"Input TLAST error flag");
  end
  @(negedge clk); start=1; @(negedge clk); start=0;
  repeat(10) @(negedge clk); rst=1;
  repeat(3) @(negedge clk); rst=0;
  @(negedge clk); if(busy || ov || error) $fatal(1,"Reset failed");
  $display("STREAM_PASS vectors=16 stalls_and_TLAST_and_reset"); $finish;
 end
 initial begin #2000000; $fatal(1,"TB watchdog"); end
endmodule
