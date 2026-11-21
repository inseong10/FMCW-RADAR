// E14: one complete 128x128 frame, in-place PL transpose, one reused FFT.
module fft128_dma_frame_ctrl (
 (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 aclk CLK",
    X_INTERFACE_PARAMETER="ASSOCIATED_BUSIF S_AXI:S_AXIS:M_AXIS, ASSOCIATED_RESET aresetn" *)
 input wire aclk,
 (* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 aresetn RST",
    X_INTERFACE_PARAMETER="POLARITY ACTIVE_LOW" *) input wire aresetn,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI AWADDR" *) input wire [11:0] s_axi_awaddr,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI AWPROT" *) input wire [2:0] s_axi_awprot,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI AWVALID" *) input wire s_axi_awvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI AWREADY" *) output wire s_axi_awready,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI WDATA" *) input wire [31:0] s_axi_wdata,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI WSTRB" *) input wire [3:0] s_axi_wstrb,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI WVALID" *) input wire s_axi_wvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI WREADY" *) output wire s_axi_wready,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI BRESP" *) output reg [1:0] s_axi_bresp,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI BVALID" *) output reg s_axi_bvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI BREADY" *) input wire s_axi_bready,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI ARADDR" *) input wire [11:0] s_axi_araddr,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI ARPROT" *) input wire [2:0] s_axi_arprot,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI ARVALID" *) input wire s_axi_arvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI ARREADY" *) output wire s_axi_arready,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI RDATA" *) output reg [31:0] s_axi_rdata,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI RRESP" *) output reg [1:0] s_axi_rresp,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI RVALID",
    X_INTERFACE_PARAMETER="PROTOCOL AXI4LITE, DATA_WIDTH 32, ADDR_WIDTH 12, READ_WRITE_MODE READ_WRITE" *) output reg s_axi_rvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI RREADY" *) input wire s_axi_rready,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 S_AXIS TDATA" *) input wire [31:0] s_axis_tdata,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 S_AXIS TKEEP" *) input wire [3:0] s_axis_tkeep,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 S_AXIS TVALID" *) input wire s_axis_tvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 S_AXIS TREADY" *) output wire s_axis_tready,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 S_AXIS TLAST" *) input wire s_axis_tlast,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 M_AXIS TDATA" *) output wire [31:0] m_axis_tdata,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 M_AXIS TKEEP" *) output wire [3:0] m_axis_tkeep,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 M_AXIS TVALID" *) output wire m_axis_tvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 M_AXIS TREADY" *) input wire m_axis_tready,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 M_AXIS TLAST" *) output wire m_axis_tlast
);
 localparam IDLE=2'd0,RANGE=2'd1,DOPPLER=2'd2,DRAIN=2'd3;
 reg [1:0] phase;
 reg running,completed,failed,soft_reset;
 reg aw_pending,w_pending;
 reg [11:0] awaddr;
 reg [31:0] wdata;
 reg [3:0] wstrb;
 reg [14:0] input_count,output_count,range_outputs,doppler_inputs,doppler_outputs,read_requests;
 reg rd_valid;
 reg [31:0] cycles,input_stalls,output_stalls,range_cycles,doppler_cycles,drain_cycles;
 reg [31:0] matrix_reads,matrix_writes,overwrite_errors,io_overlap_cycles;
 reg [31:0] stage_busy_cycles,multi_stage_cycles,vector_overlap_cycles;
 reg [31:0] stage_issue_events[0:6],stage_retire_events[0:6];
 wire [6:0] stage_issue,stage_retire,stage_calc;
 wire [7:0] inflight_vectors;
 wire [2:0] compute_stages={2'b0,stage_calc[0]}+{2'b0,stage_calc[1]}+{2'b0,stage_calc[2]}+
  {2'b0,stage_calc[3]}+{2'b0,stage_calc[4]}+{2'b0,stage_calc[5]}+{2'b0,stage_calc[6]};
 wire pipeline_busy,pipeline_error,pipeline_ready,pipeline_valid,pipeline_last;
 wire [31:0] pipeline_data,ram_data;
 wire pipeline_send,pipeline_receive;
 wire read_consume=(phase==DOPPLER && pipeline_ready) || (phase==DRAIN && m_axis_tready);
 wire ram_read=running && !soft_reset && (phase==DOPPLER || phase==DRAIN) &&
  read_requests<16384 && (!rd_valid || read_consume);
 wire [13:0] ram_read_address=phase==DOPPLER ? {read_requests[6:0],read_requests[13:7]} : read_requests[13:0];
 // A result may overwrite a column only after all 128 inputs of that column
 // were accepted by the FFT. Even a prefetched, held read is thereby safe.
 wire overwrite_safe=doppler_inputs >= ({1'b0,doppler_outputs[13:7],7'b0}+15'd128);
 wire pipeline_accept=running && !soft_reset && (phase==RANGE || (phase==DOPPLER && overwrite_safe));
 assign pipeline_send=running && !soft_reset && pipeline_ready &&
  ((phase==RANGE && input_count<16384 && s_axis_tvalid) || (phase==DOPPLER && rd_valid));
 assign pipeline_receive=pipeline_valid && pipeline_accept;
 wire ram_write=pipeline_receive;
 wire [13:0] ram_write_address=phase==RANGE ? range_outputs[13:0] : {doppler_outputs[6:0],doppler_outputs[13:7]};
 fft128_frame_ram matrix(.clk(aclk),.rd_en(ram_read),.rd_addr(ram_read_address),.rd_data(ram_data),
  .wr_en(ram_write),.wr_addr(ram_write_address),.wr_data(pipeline_data));
 fft128_streaming pipeline(.clk(aclk),.rst(!aresetn || soft_reset),
  .s_data(phase==RANGE ? s_axis_tdata : ram_data),
  .s_valid(running && !soft_reset && ((phase==RANGE && input_count<16384 && s_axis_tvalid) || (phase==DOPPLER && rd_valid))),
  .s_ready(pipeline_ready),.s_last(phase==RANGE ? input_count[6:0]==127 : doppler_inputs[6:0]==127),
  .m_data(pipeline_data),.m_valid(pipeline_valid),.m_ready(pipeline_accept),.m_last(pipeline_last),
  .busy(pipeline_busy),.input_error(pipeline_error),
  .stage_issue(stage_issue),.stage_retire(stage_retire),.stage_calc(stage_calc),.inflight_vectors(inflight_vectors));
 assign s_axis_tready=running && !soft_reset && phase==RANGE && input_count<16384 && pipeline_ready;
 assign m_axis_tdata=ram_data;
 assign m_axis_tkeep=4'hf;
 assign m_axis_tvalid=running && !soft_reset && phase==DRAIN && rd_valid;
 assign m_axis_tlast=m_axis_tvalid && output_count==16383;
 assign s_axi_awready=!aw_pending && !s_axi_bvalid;
 assign s_axi_wready=!w_pending && !s_axi_bvalid;
 assign s_axi_arready=!s_axi_rvalid;
 wire write_command=aw_pending && w_pending && !s_axi_bvalid;
 wire clear_command=write_command && awaddr==4 && wstrb==15 && (wdata==2 || (wdata==1 && !running));
 integer k;
 always @(posedge aclk) begin
  if(!aresetn) begin
   aw_pending<=0;w_pending<=0;awaddr<=0;wdata<=0;wstrb<=0;
   s_axi_bvalid<=0;s_axi_bresp<=0;s_axi_rvalid<=0;s_axi_rresp<=0;s_axi_rdata<=0;
  end else begin
   if(s_axi_bvalid && s_axi_bready) s_axi_bvalid<=0;
   if(s_axi_rvalid && s_axi_rready) s_axi_rvalid<=0;
   if(s_axi_awvalid && s_axi_awready) begin aw_pending<=1;awaddr<=s_axi_awaddr;end
   if(s_axi_wvalid && s_axi_wready) begin w_pending<=1;wdata<=s_axi_wdata;wstrb<=s_axi_wstrb;end
   if(write_command) begin
    aw_pending<=0;w_pending<=0;s_axi_bvalid<=1;s_axi_bresp<=0;
    if(awaddr[1:0]!=0) s_axi_bresp<=2;
    else if(wstrb==0) begin end
    else if(wstrb!=15) s_axi_bresp<=2;
    else if(clear_command) begin end
    else if(awaddr==12'h028 && wdata==16384 && !running) begin end
    else s_axi_bresp<=2;
   end
   if(s_axi_arvalid && s_axi_arready) begin
    s_axi_rvalid<=1;s_axi_rresp<=0;s_axi_rdata<=0;
    if(s_axi_araddr[1:0]!=0) s_axi_rresp<=2;
    else if(s_axi_araddr>=12'h080 && s_axi_araddr<=12'h098)
     s_axi_rdata<=stage_issue_events[(s_axi_araddr-12'h080)>>2];
    else if(s_axi_araddr>=12'h0a0 && s_axi_araddr<=12'h0b8)
     s_axi_rdata<=stage_retire_events[(s_axi_araddr-12'h0a0)>>2];
    else case(s_axi_araddr)
     12'h000:s_axi_rdata<=32'h46545088;
     12'h004:s_axi_rdata<=0;
     12'h008:s_axi_rdata<={29'd0,failed,completed,running};
     12'h00c:s_axi_rdata<=128;
     12'h010:s_axi_rdata<=cycles;
     12'h014:s_axi_rdata<=8;
     12'h018:s_axi_rdata<={17'd0,input_count};
     12'h01c:s_axi_rdata<={17'd0,output_count};
     12'h020:s_axi_rdata<=input_stalls;
     12'h024:s_axi_rdata<=output_stalls;
     12'h028:s_axi_rdata<=16384;
     12'h02c:s_axi_rdata<={24'd0,range_outputs[14:7]}+{24'd0,doppler_outputs[14:7]};
     12'h030:s_axi_rdata<=1;
     12'h034:s_axi_rdata<=range_cycles;
     12'h038:s_axi_rdata<=doppler_cycles;
     12'h03c:s_axi_rdata<=drain_cycles;
     12'h040:s_axi_rdata<=matrix_writes;
     12'h044:s_axi_rdata<=matrix_reads;
     12'h048:s_axi_rdata<={17'd0,range_outputs};
     12'h04c:s_axi_rdata<={17'd0,doppler_inputs};
     12'h050:s_axi_rdata<={17'd0,doppler_outputs};
     12'h054:s_axi_rdata<={30'd0,phase};
     12'h058:s_axi_rdata<=overwrite_errors;
     12'h05c:s_axi_rdata<=io_overlap_cycles;
     12'h060:s_axi_rdata<=16384;
     12'h06c:s_axi_rdata<=7;
     12'h070:s_axi_rdata<=stage_busy_cycles;
     12'h074:s_axi_rdata<=multi_stage_cycles;
     12'h078:s_axi_rdata<=vector_overlap_cycles;
     default:s_axi_rresp<=2;
    endcase
   end
  end
 end
 always @(posedge aclk) begin
  if(!aresetn || clear_command) begin
   phase<=aresetn && wdata==1 ? RANGE : IDLE;
   running<=aresetn && wdata==1;completed<=0;failed<=0;soft_reset<=aresetn;
   input_count<=0;output_count<=0;range_outputs<=0;doppler_inputs<=0;doppler_outputs<=0;read_requests<=0;rd_valid<=0;
   cycles<=0;input_stalls<=0;output_stalls<=0;range_cycles<=0;doppler_cycles<=0;drain_cycles<=0;
   matrix_reads<=0;matrix_writes<=0;overwrite_errors<=0;io_overlap_cycles<=0;
   stage_busy_cycles<=0;multi_stage_cycles<=0;vector_overlap_cycles<=0;
   for(k=0;k<7;k=k+1) begin stage_issue_events[k]<=0;stage_retire_events[k]<=0;end
  end else begin
   soft_reset<=0;
   if(running) begin
    cycles<=cycles+1;
    if(phase==RANGE) range_cycles<=range_cycles+1;
    if(phase==DOPPLER) doppler_cycles<=doppler_cycles+1;
    if(phase==DRAIN) drain_cycles<=drain_cycles+1;
    if(s_axis_tready && !s_axis_tvalid) input_stalls<=input_stalls+1;
    if(m_axis_tvalid && !m_axis_tready) output_stalls<=output_stalls+1;
    if(s_axis_tready && s_axis_tvalid && m_axis_tvalid && m_axis_tready) io_overlap_cycles<=io_overlap_cycles+1;
    if(pipeline_error) failed<=1;
    // Count premature results blocked by the overwrite guard, independently
    // of write acceptance. The matrix write itself remains hard-gated safe.
    if(phase==DOPPLER && pipeline_valid && !overwrite_safe) begin
     failed<=1;overwrite_errors<=overwrite_errors+1;
    end
    stage_busy_cycles<=stage_busy_cycles+compute_stages;
    if(compute_stages>=2) multi_stage_cycles<=multi_stage_cycles+1;
    if(inflight_vectors>=2) vector_overlap_cycles<=vector_overlap_cycles+1;
    for(k=0;k<7;k=k+1) begin
     if(stage_issue[k]) stage_issue_events[k]<=stage_issue_events[k]+1;
     if(stage_retire[k]) stage_retire_events[k]<=stage_retire_events[k]+1;
    end
    if(rd_valid && read_consume) rd_valid<=0;
    if(ram_read) begin rd_valid<=1;read_requests<=read_requests+1;matrix_reads<=matrix_reads+1;end
    if(ram_write) matrix_writes<=matrix_writes+1;
    if(pipeline_send && phase==RANGE) begin
     input_count<=input_count+1;
     if(s_axis_tkeep!=15 || s_axis_tlast!=(input_count==16383)) failed<=1;
    end
    if(pipeline_send && phase==DOPPLER) doppler_inputs<=doppler_inputs+1;
    if(pipeline_receive && phase==RANGE) begin
     range_outputs<=range_outputs+1;
     if(pipeline_last!=(range_outputs[6:0]==127)) failed<=1;
     if(range_outputs==16383) begin phase<=DOPPLER;read_requests<=0;rd_valid<=0;end
    end
    if(pipeline_receive && phase==DOPPLER) begin
     doppler_outputs<=doppler_outputs+1;
     if(pipeline_last!=(doppler_outputs[6:0]==127)) failed<=1;
     if(doppler_outputs==16383) begin phase<=DRAIN;read_requests<=0;rd_valid<=0;end
    end
    if(m_axis_tvalid && m_axis_tready) begin
     output_count<=output_count+1;
     if(output_count==16383) begin phase<=IDLE;running<=0;completed<=1;rd_valid<=0;end
    end
   end
  end
 end
endmodule
