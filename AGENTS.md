# ChromaInvert

ChromaInvert is a perceptual video and LUT reverse-engineering engine. Matching the color grade of a reference film frame onto raw or log footage takes hours of manual curve tweaking, while AI style-transfer tools ruin video with flicker and pixel artifacts. ChromaInvert solves this with differentiable inverse rendering: instead of altering pixels directly, it runs source footage through a PyTorch-based trilinear 3D LUT shader, uses semantic cues to anchor skin tones and shadows, and optimizes the LUT lattice weights with gradient descent to match the reference's perceptual color distribution. In seconds it exports a smooth, industry-standard `.cube` file ready for Premiere Pro, DaVinci Resolve, FFmpeg, or mobile camera apps, with zero AI artifacts because the grade is one fixed function of color applied identically to every frame. Spline interpolation from camera-path math upsamples the 33 x 33 x 33 RGB lattice, and Premiere Pro MCPs validate the end-to-end pipeline.

## What this repo is

Python engine plus C++ desktop host monorepo. Python source lives under `engine/chromainvert/`, tests under `engine/tests/`. Planning docs live in `docs/`, helper scripts in `scripts/`, test footage notes in `assets/`, and the C++ app skeleton in `app/`. `work/` and `.venv/` are gitignored runtime and environment directories.

## Parts of the project

