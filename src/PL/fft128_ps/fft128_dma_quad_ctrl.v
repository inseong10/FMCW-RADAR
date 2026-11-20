// E13-4core: four unchanged FFTs, group barrier and shared ordered AXIS.
// No external buffers, next-group prefetch or output cadence changes.
module fft128_dma_quad_ctrl (
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
 reg [3:0] start_pulse, work_pending;
 reg [14:0] input_count, output_count;
 reg [7:0] fft_count, completed_ffts;
 reg [5:0] group_index;
 wire [14:0] sample_count={fft_count,7'b0};
 reg [31:0] cycles, input_stalls, output_stalls;
 reg [31:0] core0_cycles, core1_cycles, core2_cycles, core3_cycles;
 reg [31:0] any_busy_cycles, multi_busy_cycles, all_busy_cycles;
 reg [31:0] multi_work_cycles, all_work_cycles, arbitration_stalls;
 wire [3:0] core_busy, core_done, core_error, in_ready, out_valid, out_last;
 wire [31:0] out_data [0:3];
 // [14:9] is the four-vector group; [8:7] selects a core, [6:0] a sample.
 wire [1:0] input_lane=input_count[8:7], output_lane=output_count[8:7];
 wire input_group=(input_count[14:9]==group_index) && (input_count<sample_count);
 wire input_fire=s_axis_tvalid && s_axis_tready;
 wire output_fire=m_axis_tvalid && m_axis_tready;
 wire [3:0] work_active=work_pending & ~out_valid;
 wire [2:0] busy_lanes={2'b0,core_busy[0]}+{2'b0,core_busy[1]}+{2'b0,core_busy[2]}+{2'b0,core_busy[3]};
 wire [2:0] work_lanes={2'b0,work_active[0]}+{2'b0,work_active[1]}+{2'b0,work_active[2]}+{2'b0,work_active[3]};
 assign s_axi_awready=!aw_pending && !s_axi_bvalid;
 assign s_axi_wready=!w_pending && !s_axi_bvalid;
 assign s_axi_arready=!s_axi_rvalid;
 assign s_axis_tready=running && input_group && in_ready[input_lane];
 assign m_axis_tvalid=running && out_valid[output_lane];
 assign m_axis_tdata=out_data[output_lane];
 assign m_axis_tlast=m_axis_tvalid && (output_count==sample_count-1'b1);
 assign m_axis_tkeep=4'hf;
 fft128_pipeline core0(
  .clk(aclk),.rst(!aresetn || soft_reset),.start(start_pulse[0]),
  .busy(core_busy[0]),.done(core_done[0]),.input_error(core_error[0]),
  .s_axis_tdata(s_axis_tdata),.s_axis_tvalid(running && input_group && input_lane==2'd0 && s_axis_tvalid),
  .s_axis_tready(in_ready[0]),.s_axis_tlast(input_count[6:0]==127),
  .m_axis_tdata(out_data[0]),.m_axis_tvalid(out_valid[0]),
  .m_axis_tready(running && output_lane==2'd0 && m_axis_tready),.m_axis_tlast(out_last[0]));
 fft128_pipeline core1(
  .clk(aclk),.rst(!aresetn || soft_reset),.start(start_pulse[1]),
  .busy(core_busy[1]),.done(core_done[1]),.input_error(core_error[1]),
  .s_axis_tdata(s_axis_tdata),.s_axis_tvalid(running && input_group && input_lane==2'd1 && s_axis_tvalid),
  .s_axis_tready(in_ready[1]),.s_axis_tlast(input_count[6:0]==127),
  .m_axis_tdata(out_data[1]),.m_axis_tvalid(out_valid[1]),
  .m_axis_tready(running && output_lane==2'd1 && m_axis_tready),.m_axis_tlast(out_last[1]));
 fft128_pipeline core2(
  .clk(aclk),.rst(!aresetn || soft_reset),.start(start_pulse[2]),
  .busy(core_busy[2]),.done(core_done[2]),.input_error(core_error[2]),
  .s_axis_tdata(s_axis_tdata),.s_axis_tvalid(running && input_group && input_lane==2'd2 && s_axis_tvalid),
  .s_axis_tready(in_ready[2]),.s_axis_tlast(input_count[6:0]==127),
  .m_axis_tdata(out_data[2]),.m_axis_tvalid(out_valid[2]),
  .m_axis_tready(running && output_lane==2'd2 && m_axis_tready),.m_axis_tlast(out_last[2]));
 fft128_pipeline core3(
  .clk(aclk),.rst(!aresetn || soft_reset),.start(start_pulse[3]),
  .busy(core_busy[3]),.done(core_done[3]),.input_error(core_error[3]),
  .s_axis_tdata(s_axis_tdata),.s_axis_tvalid(running && input_group && input_lane==2'd3 && s_axis_tvalid),
  .s_axis_tready(in_ready[3]),.s_axis_tlast(input_count[6:0]==127),
  .m_axis_tdata(out_data[3]),.m_axis_tvalid(out_valid[3]),
  .m_axis_tready(running && output_lane==2'd3 && m_axis_tready),.m_axis_tlast(out_last[3]));
 always @(posedge aclk) begin
  if(!aresetn) begin
   aw_pending<=0;w_pending<=0;awaddr<=0;wdata<=0;wstrb<=0;
   s_axi_bvalid<=0;s_axi_bresp<=0;s_axi_rvalid<=0;s_axi_rresp<=0;s_axi_rdata<=0;
   running<=0;completed<=0;failed<=0;start_pulse<=0;soft_reset<=0;
   fft_count<=128;completed_ffts<=0;group_index<=0;work_pending<=0;
   input_count<=0;output_count<=0;cycles<=0;input_stalls<=0;output_stalls<=0;
   core0_cycles<=0;core1_cycles<=0;core2_cycles<=0;core3_cycles<=0;
   any_busy_cycles<=0;multi_busy_cycles<=0;all_busy_cycles<=0;
   multi_work_cycles<=0;all_work_cycles<=0;arbitration_stalls<=0;
  end else begin
   start_pulse<=0;soft_reset<=0;
   if(s_axi_bvalid && s_axi_bready) s_axi_bvalid<=0;
   if(s_axi_rvalid && s_axi_rready) s_axi_rvalid<=0;
   if(s_axi_awvalid && s_axi_awready) begin aw_pending<=1;awaddr<=s_axi_awaddr;end
   if(s_axi_wvalid && s_axi_wready) begin w_pending<=1;wdata<=s_axi_wdata;wstrb<=s_axi_wstrb;end
   if(running) begin
    cycles<=cycles+1;
    if(input_group && in_ready[input_lane] && !s_axis_tvalid) input_stalls<=input_stalls+1;
    if(m_axis_tvalid && !m_axis_tready) output_stalls<=output_stalls+1;
    if(core_busy[0]) core0_cycles<=core0_cycles+1;
    if(core_busy[1]) core1_cycles<=core1_cycles+1;
    if(core_busy[2]) core2_cycles<=core2_cycles+1;
    if(core_busy[3]) core3_cycles<=core3_cycles+1;
    if(busy_lanes!=0) any_busy_cycles<=any_busy_cycles+1;
    if(busy_lanes>=2) multi_busy_cycles<=multi_busy_cycles+1;
    if(&core_busy) all_busy_cycles<=all_busy_cycles+1;
    // Work windows include CALC and first output-read latency; not pure CALC.
    if(work_lanes>=2) multi_work_cycles<=multi_work_cycles+1;
    if(&work_active) all_work_cycles<=all_work_cycles+1;
    // Count cycles with ANY non-selected valid output, not a sum across lanes.
    if(|(out_valid & ~(4'b0001 << output_lane))) arbitration_stalls<=arbitration_stalls+1;
    if(out_valid[0]) work_pending[0]<=0;
    if(out_valid[1]) work_pending[1]<=0;
    if(out_valid[2]) work_pending[2]<=0;
    if(out_valid[3]) work_pending[3]<=0;
    if(|core_error) failed<=1;
    if(input_fire) begin
     input_count<=input_count+1;
     if(input_count[6:0]==127) work_pending[input_lane]<=1;
     if(s_axis_tkeep!=4'hf || s_axis_tlast!=(input_count==sample_count-1'b1)) failed<=1;
    end
    if(output_fire) begin
     output_count<=output_count+1;
     if(out_last[output_lane]!=(output_count[6:0]==127)) failed<=1;
     if(output_count[6:0]==127) begin
      completed_ffts<=completed_ffts+1'b1;
      if(output_count==sample_count-1'b1) begin running<=0;completed<=1;end
      else if(output_lane==3) begin
       // All four previous results accepted before any next-group core starts.
       group_index<=group_index+1'b1;
       start_pulse[0]<=1;
       start_pulse[1]<=(fft_count>completed_ffts+2);
       start_pulse[2]<=(fft_count>completed_ffts+3);
       start_pulse[3]<=(fft_count>completed_ffts+4);
      end
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
     group_index<=0;work_pending<=0;start_pulse<=0;
     core0_cycles<=0;core1_cycles<=0;core2_cycles<=0;core3_cycles<=0;
     any_busy_cycles<=0;multi_busy_cycles<=0;all_busy_cycles<=0;
     multi_work_cycles<=0;all_work_cycles<=0;arbitration_stalls<=0;
    end else if(awaddr==4 && wdata==1 && !running) begin
     start_pulse[0]<=1;start_pulse[1]<=(fft_count>1);
     start_pulse[2]<=(fft_count>2);start_pulse[3]<=(fft_count>3);
     running<=1;completed<=0;failed<=0;completed_ffts<=0;
     input_count<=0;output_count<=0;cycles<=0;input_stalls<=0;output_stalls<=0;
     group_index<=0;work_pending<=0;
     core0_cycles<=0;core1_cycles<=0;core2_cycles<=0;core3_cycles<=0;
     any_busy_cycles<=0;multi_busy_cycles<=0;all_busy_cycles<=0;
     multi_work_cycles<=0;all_work_cycles<=0;arbitration_stalls<=0;
    end else if(awaddr==12'h028 && !running && wdata>=1 && wdata<=128) begin
     fft_count<=wdata[7:0];
    end else s_axi_bresp<=2;
   end
   if(s_axi_arvalid && s_axi_arready) begin
    s_axi_rvalid<=1;s_axi_rresp<=0;s_axi_rdata<=0;
    if(s_axi_araddr[1:0]!=0) s_axi_rresp<=2;
    else case(s_axi_araddr)
     12'h000:s_axi_rdata<=32'h46545084;
     12'h004:s_axi_rdata<=0;
     12'h008:s_axi_rdata<={29'd0,failed,completed,running};
     12'h00c:s_axi_rdata<=128;
     12'h010:s_axi_rdata<=cycles;
     12'h014:s_axi_rdata<=4;
     12'h018:s_axi_rdata<={17'd0,input_count};
     12'h01c:s_axi_rdata<={17'd0,output_count};
     12'h020:s_axi_rdata<=input_stalls;
     12'h024:s_axi_rdata<=output_stalls;
     12'h028:s_axi_rdata<={24'd0,fft_count};
     12'h02c:s_axi_rdata<={24'd0,completed_ffts};
     12'h030:s_axi_rdata<=4;
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
     default:s_axi_rresp<=2;
    endcase
   end
  end
 end
endmodule
