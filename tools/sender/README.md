# PC simulation and UDP sender

Run commands from the repository root with Python 3.10 or newer. Install NumPy
and SciPy (the external RadarSimPy package imports SciPy):

```bash
python -m pip install -r requirements.txt
```

The Windows RadarSimPy distribution lives locally in `tools/radarsimpy/`, with
`tools/radarsimpy/__init__.py` directly inside that directory. The binary package
is ignored by Git. Use the build matching the OS, Python minor version and CPU
architecture of the **sender process**. Native Windows uses `.pyd`/`.dll`; a WSL
Python process needs a Linux distribution instead.

Select a distribution in any of these ways, in precedence order:

1. `--radarsimpy-path` pointing to its root or the actual `radarsimpy/` package.
2. The `RADARSIMPY_PATH` environment variable.
3. `radarsimpy.local.json` next to `sender.py` (copy `radarsimpy.example.json`).
   A relative `package_root` is resolved from that configuration file.
4. The project-local `tools/radarsimpy/` package, if present.
5. A package installed in the active Python environment.

The local JSON is ignored by Git; `../radarsimpy` selects the package next to the
sender directory without a machine-specific absolute path. Keep macOS archives
and `__MACOSX` metadata out of Git. Windows DLL search directories are registered
when loading the selected package.

```powershell
# Native Windows: check the selected binary without sending any packets.
python tools/sender/sender.py --check-simulator

# The project-local Windows package is selected automatically.
python tools/sender/sender.py --ip 127.0.0.1 --port 5000 --pulses 160
```

On Windows, `tools/sender/run_udp_sender.bat` launches the same sender and
prompts for the destination when no IP/port arguments are supplied.

`--help` and packet construction work without loading RadarSimPy. A simulator is
loaded only for `--check-simulator` or a simulation. The Windows distribution
provided for this workspace is RadarSimPy 15.5.0 and includes CPython 3.10–3.14
AMD64 modules. Another checkout must supply its own matching distribution in
`tools/radarsimpy/` or configure an override.

For native Windows reception, start the NumPy reference receiver in another
terminal before sending:

```powershell
python src/PS/receiver/reference/receiver_numpy.py --bind 127.0.0.1 --port 5000 --warmup 0 --repeat 1
```

For a board receiver, replace `127.0.0.1` with the board's IPv4 address.
For the fixed 128×128 PL experiment, use `--pulses 128 --samples 128`.
`--samples` sets the sample rate to samples/(80 us); 128 selects 1.6 MHz and
preserves the full chirp duration. The default remains 160 samples at 2 MHz.
Packet fields and PS/PL boundaries are described in
[the interface document](../../docs/interfaces.md).

For the first board frame, a Windows-generated RadarSimPy input can also be
relayed through the Ubuntu host connected to the board. `replay_udp.py` uses
only the Python standard library and sends the original input datagrams from
an RSPB0001 record. The recording contains input IQ data; both FFT axes still
run on the PL when the board receiver uses its default MMIO backend.

The committed experiment record is
`benchmarks/fixtures/radarsimpy_128x128.rspb` (one channel, 128 chirps,
128 samples, 1.6 MHz, target range 30 m and speed -10 m/s).
Its input metadata is in the same folder. Board evidence and timings are in
`benchmarks/reports/2026-11-15-zybo128/`.
Start the board receiver first:

```bash
sudo /opt/fft128/fft128-receiver --port 5000 --timeout 300 --output /opt/fft128/rd128
```

After `LISTENING` appears, run on Ubuntu:

```bash
FFT_PROJECT="$HOME/fmcw_share/FMCW-FFT-test"
python3 "$FFT_PROJECT/tools/sender/replay_udp.py" \
  "$FFT_PROJECT/benchmarks/fixtures/radarsimpy_128x128.rspb" \
  --ip 10.0.0.3 --port 5000
```

The sender's completion message confirms UDP transmission only. The board must
report `FRAME_PASS backend=PL_MMIO bit_exact_bins=16384` to confirm the full
hardware frame. Results are `/opt/fft128/rd128.csv`, `.input.csv`, and `.json`
on the board, available under `/nfsroot/opt/fft128/` on the Ubuntu NFS host.
