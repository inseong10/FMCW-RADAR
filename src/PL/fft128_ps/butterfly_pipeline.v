// One butterfly accepted per clock; three arithmetic register stages.
// Bit-identical to butterfly_engine: signed full-width products, then /2 per stage.
module butterfly_pipeline(
 input wire clk, rst, valid_in,
 input wire signed [15:0] ar, ai, br, bi, wr, wi,
 output reg valid_out,
 output reg [31:0] y0, y1
);
 reg v0, v1;
 reg signed [31:0] rr, ii, ri, ir;
 reg signed [15:0] a0r, a0i;
 reg signed [33:0] s0r, s0i, s1r, s1i;
 wire signed [32:0] bw_r = {rr[31],rr} - {ii[31],ii};
 wire signed [32:0] bw_i = {ri[31],ri} + {ir[31],ir};
 wire signed [33:0] aq_r = {{3{a0r[15]}},a0r,15'b0};
 wire signed [33:0] aq_i = {{3{a0i[15]}},a0i,15'b0};
 function [15:0] q15;
  input signed [33:0] x;
  reg signed [33:0] shifted;
  begin
   shifted = x >>> 16; // /2 scaling then discard 15 fractional bits
   if (shifted > 32767) q15=16'h7fff;
   else if (shifted < -32768) q15=16'h8000;
   else q15=shifted[15:0];
  end
 endfunction
 always @(posedge clk or posedge rst) begin
  if(rst) begin
   v0<=0; v1<=0; valid_out<=0;
   rr<=0; ii<=0; ri<=0; ir<=0; a0r<=0; a0i<=0;
   s0r<=0; s0i<=0; s1r<=0; s1i<=0; y0<=0; y1<=0;
  end else begin
   v0<=valid_in; v1<=v0; valid_out<=v1;
   if(valid_in) begin
    rr<=br*wr; ii<=bi*wi; ri<=br*wi; ir<=bi*wr;
    a0r<=ar; a0i<=ai;
   end
   if(v0) begin
    s0r<=aq_r+{bw_r[32],bw_r}; s0i<=aq_i+{bw_i[32],bw_i};
    s1r<=aq_r-{bw_r[32],bw_r}; s1i<=aq_i-{bw_i[32],bw_i};
   end
   if(v1) begin
    y0<={q15(s0i),q15(s0r)}; y1<={q15(s1i),q15(s1r)};
   end
  end
 end
endmodule
