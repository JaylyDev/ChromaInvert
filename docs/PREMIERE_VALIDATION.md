# Premiere Pro Validation

Acceptance test for issue 4: the exported `.cube` grades the same inside Premiere Pro as in the engine and in FFmpeg.

## What is checked

`scripts/premiere_validation.py` grades one source image three ways and compares them:

1. Python `DifferentiableLUT3D` (trilinear, the optimization path).
2. FFmpeg `lut3d` with `interp=trilinear` (expected to match Python closely).
3. FFmpeg `lut3d` with `interp=tetrahedral` (FFmpeg default; used as a proxy for Premiere Pro and DaVinci Resolve, which are assumed to evaluate LUTs tetrahedrally; this is an unversioned assumption and must be confirmed with a real exported still).

A fourth optional comparison takes a still exported from Premiere and compares it against the FFmpeg tetrahedral render of the same source and cube.

Metrics per pair: mean, p50, p95, max DeltaE2000 plus mean and max absolute RGB difference and PSNR. DeltaE uses `linear_srgb_to_lab` plus `delta_e_2000` on every 16th pixel, the same sampling as the synthetic benchmark.

## Thresholds

- Python vs FFmpeg trilinear: mean DeltaE2000 at or under 1.0. Larger values mean an axis-order, range, or quantization bug, not interpolation.
- Premiere still vs FFmpeg tetrahedral: mean DeltaE2000 under 2.0 (hackathon plan Section 11 cross-tool agreement). A run without `--premiere-still` reports FFmpeg/Python agreement only and is not Premiere evidence.
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

For a meaningful end-to-end check, pass a cube produced by the engine rather than the synthetic default:

```
python -m chromainvert run work/job.json
python scripts/premiere_validation.py --cube work/out.cube --source work/src_frame.png
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

3. For S-Log3 or Apple Log clips, pass the raw log frame as the source: the exported host-domain cube already contains the log decode (see `docs/ARCHITECTURE.md` step 4), so pre-converting to Rec.709 would double-transform. Only a legacy `export_domain: working` cube needs a pre-converted source.

## Premiere Pro MCP test

Planned automated path (test harness only; end users import the `.cube` normally):

1. Open the test project through the Premiere MCP, import `work/src_frame.png` or the source clip, apply the candidate `.cube` as a Lumetri input LUT.
2. Export a still at a fixed timecode to `work/premiere_still.png`.
3. Run the script with `--premiere-still work/premiere_still.png` and record `premiere_vs_ffmpeg_tetrahedral` in the report.
4. Keep the still and the MCP session log as demo evidence.

If the MCP is flaky or version mismatched, drop to the manual checklist immediately: import the clip, apply the LUT through Lumetri, export frame, run the same command. The numeric claim is identical either way.

## Apple Log note (measured 2026-11-04)

On the `chromainvert_playground` project (Premiere Pro 2025.0, Windows, CEP MCP), the iPhone clip reports color space `Apple Log/Rec. 2020` via `get_color_space`, and Premiere color-manages it toward the Rec.709 sequence before Lumetri: the raw-log host cube (`work/apple_fix/fixed_apple_log.cube`, FFmpeg mean DeltaE2000 7.5 against the Premiere manual still) measured 31.9 to 32.0 in Premiere after a Lumetri Browse re-pick, because Lumetri receives the converted Rec.709 image, not log code values. Two host limits were measured at the same time: the MCP `apply_lut` tool is unavailable on CEP, and writing a new LUT path with `set_effect_property` updates the parameter string without reliably loading the LUT into the render (an identity and a channel-swap cube rendered identically), so every cube change in Premiere needs a manual Browse re-pick before exporting stills.

For a cube that matches inside Premiere with its default log handling, train in the domain Premiere actually feeds: export ungraded stills from Premiere itself (no LUT on the clip) as source frames and manual-grade stills as reference frames, run a `rec709` job on those PNGs, and apply the exported cube as the Lumetri Input LUT. Measured on this project that cube (`work/apple_fix/premiere_apple_log.cube`) scored mean DeltaE2000 7.28 and 7.38 against the manual stills at two source times, in line with the FFmpeg result for the raw-log cube. A vibrance follow-up on 2026-11-04 found the distribution-only cube undersaturated in Premiere (mean Oklab chroma 0.0416 against the manual 0.0434, chroma p90 about 9 percent low): an aligned-pair job (`weight_paired` 10, `weight_tv` 0.03, `weight_shadow` 0.05) plus a saturation-calibrated blend against a closed-loop variant landed at `work/apple_fix/premiere_apple_log_v5.cube`, measured in Premiere at mean DeltaE2000 6.06 and 6.11 with mean chroma within 3 percent of the manual stills. Premiere renders a given cube slightly darker than FFmpeg on the same frames, so judge Premiere cubes only by Premiere stills. Use the raw-log host cube (log `input_profile` job on FFmpeg-extracted frames) for FFmpeg, DaVinci Resolve, and any host that applies the LUT to log code values directly.

## Failure triage

- Python vs trilinear FAIL: check cube axis order (red fastest), `DOMAIN_MIN` or `DOMAIN_MAX` lines, 8-bit PNG rounding on gradients, and that the source PNG written by the script is the file FFmpeg read.
- Tetrahedral gap large: expected on high-chroma edges; inspect the max dE00 pixels before changing the optimizer.
- Premiere FAIL with FFmpeg-internal pairs green: suspect Premiere input-range interpretation or Lumetri normalization settings first, then re-export with explicit Rec.709 tags.
