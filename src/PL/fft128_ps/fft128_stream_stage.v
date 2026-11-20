// E13-stream: frame-buffered DIT stage; two input and two output frame slots.
// A dedicated butterfly accepts one pair/clock. Compute, input fill and output
// drain use distinct slots, so sustained frame initiation can reach 128 clocks.
module fft128_stream_stage #(parameter STAGE=0)(
 input wire clk,rst,
 input wire [31:0] s_data,input wire s_valid,output wire s_ready,input wire s_last,
 output wire [31:0] m_data,output wire m_valid,input wire m_ready,output wire m_last,
 output wire occupied,output reg input_error,
 output wire issue_event,retire_event,output reg calc_busy
);
 reg [1:0] input_full,output_owned,output_full;
 reg fill_slot,calc_input_slot,calc_output_slot,read_slot,data_slot;
 reg [6:0] fill_idx,read_idx;
 reg [6:0] issued,retired;
 reg output_valid,output_last;
 wire fill=s_valid && s_ready;
 wire issue=calc_busy && issued<64;
 wire [14:0] addr_a,addr_b;wire [7:0] tw_addr;wire addr_valid,tw_valid;
 address_generator addr(.fft_mode(1'b0),.stage(STAGE[2:0]),.butterfly_idx(issued[6:0]),
  .base_addr(15'd0),.rd_addr_a(addr_a),.rd_addr_b(addr_b),.twiddle_addr(tw_addr),.addr_valid(addr_valid));
 wire signed [15:0] wr,wi;
 fft128_twiddle twiddle(.clk(clk),.rst(rst),.rd_en(issue),.twiddle_addr(tw_addr),
  .twiddle_real(wr),.twiddle_imag(wi),.twiddle_valid(tw_valid));
 wire [31:0] in_a[0:1],in_b[0:1],out_a[0:1];wire [1:0] va,vb;
 wire [31:0] y0,y1;wire result_valid;
 butterfly_pipeline butterfly(.clk(clk),.rst(rst),
  .valid_in(calc_busy && va[calc_input_slot] && vb[calc_input_slot] && tw_valid),
  .ar($signed(in_a[calc_input_slot][15:0])),.ai($signed(in_a[calc_input_slot][31:16])),
  .br($signed(in_b[calc_input_slot][15:0])),.bi($signed(in_b[calc_input_slot][31:16])),
  .wr(wr),.wi(wi),.valid_out(result_valid),.y0(y0),.y1(y1));
 reg [6:0] pipe_a[0:3],pipe_b[0:3];
 wire retire=calc_busy && result_valid;
 wire read_request=!rst && output_full[read_slot] && (!output_valid || m_ready);
 wire [6:0] reversed={fill_idx[0],fill_idx[1],fill_idx[2],fill_idx[3],fill_idx[4],fill_idx[5],fill_idx[6]};
 wire [6:0] fill_addr=STAGE==0 ? reversed : fill_idx;
 genvar g;
 generate for(g=0;g<2;g=g+1) begin: slot
  wire load_here=fill && fill_slot==g;
  wire compute_read=issue && calc_input_slot==g;
  wire compute_write=retire && calc_output_slot==g;
  wire output_read=read_request && read_slot==g;
  fft_working_ram #(.ADDR_WIDTH(7),.DEPTH(128)) input_ram(
   .clk(clk),.rst(rst),.a_en(load_here || compute_read),.a_we(load_here),
   .a_addr(load_here ? fill_addr : addr_a[6:0]),.a_din(s_data),.a_dout(in_a[g]),.a_valid(va[g]),
   .b_en(compute_read),.b_we(1'b0),.b_addr(addr_b[6:0]),.b_din(32'd0),.b_dout(in_b[g]),.b_valid(vb[g]));
  fft_working_ram #(.ADDR_WIDTH(7),.DEPTH(128)) output_ram(
   .clk(clk),.rst(rst),.a_en(compute_write || output_read),.a_we(compute_write),
   .a_addr(compute_write ? pipe_a[3] : read_idx),.a_din(y0),.a_dout(out_a[g]),.a_valid(),
   .b_en(compute_write),.b_we(compute_write),.b_addr(pipe_b[3]),.b_din(y1),.b_dout(),.b_valid());
 end endgenerate
 assign s_ready=!rst && !input_full[fill_slot];
 assign m_valid=!rst && output_valid;
 assign m_data=out_a[data_slot];
 assign m_last=m_valid && output_last;
 assign occupied=calc_busy || |input_full || |output_owned || fill_idx!=0 || output_valid;
 assign issue_event=issue && addr_valid;
 assign retire_event=retire;
 integer p;
 always @(posedge clk or posedge rst) begin
  if(rst) begin
   input_full<=0;output_owned<=0;output_full<=0;
   fill_slot<=0;calc_input_slot<=0;calc_output_slot<=0;read_slot<=0;data_slot<=0;
   fill_idx<=0;read_idx<=0;issued<=0;retired<=0;
   output_valid<=0;output_last<=0;input_error<=0;calc_busy<=0;
   for(p=0;p<4;p=p+1) begin pipe_a[p]<=0;pipe_b[p]<=0;end
  end else begin
   pipe_a[0]<=addr_a[6:0];pipe_b[0]<=addr_b[6:0];
   for(p=1;p<4;p=p+1) begin pipe_a[p]<=pipe_a[p-1];pipe_b[p]<=pipe_b[p-1];end
   if(fill) begin
    if(s_last!=(fill_idx==127)) input_error<=1;
    fill_idx<=fill_idx+1'b1;
    if(fill_idx==127) begin input_full[fill_slot]<=1;fill_slot<=!fill_slot;end
   end
   if(!calc_busy && input_full[calc_input_slot] && !output_owned[calc_output_slot]) begin
    calc_busy<=1;issued<=0;retired<=0;output_owned[calc_output_slot]<=1;
   end
   if(issue) issued<=issued+1'b1;
   if(retire) begin
    retired<=retired+1'b1;
    if(retired==63) begin
     calc_busy<=0;input_full[calc_input_slot]<=0;output_full[calc_output_slot]<=1;
     calc_input_slot<=!calc_input_slot;calc_output_slot<=!calc_output_slot;
    end
   end
   if(output_valid && m_ready) output_valid<=0;
   if(read_request) begin
    output_valid<=1;output_last<=read_idx==127;data_slot<=read_slot;read_idx<=read_idx+1'b1;
    if(read_idx==127) read_slot<=!read_slot;
   end
   if(m_valid && m_ready && output_last) begin output_full[data_slot]<=0;output_owned[data_slot]<=0;end
  end
 end
endmodule
