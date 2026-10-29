# ChromaInvert Progress Log

## 2026-10-29: Bounded S-Log3 working space (issue 6)

Completed:
- Added bounded S-Log3/S-Gamut3.Cine working space in `engine/chromainvert/color.py`: `decode_slog3` to scene linear, `sgamut3cine_to_rec709` matrix to Rec.709 linear, then `linear_to_bounded` soft highlight compression (identity at 0.9 and below, smooth shoulder to 1.0 above) so optimization stays in `[0, 1]` with no hard clipping. `bounded_to_linear` provides the documented inverse for preview or debugging.
- `decode_input` accepts `slog3` plus `slog3_sgamut3cine`, `slog3_sgamut3.cine`, and `slog3_sgamut3_cine` aliases; `cli.py` accepts contract versions 1 and 2 and the same profiles, recording both in `report.json`.
- Updated `docs/ARCHITECTURE.md` to contract v2 with the working-space math, full-range versus limited-range note, and the S-Log3 preview pipeline.
- Added unit tests on known curve values (0.18 maps to 420/1023 code, 0.9 to 598/1023, 1.0 code to about 38.4 linear), neutral gamut preservation, bounded monotonicity and invertibility, alias equivalence, CLI acceptance, and v1 backwards compatibility.

Verified:
- `python -m pytest engine/tests -q`: 59 passed.
- `python scripts/validate_cube.py`: PASS.
- Real S-Log3 footage (`Slog3 -proress 444.mov` frame via FFmpeg `gbrp16le` TIFF): unbounded decode peaked at 2.39 linear, bounded working space decodes to [0.02, 0.99]; end-to-end `slog3` job (contract 2) emits progress and done events plus `out.cube` and `report.json`.

## 2026-10-29: Demo script and dry run

Completed:
- Added `docs/DEMO_SCRIPT.md`: 3 minute run-of-show (problem 20 s, live run 60 s, portability 45 s, numbers 30 s, close 25 s) with the one-command dry run, failure lines, and Resolve plus Premiere proof steps.
- Added `scripts/run_demo.py`: extracts source and reference frames with FFmpeg, writes `work/demo/job.json` (contract v1, rec709), runs `chromainvert run`, grades a preview clip with `lut3d`, runs the synthetic benchmark, writes `timings.json` and prints a timing table.
- Updated `assets/SOURCES.md` with the local SampleFootage entries (Rec709, Apple Log, S-log3) and the rec709-only contract note.
- Recorded `scripts/run_demo.py` and `docs/DEMO_SCRIPT.md` under Parts of the project in `AGENTS.md`.
- Council review (Muse Wonder) before this commit requested streaming JSONL progress, the absolute workdir fix, repo-root FFmpeg paths, and the measured dry-run numbers; applied all four.

## 2026-10-29: Fix, premiere_validation council review

Completed:
- Fixed `de00_stats` in `scripts/premiere_validation.py` to decode sRGB before CIE Lab, so the reported numbers are real DeltaE2000 instead of a gamma-distorted metric.
- Re-read the written source and Python-graded PNGs so all three renders share identical 8-bit quantization, removing representation bias from the gate.
- Made `rgb_stats` emit a finite PSNR (99.0 dB sentinel for identical images) and serialized the report with `allow_nan=False`.
- Added shape and emptiness validation in `de00_stats`, `rgb_stats`, and `compare_pair`, with a graceful FAIL report for mismatched Premiere stills.
- Rejected cubes with non-default `DOMAIN_MIN`/`DOMAIN_MAX` and missing `ffmpeg` with a clear FAIL instead of a traceback.
- Aligned the Premiere threshold comparison with the docs ("under 2.0") and marked reports/runs where Premiere was not actually tested.
- Softened the tetrahedral claim in `docs/PREMIERE_VALIDATION.md` to a stated proxy assumption and added an end-to-end command using an engine-generated cube.
- Added `engine/tests/test_premiere_validation.py` (6 tests, including an FFmpeg integration test).

