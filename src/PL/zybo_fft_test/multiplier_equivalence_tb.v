`timescale 1ns/1ps
module multiplier_equivalence_tb;
    reg clk = 0;
    reg rst = 0;
    reg [15:0] A = 0, B = 0;
    wire [15:0] reference_c, optimized_c;
    reg done = 0, passed = 0;
    integer checks = 0;
    integer operand, index;
    reg [31:0] random_state = 32'h13579bdf;
    reg [15:0] random_a, random_b;
    multiplier_reference #(.N(16), .Q(8)) reference_dut
        (.clk(clk), .rst(rst), .A(A), .B(B), .C(reference_c));
    multiplier #(.N(16), .Q(8)) optimized_dut
        (.clk(clk), .rst(rst), .A(A), .B(B), .C(optimized_c));
    always #1 clk = ~clk;

    function [15:0] boundary;
        input integer which;
        begin
            case (which)
                0: boundary = 16'h0000;
                1: boundary = 16'h0001;
                2: boundary = 16'h00ff;
                3: boundary = 16'h0100;
                4: boundary = 16'h7fff;
                5: boundary = 16'h8000;
                6: boundary = 16'h8001;
                7: boundary = 16'hffff;
                default: boundary = 0;
            endcase
        end
    endfunction

    task check_pair;
        input [15:0] a, b;
        begin
            @(posedge clk);
            A = a;
            B = b;
            @(negedge clk);
            #0.1;
            if (reference_c !== optimized_c)
                $fatal(1, "MULTIPLIER MISMATCH A=%h B=%h original=%h optimized=%h",
                       A, B, reference_c, optimized_c);
            checks = checks + 1;
        end
    endtask

    task check_reset;
        begin
            #0.2 rst = 1;
            #0.1;
            if (reference_c !== 0 || optimized_c !== 0)
                $fatal(1, "MULTIPLIER ASYNC RESET FAIL");
            #0.2 rst = 0;
        end
    endtask

    initial begin
        check_reset;
        // Exhaust all 16-bit A values against both signs, Q8 boundaries,
        // overflow and the most-negative B input (524288 comparisons).
        for (index = 0; index < 8; index = index + 1)
            for (operand = 0; operand < 65536; operand = operand + 1)
                check_pair(operand[15:0], boundary(index));
        // Deterministic, simulator-independent random pairs.
        for (index = 0; index < 65536; index = index + 1) begin
            random_state = random_state ^ (random_state << 13);
            random_state = random_state ^ (random_state >> 17);
            random_state = random_state ^ (random_state << 5);
            random_a = random_state[15:0];
            random_b = random_state[31:16];
            check_pair(random_a, random_b);
        end
        check_pair(16'hffff, 16'h0100);
        check_reset;
        passed = 1;
        done = 1;
        $display("MULTIPLIER EQUIVALENCE PASS: %0d pairs and asynchronous reset", checks);
        $finish;
    end
    initial begin
        #3000000;
        $fatal(1, "MULTIPLIER EQUIVALENCE TIMEOUT");
    end
endmodule
