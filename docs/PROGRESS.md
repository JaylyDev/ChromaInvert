# ChromaInvert Progress Log

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

## 2026-10-29: Feature, Real-footage CLI run and validation

Completed:
- Added `engine/chromainvert/__main__.py` so `python -m chromainvert` works.
- Extracted 3 source frames from Rec709 clip `A001_10290006_C101.mov` into `work/frames/source/`.
- Created warm graded reference frames `work/frames/reference/ref_001.png` and `ref_002.png`.
- Added `assets/job.json.example` (tracked sample; contract v1, rec709, coarse 17, lut 33, 150 + 30 iters). The scratch `work/job.json` used for the live run is gitignored.
- Added `scripts/validate_real_footage.py`: reads cube, checks size, finiteness, range, neighbor delta, title, domain, FFmpeg lut3d, DeltaE effect magnitude.
- Set LUT title to `ChromaInvert` in `engine/chromainvert/cli.py` so exported cubes carry a non-empty title.
- Added `scripts/extract_frames.py` and `scripts/run_real_footage.py` (frame extraction, job creation, run, validation, synthetic fallback).
- Added `docs/DEMO_SCRIPT.md` and README real-footage quickstart.
- Added `engine/tests/test_real_footage.py` (8-bit PNG handling, optimize + CLI smoke).

Verified:
- `python -m chromainvert run work/job.json`: done in 4.47s, `work/out.cube` (33), `work/report.json` (device cuda, clamped cube 0.0 to 1.0, max_neighbor_delta 0.1395).
- `python scripts/validate_cube.py`: PASS.
- `python scripts/validate_real_footage.py work/out.cube work/frames/source/source_001.png`: PASS (effect magnitude dE00 10.8139, informational).
- `python scripts/run_benchmark.py`: improvement reported, no regression.
- `python -m pytest engine/tests -q`: 49 passed.