Verified:
- `python -m pytest engine/tests -q`: 52 passed.
- `python scripts/validate_cube.py`: PASS.
- `python scripts/premiere_validation.py` on synthetic chart: PASS (python vs trilinear mean 0.224; tetrahedral gap mean 0.007, max 1.079).

## 2026-10-29: Fix, harden premiere_validation I/O

Completed:
- Hardened `read_rgb` in `scripts/premiere_validation.py` to handle grayscale and 16-bit inputs (dtype-aware scaling, channel expansion), matching `load_frames` in `engine/chromainvert/cli.py`.
- Hardened `write_rgb` to create parent directories and expand grayscale images to RGB.
- Ensured `main()` creates the output report's parent directory.
- Verified `python scripts/premiere_validation.py` still prints PASS and the full engine suite stays green.

## 2026-10-29: Feature, Premiere Pro validation run

Completed:
- Added `scripts/premiere_validation.py`: grades one source three ways (Python `DifferentiableLUT3D` trilinear, FFmpeg `lut3d` trilinear, FFmpeg `lut3d` tetrahedral), scores each pair with mean/p50/p95/max DeltaE2000 plus RGB diff and PSNR, and optionally scores a Premiere exported still against the FFmpeg tetrahedral render. Writes `work/premiere_validation.json`, exits 0 on PASS.
- Added `docs/PREMIERE_VALIDATION.md`: thresholds (Python vs trilinear mean at or under 1.0; Premiere vs FFmpeg tetrahedral under 2.0), synthetic and SampleFootage run commands, MCP test steps with manual fallback, failure triage.
- Recorded both files under Parts of the project in `AGENTS.md`.

Verified:
- `python -m pytest engine/tests -q`: 46 passed.
- `python scripts/validate_cube.py`: PASS.
- `python scripts/run_demo.py` on SampleFootage (Rec709 `A001_10290006_C101.mov` source, Apple Log `A001_10290006_C100.mov` reference, canonical 400 plus 30): extract 2.9 s, optimize 12.5 s, export 6.9 s, benchmark 6.3 s, total 31.1 s on CUDA.
- Demo benchmark: baseline 4.04, recovered 2.06 mean DeltaE2000, improvement 48.9 percent (gate 40 percent).
- `work/demo/out.cube`, `work/demo/graded.mp4`, `work/demo/before.png`, `work/demo/after.png`, `work/demo/report.json` all written; max_neighbor_delta 0.161.

Decisions locked:
- Contract v1 stays rec709-only for the demo; log footage is decoded as display-referred with an on-screen note until the bounded log working-space milestone lands.

Next steps:
- Rehearse the run-of-show on the demo machine and replace the timing numbers; precompute a fallback `work/demo` folder for the failure lines.
- `python scripts/premiere_validation.py` on synthetic chart: PASS (python vs trilinear mean 0.232; tetrahedral gap mean 0.008, max 1.973).
- Same script on Rec.709 SampleFootage frame (`A001_10290006_C101.mov` at 1s): PASS (python vs trilinear mean 0.258; tetrahedral gap mean 0.015, max 1.897).
- Identity cube plus FFmpeg tetrahedral output as `--premiere-still`: PASS (premiere pair mean 0.000).

## 2026-10-27: CI, GitHub Actions test workflow

Completed:
- Added `.github/workflows/tests.yml`: checkout, setup-python 3.11 with pip cache, install `./engine[dev]`, run `python -m pytest engine/tests -q` on push and pull request. Pins `actions/checkout@v7` and `actions/setup-python@v7` (Node 24 runtime).
- Recorded the workflow under Parts of the project in `AGENTS.md`.
- Council review (Muse Wonder) before this commit requested Node 24 action majors instead of v4/v5; verified the current latest is v7 and applied it with explicit `cache-dependency-path` and a quoted extra.

Verified:
- `python -m pytest engine/tests -q`: 46 passed.
- Workflow YAML parses with `yaml.safe_load`.

## 2026-10-27: Hackathon plan drafted

