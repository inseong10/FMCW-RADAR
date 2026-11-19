// E11b: one AXIS packet holds 1..128 sequential FFTs; no transfer/compute overlap.
// The FFT arithmetic/schedule is the unchanged fft128_pipeline core.
module fft128_dma_batch_ctrl (
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
 reg running, completed, failed, start_pulse, soft_reset;
 reg [14:0] input_count, output_count;
 reg [7:0] fft_count, completed_ffts;
 wire [14:0] sample_count={fft_count,7'b0};
 reg [31:0] cycles, input_stalls, output_stalls;
 wire core_busy, core_done, core_error, in_ready, out_valid, out_last;
 wire [31:0] out_data;
 wire input_fire=s_axis_tvalid && s_axis_tready;
 wire output_fire=m_axis_tvalid && m_axis_tready;
 assign s_axi_awready=!aw_pending && !s_axi_bvalid;
 assign s_axi_wready=!w_pending && !s_axi_bvalid;
 assign s_axi_arready=!s_axi_rvalid;
 assign s_axis_tready=running && in_ready;
 assign m_axis_tvalid=running && out_valid;
 assign m_axis_tdata=out_data;
 assign m_axis_tlast=out_valid && (output_count==sample_count-1'b1);
 assign m_axis_tkeep=4'hf;
 fft128_pipeline core(
  .clk(aclk),.rst(!aresetn || soft_reset),.start(start_pulse),
  .busy(core_busy),.done(core_done),.input_error(core_error),
  .s_axis_tdata(s_axis_tdata),.s_axis_tvalid(running && s_axis_tvalid),
  .s_axis_tready(in_ready),.s_axis_tlast(input_count[6:0]==127),
  .m_axis_tdata(out_data),.m_axis_tvalid(out_valid),
  .m_axis_tready(running && m_axis_tready),.m_axis_tlast(out_last));
 always @(posedge aclk) begin
  if(!aresetn) begin
   aw_pending<=0;w_pending<=0;awaddr<=0;wdata<=0;wstrb<=0;
   s_axi_bvalid<=0;s_axi_bresp<=0;s_axi_rvalid<=0;s_axi_rresp<=0;s_axi_rdata<=0;
   running<=0;completed<=0;failed<=0;start_pulse<=0;soft_reset<=0;
   fft_count<=128;completed_ffts<=0;
   input_count<=0;output_count<=0;cycles<=0;input_stalls<=0;output_stalls<=0;
  end else begin
   start_pulse<=0;soft_reset<=0;
   if(s_axi_bvalid && s_axi_bready) s_axi_bvalid<=0;
   if(s_axi_rvalid && s_axi_rready) s_axi_rvalid<=0;
   if(s_axi_awvalid && s_axi_awready) begin aw_pending<=1;awaddr<=s_axi_awaddr;end
   if(s_axi_wvalid && s_axi_wready) begin w_pending<=1;wdata<=s_axi_wdata;wstrb<=s_axi_wstrb;end
   if(running) begin
    cycles<=cycles+1;
    if(in_ready && !s_axis_tvalid) input_stalls<=input_stalls+1;
    if(out_valid && !m_axis_tready) output_stalls<=output_stalls+1;
    if(core_error) failed<=1;
    if(input_fire) begin
     input_count<=input_count+1;
     if(s_axis_tkeep!=4'hf || s_axis_tlast!=(input_count==sample_count-1'b1)) failed<=1;
    end
    if(output_fire) begin
     output_count<=output_count+1;
     if(out_last!=(output_count[6:0]==127)) failed<=1;
     if(output_count[6:0]==127) begin
      completed_ffts<=completed_ffts+1'b1;
      if(output_count==sample_count-1'b1) begin running<=0;completed<=1;end
      // The core enters IDLE on this edge; the pulse starts the next FFT
      // on the following edge. No next-vector load overlaps calculation/output.
      else start_pulse<=1;
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
    end else if(awaddr==4 && wdata==1 && !running) begin
     start_pulse<=1;running<=1;completed<=0;failed<=0;completed_ffts<=0;
     input_count<=0;output_count<=0;cycles<=0;input_stalls<=0;output_stalls<=0;
    end else if(awaddr==12'h028 && !running && wdata>=1 && wdata<=128) begin
     fft_count<=wdata[7:0];
    end else s_axi_bresp<=2;
   end
   if(s_axi_arvalid && s_axi_arready) begin
    s_axi_rvalid<=1;s_axi_rresp<=0;s_axi_rdata<=0;
    if(s_axi_araddr[1:0]!=0) s_axi_rresp<=2;
    else case(s_axi_araddr)
     12'h000:s_axi_rdata<=32'h46544280; // incompatible with old sample-window frontend
     12'h004:s_axi_rdata<=0;
     12'h008:s_axi_rdata<={29'd0,failed,completed,running};
     12'h00c:s_axi_rdata<=128;
     12'h010:s_axi_rdata<=cycles; // active interval INCLUDING AXIS starvation/backpressure
     12'h014:s_axi_rdata<=2; // E11b register ABI v2
     12'h018:s_axi_rdata<={17'd0,input_count};
     12'h01c:s_axi_rdata<={17'd0,output_count};
     12'h020:s_axi_rdata<=input_stalls;
     12'h024:s_axi_rdata<=output_stalls;
     12'h028:s_axi_rdata<={24'd0,fft_count};
     12'h02c:s_axi_rdata<={24'd0,completed_ffts};
     default:s_axi_rresp<=2;
    endcase
   end
  end
 end
endmodule
