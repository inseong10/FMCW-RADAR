
module address_generator (
    input wire        fft_mode,       // 0: 128-point, 1: 256-point
    input wire [2:0]  stage,          // FFT Stage
    input wire [6:0]  butterfly_idx,  // Butterfly index
    input wire [14:0] base_addr,      // FFT data base address

    output reg [14:0] rd_addr_a,
    output reg [14:0] rd_addr_b,
    output reg [7:0]  twiddle_addr,
    output reg        addr_valid
);

    // ------------------------------------------------
    // FFT Configuration
    // ------------------------------------------------

    reg [8:0] n_points;
    reg [3:0] log2_n;

    // ------------------------------------------------
    // Address Calculation Variables
    // ------------------------------------------------

    reg [15:0] idx_ext;
    reg [15:0] half_size;
    reg [15:0] group_base;
    reg [15:0] local_idx;
    reg [15:0] twiddle_step;
    reg [15:0] twiddle_calc;

    reg [15:0] addr_a_calc;
    reg [15:0] addr_b_calc;

    always @(*) begin

        // Default values
        rd_addr_a   = 0;
        rd_addr_b   = 0;
        twiddle_addr = 0;
        addr_valid  = 0;

        n_points    = 0;
        log2_n      = 0;

        idx_ext     = butterfly_idx;
        half_size   = 0;
        group_base  = 0;
        local_idx   = 0;
        twiddle_step = 0;
        twiddle_calc = 0;

        addr_a_calc = 0;
        addr_b_calc = 0;

        // --------------------------------------------
        // Select FFT Size
        // --------------------------------------------

        if (fft_mode == 1'b0) begin

            // Range FFT: 128-point
            n_points = 9'd128;
            log2_n   = 4'd7;

        end
        else begin

            // Doppler FFT: 256-point
            n_points = 9'd256;
            log2_n   = 4'd8;

        end

        // --------------------------------------------
        // Check Stage and Butterfly Index
        // --------------------------------------------

        if ((stage < log2_n) &&
            (idx_ext < (n_points >> 1))) begin

            // ----------------------------------------
            // Half Size = 2^stage
            // ----------------------------------------

            half_size = 16'd1 << stage;

            // ----------------------------------------
            // Group Base Calculation
            //
            // group_base =
            // (butterfly_idx >> stage) << (stage+1)
            // ----------------------------------------

            group_base =
                (idx_ext >> stage) << (stage + 1'b1);

            // ----------------------------------------
            // Local Butterfly Index
            //
            // local_idx = butterfly_idx % half_size
            // ----------------------------------------

            local_idx = idx_ext & (half_size - 1'b1);

            // ----------------------------------------
            // RAM Address A / B
            // ----------------------------------------

            addr_a_calc = base_addr + group_base + local_idx;

            addr_b_calc = addr_a_calc + half_size;

            // ----------------------------------------
            // Twiddle Address
            //
            // twiddle_addr =
            // local_idx * (N / (2^stage * 2))
            // ----------------------------------------

            twiddle_step = log2_n - stage - 1'b1;

            twiddle_calc = local_idx << twiddle_step;

            // ----------------------------------------
            // Output
            // ----------------------------------------

            rd_addr_a    = addr_a_calc[14:0];
            rd_addr_b    = addr_b_calc[14:0];
            twiddle_addr = twiddle_calc[7:0];

            addr_valid = 1'b1;

        end

    end

endmodule