Completed:
- Added `docs/CHROMAINVERT_HACKATHON_PLAN.md`: detailed plan extending the initial 3D LUT pipeline spec (product definition, honest problem framing, MVP/Target/Stretch scope, C++/Python contract, engine plan, app plan, spline component, validation and Premiere Pro MCP testing, metrics, team workflow, 36h timeline, risks, demo script, pre-hackathon checklist, open questions).
- Repo state verified: branch `main`, one commit (`Initial commit`), remote `origin` is `https://github.com/JaylyDev/ChromaInvert.git`.

Decisions locked:
- Subprocess plus files interface (job.json in, JSONL progress plus report.json plus .cube out). No embedded Python for the hackathon.
- Vertical slice first: .cube round trip, identity forward pass, benchmark recovery, then GUI wiring.

Next steps:
- Feature: end-to-end CLI run on real footage plus FFmpeg graded-video export, then the C++ host.

## 2026-10-27: Feature, LUT optimization loop with CLI and synthetic benchmark

Completed:
- Added `engine/chromainvert/optimize.py` (`OptimizeConfig`, seeded sampling, affine warm start, coarse Adam plus spline upsample plus fine Adam, progress callback, report dict).
- Added `engine/chromainvert/cli.py` (`chromainvert run job.json`, `chromainvert benchmark`), `docs/ARCHITECTURE.md` (contract v1), `scripts/run_benchmark.py`, tests for optimizer smoke and synthetic recovery.
- Added `covariance_loss` and a NaN-safe cube-root autograd function in `losses.py`.
- Added `AGENTS.md` (repo context, scoped semantic commits, file-log rule) per user request.

Verified:
- `python -m pytest engine/tests -q`: 46 passed.
- `python scripts/validate_cube.py`: PASS.
- `python scripts/run_benchmark.py` on GPU, canonical config: baseline 4.04, recovered 2.17 to 2.35 mean DeltaE2000, improvement 41.9 to 46.2 percent across runs (bar 40 percent), PSNR about 31 dB, about 6 s. Run-to-run spread comes from GPU atomic nondeterminism in grid_sample backward and quantile ties on flat chart patches; the CPU regression test is deterministic.

Tuning notes:
- Pure distribution matching is underdetermined; covariance matching plus affine warm start plus skin and shadow anchors were needed to generalize.
- Exact-zero blacks gave infinite cube-root gradients on GPU (NaN at iter 2). Fixed with half-LSB dither on samples and a sign-correct capped custom backward (derivative is positive on both sides; cap 1e4, exact zero maps to 0).
- Default lr 0.02 diverged at production scale (loss 0.05 to 0.83); lr 0.01 converges. Fine 50 overfit; fine 30 generalizes best at production scale.
- Contract v1 is rec709-only: S-Log3 decodes highlights up to 38x linear with no bounded working-space design, so the CLI rejects it instead of silently clipping. 16-bit TIFF is the preferred frame format because the Pillow reader downconverts 16-bit PNG to 8-bit.
- Council review (Muse Wonder) before this commit found and fixed: cube-root sign bug, covariance normalization on unequal counts, silent device fallback, stage-anchored identity prior, late strength validation, entry-point dependency gap, plus contract default alignment and test hardening.

## 2026-10-27: Feature 2, DifferentiableLUT3D identity module

Completed:
- Added `engine/chromainvert/lut_module.py` with `DifferentiableLUT3D`: learnable `(1, 3, N, N, N)` volume sampled with `F.grid_sample` trilinear, identity initialization, `lattice()` accessor returning `(N, N, N, 3)` in `.cube` file order.
- Added `engine/tests/test_lut_identity.py`.

Verified:
- `python -m pytest engine/tests -q`: 8 passed. Identity forward reproduces a random image within 1e-5, corners are exact, gradients flow to the volume, and the module lattice round-trips through `.cube` export.

## 2026-10-27: Feature 1, .cube read/write engine

Completed:
- Added `engine/chromainvert/cube.py` with `CubeLut`, `identity_lattice`, `write_cube`, `read_cube`. Red varies fastest in file order, matching FFmpeg `lut3d` expectations. Writer clamps to [0, 1].
- Added `engine/tests/test_cube_roundtrip.py`, `scripts/validate_cube.py`, plus project skeleton (`README.md`, `.gitignore`, `engine/pyproject.toml`, `assets/SOURCES.md`).

