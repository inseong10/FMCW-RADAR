
// Adapted from supplied doppler_fft.v: fixed 128 points, seven stages.
module fft128_stream (
    input wire clk,
    input wire rst,

    // =========================================
    // Control Interface
    // =========================================
    input wire start,
    output wire busy,
    output reg done,
    output reg input_error,

    // =========================================
    // Transpose Buffer Input Stream
    // =========================================
    input wire [31:0] s_axis_tdata,
    input wire        s_axis_tvalid,
    output wire       s_axis_tready,
    input wire        s_axis_tlast,

    // =========================================
    // Doppler FFT Output Stream
    // =========================================
    output wire [31:0] m_axis_tdata,
    output wire        m_axis_tvalid,
    input wire         m_axis_tready,
    output wire        m_axis_tlast
);

    // =========================================
    // FSM State Definition
    // =========================================

    localparam IDLE      = 4'd0;
    localparam LOAD      = 4'd1;
    localparam BF_READ   = 4'd2;
    localparam BF_WAIT   = 4'd3;
    localparam BF_START  = 4'd4;
    localparam BF_DONE   = 4'd5;
    localparam BF_WRITE  = 4'd6;
    localparam OUT_REQ   = 4'd7;
    localparam OUT_SEND  = 4'd8;

    reg [3:0] state;

    // =========================================
    // Counters
    // =========================================

    reg [7:0] load_idx;
    reg [2:0] stage;
    reg [6:0] butterfly_idx;
    reg [7:0] output_idx;

    // =========================================
    // Bit-Reversal Function
    // =========================================

    function [7:0] bit_reverse7;

        input [7:0] value;

        begin

            bit_reverse7 = {1'b0,value[0],value[1],value[2],value[3],value[4],value[5],value[6]};

        end

    endfunction

    // =========================================
    // Status
    // =========================================

    assign busy = (state != IDLE);

    assign s_axis_tready = (state == LOAD);

    // =========================================
    // Address Generator Signals
    // =========================================

    wire [14:0] rd_addr_a;
    wire [14:0] rd_addr_b;

    wire [7:0] twiddle_addr;
    wire addr_valid;

    // =========================================
    // Working RAM Signals
    // =========================================

    reg ram_a_en;
    reg ram_a_we;
    reg [7:0] ram_a_addr;
    reg [31:0] ram_a_din;

    wire [31:0] ram_a_dout;
    wire ram_a_valid;

    reg ram_b_en;
    reg ram_b_we;
    reg [7:0] ram_b_addr;
    reg [31:0] ram_b_din;

    wire [31:0] ram_b_dout;
    wire ram_b_valid;

    // =========================================
    // Twiddle ROM Signals
    // =========================================

    reg twiddle_rd_en;

    wire signed [15:0] twiddle_real;
    wire signed [15:0] twiddle_imag;

    wire twiddle_valid;

    // =========================================
    // Butterfly Engine Signals
    // =========================================

    reg butterfly_start;

    wire butterfly_busy;
    wire butterfly_done;

    wire signed [15:0] y0_real;
    wire signed [15:0] y0_imag;

    wire signed [15:0] y1_real;
    wire signed [15:0] y1_imag;

    // =========================================
    // Address Generator
    // =========================================

    address_generator u_address_generator (

        .fft_mode      (1'b0),
        .stage         (stage),
        .butterfly_idx (butterfly_idx),
        .base_addr     (15'd0),

        .rd_addr_a     (rd_addr_a),
        .rd_addr_b     (rd_addr_b),
        .twiddle_addr  (twiddle_addr),
        .addr_valid    (addr_valid)

    );

    // =========================================
    // FFT Working RAM
    // =========================================

    fft_working_ram #(.DEPTH(128)) u_fft_working_ram (

        .clk     (clk),
        .rst     (rst),

        // Port A
        .a_en    (ram_a_en),
        .a_we    (ram_a_we),
        .a_addr  (ram_a_addr),
        .a_din   (ram_a_din),
        .a_dout  (ram_a_dout),
        .a_valid (ram_a_valid),

        // Port B
        .b_en    (ram_b_en),
        .b_we    (ram_b_we),
        .b_addr  (ram_b_addr),
        .b_din   (ram_b_din),
        .b_dout  (ram_b_dout),
        .b_valid (ram_b_valid)

    );

    // =========================================
    // Twiddle ROM
    // =========================================

    fft128_twiddle u_twiddle_rom (

        .clk           (clk),
        .rst           (rst),

        .rd_en         (twiddle_rd_en),
        .twiddle_addr  (twiddle_addr),

        .twiddle_real  (twiddle_real),
        .twiddle_imag  (twiddle_imag),
        .twiddle_valid (twiddle_valid)

    );

    // =========================================
    // Butterfly Engine
    // =========================================

    butterfly_engine u_butterfly_engine (

        .clk          (clk),
        .rst          (rst),

        .start        (butterfly_start),
        .busy         (butterfly_busy),
        .done         (butterfly_done),

        // Input A
        .a_real       ($signed(ram_a_dout[15:0])),
        .a_imag       ($signed(ram_a_dout[31:16])),

        // Input B
        .b_real       ($signed(ram_b_dout[15:0])),
        .b_imag       ($signed(ram_b_dout[31:16])),

        // Twiddle Factor
        .twiddle_real (twiddle_real),
        .twiddle_imag (twiddle_imag),

        // Output Y0
        .y0_real      (y0_real),
        .y0_imag      (y0_imag),

        // Output Y1
        .y1_real      (y1_real),
        .y1_imag      (y1_imag)

    );

    // =========================================
    // RAM / ROM Control
    // =========================================

    always @(*) begin

        // Default values
        ram_a_en = 1'b0;
        ram_a_we = 1'b0;
        ram_a_addr = 8'd0;
        ram_a_din = 32'd0;

        ram_b_en = 1'b0;
        ram_b_we = 1'b0;
        ram_b_addr = 8'd0;
        ram_b_din = 32'd0;

        twiddle_rd_en = 1'b0;
        butterfly_start = 1'b0;

        // -------------------------------------
        // Load input stream into RAM
        // -------------------------------------

        if (state == LOAD) begin

            if (s_axis_tvalid && s_axis_tready) begin

                ram_a_en = 1'b1;
                ram_a_we = 1'b1;

                // Bit-reversed input address
                ram_a_addr = bit_reverse7(load_idx);

                ram_a_din = s_axis_tdata;

            end

        end

        // -------------------------------------
        // Read Butterfly Inputs
        // -------------------------------------

        if (state == BF_READ) begin

            ram_a_en = 1'b1;
            ram_a_we = 1'b0;
            ram_a_addr = rd_addr_a[7:0];

            ram_b_en = 1'b1;
            ram_b_we = 1'b0;
            ram_b_addr = rd_addr_b[7:0];

            twiddle_rd_en = 1'b1;

        end

        // -------------------------------------
        // Start Butterfly
        // -------------------------------------

        if (state == BF_START) begin

            butterfly_start = 1'b1;

        end

        // -------------------------------------
        // Write Butterfly Results
        // -------------------------------------

        if (state == BF_WRITE) begin

            ram_a_en = 1'b1;
            ram_a_we = 1'b1;
            ram_a_addr = rd_addr_a[7:0];

            ram_a_din = {
                y0_imag,
                y0_real
            };

            ram_b_en = 1'b1;
            ram_b_we = 1'b1;
            ram_b_addr = rd_addr_b[7:0];

            ram_b_din = {
                y1_imag,
                y1_real
            };

        end

        // -------------------------------------
        // Read Final FFT Output
        // -------------------------------------

        if (state == OUT_REQ) begin

            ram_a_en = 1'b1;
            ram_a_we = 1'b0;
            ram_a_addr = output_idx;

        end

    end

    // =========================================
    // AXI4-Stream Output
    // =========================================

    assign m_axis_tdata = ram_a_dout;

    assign m_axis_tvalid = (state == OUT_SEND);

    assign m_axis_tlast =
        (state == OUT_SEND) &&
        (output_idx == 8'd127);

    // =========================================
    // Main FSM
    // =========================================

    always @(posedge clk or posedge rst) begin

        if (rst) begin

            state <= IDLE;

            load_idx <= 0;
            stage <= 0;
            butterfly_idx <= 0;
            output_idx <= 0;

            done <= 0;
            input_error <= 0;

        end

        else begin

            done <= 0;

            case (state)

                // ---------------------------------
                // IDLE
                // ---------------------------------

                IDLE: begin

                    if (start) begin

                        load_idx <= 0;
                        stage <= 0;
                        butterfly_idx <= 0;
                        output_idx <= 0;

                        input_error <= 0;

                        state <= LOAD;

                    end

                end

                // ---------------------------------
                // LOAD 128 Input Samples
                // ---------------------------------

                LOAD: begin

                    if (s_axis_tvalid && s_axis_tready) begin

                        // TLAST must be asserted only
                        // on the 128th input sample

                        if ((load_idx == 8'd127) &&
                            !s_axis_tlast) begin

                            input_error <= 1'b1;

                        end

                        if ((load_idx != 8'd127) &&
                            s_axis_tlast) begin

                            input_error <= 1'b1;

                        end

                        if (load_idx == 8'd127) begin

                            stage <= 0;
                            butterfly_idx <= 0;

                            state <= BF_READ;

                        end

                        else begin

                            load_idx <= load_idx + 1'b1;

                        end

                    end

                end

                // ---------------------------------
                // Read RAM / Twiddle ROM
                // ---------------------------------

                BF_READ: begin

                    if (addr_valid) begin

                        state <= BF_WAIT;

                    end

                end

                // ---------------------------------
                // Wait for Read Valid
                // ---------------------------------

                BF_WAIT: begin

                    if (ram_a_valid &&
                        ram_b_valid &&
                        twiddle_valid) begin

                        state <= BF_START;

                    end

                end

                // ---------------------------------
                // Start Butterfly
                // ---------------------------------

                BF_START: begin

                    state <= BF_DONE;

                end

                // ---------------------------------
                // Wait Butterfly Done
                // ---------------------------------

                BF_DONE: begin

                    if (butterfly_done) begin

                        state <= BF_WRITE;

                    end

                end

                // ---------------------------------
                // Write Butterfly Results
                // ---------------------------------

                BF_WRITE: begin

                    if (butterfly_idx == 7'd63) begin

                        if (stage == 3'd6) begin

                            output_idx <= 0;

                            state <= OUT_REQ;

                        end

                        else begin

                            stage <= stage + 1'b1;
                            butterfly_idx <= 0;

                            state <= BF_READ;

                        end

                    end

                    else begin

                        butterfly_idx <=
                            butterfly_idx + 1'b1;

                        state <= BF_READ;

                    end

                end

                // ---------------------------------
                // Output Read Request
                // ---------------------------------

                OUT_REQ: begin

                    state <= OUT_SEND;

                end

                // ---------------------------------
                // Output FFT Results
                // ---------------------------------

                OUT_SEND: begin

                    if (m_axis_tvalid && m_axis_tready) begin

                        if (output_idx == 8'd127) begin

                            done <= 1'b1;

                            state <= IDLE;

                        end

                        else begin

                            output_idx <= output_idx + 1'b1;

                            state <= OUT_REQ;

                        end

                    end

                end

                default: begin

                    state <= IDLE;

                end

            endcase

        end

    end

endmodule
