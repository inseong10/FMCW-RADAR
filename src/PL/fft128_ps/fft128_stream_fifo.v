// E12: synchronous-read block RAM FIFO with a registered, stall-stable output.
// used includes the output register; backing storage has 256 words.
module fft128_stream_fifo (
 input wire clk, rst,
 input wire [31:0] s_data, input wire s_valid, output wire s_ready,
 output reg [31:0] m_data, output reg m_valid, input wire m_ready,
 output wire [9:0] used
);
 (* ram_style="block" *) reg [31:0] memory [0:255];
 reg [7:0] wr_ptr, rd_ptr;
 reg [8:0] stored;
 wire push=s_valid && s_ready;
 wire refill=stored!=0 && (!m_valid || m_ready);
 assign s_ready=stored<256;
 assign used={1'b0,stored}+{9'b0,m_valid};
 // Separate from reset: RAM contents need not be cleared or resettable.
 always @(posedge clk) begin
  if(push) memory[wr_ptr]<=s_data;
  if(refill) m_data<=memory[rd_ptr];
 end
 always @(posedge clk) begin
  if(rst) begin wr_ptr<=0;rd_ptr<=0;stored<=0;m_valid<=0;end
  else begin
   if(push) wr_ptr<=wr_ptr+1'b1;
   if(refill) begin rd_ptr<=rd_ptr+1'b1;m_valid<=1;end
   else if(m_ready) m_valid<=0;
   case({push,refill})
    2'b10:stored<=stored+1'b1;
    2'b01:stored<=stored-1'b1;
    default:stored<=stored;
   endcase
  end
 end
endmodule