Verified:
- `python -m pytest engine/tests -q`: 5 passed (round trip at sizes 2, 17, 33, axis order, domain, rejection of bad files, writer validation).
- `python scripts/validate_cube.py`: PASS. Identity 33 LUT applied with FFmpeg `lut3d` gives pixel-identical output (peak diff 0.0). Channel-swap LUT turns pure red into blue, confirming lattice axis order matches FFmpeg.

## 2026-10-29: Feature, deterministic GPU mode and random-RGB probe heldout gate

Completed:
- Added `deterministic: bool = False` to `OptimizeConfig` and `enable_deterministic(seed)` in `engine/chromainvert/optimize.py`: sets `CUBLAS_WORKSPACE_CONFIG`, toggles torch deterministic algorithms and cuDNN flags, returns status dict.
- `optimize_lut` seeds torch/numpy/python/random/cuda when deterministic, records `deterministic` and `variance_note` in report.
- Added `random_rgb_probe`, `heldout_probe_metrics`, `mean_de00_full` to `engine/chromainvert/benchmark.py`; `run_benchmark` now accepts `deterministic`, `probe_count`, `probe_seed` and returns probe metrics plus `heldout_gate_pass`.
- CLI `run` reads `deterministic` from job.json; `benchmark` gains `--deterministic`, `--probe-count`, `--probe-seed`; gates on both chart and probe improvement.
- `scripts/run_benchmark.py` forwards the new flags.
- Added `engine/tests/test_deterministic_heldout.py`.

Verified:
- `python -m pytest engine/tests -q`: 55 passed.
- Deterministic GPU mode uses `torch.use_deterministic_algorithms(True, warn_only=True)` because the 3D LUT `grid_sample` backward has no deterministic CUDA kernel; cuDNN benchmarking disabled.

## 2026-10-29: Review, deterministic GPU followup and probe gate cleanup

Completed:
- Removed duplicate and placeholder tests in `engine/tests/test_deterministic_heldout.py`; kept six focused tests for probe determinism, gate failure on identity, config default, CPU deterministic status, and benchmark probe keys.
- Simplified `cmd_benchmark` in `engine/chromainvert/cli.py` to use direct argparse attributes.
- Updated `AGENTS.md` Parts of the project for the `deterministic` flag in `optimize.py` and the probe heldout gate in `benchmark.py`.

Verified:
- `python -m pytest engine/tests -q`: 52 passed.
- `python scripts/validate_cube.py`: PASS.
- Rec709 SampleFootage smoke test: extracted 320x180 PNG frames with FFmpeg, ran `chromainvert run` with `deterministic: true` on CPU, report records `deterministic: true` with variance note and exports a valid cube.
- Synthetic probe smoke test on CPU: probe gate reports baseline and recovered DeltaE with `heldout_gate_pass`, `probe_count`, and `probe_seed` in `work/benchmark.json`.

## 2026-10-29: Review, Wonder findings for deterministic best effort and probe gate

Completed:
- Moved all seeding into `enable_deterministic(seed)` in `engine/chromainvert/optimize.py`; report now includes `deterministic_warn_only`, `deterministic_cublas`, and `deterministic_algorithms_enabled` with a best-effort variance note (CPU exact, CUDA may still vary; mode is process-global and sticky).
- Added `is_probe_gate_pass` in `engine/chromainvert/benchmark.py`: absolute fallback now requires strict improvement over baseline; `run_benchmark` returns `probe_gate_pass`, `chart_gate_pass`, `benchmark_gate_pass`, and `heldout_gate_absolute`; unified `mean_de00` stride and validated `probe_count`.
- `engine/chromainvert/cli.py` and `scripts/run_benchmark.py` exit on `benchmark_gate_pass`.
- Reworked `engine/tests/test_deterministic_heldout.py` to exercise production paths: CPU repeat equality, gate helper pass and fail, probe seed forwarding, deterministic forwarding, and CLI wiring.

