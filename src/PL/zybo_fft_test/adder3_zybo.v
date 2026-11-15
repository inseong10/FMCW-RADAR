`timescale 1ns/1ps

// Use simultaneous register updates for the feedback between butterflies.
// Blocking clocked assignments can expose newly computed peer outputs in RTL
// simulation, whereas physical flip-flops all capture their pre-edge inputs.
module adder3 #(parameter N = 16)(
    input wire clk,
    input wire rst,
    input wire [N-1:0] A, B, C,
    output reg [N-1:0] D
);
    always @(posedge clk or posedge rst) begin
        if (rst) D <= {N{1'b0}};
        else D <= A + B + C;
    end
endmodule
