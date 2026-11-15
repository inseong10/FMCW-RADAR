`timescale 1ns/1ps

// Drop-in replacement for the upstream multiplier. Multiply magnitudes once,
// truncate to Q bits, THEN restore the sign, just like all four upstream cases.
// A signed product followed by >>> Q would round negative fractions differently.
// Unsigned N-bit magnitudes also preserve the minimum negative input (-32768).
module multiplier #(
    parameter Q = 8,
    parameter N = 16
)(
    input wire clk,
    input wire rst,
    input wire [N-1:0] A,
    input wire [N-1:0] B,
    output reg [N-1:0] C
);
    wire [N-1:0] magnitude_a = A[N-1] ? (~A + 1'b1) : A;
    wire [N-1:0] magnitude_b = B[N-1] ? (~B + 1'b1) : B;
    (* use_dsp = "yes" *) wire [2*N-1:0] product = magnitude_a * magnitude_b;
    wire [N-1:0] truncated = product[N-1+Q:Q];
    wire [N-1:0] result = (A[N-1] ^ B[N-1]) ? (~truncated + 1'b1) : truncated;
    always @(negedge clk or posedge rst) begin
        if (rst) C <= {N{1'b0}};
        else C <= result;
    end
endmodule
