`timescale 1ns/1ps
module zybo_fft_test_top (
    input wire sysclk,
    input wire btn_reset,
    output wire [3:0] led
);
    wire clk_test, locked, debug_reset;
    reg [2:0] reset_sync = 3'b111;
    reg [23:0] heartbeat = 0;
    wire reset = reset_sync[2];
    wire done;
    wire [4:0] passed;
    wire [7:0] error_count, first_error_index;
    wire [31:0] first_actual, first_expected;
    fft_test_clk clocking (.clk_in1(sysclk), .reset(1'b0), .clk_out1(clk_test), .locked(locked));
    always @(posedge clk_test or negedge locked) begin
        if (!locked) reset_sync <= 3'b111;
        else reset_sync <= {reset_sync[1:0], btn_reset | debug_reset};
    end
    always @(posedge clk_test) heartbeat <= heartbeat + 1;
    fft_selftest tester (
        .clk(clk_test), .reset(reset), .done(done), .passed(passed),
        .error_count(error_count), .first_error_index(first_error_index),
        .first_actual(first_actual), .first_expected(first_expected)
    );
    fft_test_vio monitor (
        .clk(clk_test),
        .probe_in0(done), .probe_in1(passed), .probe_in2(error_count),
        .probe_in3(first_error_index), .probe_in4(first_actual), .probe_in5(first_expected),
        .probe_out0(debug_reset)
    );
    assign led[0] = locked;
    assign led[1] = done && passed == 5'b11111;
    assign led[2] = done && error_count != 0;
    assign led[3] = heartbeat[23];
endmodule
