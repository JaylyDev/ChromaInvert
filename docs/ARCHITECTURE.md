# ChromaInvert Architecture: Engine Contract

## Process model

The Electron GUI drives the Python engine as a subprocess. No shared memory, no embedded interpreter, no sockets.

```
app --writes--> work/job.json --reads--> chromainvert run work/job.json
                                   --writes--> work/out.cube, work/report.json
app --reads--> work/out.cube --applies--> FFmpeg lut3d preview and encode
```

`work/` is a gitignored runtime scratch directory. All job paths may be absolute or relative to the job file directory.

## job.json (contract_version 2)

Contract v2 is backwards compatible with v1; v1 jobs with `input_profile` `rec709`, `rec2020`, or `apple_log` still run when `contract_version` is 1 or 2. V2 adds bounded S-Log3 working-space support. `reference_only` jobs run under either version; the report records `mode` as `single_image` or `paired`.

| Key | Type | Default | Meaning |
|---|---|---|---|
| `contract_version` | int | required, must be 1 or 2 | schema version; 1 supports rec709, rec2020, and apple_log, 2 adds slog3 profiles with bounded working space |
| `source_frames` | list[str] | required | ungraded frames, 16-bit TIFF preferred (the imageio/Pillow reader downconverts 16-bit PNG to 8-bit, so use TIFF to keep precision); omit or leave empty when `reference_only` is true |
| `reference_frames` | list[str] | required | reference grade frames |
| `reference_only` | bool | `false` | predict the look from graded frames alone with the trained predictor; no source frames needed, `predict_weights` required |
| `predict_weights` | str | required with `reference_only` | path to a predictor checkpoint you trained yourself (no checkpoint is shipped; see `data/README.md` for training and picking the file in the app or via `--weights`) |
| `input_profile` | str | `rec709` | source frame decoding; `rec709` for display-referred Rec.709/sRGB, `rec2020` for display-referred Rec.2020 mapped to Rec.709, `apple_log` for Apple Log (Rec.2020) to bounded SDR working space, `slog3` or `slog3_sgamut3cine` for Sony S-Log3/S-Gamut3.Cine with bounded working-space transform |
| `reference_profile` | str | `rec709` for log input profiles, otherwise `input_profile` | reference frame decoding; graded reference frames (for example a manual grade exported from Premiere) are display-referred, so log sources default to `rec709` instead of decoding the graded export as log; set it explicitly only when the reference frames really use another profile |
| `weight_tv` / `weight_shadow` | float | `0.1` / `0.25` | optimizer loss weights, same meaning as in `OptimizeConfig`; lower values fit the reference distribution (including saturation) more closely at the cost of cross-content generalization |
| `export_target` | str | `log` | `log` bakes the cube for raw log code values (FFmpeg, Resolve); `premiere` requires `input_profile` `apple_log` and bakes it for what Premiere Pro feeds Lumetri after its Apple Log color management, using a 17-point display curve measured in Premiere 2025 (Rec.709 sequence); load it as the Lumetri Input LUT with the clip left on Apple Log |
| `weight_paired` | float | `0.0` | when positive, source and reference frames must be aligned pairs (same count and shapes) and an additional per-pixel Oklab MSE loss on corresponding pixels is added; use it when the reference is the same footage after grading, not for matching a look across different scenes |
| `coarse_size` | int | 17 | coarse optimization lattice |
| `lut_size` | int | 33 | exported lattice size |
| `iterations` | int | 400 | coarse Adam iterations |
| `fine_iterations` | int | 30 | fine Adam iterations after spline upsample |
| `strength` | float | 1.0 | blend of recovered LUT toward identity |
| `seed` | int | 42 | deterministic pixel sampling |
| `device` | str | `auto` | `auto`, `cuda`, or `cpu` |
| `deterministic` | bool | `false` | enable deterministic GPU mode |
| `output_cube` | str | required | exported `.cube` path |
| `report_json` | str | required | metrics report path |

`input_profile` aliases: `slog3`, `slog3_sgamut3cine`, `slog3_sgamut3.cine`, and `slog3_sgamut3_cine` all select the same S-Log3 bounded working-space pipeline. `input_profile` decodes source frames and `reference_profile` decodes reference frames; the defaults above cover the usual pair of log source plus display-referred graded reference, and any other mixed pair should set `reference_profile` explicitly.

## stdout protocol

The engine prints one JSON object per line, flushed:

