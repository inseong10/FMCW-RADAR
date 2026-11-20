// E13-bf2: two bit-identical butterflies per cycle, 32 pairs per DIT stage.
// Each ping-pong store is split by address bit0 into even/odd dual-port RAMs.
// Stage0 routes A0/A1 to even and B0/B1 to odd; later stages route BF0 to
// even and BF1 to odd. Thus each of four banks has at most two accesses.
module fft128_bf2 (
 input wire clk, rst, start,
 output wire busy, output reg done, input_error,
 input wire [31:0] s_axis_tdata,
 input wire s_axis_tvalid, output wire s_axis_tready, input wire s_axis_tlast,
 output wire [31:0] m_axis_tdata,
 output wire m_axis_tvalid, input wire m_axis_tready, output wire m_axis_tlast,
 output wire dual_issue, dual_retire, calc_active
);
 localparam IDLE=0, LOAD=1, CALC=2, OUT_REQ=3, OUT_SEND=4;
 reg [2:0] state;
 reg [6:0] load_idx, output_idx;
 reg [2:0] stage;
 reg [5:0] issued, retired;
 wire issue=state==CALC && issued<32;
 wire [14:0] addr_a0,addr_b0,addr_a1,addr_b1;
 wire [7:0] tw_addr0,tw_addr1;
 wire addr_valid0,addr_valid1,tw_valid0,tw_valid1;
 address_generator address0(.fft_mode(1'b0),.stage(stage),
  .butterfly_idx({1'b0,issued[4:0],1'b0}),.base_addr(15'd0),
  .rd_addr_a(addr_a0),.rd_addr_b(addr_b0),.twiddle_addr(tw_addr0),.addr_valid(addr_valid0));
 address_generator address1(.fft_mode(1'b0),.stage(stage),
  .butterfly_idx({1'b0,issued[4:0],1'b1}),.base_addr(15'd0),
  .rd_addr_a(addr_a1),.rd_addr_b(addr_b1),.twiddle_addr(tw_addr1),.addr_valid(addr_valid1));
 wire signed [15:0] wr0,wi0,wr1,wi1;
 fft128_twiddle twiddle0(.clk(clk),.rst(rst),.rd_en(issue),.twiddle_addr(tw_addr0),
  .twiddle_real(wr0),.twiddle_imag(wi0),.twiddle_valid(tw_valid0));
 fft128_twiddle twiddle1(.clk(clk),.rst(rst),.rd_en(issue),.twiddle_addr(tw_addr1),
  .twiddle_real(wr1),.twiddle_imag(wi1),.twiddle_valid(tw_valid1));
 reg [6:0] pipe_a0[0:3],pipe_b0[0:3],pipe_a1[0:3],pipe_b1[0:3];
 wire [31:0] ea[0:1],eb[0:1],oa[0:1],ob[0:1];
 wire [1:0] vea,veb,voa,vob;
 wire source_valid=stage[0] ? (vea[1] && veb[1] && voa[1] && vob[1]) :
                                            (vea[0] && veb[0] && voa[0] && vob[0]);
 wire [31:0] a0=ea[stage[0]];
 wire [31:0] b0=stage==0 ? oa[stage[0]] : eb[stage[0]];
 wire [31:0] a1=stage==0 ? eb[stage[0]] : oa[stage[0]];
 wire [31:0] b1=ob[stage[0]];
 wire result_valid0,result_valid1;
 wire [31:0] y00,y01,y10,y11;
 wire butterfly_valid=state==CALC && source_valid && tw_valid0 && tw_valid1;
 butterfly_pipeline butterfly0(.clk(clk),.rst(rst),.valid_in(butterfly_valid),
  .ar($signed(a0[15:0])),.ai($signed(a0[31:16])),.br($signed(b0[15:0])),.bi($signed(b0[31:16])),
  .wr(wr0),.wi(wi0),.valid_out(result_valid0),.y0(y00),.y1(y01));
 butterfly_pipeline butterfly1(.clk(clk),.rst(rst),.valid_in(butterfly_valid),
  .ar($signed(a1[15:0])),.ai($signed(a1[31:16])),.br($signed(b1[15:0])),.bi($signed(b1[31:16])),
  .wr(wr1),.wi(wi1),.valid_out(result_valid1),.y0(y10),.y1(y11));
 wire load=state==LOAD && s_axis_tvalid;
 wire write_result=state==CALC && result_valid0 && result_valid1;
 wire output_read=state==OUT_REQ;
 wire [6:0] reversed={load_idx[0],load_idx[1],load_idx[2],load_idx[3],load_idx[4],load_idx[5],load_idx[6]};
 wire [5:0] read_ea=addr_a0[6:1];
 wire [5:0] read_eb=stage==0 ? addr_a1[6:1] : addr_b0[6:1];
 wire [5:0] read_oa=stage==0 ? addr_b0[6:1] : addr_a1[6:1];
 wire [5:0] read_ob=addr_b1[6:1];
 wire [5:0] write_ea=pipe_a0[3][6:1];
 wire [5:0] write_eb=stage==0 ? pipe_a1[3][6:1] : pipe_b0[3][6:1];
 wire [5:0] write_oa=stage==0 ? pipe_b0[3][6:1] : pipe_a1[3][6:1];
 wire [5:0] write_ob=pipe_b1[3][6:1];
 genvar g;
 generate for(g=0;g<2;g=g+1) begin: store
  wire read_here=issue && stage[0]==g;
  wire write_here=write_result && stage[0]!=g;
  wire load_even=load && g==0 && !reversed[0];
  wire load_odd=load && g==0 && reversed[0];
  wire output_even=output_read && g==1 && !output_idx[0];
  wire output_odd=output_read && g==1 && output_idx[0];
  fft_working_ram #(.ADDR_WIDTH(6),.DEPTH(64)) even_bank(
   .clk(clk),.rst(rst),
   .a_en(load_even || read_here || write_here || output_even),.a_we(load_even || write_here),
   .a_addr(load_even ? reversed[6:1] : output_even ? output_idx[6:1] : read_here ? read_ea : write_ea),
   .a_din(load_even ? s_axis_tdata : y00),.a_dout(ea[g]),.a_valid(vea[g]),
   .b_en(read_here || write_here),.b_we(write_here),
   .b_addr(read_here ? read_eb : write_eb),.b_din(stage==0 ? y10 : y01),
   .b_dout(eb[g]),.b_valid(veb[g]));
  fft_working_ram #(.ADDR_WIDTH(6),.DEPTH(64)) odd_bank(
   .clk(clk),.rst(rst),
   .a_en(load_odd || read_here || write_here || output_odd),.a_we(load_odd || write_here),
   .a_addr(load_odd ? reversed[6:1] : output_odd ? output_idx[6:1] : read_here ? read_oa : write_oa),
   .a_din(load_odd ? s_axis_tdata : stage==0 ? y01 : y10),.a_dout(oa[g]),.a_valid(voa[g]),
   .b_en(read_here || write_here),.b_we(write_here),
   .b_addr(read_here ? read_ob : write_ob),.b_din(y11),.b_dout(ob[g]),.b_valid(vob[g]));
 end endgenerate
 assign busy=state!=IDLE;
 assign s_axis_tready=state==LOAD;
 assign m_axis_tdata=output_idx[0] ? oa[1] : ea[1];
 assign m_axis_tvalid=state==OUT_SEND;
 assign m_axis_tlast=m_axis_tvalid && output_idx==127;
 assign dual_issue=issue && addr_valid0 && addr_valid1;
 assign dual_retire=write_result;
 assign calc_active=state==CALC;
 integer p;
 always @(posedge clk or posedge rst) begin
  if(rst) begin
   state<=IDLE;done<=0;input_error<=0;load_idx<=0;output_idx<=0;stage<=0;issued<=0;retired<=0;
   for(p=0;p<4;p=p+1) begin pipe_a0[p]<=0;pipe_b0[p]<=0;pipe_a1[p]<=0;pipe_b1[p]<=0;end
  end else begin
   done<=0;
   pipe_a0[0]<=addr_a0[6:0];pipe_b0[0]<=addr_b0[6:0];
   pipe_a1[0]<=addr_a1[6:0];pipe_b1[0]<=addr_b1[6:0];
   for(p=1;p<4;p=p+1) begin
    pipe_a0[p]<=pipe_a0[p-1];pipe_b0[p]<=pipe_b0[p-1];
    pipe_a1[p]<=pipe_a1[p-1];pipe_b1[p]<=pipe_b1[p-1];
   end
   case(state)
    IDLE:if(start) begin state<=LOAD;load_idx<=0;input_error<=0;end
    LOAD:if(s_axis_tvalid) begin
     if(s_axis_tlast!=(load_idx==127)) input_error<=1;
     if(load_idx==127) begin state<=CALC;stage<=0;issued<=0;retired<=0;end
     else load_idx<=load_idx+1'b1;
    end
    CALC:begin
     if(issue) issued<=issued+1'b1;
     if(write_result) begin
      if(retired==31) begin
       issued<=0;retired<=0;
       if(stage==6) begin state<=OUT_REQ;output_idx<=0;end
       else stage<=stage+1'b1;
      end else retired<=retired+1'b1;
     end
    end
    OUT_REQ:state<=OUT_SEND;
    OUT_SEND:if(m_axis_tready) begin
     if(output_idx==127) begin state<=IDLE;done<=1;end
     else begin output_idx<=output_idx+1'b1;state<=OUT_REQ;end
    end
    default:state<=IDLE;
   endcase
  end
 end
endmodule
