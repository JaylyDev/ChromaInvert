# ChromaInvert Architecture: Engine Contract

## Process model

The C++ desktop host drives the Python engine as a subprocess. No shared memory, no embedded interpreter, no sockets.

```
app --writes--> work/job.json --reads--> chromainvert run work/job.json
                                   --writes--> work/out.cube, work/report.json
app --reads--> work/out.cube --applies--> FFmpeg lut3d preview and encode
```

`work/` is a gitignored runtime scratch directory. All job paths may be absolute or relative to the job file directory.

## job.json (contract_version 2)

Contract v2 is backwards compatible with v1; v1 jobs with `input_profile: rec709` still run when `contract_version` is 1 or 2. V2 adds bounded S-Log3 working-space support.

| Key | Type | Default | Meaning |
|---|---|---|---|
| `contract_version` | int | required, must be 1 or 2 | schema version; 1 supported rec709 only, 2 adds slog3 profiles with bounded working space |
| `source_frames` | list[str] | required | ungraded frames, 16-bit TIFF preferred (the imageio/Pillow reader downconverts 16-bit PNG to 8-bit, so use TIFF to keep precision) |
| `reference_frames` | list[str] | required | reference grade frames |
| `input_profile` | str | `rec709` | frame decoding; `rec709` for display-referred Rec.709/sRGB, `slog3` or `slog3_sgamut3cine` for Sony S-Log3/S-Gamut3.Cine with bounded working-space transform |
| `coarse_size` | int | 17 | coarse optimization lattice |
| `lut_size` | int | 33 | exported lattice size |
| `iterations` | int | 400 | coarse Adam iterations |
| `fine_iterations` | int | 30 | fine Adam iterations after spline upsample |
| `strength` | float | 1.0 | blend of recovered LUT toward identity |
| `seed` | int | 42 | deterministic pixel sampling |
| `device` | str | `auto` | `auto`, `cuda`, or `cpu` |
| `output_cube` | str | required | exported `.cube` path |
| `report_json` | str | required | metrics report path |

`input_profile` aliases: `slog3`, `slog3_sgamut3cine`, `slog3_sgamut3.cine`, and `slog3_sgamut3_cine` all select the same S-Log3 bounded working-space pipeline. The profile applies to both source and reference frames; mixed-profile jobs should pre-convert outside the engine.

## stdout protocol

The engine prints one JSON object per line, flushed:

- Progress: `{"event": "progress", "iter": 120, "iters": 450, "loss": 0.031, "elapsed_s": 1.8}`
- Success: `{"event": "done", "cube": "work/out.cube", "seconds": 4.2}` with exit code 0.

Failure is a nonzero exit with no `done` line and diagnostics on stderr. Hosts treat any run that ends without a `done` line as failed and surface the stderr tail.

## report.json

Final loss terms per name, `device` actually used, `seconds`, lattice stats (`lattice_min`, `lattice_max`, `max_neighbor_delta`), pixel counts, and library versions. `report.json` also records `contract_version` and `input_profile` as received.

## Color pipeline

### 1. Frame loading and range handling

Frames are read with imageio and normalized to float code values in `[0, 1]`. For integer images the divisor is the dtype max (255 for 8-bit, 65535 for 16-bit), which assumes full-range RGB. Floating point images are taken as already in `[0, 1]`. Grayscale inputs are expanded to RGB by channel replication. Alpha is discarded.

Full-range versus limited-range: the engine assumes full-range code values where 0 maps to 0.0 and 1 maps to 1023 CV for S-Log3, and 0 maps to 0 and 1 maps to 1 for Rec.709. Frames extracted by the app via FFmpeg use `format=gbrp16le` which is full-range, so no range expansion is needed. Limited-range YUV sources (16 to 235/240) must be expanded to full-range RGB by the caller (for example FFmpeg `scale=in_range=limited:out_range=full`) before writing the TIFF; the engine does not guess and does not silently stretch.

### 2. Input profile decoding

`rec709`: `decode_input` applies `srgb_to_linear` (Rec.709/sRGB OETF inverse) to obtain display-referred linear light in `[0, 1]`. This path is unchanged from v1.

`slog3` and `slog3_sgamut3cine`: `decode_input` performs the bounded S-Log3 working-space transform defined in `engine/chromainvert/color.py`:

1. S-Log3 decode: Sony published curve from code in `[0, 1]` (0 to 1023 CV) to scene-referred linear reflection. Middle gray 0.18 maps to 420/1023 code, 0.9 reflectance to 598/1023, and 1.0 code to about 38.4 linear. Values below the knee (code < 171.21/1023) use the linear toe.
2. Gamut matrix: S-Gamut3.Cine primaries to Rec.709 linear via the matrix derived from Sony primaries and colour-science data. The matrix preserves neutrals (row sums about 1) and is:
   ```
   [[ 1.62668883, -0.54005271, -0.08679511],
    [-0.17851985,  1.41797367, -0.23943090],
    [-0.04444677, -0.19596694,  1.24065373]]
   ```
   This maps S-Gamut3.Cine linear to Rec.709 linear. The `slog3` alias assumes this gamut; there is no separate Rec.709-only S-Log3 matrix because Sony S-Log3 footage is normally S-Gamut3.Cine.
3. Bounded highlight handling: scene linear can be up to 38 and negative after the gamut matrix for out-of-gamut colors. The pipeline first clamps negatives to 0, then applies a soft highlight compression to map HDR into bounded `[0, 1]` without hard clipping:
   - For `x <= 0.9`: `y = x` (identity, so midtones and 90 percent white are untouched).
   - For `x > 0.9`: `y = 0.9 + 0.1 * (x - 0.9) / (x - 0.9 + 0.15)`
   - This is monotonic, smooth, and invertible; as `x` goes to infinity `y` approaches 1. Exposure is preserved at 1:1 below the knee, so 0.18 scene maps to 0.18 working space and 0.9 scene maps to 0.9 working space. Highlights above 0.9 are compressed into 0.9 to 1.0 with a shoulder of 0.15 that avoids banding and preserves detail that a hard clip would destroy.
   - Inverse: `bounded_to_linear` recovers scene linear for preview or debugging via `x = 0.9 + a * 0.15 / (1 - a)` where `a = (y - 0.9) / 0.1`. The forward is documented as working-space only; the exported `.cube` operates in the bounded display-referred domain and does not need the inverse at runtime.

This bounded space keeps optimization in `[0, 1]` so Oklab, quantile, moment, covariance, and gamut losses remain well behaved on log footage.

### 3. Optimization

Optimization compares graded source against reference in Oklab with quantile and moment matching, TV smoothness on the lattice, an identity prior, skin chroma and shadow luminance anchors, and a gamut penalty. Losses operate on the decoded working-space values; for S-Log3 this is the bounded Rec.709 display-referred linear from step 2, so the recovered LUT maps bounded working-space colors to graded display colors in a single fixed function.

### 4. Export

The recovered lattice is blended by `strength` toward identity, clamped to `[0, 1]`, and written red-fastest per the IRIDAS/Adobe `.cube` subset. `DOMAIN_MIN` and `DOMAIN_MAX` remain 0 to 1 because the working space is already bounded.

### 5. Preview

FFmpeg `lut3d` applies the same file for preview and export, so the in-app result matches DaVinci Resolve and Premiere Pro by construction. For S-Log3 sources the preview pipeline is: decode S-Log3 to bounded working space, apply `out.cube`, display as Rec.709. No additional inverse is needed because the LUT was optimized in that bounded domain.
