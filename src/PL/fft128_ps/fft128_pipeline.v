// Radix-2 DIT: ping-pong RAM banks permit simultaneous read and write.
// During each stage, issue 64 butterflies at one per clock, then drain pipeline.
// One FFT at a time; PS transfers still use the existing AXI-Lite frontend.
module fft128_pipeline(
 input wire clk, rst, start,
 output wire busy, output reg done, input_error,
 input wire [31:0] s_axis_tdata,
 input wire s_axis_tvalid, output wire s_axis_tready, input wire s_axis_tlast,
 output wire [31:0] m_axis_tdata,
 output wire m_axis_tvalid, input wire m_axis_tready, output wire m_axis_tlast
);
 localparam IDLE=0, LOAD=1, CALC=2, OUT_REQ=3, OUT_SEND=4;
 reg [2:0] state;
 reg [6:0] load_idx, output_idx;
 reg [2:0] stage;
 reg [6:0] issued, retired;
 wire issue = state==CALC && issued<64;
 wire [14:0] addr_a, addr_b;
 wire [7:0] tw_addr;
 wire addr_valid;
 address_generator addresses(.fft_mode(1'b0),.stage(stage),.butterfly_idx(issued),
  .base_addr(15'd0),.rd_addr_a(addr_a),.rd_addr_b(addr_b),
  .twiddle_addr(tw_addr),.addr_valid(addr_valid));
 wire signed [15:0] wr, wi;
 wire tw_valid;
 fft128_twiddle tw(.clk(clk),.rst(rst),.rd_en(issue),.twiddle_addr(tw_addr),
  .twiddle_real(wr),.twiddle_imag(wi),.twiddle_valid(tw_valid));
 reg [6:0] pipe_a[0:3], pipe_b[0:3];
 integer p;
 wire [31:0] d0a,d0b,d1a,d1b;
 wire v0a,v0b,v1a,v1b;
 wire [31:0] source_a = stage[0] ? d1a : d0a;
 wire [31:0] source_b = stage[0] ? d1b : d0b;
 wire source_valid = stage[0] ? (v1a && v1b) : (v0a && v0b);
 wire result_valid;
 wire [31:0] y0,y1;
 butterfly_pipeline butterfly(.clk(clk),.rst(rst),
  .valid_in(state==CALC && source_valid && tw_valid),
  .ar($signed(source_a[15:0])),.ai($signed(source_a[31:16])),
  .br($signed(source_b[15:0])),.bi($signed(source_b[31:16])),
  .wr(wr),.wi(wi),.valid_out(result_valid),.y0(y0),.y1(y1));
 wire load = state==LOAD && s_axis_tvalid;
 wire write_result = state==CALC && result_valid;
 wire output_read = state==OUT_REQ;
 wire [6:0] reversed = {load_idx[0],load_idx[1],load_idx[2],load_idx[3],load_idx[4],load_idx[5],load_idx[6]};
 // Stage 0 reads bank 0; stage 6 writes bank 1, the final output bank.
 fft_working_ram #(.DEPTH(128)) bank0(
  .clk(clk),.rst(rst),
  .a_en(load || (issue && !stage[0]) || (write_result && stage[0])),
  .a_we(load || (write_result && stage[0])),
  .a_addr({1'b0,load ? reversed : stage[0] ? pipe_a[3] : addr_a[6:0]}),
  .a_din(load ? s_axis_tdata : y0),.a_dout(d0a),.a_valid(v0a),
  .b_en((issue && !stage[0]) || (write_result && stage[0])),
  .b_we(write_result && stage[0]),
  .b_addr({1'b0,stage[0] ? pipe_b[3] : addr_b[6:0]}),
  .b_din(y1),.b_dout(d0b),.b_valid(v0b));
 fft_working_ram #(.DEPTH(128)) bank1(
  .clk(clk),.rst(rst),
  .a_en(output_read || (issue && stage[0]) || (write_result && !stage[0])),
  .a_we(write_result && !stage[0]),
  .a_addr({1'b0,output_read ? output_idx : stage[0] ? addr_a[6:0] : pipe_a[3]}),
  .a_din(y0),.a_dout(d1a),.a_valid(v1a),
  .b_en((issue && stage[0]) || (write_result && !stage[0])),
  .b_we(write_result && !stage[0]),
  .b_addr({1'b0,stage[0] ? addr_b[6:0] : pipe_b[3]}),
  .b_din(y1),.b_dout(d1b),.b_valid(v1b));
 assign busy=state!=IDLE;
 assign s_axis_tready=state==LOAD;
 assign m_axis_tdata=d1a;
 assign m_axis_tvalid=state==OUT_SEND;
 assign m_axis_tlast=state==OUT_SEND && output_idx==127;
 always @(posedge clk or posedge rst) begin
  if(rst) begin
   state<=IDLE; done<=0; input_error<=0;
   load_idx<=0; output_idx<=0; stage<=0; issued<=0; retired<=0;
   for(p=0;p<4;p=p+1) begin pipe_a[p]<=0; pipe_b[p]<=0; end
  end else begin
   done<=0;
   pipe_a[0]<=addr_a[6:0]; pipe_b[0]<=addr_b[6:0];
   for(p=1;p<4;p=p+1) begin pipe_a[p]<=pipe_a[p-1]; pipe_b[p]<=pipe_b[p-1]; end
   case(state)
    IDLE: if(start) begin state<=LOAD; load_idx<=0; input_error<=0; end
    LOAD: if(s_axis_tvalid) begin
     if(s_axis_tlast != (load_idx==127)) input_error<=1;
     if(load_idx==127) begin state<=CALC; stage<=0; issued<=0; retired<=0; end
     else load_idx<=load_idx+1'b1;
    end
    CALC: begin
     if(issue) issued<=issued+1'b1;
     if(write_result) begin
      if(retired==63) begin
       issued<=0; retired<=0;
       if(stage==6) begin state<=OUT_REQ; output_idx<=0; end
       else stage<=stage+1'b1;
      end else retired<=retired+1'b1;
     end
    end
    OUT_REQ: state<=OUT_SEND;
    OUT_SEND: if(m_axis_tready) begin
     if(output_idx==127) begin state<=IDLE; done<=1; end
     else begin output_idx<=output_idx+1'b1; state<=OUT_REQ; end
    end
    default: state<=IDLE;
   endcase
  end
 end
endmodule
