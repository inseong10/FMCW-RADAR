`timescale 1ns/1ps
module fft_selftest_tb;
    reg clk = 0;
    reg reset = 1;
    wire done;
    wire [4:0] passed;
    wire [7:0] error_count, first_error_index;
    wire [31:0] first_actual, first_expected;
    integer result_file;
    fft_selftest tester (
        .clk(clk), .reset(reset), .done(done), .passed(passed),
        .error_count(error_count), .first_error_index(first_error_index),
        .first_actual(first_actual), .first_expected(first_expected)
    );
    // Match the board's 20 MHz functional test clock.
    always #25 clk = ~clk;
    initial begin
        result_file = $fopen("fft_selftest_results.csv", "w");
        $fdisplay(result_file, "test,bin,actual_real,actual_imag,expected_real,expected_imag,tolerance_raw,pass");
        repeat (8) @(negedge clk);
        reset = 0;
        wait(done);
        @(negedge clk);
        $fclose(result_file);
        if (passed !== 5'b11111 || error_count !== 0)
            $fatal(1, "FFT SELFTEST FAIL: mask=%b errors=%d first=%h actual=%h expected=%h",
                   passed, error_count, first_error_index, first_actual, first_expected);
        $display("FFT SELFTEST PASS: five vectors, 160 complex output bins");
        $finish;
    end
    always @(posedge clk) begin
        if (!reset && tester.state == 3 && tester.read_phase == 2)
            $fdisplay(result_file, "%0d,%0d,%0d,%0d,%0d,%0d,%0d,%b",
                      tester.test_index, tester.bin_index, tester.actual_r, tester.actual_i,
                      tester.expected_r, tester.expected_i, tester.tolerance, tester.bin_ok);
    end
    initial begin
        #100000;
        $fatal(1, "FFT SELFTEST TIMEOUT");
    end
endmodule