- `engine/chromainvert/cube.py`: `.cube` read/write, lattice reshape and validation. Red varies fastest in file order, matching FFmpeg `lut3d` expectations.
- `engine/chromainvert/lut_module.py`: `DifferentiableLUT3D`, the learnable `(1, 3, N, N, N)` volume sampled with `F.grid_sample`.
- `engine/chromainvert/color.py`: sRGB transfers, Oklab and CIE Lab conversion, DeltaE2000, Sony S-Log3 and Apple Log decode, `decode_input` for the `rec709`, `rec2020`, `slog3`, and `apple_log` profiles.
- `engine/chromainvert/losses.py`: quantile and moment distribution matching, covariance matching, TV smoothness, identity prior, skin and shadow anchors, gamut penalty.
- `engine/chromainvert/masks.py`: YCbCr skin heuristic and luminance shadow masks.
- `engine/chromainvert/spline.py`: separable Catmull-Rom upsampling for coarse-to-fine lattices.
- `engine/chromainvert/optimize.py`: Adam optimization loop with seeded pixel sampling, the `OptimizeConfig` weights, and the `deterministic` GPU mode flag.
- `engine/chromainvert/cli.py`: `chromainvert run job.json`, `chromainvert predict image`, and `chromainvert benchmark` entry points; `run` accepts `reference_only` jobs with `predict_weights`.
- `engine/chromainvert-engine.spec`: PyInstaller directory-bundle recipe exposing the same CLI (`run`, `predict`, `benchmark`); single-file is avoided because torch's cuDNN DLLs fail to extract from a onefile archive on Windows. Build on each release platform, staged via `scripts/build_engine_bundle.py`.
- `engine/chromainvert/lut_predictor.py`: single-image LUT predictor; 38 grade statistics plus a residual MLP around identity, 17 lattice spline-upsampled to 33. No checkpoint is shipped; checkpoints are never committed since they distill their training LUTs; see `data/README.md` and pass the file via `predict_weights` or `--weights`.
- `engine/chromainvert/benchmark.py`: synthetic ground-truth recovery benchmark (known LUT applied to test charts, recovered blind, scored with mean DeltaE2000) plus the seeded random-RGB probe heldout gate and `style_probe_metrics` for LUT-to-LUT comparison on a random probe.
- `app/CMakeLists.txt`: builds both the Win32 `ChromaInvert` desktop host and the `chromainvert-host` console driver (C++17, standard library only); the desktop target also compiles the shared `ffmpeg` module and `Preview` for the upcoming preview pane.
- `app/src/main.cpp`, `app/src/MainWindow.*`, `app/src/JobRunner.*`: Win32 desktop host fallback (file pickers, Match and Cancel, progress bar, log pane). JobRunner writes `job.json`, spawns the engine, parses stdout JSONL progress. Product GUI is Electron + React in `app/gui/` per `docs/GUI_DECISION.md`; no Qt port.
- `app/src/host_main.cpp`: `chromainvert-host run` and `preview` subcommands, flag parsing, frame extraction orchestration.
- `app/src/job_runner.h`, `app/src/job_runner.cpp`: `job.json` writer (contract v1), engine subprocess spawn with JSONL progress parsing, `report.json` summary.
- `app/src/ffmpeg.h`, `app/src/ffmpeg.cpp`: unified FFmpeg Level 1 module: `host::` helpers (ffprobe duration probe, frame extraction, `lut3d` preview encode) for the console driver plus the `Ffmpeg` class (rich ffprobe JSON parse, multi-frame extraction with 16-bit plus 8-bit fallback, `lut3d` preview with tetrahedral interp, before/after grab) with unquoted double-level `lut3d` path escaping and output-directory creation.
- `app/src/Preview.h`, `app/src/Preview.cpp`: graded preview encode plus before/after stills via the `Ffmpeg` class.
- `app/README.md`: Windows build and run steps for the Electron GUI, both C++ hosts, shared module notes, Level 2 plan.
- `app/gui/package.json`, `app/gui/vite.config.ts`, `app/gui/index.html`: Electron + React product GUI shell (Vite renderer, TypeScript, no Qt); ships `engine-bin/${os}` via `extraResources`, unpacks `ffmpeg-static`/`ffprobe-static` via `asarUnpack` with a per-platform ffprobe prune.
- `app/gui/engine-bin/`: per-platform bundled `chromainvert-engine` binaries (gitignored) plus README; every `dist*` script runs `scripts/ensure-engine-bin.js` so packaging succeeds with no binary staged.
- `app/gui/electron/main.ts`, `app/gui/electron/preload.ts`: Electron main (writes `job.json`, resolves engine/ffmpeg/ffprobe with bundled, PATH, then Python fallback, parses stdout JSONL progress) and preload bridge.
- `app/gui/electron/ffprobe-static.d.ts`: types the untyped `ffprobe-static` export (`ffmpeg-static` ships its own).
- `app/gui/src/App.tsx`, `app/gui/src/api.ts`, `app/gui/src/types.ts`: React one-screen GUI (inputs, reference-only predict mode, Match and Cancel, progress bar, status, log tail) on the preload bridge.
- `scripts/ffmpeg_helpers.py`: FFmpeg Level 1 subprocess helpers (ffprobe parse, 16-bit PNG frame extraction with 8-bit fallback, lut3d preview, before/after, EngineRunner, error surfaces).
- `docs/GUI_DECISION.md`: Electron + React product decision per issue #9 (Qt rejected for licensing, ImGui rejected as too developer focused, Win32 kept as fallback).
- `scripts/validate_cube.py`: FFmpeg `lut3d` acceptance check for exported cubes.
- `scripts/premiere_validation.py`: FFmpeg `lut3d` vs Python `DifferentiableLUT3D` comparison with tetrahedral gap check and optional Premiere still scoring.
- `scripts/run_benchmark.py`: runs the synthetic benchmark and writes `work/benchmark.json`.
- `scripts/run_demo.py`: demo dry run; extracts frames with FFmpeg, writes `work/demo/job.json`, runs the engine, grades a preview clip with `lut3d`, runs the synthetic benchmark, prints a timing table.
- `scripts/export_graded.py`: graded video export, applies a `.cube` with FFmpeg `lut3d` with quoting, CRF and Rec.709 tags; standalone and job.json driven.
- `docs/DEMO_SCRIPT.md`: 3 minute run-of-show with commands, timings, and failure lines, plus the real-footage quickstart.
- `scripts/validate_real_footage.py`: validates a real-footage cube (size, finiteness, range, neighbor delta, FFmpeg lut3d, informational effect-magnitude DeltaE).
- `scripts/make_reference_pairs.py`: builds graded eval pairs from SampleFootage clips and real `.cube` files via FFmpeg `lut3d`, writes `work/pairs/manifest.json`; `--working-synthesis` applies the LUT in decoded working space for rec709 clips.
- `scripts/evaluate_single_image.py`: paired recovery and predictor check on one manifest pair with style-probe and heldout DeltaE2000 plus baselines; `--weights` adds the predicted LUT comparison.
- `scripts/make_training_data.py`: builds predictor training data in working space (real frames graded with real 33x LUTs plus mild parametric grades and identity).
- `scripts/train_lut_predictor.py`: trains the predictor MLP with held-out LUT validation, writes weights plus metrics JSON.
- `scripts/build_engine_bundle.py`: builds the PyInstaller engine bundle and stages the `chromainvert-engine` directory into `app/gui/engine-bin/<platform>/`.
- `engine/tests/test_predict.py`: predict CLI and reference-only run acceptance, rejection, and weights requirement.
- `engine/tests/test_lut_predictor.py`: feature determinism, near-identity init, single-sample overfit, 17 to 33 upsample export.
- `scripts/extract_frames.py`: extracts N frames from a video via FFmpeg.
- `scripts/run_real_footage.py`: reusable driver for frame extraction, job creation, run, and validation with synthetic fallback.
- `engine/tests/test_real_footage.py`: real-footage CLI and optimize smoke tests.
- `engine/chromainvert/__main__.py`: enables `python -m chromainvert`.
- `assets/job.json.example`: tracked sample job for the real-footage CLI run.
- `docs/CHROMAINVERT_HACKATHON_PLAN.md`: full technical plan and team guide.
- `docs/ARCHITECTURE.md`: engine contract v2, backwards compatible with v1 (`job.json` schema, stdout JSONL protocol, `report.json` fields, color pipeline).
- `docs/PREMIERE_VALIDATION.md`: Premiere Pro MCP validation procedure, thresholds, and SampleFootage steps.
- `docs/PROGRESS.md`: timestamped build log, updated with every feature.
- `engine/tests/test_*.py`: one test module per engine module above; update both together.
- `.github/workflows/tests.yml`: CI workflow running `python -m pytest engine/tests -q` on Ubuntu plus an MSVC Release build of `app` on Windows, on push and pull request.
- `.github/workflows/gui.yml`: CI matrix on `windows-latest`, `macos-latest`, and `ubuntu-latest` running GUI `npm ci`, `typecheck`, `build`, and per-platform `electron-builder` packaging with artifact upload, on push and pull request.

