`timescale 1ns/1ps

// Exercise the complete synthesized/routed board netlist. These are preserved
// tester output ports connected to VIO; no behavioral FFT is substituted.
module fft_board_tb;
    reg sysclk = 0;
    reg btn_reset = 1;
    wire [3:0] led;
    zybo_fft_test_top dut (.sysclk(sysclk), .btn_reset(btn_reset), .led(led));
    wire done = dut.tester.done;
    wire [4:0] passed = dut.tester.passed;
    wire [7:0] error_count = dut.tester.error_count;
    wire [7:0] first_error_index = dut.tester.first_error_index;
    wire [31:0] first_actual = dut.tester.first_actual;
    wire [31:0] first_expected = dut.tester.first_expected;
    always #4 sysclk = ~sysclk; // Board oscillator: 125 MHz.
    initial begin
        // No JTAG transactions occur in this simulation. Model VIO's configured
        // reset output value of zero, while retaining the physical BTN0 path.
        force dut.debug_reset = 1'b0;
        #25000;
        btn_reset = 0;
        wait (done === 1'b1);
        #100;
        if (passed !== 5'b11111 || error_count !== 0)
            $fatal(1, "BOARD NETLIST FAIL: mask=%d errors=%d first=%h actual=%h expected=%h",
                   passed, error_count, first_error_index, first_actual, first_expected);
        $display("BOARD NETLIST PASS: five vectors / 160 bins, 20 MHz test clock");
        $finish;
    end
    initial begin
        #200000;
        $fatal(1, "BOARD NETLIST TIMEOUT");
    end
endmodule
