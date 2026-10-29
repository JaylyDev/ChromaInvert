# ChromaInvert

ChromaInvert is a perceptual video and LUT reverse-engineering engine. Matching the color grade of a reference film frame onto raw or log footage takes hours of manual curve tweaking, while AI style-transfer tools ruin video with flicker and pixel artifacts. ChromaInvert solves this with differentiable inverse rendering: instead of altering pixels directly, it runs source footage through a PyTorch-based trilinear 3D LUT shader, uses semantic cues to anchor skin tones and shadows, and optimizes the LUT lattice weights with gradient descent to match the reference's perceptual color distribution. In seconds it exports a smooth, industry-standard `.cube` file ready for Premiere Pro, DaVinci Resolve, FFmpeg, or mobile camera apps, with zero AI artifacts because the grade is one fixed function of color applied identically to every frame. Spline interpolation from camera-path math upsamples the 33 x 33 x 33 RGB lattice, and Premiere Pro MCPs validate the end-to-end pipeline.

## What this repo is

Python engine plus C++ desktop host monorepo. Python source lives under `engine/chromainvert/`, tests under `engine/tests/`. Planning docs live in `docs/`, helper scripts in `scripts/`, test footage notes in `assets/`, and the C++ app skeleton in `app/`. `work/` and `.venv/` are gitignored runtime and environment directories.

## Parts of the project

- `engine/chromainvert/cube.py`: `.cube` read/write, lattice reshape and validation. Red varies fastest in file order, matching FFmpeg `lut3d` expectations.
- `engine/chromainvert/lut_module.py`: `DifferentiableLUT3D`, the learnable `(1, 3, N, N, N)` volume sampled with `F.grid_sample`.
- `engine/chromainvert/color.py`: sRGB transfers, Oklab and CIE Lab conversion, DeltaE2000, Sony S-Log3 decode, `decode_input` for the `rec709` and `slog3` profiles.
- `engine/chromainvert/losses.py`: quantile and moment distribution matching, covariance matching, TV smoothness, identity prior, skin and shadow anchors, gamut penalty.
- `engine/chromainvert/masks.py`: YCbCr skin heuristic and luminance shadow masks.
- `engine/chromainvert/spline.py`: separable Catmull-Rom upsampling for coarse-to-fine lattices.
- `engine/chromainvert/optimize.py`: Adam optimization loop with seeded pixel sampling and the `OptimizeConfig` weights.
- `engine/chromainvert/cli.py`: `chromainvert run job.json` and `chromainvert benchmark` entry points.
- `engine/chromainvert/benchmark.py`: synthetic ground-truth recovery benchmark (known LUT applied to test charts, recovered blind, scored with mean DeltaE2000).
- `app/`: C++ desktop host skeleton (FFmpeg pipeline, preview UI). Not yet implemented.
- `scripts/validate_cube.py`: FFmpeg `lut3d` acceptance check for exported cubes.
- `scripts/premiere_validation.py`: FFmpeg `lut3d` vs Python `DifferentiableLUT3D` comparison with tetrahedral gap check and optional Premiere still scoring.
- `scripts/run_benchmark.py`: runs the synthetic benchmark and writes `work/benchmark.json`.
- `docs/CHROMAINVERT_HACKATHON_PLAN.md`: full technical plan and team guide.
- `docs/ARCHITECTURE.md`: engine contract v1 (`job.json` schema, stdout JSONL protocol, `report.json` fields, color pipeline).
- `docs/PREMIERE_VALIDATION.md`: Premiere Pro MCP validation procedure, thresholds, and SampleFootage steps.
- `docs/PROGRESS.md`: timestamped build log, updated with every feature.
- `engine/tests/test_*.py`: one test module per engine module above; update both together.
- `.github/workflows/tests.yml`: CI workflow running `python -m pytest engine/tests -q` on push and pull request.

## Build and run

From the repo root (Windows PowerShell):

- `python -m venv .venv --system-site-packages`: create the dev venv. It reuses the system GPU PyTorch install so no large CUDA download is needed.
- `.venv\Scripts\Activate.ps1`, then `python -m pip install -e ./engine`: install the engine editable.
- `python -m pytest engine/tests -q`: full engine test suite, must be green before any commit.
- `python scripts/validate_cube.py`: FFmpeg `lut3d` acceptance check, must print `PASS`.
- `python scripts/run_benchmark.py`: synthetic recovery benchmark, gates on 40 percent DeltaE2000 improvement.
- `python -m chromainvert run work/job.json`: optimize a LUT from a job file per `docs/ARCHITECTURE.md`.

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
