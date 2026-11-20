// E13-stream: one seven-stage frame-streaming DIT pipeline, shared DMA.
// Fixed Q15 arithmetic and 50MHz. Dedicated stages overlap different FFTs.
module fft128_dma_stream_ctrl (
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
 reg aw_pending, w_pending;
 reg [11:0] awaddr;
 reg [31:0] wdata;
 reg [3:0] wstrb;
 reg running, completed, failed, soft_reset;

 reg [14:0] input_count, output_count;
 reg [7:0] fft_count, completed_ffts;
 reg [31:0] overlap_io, overlap_input_work, overlap_output_work, overlap_three;
 wire [14:0] sample_count={fft_count,7'b0};
 reg [31:0] cycles, input_stalls, output_stalls;
 reg [31:0] core0_cycles, core1_cycles, core2_cycles, core3_cycles;
 reg [31:0] any_busy_cycles, multi_busy_cycles, all_busy_cycles;
 reg [31:0] multi_work_cycles, all_work_cycles, arbitration_stalls;
 wire [3:0] core_busy, core_done, core_error, in_ready, out_valid, out_last;
 wire [31:0] out_data [0:3];
 wire input_group=input_count<sample_count;
 wire input_fire=s_axis_tvalid && s_axis_tready;
 wire output_fire=m_axis_tvalid && m_axis_tready;
 wire [3:0] work_active;
 wire [6:0] stage_issue,stage_retire,stage_calc;
 wire [7:0] inflight_vectors;
 reg [31:0] stage_issue_events[0:6],stage_retire_events[0:6];
 reg [31:0] stage_busy_cycles,multi_stage_cycles,vector_overlap_cycles;
 wire [2:0] compute_stages={2'b0,stage_calc[0]}+{2'b0,stage_calc[1]}+{2'b0,stage_calc[2]}+
  {2'b0,stage_calc[3]}+{2'b0,stage_calc[4]}+{2'b0,stage_calc[5]}+{2'b0,stage_calc[6]};
 wire [2:0] busy_lanes={2'b0,core_busy[0]};
 wire [2:0] work_lanes={2'b0,work_active[0]};
 integer k;
 assign s_axi_awready=!aw_pending && !s_axi_bvalid;
 assign s_axi_wready=!w_pending && !s_axi_bvalid;
 assign s_axi_arready=!s_axi_rvalid;
 assign s_axis_tready=running && input_group && in_ready[0];
 assign m_axis_tvalid=running && out_valid[0];
 assign m_axis_tdata=out_data[0];
 assign m_axis_tlast=m_axis_tvalid && (output_count==sample_count-1'b1);
 assign m_axis_tkeep=4'hf;
 assign core_busy[3:1]=0;assign core_error[3:1]=0;
 assign core_done=0;assign in_ready[3:1]=0;assign out_valid[3:1]=0;assign out_last[3:1]=0;
 assign out_data[1]=0;assign out_data[2]=0;assign out_data[3]=0;
 assign work_active={3'b0,|stage_calc};
 fft128_streaming pipeline(.clk(aclk),.rst(!aresetn || soft_reset),
  .s_data(s_axis_tdata),.s_valid(running && input_group && s_axis_tvalid),.s_ready(in_ready[0]),
  .s_last(input_count[6:0]==127),
  .m_data(out_data[0]),.m_valid(out_valid[0]),.m_ready(running && m_axis_tready),.m_last(out_last[0]),
  .busy(core_busy[0]),.input_error(core_error[0]),
  .stage_issue(stage_issue),.stage_retire(stage_retire),.stage_calc(stage_calc),.inflight_vectors(inflight_vectors));
 always @(posedge aclk) begin
  if(!aresetn) begin
   aw_pending<=0;w_pending<=0;awaddr<=0;wdata<=0;wstrb<=0;
   s_axi_bvalid<=0;s_axi_bresp<=0;s_axi_rvalid<=0;s_axi_rresp<=0;s_axi_rdata<=0;
   running<=0;completed<=0;failed<=0;soft_reset<=0;
   fft_count<=128;completed_ffts<=0;overlap_io<=0;overlap_input_work<=0;overlap_output_work<=0;overlap_three<=0;
   input_count<=0;output_count<=0;cycles<=0;input_stalls<=0;output_stalls<=0;
   core0_cycles<=0;core1_cycles<=0;core2_cycles<=0;core3_cycles<=0;
   any_busy_cycles<=0;multi_busy_cycles<=0;all_busy_cycles<=0;
   multi_work_cycles<=0;all_work_cycles<=0;arbitration_stalls<=0;stage_busy_cycles<=0;multi_stage_cycles<=0;vector_overlap_cycles<=0;
     for(k=0;k<7;k=k+1) begin stage_issue_events[k]<=0;stage_retire_events[k]<=0;end
  end else begin
   soft_reset<=0;
   if(s_axi_bvalid && s_axi_bready) s_axi_bvalid<=0;
   if(s_axi_rvalid && s_axi_rready) s_axi_rvalid<=0;
   if(s_axi_awvalid && s_axi_awready) begin aw_pending<=1;awaddr<=s_axi_awaddr;end
   if(s_axi_wvalid && s_axi_wready) begin w_pending<=1;wdata<=s_axi_wdata;wstrb<=s_axi_wstrb;end
   if(running) begin
    cycles<=cycles+1;
    stage_busy_cycles<=stage_busy_cycles+compute_stages;
    if(compute_stages>=2) multi_stage_cycles<=multi_stage_cycles+1;
    if(inflight_vectors>=2) vector_overlap_cycles<=vector_overlap_cycles+1;
    for(k=0;k<7;k=k+1) begin
     if(stage_issue[k]) stage_issue_events[k]<=stage_issue_events[k]+1;
     if(stage_retire[k]) stage_retire_events[k]<=stage_retire_events[k]+1;
    end
    if(input_group && in_ready[0] && !s_axis_tvalid) input_stalls<=input_stalls+1;
    if(m_axis_tvalid && !m_axis_tready) output_stalls<=output_stalls+1;
    if(core_busy[0]) core0_cycles<=core0_cycles+1;
    if(core_busy[1]) core1_cycles<=core1_cycles+1;
    if(core_busy[2]) core2_cycles<=core2_cycles+1;
    if(core_busy[3]) core3_cycles<=core3_cycles+1;
    if(busy_lanes!=0) any_busy_cycles<=any_busy_cycles+1;
    if(busy_lanes>=2) multi_busy_cycles<=multi_busy_cycles+1;
    if(&core_busy) all_busy_cycles<=all_busy_cycles+1;
    // Legacy multi-lane registers stay zero; work_active[0] is actual stage CALC.
    if(work_lanes>=2) multi_work_cycles<=multi_work_cycles+1;
    if(&work_active) all_work_cycles<=all_work_cycles+1;
    // No four-lane output arbitration in this architecture.
    if(input_fire && output_fire) overlap_io<=overlap_io+1;
    if(input_fire && |work_active) overlap_input_work<=overlap_input_work+1;
    if(output_fire && |work_active) overlap_output_work<=overlap_output_work+1;
    if(input_fire && output_fire && |work_active) overlap_three<=overlap_three+1;
    if(|core_error) failed<=1;
    if(input_fire) begin
     input_count<=input_count+1;
     if(s_axis_tkeep!=4'hf || s_axis_tlast!=(input_count==sample_count-1'b1)) failed<=1;
    end
    if(output_fire) begin
     output_count<=output_count+1;
     if(out_last[0]!=(output_count[6:0]==127)) failed<=1;
     if(output_count[6:0]==127) begin
      completed_ffts<=completed_ffts+1'b1;
      if(output_count==sample_count-1'b1) begin running<=0;completed<=1;end

     end
    end
   end
   if(aw_pending && w_pending && !s_axi_bvalid) begin
    aw_pending<=0;w_pending<=0;s_axi_bvalid<=1;s_axi_bresp<=0;
    if(awaddr[1:0]!=0) s_axi_bresp<=2;
    else if(wstrb==0) begin end
    else if(wstrb!=4'hf) s_axi_bresp<=2;
    else if(awaddr==4 && wdata==2) begin
     soft_reset<=1;running<=0;completed<=0;failed<=0;completed_ffts<=0;
     input_count<=0;output_count<=0;cycles<=0;input_stalls<=0;output_stalls<=0;
     overlap_io<=0;overlap_input_work<=0;overlap_output_work<=0;overlap_three<=0;
     core0_cycles<=0;core1_cycles<=0;core2_cycles<=0;core3_cycles<=0;
     any_busy_cycles<=0;multi_busy_cycles<=0;all_busy_cycles<=0;
     multi_work_cycles<=0;all_work_cycles<=0;arbitration_stalls<=0;stage_busy_cycles<=0;multi_stage_cycles<=0;vector_overlap_cycles<=0;
     for(k=0;k<7;k=k+1) begin stage_issue_events[k]<=0;stage_retire_events[k]<=0;end
    end else if(awaddr==4 && wdata==1 && !running) begin
     running<=1;completed<=0;failed<=0;completed_ffts<=0;
     input_count<=0;output_count<=0;cycles<=0;input_stalls<=0;output_stalls<=0;
     overlap_io<=0;overlap_input_work<=0;overlap_output_work<=0;overlap_three<=0;
     core0_cycles<=0;core1_cycles<=0;core2_cycles<=0;core3_cycles<=0;
     any_busy_cycles<=0;multi_busy_cycles<=0;all_busy_cycles<=0;
     multi_work_cycles<=0;all_work_cycles<=0;arbitration_stalls<=0;stage_busy_cycles<=0;multi_stage_cycles<=0;vector_overlap_cycles<=0;
     for(k=0;k<7;k=k+1) begin stage_issue_events[k]<=0;stage_retire_events[k]<=0;end
    end else if(awaddr==12'h028 && !running && wdata>=1 && wdata<=128) begin
     fft_count<=wdata[7:0];
    end else s_axi_bresp<=2;
   end
   if(s_axi_arvalid && s_axi_arready) begin
    s_axi_rvalid<=1;s_axi_rresp<=0;s_axi_rdata<=0;
    if(s_axi_araddr[1:0]!=0) s_axi_rresp<=2;
    else case(s_axi_araddr)
     12'h000:s_axi_rdata<=32'h46545087;
     12'h004:s_axi_rdata<=0;
     12'h008:s_axi_rdata<={29'd0,failed,completed,running};
     12'h00c:s_axi_rdata<=128;
     12'h010:s_axi_rdata<=cycles;
     12'h014:s_axi_rdata<=7;
     12'h018:s_axi_rdata<={17'd0,input_count};
     12'h01c:s_axi_rdata<={17'd0,output_count};
     12'h020:s_axi_rdata<=input_stalls;
     12'h024:s_axi_rdata<=output_stalls;
     12'h028:s_axi_rdata<={24'd0,fft_count};
     12'h02c:s_axi_rdata<={24'd0,completed_ffts};
     12'h030:s_axi_rdata<=1;
     12'h034:s_axi_rdata<=core0_cycles;
     12'h038:s_axi_rdata<=core1_cycles;
     12'h03c:s_axi_rdata<=core2_cycles;
     12'h040:s_axi_rdata<=core3_cycles;
     12'h044:s_axi_rdata<=any_busy_cycles;
     12'h048:s_axi_rdata<=multi_busy_cycles;
     12'h04c:s_axi_rdata<=all_busy_cycles;
     12'h050:s_axi_rdata<=multi_work_cycles;
     12'h054:s_axi_rdata<=all_work_cycles;
     12'h058:s_axi_rdata<=arbitration_stalls;
     12'h05c:s_axi_rdata<=overlap_io;
     12'h060:s_axi_rdata<=overlap_input_work;
     12'h064:s_axi_rdata<=overlap_output_work;
     12'h068:s_axi_rdata<=overlap_three;
     12'h06c:s_axi_rdata<=7;
     12'h070:s_axi_rdata<=stage_busy_cycles;
     12'h074:s_axi_rdata<=multi_stage_cycles;
     12'h078:s_axi_rdata<=vector_overlap_cycles;
     12'h080:s_axi_rdata<=stage_issue_events[0];
     12'h0a0:s_axi_rdata<=stage_retire_events[0];
     12'h084:s_axi_rdata<=stage_issue_events[1];
     12'h0a4:s_axi_rdata<=stage_retire_events[1];
     12'h088:s_axi_rdata<=stage_issue_events[2];
     12'h0a8:s_axi_rdata<=stage_retire_events[2];
     12'h08c:s_axi_rdata<=stage_issue_events[3];
     12'h0ac:s_axi_rdata<=stage_retire_events[3];
     12'h090:s_axi_rdata<=stage_issue_events[4];
     12'h0b0:s_axi_rdata<=stage_retire_events[4];
     12'h094:s_axi_rdata<=stage_issue_events[5];
     12'h0b4:s_axi_rdata<=stage_retire_events[5];
     12'h098:s_axi_rdata<=stage_issue_events[6];
     12'h0b8:s_axi_rdata<=stage_retire_events[6];

     default:s_axi_rresp<=2;
    endcase
   end
  end
 end
endmodule
