
module butterfly_engine (
    input wire clk,
    input wire rst,

    // =========================================
    // Control Interface
    // =========================================
    input wire start,
    output reg busy,
    output reg done,

    // =========================================
    // Complex Input A (Q1.15)
    // =========================================
    input wire signed [15:0] a_real,
    input wire signed [15:0] a_imag,

    // =========================================
    // Complex Input B (Q1.15)
    // =========================================
    input wire signed [15:0] b_real,
    input wire signed [15:0] b_imag,

    // =========================================
    // Twiddle Factor (Q1.15)
    // =========================================
    input wire signed [15:0] twiddle_real,
    input wire signed [15:0] twiddle_imag,

    // =========================================
    // Complex Output Y0 (Q1.15)
    // =========================================
    output reg signed [15:0] y0_real,
    output reg signed [15:0] y0_imag,

    // =========================================
    // Complex Output Y1 (Q1.15)
    // =========================================
    output reg signed [15:0] y1_real,
    output reg signed [15:0] y1_imag
);

    // =========================================
    // 1. Complex Multiplication
    // =========================================

    wire signed [31:0] mult_rr;
    wire signed [31:0] mult_ii;
    wire signed [31:0] mult_ri;
    wire signed [31:0] mult_ir;

    assign mult_rr = b_real * twiddle_real;
    assign mult_ii = b_imag * twiddle_imag;

    assign mult_ri = b_real * twiddle_imag;
    assign mult_ir = b_imag * twiddle_real;

    // =========================================
    // 2. B * W Complex Result
    // Q2.30
    // =========================================

    wire signed [32:0] bw_real;
    wire signed [32:0] bw_imag;

    assign bw_real =
        {mult_rr[31], mult_rr} -
        {mult_ii[31], mult_ii};

    assign bw_imag =
        {mult_ri[31], mult_ri} +
        {mult_ir[31], mult_ir};

    // =========================================
    // 3. Convert A to Q2.30
    // =========================================

    wire signed [33:0] a_real_q30;
    wire signed [33:0] a_imag_q30;

    assign a_real_q30 =
        {{3{a_real[15]}}, a_real, 15'b0};

    assign a_imag_q30 =
        {{3{a_imag[15]}}, a_imag, 15'b0};

    // =========================================
    // 4. Butterfly Addition / Subtraction
    // =========================================

    wire signed [33:0] y0_real_q30;
    wire signed [33:0] y0_imag_q30;

    wire signed [33:0] y1_real_q30;
    wire signed [33:0] y1_imag_q30;

    assign y0_real_q30 =
        a_real_q30 + {{1{bw_real[32]}}, bw_real};

    assign y0_imag_q30 =
        a_imag_q30 + {{1{bw_imag[32]}}, bw_imag};

    assign y1_real_q30 =
        a_real_q30 - {{1{bw_real[32]}}, bw_real};

    assign y1_imag_q30 =
        a_imag_q30 - {{1{bw_imag[32]}}, bw_imag};

    // =========================================
    // 5. Stage Scaling
    // Divide by 2
    // =========================================

    wire signed [33:0] scaled_y0_real;
    wire signed [33:0] scaled_y0_imag;

    wire signed [33:0] scaled_y1_real;
    wire signed [33:0] scaled_y1_imag;

    assign scaled_y0_real = y0_real_q30 >>> 1;
    assign scaled_y0_imag = y0_imag_q30 >>> 1;

    assign scaled_y1_real = y1_real_q30 >>> 1;
    assign scaled_y1_imag = y1_imag_q30 >>> 1;

    // =========================================
    // 6. Q2.30 to Q1.15 Saturation
    // =========================================

    function signed [15:0] saturate_q15;

        input signed [33:0] value;

        reg signed [33:0] shifted;

        begin

            // Remove 15 fractional bits
            shifted = value >>> 15;

            if (shifted > 34'sd32767) begin

                saturate_q15 = 16'sh7FFF;

            end
            else if (shifted < -34'sd32768) begin

                saturate_q15 = 16'sh8000;

            end
            else begin

                saturate_q15 = shifted[15:0];

            end

        end

    endfunction

    // =========================================
    // 7. Final Output Calculation
    // =========================================

    wire signed [15:0] result_y0_real;
    wire signed [15:0] result_y0_imag;

    wire signed [15:0] result_y1_real;
    wire signed [15:0] result_y1_imag;

    assign result_y0_real = saturate_q15(scaled_y0_real);
    assign result_y0_imag = saturate_q15(scaled_y0_imag);

    assign result_y1_real = saturate_q15(scaled_y1_real);
    assign result_y1_imag = saturate_q15(scaled_y1_imag);

    // =========================================
    // 8. Control and Output Registers
    // =========================================

    always @(posedge clk or posedge rst) begin

        if (rst) begin

            busy <= 1'b0;
            done <= 1'b0;

            y0_real <= 16'sd0;
            y0_imag <= 16'sd0;

            y1_real <= 16'sd0;
            y1_imag <= 16'sd0;

        end

        else begin

            done <= 1'b0;

            if (start && !busy) begin

                // Capture Butterfly Results
                y0_real <= result_y0_real;
                y0_imag <= result_y0_imag;

                y1_real <= result_y1_real;
                y1_imag <= result_y1_imag;

                busy <= 1'b1;

            end

            else if (busy) begin

                busy <= 1'b0;
                done <= 1'b1;

            end

        end

    end

endmodule

