// E14: 64KiB simple dual-port block RAM, one synchronous read and one write.
// Contents are deliberately not reset; the controller owns all valid epochs.
module fft128_frame_ram(
 input wire clk,
 input wire rd_en,input wire [13:0] rd_addr,output reg [31:0] rd_data,
 input wire wr_en,input wire [13:0] wr_addr,input wire [31:0] wr_data
);
 (* ram_style="block" *) reg [31:0] words[0:16383];
 always @(posedge clk) begin
  if(wr_en) words[wr_addr]<=wr_data;
  if(rd_en) rd_data<=words[rd_addr];
 end
endmodule
