`timescale 1ns/1ps
module axi_tb;
 reg clk=0; always #5 clk=~clk;
 reg resetn=0;
 reg [11:0] awaddr=0, araddr=0;
 reg awvalid=0,wvalid=0,bready=0,arvalid=0,rready=0;
 reg [31:0] wdata=0;
 reg [3:0] wstrb=15;
 wire awready,wready,bvalid,arready,rvalid;
 wire [31:0] rdata;
 wire [1:0] bresp,rresp;
 fft128_axi dut(.aclk(clk),.aresetn(resetn),
  .s_axi_awaddr(awaddr),.s_axi_awprot(3'b0),.s_axi_awvalid(awvalid),.s_axi_awready(awready),
  .s_axi_wdata(wdata),.s_axi_wstrb(wstrb),.s_axi_wvalid(wvalid),.s_axi_wready(wready),
  .s_axi_bresp(bresp),.s_axi_bvalid(bvalid),.s_axi_bready(bready),
  .s_axi_araddr(araddr),.s_axi_arprot(3'b0),.s_axi_arvalid(arvalid),.s_axi_arready(arready),
  .s_axi_rdata(rdata),.s_axi_rresp(rresp),.s_axi_rvalid(rvalid),.s_axi_rready(rready));
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
 reg [31:0] value;
 integer cases, testno, k, polls;
 initial begin
  if (!$value$plusargs("CASES=%d",cases)) $fatal(1,"Missing CASES");
  $readmemh("inputs.hex",inputs,0,cases*128-1);
  $readmemh("expected.hex",expected,0,cases*128-1);
  repeat(5) @(negedge clk); resetn=1;
  read_word(0,value,0); if(value!==32'h46543128) $fatal(1,"ID");
  read_word(12,value,0); if(value!==128) $fatal(1,"SIZE");
  write_word(4,1,0,15,2); // start rejected until all words initialized
  write_word(12'h100,1,1,1,2); // partial store rejected
  write_word(12'h101,1,2,15,2); // unaligned rejected
  write_word(4,1,1,0,0); // zero strobe must not start
  read_word(12'h800,value,2); // no completed result yet
  read_word(12'hfff,value,2);
  for(testno=0;testno<cases;testno=testno+1) begin
   for(k=0;k<128;k=k+1) write_word(12'h100+k*4,inputs[testno*128+k],k%3,15,0);
   write_word(4,1,testno%3,15,0);
   write_word(12'h100,0,0,15,2); // cannot overwrite running FFT
   polls=0; value=1;
   while(value[0]) begin
    read_word(8,value,0); polls=polls+1;
    if(polls>1000) $fatal(1,"FFT timeout");
   end
   if(value!==2) $fatal(1,"STATUS %h",value);
   for(k=0;k<128;k=k+1) begin
    read_word(12'h800+k*4,value,0);
    if(value!==expected[testno*128+k])
     $fatal(1,"MISMATCH vector=%0d bin=%0d actual=%h expected=%h",testno,k,value,expected[testno*128+k]);
   end
   if(testno%64==0) $display("AXI checked vectors=%0d",testno+1);
  end
  // Reset aborts in-flight work, clears initialization and completed status.
  write_word(4,1,0,15,0);
  write_word(4,2,1,15,0);
  repeat(5) @(negedge clk);
  read_word(8,value,0); if(value!==0) $fatal(1,"RESET status");
  write_word(4,1,2,15,2);
  $display("AXI_PASS vectors=%0d bins=%0d independent_AW_W_and_response_stalls",cases,cases*128);
  $finish;
 end
 initial begin #500000000; $fatal(1,"TB watchdog"); end
endmodule
