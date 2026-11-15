# FFTW wisdom

`legacy-fftw-3.3.11/` preserves the five wisdom files originally committed to this
repository. Their header identifies FFTW 3.3.11; the original CPU, OS and build
options were not recorded. They are reference material, not the default for a
new PC or the Zybo ARM target.

Generate wisdom on the machine that will run the receiver:

```bash
# From the repository root, after building the C++ receiver.
python src/PS/receiver/select_wisdom.py --input benchmarks/data/frame.bin
```

New wisdom and its JSON environment metadata are written under
`build/wisdom/<os>-<architecture>/`, which is ignored by Git. Keep outputs from
different machines in separate directories. Regenerate after changing the CPU,
FFTW build or frame dimensions. Use `--output-dir` to select another directory.
If sharing a plan, copy both `.wis` and `.json` into an explicitly named
environment directory here and record the compiler/FFTW build options as well.
