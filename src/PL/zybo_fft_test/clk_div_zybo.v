`timescale 1ns/1ps

// Capture the fifth butterfly result AFTER its rising-edge adder update.
// The upstream rising-edge divider causes the output registers to capture
// the fourth stage in hardware; zero-delay RTL simulation hides that cycle.
// Moving the divider to the falling edge gives a real half-cycle separation.
// Reset is released by a rising-edge state register. Skip the first falling
// edge so the divider does not start one cycle before control_unit's counter.
module Clk_div #(parameter DIVISOR = 5)(
    input wire rst,
    input wire clock_in,
    output reg clock_out
);
    reg [3:0] counter;
    always @(negedge clock_in or posedge rst) begin
        if (rst) begin
            counter <= DIVISOR-1;
            clock_out <= 0;
        end else begin
            if (counter >= DIVISOR-1) counter <= 0;
            else counter <= counter + 1'b1;
            clock_out <= counter < DIVISOR/2;
        end
    end
endmodule
