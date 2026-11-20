// E13-stream: seven dedicated DIT stages connected by ready/valid streams.
// Each stage buffers complete frames. Natural external input/output order;
// stage0 loads bit-reversed input. No inter-frame arithmetic state is shared.
module fft128_streaming(
 input wire clk,rst,
 input wire [31:0] s_data,input wire s_valid,output wire s_ready,input wire s_last,
 output wire [31:0] m_data,output wire m_valid,input wire m_ready,output wire m_last,
 output wire busy,input_error,
 output wire [6:0] stage_issue,stage_retire,stage_calc,
 output reg [7:0] inflight_vectors
);
 reg [6:0] input_index;
 wire [31:0] data[0:7];wire [7:0] valid,ready,last;
 wire [6:0] occupied,errors;
 assign data[0]=s_data;assign valid[0]=s_valid;assign last[0]=s_last;assign s_ready=ready[0];
 assign m_data=data[7];assign m_valid=valid[7];assign m_last=last[7];assign ready[7]=m_ready;
 assign busy=|occupied;assign input_error=|errors;
 genvar g;
 generate for(g=0;g<7;g=g+1) begin: stage
  fft128_stream_stage #(.STAGE(g)) unit(.clk(clk),.rst(rst),
   .s_data(data[g]),.s_valid(valid[g]),.s_ready(ready[g]),.s_last(last[g]),
   .m_data(data[g+1]),.m_valid(valid[g+1]),.m_ready(ready[g+1]),.m_last(last[g+1]),
   .occupied(occupied[g]),.input_error(errors[g]),
   .issue_event(stage_issue[g]),.retire_event(stage_retire[g]),.calc_busy(stage_calc[g]));
 end endgenerate
 always @(posedge clk or posedge rst) begin
  if(rst) begin inflight_vectors<=0;input_index<=0;end
  else begin
   if(s_valid && s_ready) input_index<=input_index+1'b1;
   case({s_valid && s_ready && input_index==127,m_valid && m_ready && m_last})
   2'b10:inflight_vectors<=inflight_vectors+1'b1;
   2'b01:inflight_vectors<=inflight_vectors-1'b1;
   default:begin end
   endcase
  end
 end
endmodule
