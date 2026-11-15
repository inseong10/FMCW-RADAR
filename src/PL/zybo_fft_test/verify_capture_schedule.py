"""Model stage capture from the real upstream mux wiring, without HDL tools.

This diagnoses the observed board signature; it does not replace gate simulation
or establish a board pass. Run from any directory with Python 3.
"""
import re
from pathlib import Path


HERE = Path(__file__).resolve().parent
RTL = HERE.parent / "fft32-dit-butterfly" / "FPGA" / "RTL"


def signed(value):
    return ((int(value) + 32768) & 65535) - 32768


def multiply(a, b):
    product = int(a) * int(b)
    return signed((abs(product) // 256) * (-1 if product < 0 else 1))


def main():
    top = (RTL / "top_n.v").read_text()
    ports = lambda body: dict(re.findall(r"\.(\w+)\(([^()]*)\)", body))
    muxes = [ports(body) for body in re.findall(
        r"mux\s*#\s*\(\s*\.N\(N\)\s*\)\s+\w+\s*\((.*?)\);", top, re.S)]
    butterflies = [ports(body) for body in re.findall(
        r"butterfly2\s*#\s*\(.*?\)\s+b2_\d+\s*\((.*?)\);", top, re.S)]
    assert len(muxes) == 96 and len(butterflies) == 16
    constants = {}
    for part, component in [("real", "r"), ("imag", "i")]:
        text = (RTL / f"twiddle_rom_{part}_n.v").read_text()
        for index, bits in re.findall(r"reg(\d+)_[ri]\s*<=\s*16'b([01]+)", text):
            constants[f"twiddle{index}_{component}"] = signed(int(bits, 2))
    vectors = (HERE / "test_vectors.vh").read_text()
    pattern = {int(index): signed(int(value, 16)) for index, value in re.findall(
        r"5'd(\d+): input_sample = 16'h([0-9a-fA-F]+)", vectors)}
    expected = {int(index): int(value, 16) for index, value in re.findall(
        r"8'd(\d+): expected_bin = 32'h([0-9a-fA-F]+)", vectors)}
    assert len(pattern) == 32 and len(expected) == 160
    inputs = [[0] * 32, [256] + [0] * 31, [256] * 32,
              [0, 256] + [0] * 30, [pattern[i] for i in range(32)]]

    def value(expression, signals):
        expression = expression.strip()
        if expression in signals:
            return signals[expression]
        if expression in {"0", "16'b0"}:
            return 0
        raise ValueError(f"Unrecognized mux input: {expression}")

    captured = {3: [], 4: []}
    order = list(range(0, 32, 2)) + list(range(1, 32, 2))
    for test, samples in enumerate(inputs):
        signals = dict(constants)
        signals.update({f"in{i}_butterfly_2": v for i, v in enumerate(samples)})
        signals.update({f"out{i}_{c}_mac": 0 for i in range(32) for c in "ri"})
        for stage in range(5):
            for mux in muxes:
                signals[mux["c"]] = value(mux[f"a{stage + 1}"], signals)
            updates = {}
            for butterfly in butterflies:
                ar, ai, br, bi, wr, wi = [value(butterfly[p], signals) for p in
                    ["in0_r", "in0_i", "in1_r", "in1_i", "twiddle_r", "twiddle_i"]]
                results = [ar + multiply(br, wr) + multiply(bi, wi),
                           ai - multiply(br, wi) + multiply(bi, wr),
                           ar - multiply(br, wr) - multiply(bi, wi),
                           ai - multiply(bi, wr) + multiply(br, wi)]
                updates.update({butterfly[p]: signed(v) for p, v in zip(
                    ["out0_r", "out0_i", "out1_r", "out1_i"], results)})
            signals.update(updates)
            if stage in captured:
                actual = [(signals[f"out{i}_r_mac"] & 65535) << 16 |
                          (signals[f"out{i}_i_mac"] & 65535) for i in order]
                captured[stage].append(actual)

    summaries = {}
    for stage, tests in captured.items():
        mask, errors, first = 0, 0, None
        for test, actual_bins in enumerate(tests):
            failures = 0
            tolerance = [0, 0, 0, 4, 32][test]
            for index, actual in enumerate(actual_bins):
                address = test * 32 + index
                reference = expected[address]
                ok = all(abs(signed(actual >> shift) - signed(reference >> shift))
                         <= tolerance for shift in (16, 0))
                if not ok:
                    failures += 1
                    if first is None:
                        first = (address, actual, reference)
            mask |= (failures == 0) << test
            errors += failures
        summaries[stage] = (mask, errors, first)
        print(f"Capture stage {stage + 1}/5: passed={mask} errors={errors} first={first}")
    assert summaries[3] == (1, 81, (40, 0, 16777216)), summaries[3]
    assert summaries[4] == (31, 0, None), summaries[4]
    print("Schedule model reproduces the board failure exactly; final-stage capture passes references.")


if __name__ == "__main__":
    main()
