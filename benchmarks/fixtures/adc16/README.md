# Frozen ADC profile1

These four unwindowed records are ADC-emulated signed16 IQ, produced from the
original float records without modifying them. `adc16_profile.json` and each
sidecar record the exact original/output SHA256, targets and clipping counts.
All four have zero clipped components. This is simulated input, not ADC hardware.

Profile1 uses 16 bits, S=1,600,000 codes/source-unit, fixed for every sample,
frame and scenario. Round nearest/ties-even, then saturate to [-32768,32767].
One-time calibration across the four sources has maximum complex magnitude
0.009593515132970855, giving 6.586778670641943 dB complex headroom. Using complex
magnitude is conservative relative to individual I/Q clipping. Known source
complex noise RMS0.00179 becomes2864 LSB (component standard deviation2025.15).
The noise-free source has no injected noise. Future stronger signals can clip;
do not renormalize them per frame. Bit-depth/gain sweeps require another experiment.

RSPB0002 is one 40-byte big-endian header `!8sIIddHHI`: magic, chirps128,
samples128, sample rate, S, bits16, reserved0, profile1. Then65536 bytes of
big-endian signed16 interleaved I,Q in chirp-major/sample-minor order. Total65576.
Hann is absent here and in the sender. The receiver applies the selected window.

Generate into a **fresh** directory (existing files are refused):

```bash
python3 tools/detection/make_adc16_fixture.py --out build/adc16_regenerated
```

The sender automatically selects explicit RSPY v3/dtype2/profile1 from this
record. Legacy RSPB0001 still sends v2/dtype1 float32. See
[protocol and measurement details](../../../docs/adc16_runbook.md).
