// E13-bf2: two butterflies per engine, unchanged E12 input/output FIFO policy.
// A whole FFT is available and its whole output is reserved before launch.
// The lane can accept future input and drain older output during calculation.
module fft128_buffered_bf2_lane (
 input wire clk, rst, enable,
 output wire busy, done, input_error, work_active,
 output wire dual_issue, dual_retire, calc_active,
 input wire [31:0] s_axis_tdata,
 input wire s_axis_tvalid, output wire s_axis_tready, input wire s_axis_tlast,
 output wire [31:0] m_axis_tdata,
 output wire m_axis_tvalid, input wire m_axis_tready, output wire m_axis_tlast
);
 wire [31:0] input_data, output_data;
 wire input_valid,input_ready,output_valid,output_ready;
 wire output_last;
 wire [9:0] input_used,output_used;
 reg start;
 reg [6:0] input_index,output_index;
 reg working;
 assign work_active=working && !output_valid;
 assign m_axis_tlast=m_axis_tvalid && output_index==127;
 fft128_stream_fifo ingress(.clk(clk),.rst(rst),
  .s_data(s_axis_tdata),.s_valid(enable && s_axis_tvalid),.s_ready(s_axis_tready),
  .m_data(input_data),.m_valid(input_valid),.m_ready(input_ready),.used(input_used));
 fft128_stream_fifo egress(.clk(clk),.rst(rst),
  .s_data(output_data),.s_valid(output_valid),.s_ready(output_ready),
  .m_data(m_axis_tdata),.m_valid(m_axis_tvalid),.m_ready(enable && m_axis_tready),.used(output_used));
 fft128_bf2 core(.clk(clk),.rst(rst),.start(start),
  .busy(busy),.done(done),.input_error(input_error),
  .s_axis_tdata(input_data),.s_axis_tvalid(input_valid),.s_axis_tready(input_ready),
  .s_axis_tlast(input_index==127),
  .m_axis_tdata(output_data),.m_axis_tvalid(output_valid),
  .m_axis_tready(output_ready),.m_axis_tlast(output_last),
  .dual_issue(dual_issue),.dual_retire(dual_retire),.calc_active(calc_active));
 always @(posedge clk) begin
  if(rst) begin start<=0;input_index<=0;output_index<=0;working<=0;end
  else begin
   start<=0;
   // Keep <=256 total output words, including the FIFO output register.
   if(enable && !busy && !start && input_used>=128 && output_used<=128) start<=1;
   if(input_valid && input_ready) begin
    input_index<=input_index+1'b1;
    if(input_index==127) working<=1;
   end
   if(output_valid) working<=0;
   if(enable && m_axis_tvalid && m_axis_tready) output_index<=output_index+1'b1;
  end
 end
endmodule
