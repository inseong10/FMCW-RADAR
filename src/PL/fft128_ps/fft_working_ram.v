
module fft_working_ram #(
    parameter DATA_WIDTH = 32,
    parameter ADDR_WIDTH = 8,
    parameter DEPTH      = 256
)(
    input wire clk,
    input wire rst,

    // =========================================
    // Port A
    // =========================================
    input wire                  a_en,
    input wire                  a_we,
    input wire [ADDR_WIDTH-1:0] a_addr,
    input wire [DATA_WIDTH-1:0] a_din,
    output reg [DATA_WIDTH-1:0] a_dout,
    output reg                  a_valid,

    // =========================================
    // Port B
    // =========================================
    input wire                  b_en,
    input wire                  b_we,
    input wire [ADDR_WIDTH-1:0] b_addr,
    input wire [DATA_WIDTH-1:0] b_din,
    output reg [DATA_WIDTH-1:0] b_dout,
    output reg                  b_valid
);

    // =========================================
    // Dual-Port RAM Declaration
    // =========================================

    reg [DATA_WIDTH-1:0] mem [0:DEPTH-1];

    // =========================================
    // Port A: Read / Write
    // =========================================

    always @(posedge clk) begin

        if (a_en && (a_addr < DEPTH)) begin

            if (a_we) begin

                // Write operation
                mem[a_addr] <= a_din;

            end
            else begin

                // Synchronous read operation
                a_dout <= mem[a_addr];

            end

        end

    end

    // =========================================
    // Port B: Read / Write
    // =========================================

    always @(posedge clk) begin

        if (b_en && (b_addr < DEPTH)) begin

            if (b_we) begin

                // Write operation
                mem[b_addr] <= b_din;

            end
            else begin

                // Synchronous read operation
                b_dout <= mem[b_addr];

            end

        end

    end

    // =========================================
    // Read Valid Signal
    // =========================================

    always @(posedge clk or posedge rst) begin

        if (rst) begin

            a_valid <= 1'b0;
            b_valid <= 1'b0;

        end
        else begin

            a_valid <= a_en &&
                       !a_we &&
                       (a_addr < DEPTH);

            b_valid <= b_en &&
                       !b_we &&
                       (b_addr < DEPTH);

        end

    end

endmodule

