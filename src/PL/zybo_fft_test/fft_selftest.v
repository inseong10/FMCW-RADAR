`timescale 1ns/1ps

// Exercises the upstream fft_wrapper with five real Q8 vectors. The board
// build shares the multiplier and retimes the divider/adder registers for
// physical flip-flop behavior; original submodule files remain unchanged.
// Inputs are held until all 32 complex output bins have been checked.
module fft_selftest (
    input wire clk,
    input wire reset,
    output reg done,
    output reg [4:0] passed,
    output reg [7:0] error_count,
    output reg [7:0] first_error_index,
    output reg [31:0] first_actual,
    output reg [31:0] first_expected
);
    localparam LOAD=0, HOLD_RESET=1, RUN_FFT=2, READ_BINS=3, NEXT_TEST=4, FINISHED=5;
    reg [2:0] state;
    reg [2:0] test_index;
    reg [4:0] bin_index;
    reg [7:0] cycles;
    reg [1:0] read_phase;
    reg vector_ok;
    wire core_reset = reset || state == LOAD || state == HOLD_RESET;
    wire [4:0] write_address = cycles[4:0];
    wire write_enable = state == LOAD && !reset;
    wire [15:0] write_data;
    wire [31:0] read_data;
    wire [31:0] expected;

    `include "test_vectors.vh"
    assign write_data = input_sample(test_index, write_address);
    assign expected = expected_bin({test_index, bin_index});

    // fft_wrapper packs {real, imaginary}; each component is signed Q8.
    wire signed [16:0] actual_r = {read_data[31], read_data[31:16]};
    wire signed [16:0] actual_i = {read_data[15], read_data[15:0]};
    wire signed [16:0] expected_r = {expected[31], expected[31:16]};
    wire signed [16:0] expected_i = {expected[15], expected[15:0]};
    wire signed [16:0] difference_r = actual_r - expected_r;
    wire signed [16:0] difference_i = actual_i - expected_i;
    wire signed [16:0] tolerance = test_index == 4 ? 17'sd32 :
                                    test_index == 3 ? 17'sd4 : 17'sd0;
    wire bin_ok = difference_r >= -tolerance && difference_r <= tolerance &&
                  difference_i >= -tolerance && difference_i <= tolerance;

    fft_wrapper #(.N(16), .Q(8)) dut (
        .clk(clk), .rst(core_reset),
        .m_addr(write_address), .m_data(write_data), .m_we(write_enable),
        .s_addr(bin_index), .s_re(state == READ_BINS), .s_data(read_data)
    );

    always @(posedge clk) begin
        if (reset) begin
            state <= LOAD;
            test_index <= 0;
            bin_index <= 0;
            cycles <= 0;
            read_phase <= 0;
            vector_ok <= 1;
            done <= 0;
            passed <= 0;
            error_count <= 0;
            first_error_index <= 0;
            first_actual <= 0;
            first_expected <= 0;
        end else begin
            case (state)
                LOAD: begin
                    if (cycles == 31) begin
                        cycles <= 0;
                        state <= HOLD_RESET;
                    end else cycles <= cycles + 1;
                end
                HOLD_RESET: begin
                    if (cycles == 7) begin
                        cycles <= 0;
                        state <= RUN_FFT;
                    end else cycles <= cycles + 1;
                end
                RUN_FFT: begin
                    // Allow repeated identical frames to settle before reading.
                    if (cycles == 127) begin
                        cycles <= 0;
                        bin_index <= 0;
                        read_phase <= 0;
                        state <= READ_BINS;
                    end else cycles <= cycles + 1;
                end
                READ_BINS: begin
                    // Registered output RAM requires an address/read latency.
                    if (read_phase == 2) begin
                        read_phase <= 0;
                        if (bin_ok) begin
                            // Keep vector_ok set unless any bin fails.
                        end else begin
                            vector_ok <= 0;
                            error_count <= error_count + 1;
                            if (error_count == 0) begin
                                first_error_index <= {test_index, bin_index};
                                first_actual <= read_data;
                                first_expected <= expected;
                            end
                        end
                        if (bin_index == 31) state <= NEXT_TEST;
                        else bin_index <= bin_index + 1;
                    end else read_phase <= read_phase + 1;
                end
                NEXT_TEST: begin
                    passed[test_index] <= vector_ok;
                    if (test_index == 4) begin
                        done <= 1;
                        state <= FINISHED;
                    end else begin
                        test_index <= test_index + 1;
                        cycles <= 0;
                        vector_ok <= 1;
                        state <= LOAD;
                    end
                end
                FINISHED: state <= FINISHED;
                default: state <= LOAD;
            endcase
        end
    end
endmodule