- Progress: `{"event": "progress", "iter": 120, "iters": 450, "loss": 0.031, "elapsed_s": 1.8}`
- Success: `{"event": "done", "cube": "work/out.cube", "seconds": 4.2}` with exit code 0.

Failure is a nonzero exit with no `done` line and diagnostics on stderr. Hosts treat any run that ends without a `done` line as failed and surface the stderr tail.

## report.json

Final loss terms per name, `device` actually used, `seconds`, lattice stats (`lattice_min`, `lattice_max`, `max_neighbor_delta`), pixel counts, and library versions. `report.json` also records `contract_version`, `input_profile`, the resolved `reference_profile`, and `export_domain` (`host` or legacy `working`). Note the bug fix behind these fields changes v1 `apple_log` jobs that omit `reference_profile`: they now decode references as display Rec.709 and export a host-domain cube; add `"reference_profile": "apple_log"` to a v1 job to reproduce the old working-space behavior.

## Deterministic mode and variance note

GPU nondeterminism from `grid_sample` backward atomic adds and quantile ties on flat chart patches causes a 4-5 percent spread in improvement without deterministic mode (observed 41.9 to 46.2 percent, baseline 4.04 to recovered 2.17-2.35 mean DeltaE2000 across runs). CPU runs are deterministic by default.

Deterministic mode is best effort, not exact on CUDA. It is enabled via `job.json` with `deterministic: true` for `chromainvert run`, or via the `benchmark` subcommand flag `--deterministic` for `chromainvert benchmark`. It sets `CUBLAS_WORKSPACE_CONFIG=:4096:8` when absent (must be set before the first CUDA init) and calls `torch.use_deterministic_algorithms(True, warn_only=True)` (warn_only because the 3D LUT `grid_sample` backward has no deterministic CUDA kernel in current PyTorch), seeds torch, NumPy, Python random and CUDA, and disables cuDNN benchmarking. CPU repeats exactly under identical seeds; CUDA may still vary across identical seeded runs. Mode is process-global and sticky: once enabled it stays on for later calls in the same process. Performance tradeoff is a 10-30 percent slowdown. The report includes `deterministic`, `deterministic_warn_only`, `deterministic_cublas`, `deterministic_algorithms_enabled`, and a `variance_note` field describing this behavior.

The random-RGB probe heldout uses `is_probe_gate_pass`: pass when probe improvement reaches 0.4, or when recovered probe DeltaE is below 3.0 and strictly better than baseline. `run_benchmark` returns `probe_gate_pass` (alias `heldout_gate_pass` for compatibility), `chart_gate_pass`, combined `benchmark_gate_pass`, `heldout_gate_threshold` 0.4, and `heldout_gate_absolute` 3.0. The `benchmark` CLI exits 0 only when `benchmark_gate_pass` is true.

## Color pipeline

### 1. Frame loading and range handling

Frames are read with imageio and normalized to float code values in `[0, 1]`. For integer images the divisor is the dtype max (255 for 8-bit, 65535 for 16-bit), which assumes full-range RGB. Floating point images are taken as already in `[0, 1]`. Grayscale inputs are expanded to RGB by channel replication. Alpha is discarded.

Full-range versus limited-range: the engine assumes full-range code values where 0 maps to 0.0 and 1 maps to 1023 CV for S-Log3, and 0 maps to 0 and 1 maps to 1 for Rec.709. Frames extracted by the app via FFmpeg use `format=gbrp16le` which is full-range, so no range expansion is needed. Limited-range YUV sources (16 to 235/240) must be expanded to full-range RGB by the caller (for example FFmpeg `scale=in_range=limited:out_range=full`) before writing the TIFF; the engine does not guess and does not silently stretch.

### 2. Input profile decoding

`rec709`: `decode_input` applies `srgb_to_linear` (Rec.709/sRGB OETF inverse) to obtain display-referred linear light in `[0, 1]`. This path is unchanged from v1.

`rec2020`: `decode_input` applies `srgb_to_linear`, then `rec2020_to_rec709_linear` to map Rec.2020 primaries to Rec.709 linear, clipped to `[0, 1]`. Display-referred Rec.2020 footage is treated like Rec.709 with a gamut map; no HDR OETF is assumed.

`apple_log`: `decode_input` applies the Apple Log inverse OETF (`decode_apple_log` with the Apple Log Profile constants) to obtain linear Rec.2020, converts to linear Rec.709 via `rec2020_to_rec709_linear`, and clips to `[0, 1]` for a bounded SDR working space. Available under contract v1 and v2. This decodes source frames; reference frames use `reference_profile` (default `rec709` here, because graded references are display-referred).

