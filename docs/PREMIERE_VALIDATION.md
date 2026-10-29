# Premiere Pro Validation

Acceptance test for issue 4: the exported `.cube` grades the same inside Premiere Pro as in the engine and in FFmpeg.

## What is checked

`scripts/premiere_validation.py` grades one source image three ways and compares them:

1. Python `DifferentiableLUT3D` (trilinear, the optimization path).
2. FFmpeg `lut3d` with `interp=trilinear` (expected to match Python closely).
3. FFmpeg `lut3d` with `interp=tetrahedral` (the FFmpeg default; Premiere Pro and DaVinci Resolve evaluate LUTs this way).

A fourth optional comparison takes a still exported from Premiere and compares it against the FFmpeg tetrahedral render of the same source and cube.

Metrics per pair: mean, p50, p95, max DeltaE2000 plus mean and max absolute RGB difference and PSNR. DeltaE uses `linear_srgb_to_lab` plus `delta_e_2000` on every 16th pixel, the same sampling as the synthetic benchmark.

## Thresholds

- Python vs FFmpeg trilinear: mean DeltaE2000 at or under 1.0. Larger values mean an axis-order, range, or quantization bug, not interpolation.
- Premiere still vs FFmpeg tetrahedral: mean DeltaE2000 under 2.0 (hackathon plan Section 11 cross-tool agreement).
- Trilinear vs tetrahedral gap is reported, not gated. Typical smooth photo grades show a mean gap well under 1.0 with isolated saturated colors reaching higher. Record the numbers; only fine-tune under a tetrahedral approximation if the gap is visible on real footage.

## Run

Synthetic chart and generated commercial-style cube, no footage needed:

```
python scripts/premiere_validation.py
```

Own cube and source frame:

```
python scripts/premiere_validation.py --cube work/out.cube --source work/src_frame.png
```

With a Premiere exported still (same source frame, same cube applied in Premiere, exported PNG):

```
python scripts/premiere_validation.py --cube work/out.cube --source work/src_frame.png --premiere-still work/premiere_still.png
```

JSON report defaults to `work/premiere_validation.json`. Exit code 0 means PASS, 1 means FAIL. Console prints one line per pair plus the tetrahedral gap line.

## SampleFootage procedure

1. Extract a representative Rec.709 frame (range handling is explicit; the sample clips are `bt709` with `tv` range):

```
ffmpeg -y -loglevel error -ss 1 -i "C:\Users\lokwa\Documents\SampleFootage\Rec709\A001_10290006_C101.mov" -frames:v 1 work/src_frame.png
```

2. Run validation with the candidate cube:

```
python scripts/premiere_validation.py --cube work/out.cube --source work/src_frame.png
```

3. For S-Log3 or Apple Log clips, extract first and convert to the Rec.709 working space before this test. The v1 contract grades display-referred Rec.709 values; log decoding is out of scope for this check.

## Premiere Pro MCP test

Planned automated path (test harness only; end users import the `.cube` normally):

1. Open the test project through the Premiere MCP, import `work/src_frame.png` or the source clip, apply the candidate `.cube` as a Lumetri input LUT.
2. Export a still at a fixed timecode to `work/premiere_still.png`.
3. Run the script with `--premiere-still work/premiere_still.png` and record `premiere_vs_ffmpeg_tetrahedral` in the report.
4. Keep the still and the MCP session log as demo evidence.

If the MCP is flaky or version mismatched, drop to the manual checklist immediately: import the clip, apply the LUT through Lumetri, export frame, run the same command. The numeric claim is identical either way.

## Failure triage

- Python vs trilinear FAIL: check cube axis order (red fastest), `DOMAIN_MIN` or `DOMAIN_MAX` lines, 8-bit PNG rounding on gradients, and that the source PNG written by the script is the file FFmpeg read.
- Tetrahedral gap large: expected on high-chroma edges; inspect the max-ΔE pixels before changing the optimizer.
- Premiere FAIL with FFmpeg-internal pairs green: suspect Premiere input-range interpretation or Lumetri normalization settings first, then re-export with explicit Rec.709 tags.