## Build and run

From the repo root (Windows PowerShell):

- `python -m venv .venv --system-site-packages`: create the dev venv. It reuses the system GPU PyTorch install so no large CUDA download is needed.
- `.venv\Scripts\Activate.ps1`, then `python -m pip install -e ./engine`: install the engine editable.
- `python -m pytest engine/tests -q`: full engine test suite, must be green before any commit.
- `python scripts/validate_cube.py`: FFmpeg `lut3d` acceptance check, must print `PASS`.
- `python scripts/run_benchmark.py`: synthetic recovery benchmark, gates on 40 percent DeltaE2000 improvement.
- `python -m chromainvert run work/job.json`: optimize a LUT from a job file per `docs/ARCHITECTURE.md`.
- `cd app/gui && npm install && npm run typecheck`: GUI typecheck, must pass before any GUI commit.
- `cd app/gui && npm run build`: GUI production build (renderer plus Electron main), must succeed before any GUI commit.

## Workflow

- Version is `0.1.0` in `engine/pyproject.toml`; releases are tagged `v0.1.0`, `v0.2.0`, and so on.
- Use semantic commits with a scope on every commit: `type(scope): subject`. Scopes are `engine`, `app`, `scripts`, `docs`, or `repo`. Examples: `feat(engine): add covariance matching loss`, `fix(scripts): quote ffmpeg filter path`, `chore(repo): harden packaging metadata`, `docs(plan): clarify tetrahedral check`.
- Only commit when a new feature is implemented.
- Append each milestone to `docs/PROGRESS.md` in the same commit.
- When a new important file is created (engine module, script, doc, app source), record it under Parts of the project in the same commit. Scratch files in `work/`, `__pycache__/`, and `*.egg-info/` are never logged.
- Before submitting every commit, spawn a subagent on `meta/muse-wonder-1.0` to review the changed files as a council; argue to agreement and implement the feedback first.

## Conventions

- No emojis anywhere in the codebase, including docs and user-facing strings; Minecraft does not render them.
- No em-dashes in files; use colons or semicolons instead.
- Follow the `jayly-guidelines` skill for code changes: minimal code, surgical edits, explicit types, no speculative `try/catch`.
