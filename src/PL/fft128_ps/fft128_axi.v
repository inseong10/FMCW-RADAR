// Functional PS/PL bring-up frontend. One outstanding AXI-Lite transaction.
// No frame-sized storage: PS supplies one 128-word FFT at a time.
module fft128_axi (
 (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 aclk CLK",
    X_INTERFACE_PARAMETER="ASSOCIATED_BUSIF S_AXI, ASSOCIATED_RESET aresetn" *)
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
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI RREADY" *) input wire s_axi_rready
);
 reg [31:0] input_mem [0:127];
 reg [31:0] output_mem [0:127];
 reg [127:0] written;
 reg aw_pending, w_pending;
 reg [11:0] awaddr;
 reg [31:0] wdata;
 reg [3:0] wstrb;
 reg running, completed, failed, start_pulse, soft_reset;
 reg [7:0] input_count, output_count;
 reg [31:0] cycles;
 wire core_busy, core_done, core_error, in_ready, out_valid, out_last;
 wire [31:0] out_data;
 assign s_axi_awready = !aw_pending && !s_axi_bvalid;
 assign s_axi_wready = !w_pending && !s_axi_bvalid;
 assign s_axi_arready = !s_axi_rvalid;

 fft128_stream core (
  .clk(aclk), .rst(!aresetn || soft_reset), .start(start_pulse),
  .busy(core_busy), .done(core_done), .input_error(core_error),
  .s_axis_tdata(input_mem[input_count[6:0]]),
  .s_axis_tvalid(running && input_count < 128), .s_axis_tready(in_ready),
  .s_axis_tlast(input_count == 127),
  .m_axis_tdata(out_data), .m_axis_tvalid(out_valid),
  .m_axis_tready(running), .m_axis_tlast(out_last)
 );

 always @(posedge aclk) begin
  if (!aresetn) begin
   aw_pending<=0; w_pending<=0; awaddr<=0; wdata<=0; wstrb<=0;
   s_axi_bvalid<=0; s_axi_bresp<=0;
   s_axi_rvalid<=0; s_axi_rresp<=0; s_axi_rdata<=0;
   running<=0; completed<=0; failed<=0; written<=0;
   start_pulse<=0; soft_reset<=0; input_count<=0; output_count<=0; cycles<=0;
  end else begin
   start_pulse<=0; soft_reset<=0;
   if (s_axi_bvalid && s_axi_bready) s_axi_bvalid<=0;
   if (s_axi_rvalid && s_axi_rready) s_axi_rvalid<=0;
   if (s_axi_awvalid && s_axi_awready) begin aw_pending<=1; awaddr<=s_axi_awaddr; end
   if (s_axi_wvalid && s_axi_wready) begin w_pending<=1; wdata<=s_axi_wdata; wstrb<=s_axi_wstrb; end

   if (running) begin
    cycles<=cycles+1;
    if (input_count<128 && in_ready) input_count<=input_count+1;
    if (core_error) failed<=1;
    if (out_valid) begin
     output_mem[output_count[6:0]]<=out_data;
     output_count<=output_count+1;
     if (out_last != (output_count==127)) failed<=1;
     if (output_count==127) begin running<=0; completed<=1; end
    end
   end

   // Address and data are captured independently, in either order.
   if (aw_pending && w_pending && !s_axi_bvalid) begin
    aw_pending<=0; w_pending<=0; s_axi_bvalid<=1; s_axi_bresp<=0;
    if (awaddr[1:0]!=0) s_axi_bresp<=2;
    else if (wstrb==0) begin end // legal no-op; no register side effects
    else if (wstrb!=4'hf) s_axi_bresp<=2; // this peripheral requires word writes
    else if (awaddr==12'h004 && wdata==2) begin
     soft_reset<=1; running<=0; completed<=0; failed<=0; written<=0;
     input_count<=0; output_count<=0; cycles<=0;
    end else if (awaddr==12'h004 && wdata==1 && !running && &written) begin
     start_pulse<=1; running<=1; completed<=0; failed<=0;
     input_count<=0; output_count<=0; cycles<=0;
    end else if (awaddr>=12'h100 && awaddr<12'h300 && !running) begin
     input_mem[awaddr[9:2]-8'd64]<=wdata;
     written[awaddr[9:2]-8'd64]<=1;
    end else s_axi_bresp<=2;
   end

   if (s_axi_arvalid && s_axi_arready) begin
    s_axi_rvalid<=1; s_axi_rresp<=0; s_axi_rdata<=0;
    if (s_axi_araddr[1:0]!=0) s_axi_rresp<=2;
    else case (s_axi_araddr)
     12'h000: s_axi_rdata<=32'h46543128;
     12'h004: s_axi_rdata<=0;
     12'h008: s_axi_rdata<={29'd0,failed,completed,running};
     12'h00c: s_axi_rdata<=128;
     12'h010: s_axi_rdata<=cycles;
     default: begin
      if (s_axi_araddr>=12'h800 && s_axi_araddr<12'ha00 && completed && !running)
       s_axi_rdata<=output_mem[s_axi_araddr[8:2]];
      else s_axi_rresp<=2;
     end
    endcase
   end
  end
 end
endmodule
