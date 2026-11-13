"""Select an FFTW wisdom file for one frame size by re-measuring candidates.

MEASURE picks a different plan from run to run, so a single run cannot tell which
plan is fast. Each candidate is measured in fresh processes; the lowest median wins.
Wisdom depends on the FFTW build and the machine: regenerate it when either changes.
"""
from pathlib import Path
import argparse, csv, random, re, shutil, statistics, subprocess, tempfile

HERE = Path(__file__).resolve().parent


def median_total(binary, packets, wisdom, flags, repeat, workdir):
    timings = Path(workdir) / "timings.csv"
    result = subprocess.run(
        [str(binary), "--input", str(packets), "--warmup", "10", "--repeat", str(repeat),
         "--timings", str(timings), *flags, str(wisdom)],
        capture_output=True, text=True, check=True,
    )
    with timings.open() as f:
        values = [float(r["wall_ms"]) for r in csv.DictReader(f) if r["stage"] == "processing_total"]
    return statistics.median(values), result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Packet file (RSPB0001) of the target frame size")
    parser.add_argument("--output-dir", default=str(HERE / "wisdom"))
    parser.add_argument("--binary", default=str(HERE / "receiver_cpp"))
    parser.add_argument("--candidates", type=int, default=10)
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--repeat", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    with tempfile.TemporaryDirectory() as workdir:
        candidates = []
        size = None
        for index in range(args.candidates):
            wisdom = Path(workdir) / f"candidate_{index:02d}.wis"
            _, stdout = median_total(args.binary, args.input, wisdom, ["--measure-plan", "--wisdom-out"], args.repeat, workdir)
            size = re.search(r"Range plan \((\d+x\d+)\)", stdout)[1]
            candidates.append(wisdom)

        scores = {wisdom: [] for wisdom in candidates}
        for _ in range(args.rounds):
            order = candidates[:]
            rng.shuffle(order)
            for wisdom in order:
                value, stdout = median_total(args.binary, args.input, wisdom, ["--wisdom-in"], args.repeat, workdir)
                if "FFTW WISDOM" not in stdout:
                    raise RuntimeError(f"Candidate was not applied: {wisdom.name}")
                scores[wisdom].append(value)

        ranked = sorted(candidates, key=lambda w: statistics.median(scores[w]))
        best = ranked[0]
        output = Path(args.output_dir)
        output.mkdir(parents=True, exist_ok=True)
        target = output / f"wisdom_{size}.wis"
        shutil.copy2(best, target)
        medians = [statistics.median(scores[w]) for w in ranked]
        print(f"{size}: best {medians[0]:.3f} ms, worst {medians[-1]:.3f} ms, saved {target}")


if __name__ == "__main__":
    main()