`slog3` and `slog3_sgamut3cine`: `decode_input` performs the bounded S-Log3 working-space transform defined in `engine/src/chromainvert/color.py`:

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
   - This is monotonic, continuous, and invertible for `y` in `[0, 1)`; as `x` goes to infinity `y` approaches 1. Exposure is preserved at 1:1 below the knee, so 0.18 scene maps to 0.18 working space and 0.9 scene maps to 0.9 working space. Highlights above 0.9 are compressed into 0.9 to 1.0 with a shoulder of 0.15 that avoids banding and preserves detail that a hard clip would destroy.
   - Inverse: `bounded_to_linear` recovers scene linear for preview or debugging via `x = 0.9 + a * 0.15 / (1 - a)` where `a = (y - 0.9) / 0.1`. The bounded transform is optimization-internal; step 4 bakes the full decode into the exported host-domain cube, so no inverse is needed at runtime.

This bounded space keeps optimization in `[0, 1]` so Oklab, quantile, moment, covariance, and gamut losses remain well behaved on log footage.

### 3. Optimization

Optimization compares graded source against reference in Oklab with quantile and moment matching, TV smoothness on the lattice, an identity prior, skin chroma and shadow luminance anchors, and a gamut penalty. Losses operate on the decoded working-space values; for S-Log3 this is the bounded Rec.709 display-referred linear from step 2, so the recovered LUT maps bounded working-space colors to graded display colors in a single fixed function.

### 3b. Single-image prediction

`chromainvert predict image --weights /path/to/your/checkpoint.pt --profile rec709 --out out.cube` skips optimization: it extracts 38 grade statistics (per-channel mean, std, quantiles, Oklab moments, saturation) from the decoded graded frame and feeds them to a compact MLP that outputs a 17 x 17 x 17 residual lattice around identity, spline-upsampled to 33 and written as `.cube`. No checkpoint is shipped; you must train one on LUTs you own (see `data/README.md`): `scripts/make_training_data.py --data-dir data` builds `data/training_data.npz` from frames under `data/videos/` (by profile) and 33x LUTs under `data/luts/` plus mild synthetic grades, and `scripts/train_lut_predictor.py --data-dir data` writes a checkpoint (default `data/weights/predictor_rec709.pt`, overridable with `--out-weights`). Train only on LUTs you own or that are openly licensed, since a checkpoint distills its training LUTs. `run` jobs with `reference_only: true` pass the checkpoint you picked in the GUI weights field via `predict_weights` in the job file, so the app needs no source frames. Future GUI work will add a finished-video picker that extracts frames internally (currently pick frames). Measured in prior experiments on openly licensed data: unseen commercial LUT 4.5 to 4.7 mean style-probe DeltaE2000 against a 14.0 identity baseline; a mild Premiere Lumetri grade improves 16 percent over baseline.

### 4. Export

The recovered lattice is blended by `strength` toward identity in working space, then baked into a host-domain cube: each lattice node holds source code values as a host LUT receives them, so the baked value is `encode_input(graded_working(decode_input(node)))` with the source decode from `input_profile` and the display encode from `reference_profile`. The baked lattice is clamped to `[0, 1]` and written red-fastest per the IRIDAS/Adobe `.cube` subset, with `DOMAIN_MIN` and `DOMAIN_MAX` 0 to 1. Applying the exported cube directly to source footage therefore targets the graded reference without a separate decode step in the host; because hosts interpolate between lattice nodes in code space, saturated log colors carry some interpolation error versus a per-pixel decode (mean abs error under 0.02 on random codes for an identity Apple Log bake, with larger isolated errors on saturated colors). The one exception is a legacy job that sets `reference_profile` equal to a log `input_profile`: there is no display encoding for a log target, so the working-space lattice is exported unchanged and `report.json` records `export_domain` as `working` (otherwise `host`).

### 5. Preview

FFmpeg `lut3d` applies the exported host-domain cube directly to the source footage for preview and export: for Apple Log and S-Log3 sources the cube already contains the log decode and the display encode from step 4. Premiere Pro is not identical by construction: current Premiere builds recognize Apple Log clips (color space `Apple Log/Rec. 2020` in `get_color_space`) and color-manage them toward the Rec.709 sequence before Lumetri, so a cube that is correct in FFmpeg can still differ as a Lumetri Input LUT unless that conversion is accounted for; see `docs/PREMIERE_VALIDATION.md` for the still-based check.
