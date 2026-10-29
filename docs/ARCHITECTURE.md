# ChromaInvert Architecture: Engine Contract

## Process model

The C++ desktop host drives the Python engine as a subprocess. No shared memory, no embedded interpreter, no sockets.

```
app --writes--> work/job.json --reads--> chromainvert run work/job.json
                                   --writes--> work/out.cube, work/report.json
app --reads--> work/out.cube --applies--> FFmpeg lut3d preview and encode
```

`work/` is a gitignored runtime scratch directory. All job paths may be absolute or relative to the job file directory.

## job.json (contract_version 1)

| Key | Type | Default | Meaning |
|---|---|---|---|
| `contract_version` | int | required, must be 1 | schema version |
| `source_frames` | list[str] | required | ungraded frames, 16-bit TIFF preferred (the imageio/Pillow reader downconverts 16-bit PNG to 8-bit, so use TIFF to keep precision) |
| `reference_frames` | list[str] | required | reference grade frames |
| `input_profile` | str | `rec709` | frame decoding; contract v1 supports `rec709` and `apple_log`; `slog3` stays rejected until a bounded log working space is designed |
| `coarse_size` | int | 17 | coarse optimization lattice |
| `lut_size` | int | 33 | exported lattice size |
| `iterations` | int | 400 | coarse Adam iterations |
| `fine_iterations` | int | 30 | fine Adam iterations after spline upsample |
| `strength` | float | 1.0 | blend of recovered LUT toward identity |
| `seed` | int | 42 | deterministic pixel sampling |
| `device` | str | `auto` | `auto`, `cuda`, or `cpu` |
| `output_cube` | str | required | exported `.cube` path |
| `report_json` | str | required | metrics report path |

## stdout protocol

The engine prints one JSON object per line, flushed:

- Progress: `{"event": "progress", "iter": 120, "iters": 450, "loss": 0.031, "elapsed_s": 1.8}`
- Success: `{"event": "done", "cube": "work/out.cube", "seconds": 4.2}` with exit code 0.

Failure is a nonzero exit with no `done` line and diagnostics on stderr. Hosts treat any run that ends without a `done` line as failed and surface the stderr tail.

## report.json

Final loss terms per name, `device` actually used, `seconds`, lattice stats (`lattice_min`, `lattice_max`, `max_neighbor_delta`), pixel counts, and library versions.

## Color pipeline

1. Frames load as display-referred values in `[0, 1]`. The `rec709` profile applies `srgb_to_linear`. The `apple_log` profile applies the Apple Log inverse OETF (Rec.2020 primaries), converts linear Rec.2020 to linear Rec.709, and clips to `[0, 1]` for a bounded SDR working space. S-Log3 decoding exists in `color.py` but its HDR range has no bounded working-space design yet, so the CLI refuses it rather than silently clipping highlights.
2. Optimization compares graded source against reference in Oklab with quantile and moment matching, TV smoothness on the lattice, an identity prior, skin chroma and shadow luminance anchors, and a gamut penalty.
3. The recovered lattice is blended by `strength` toward identity, clamped to `[0, 1]`, and written red-fastest per the IRIDAS/Adobe `.cube` subset.
4. FFmpeg `lut3d` applies the same file for preview and export, so the in-app result matches DaVinci Resolve and Premiere Pro by construction.
