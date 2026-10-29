# ChromaInvert Progress Log

## 2026-10-29: Wonder re-review fixes for the GUI host

Completed:
- Added `engine/chromainvert/__main__.py` so the `python -m chromainvert run` command that `JobRunner` spawns works on this branch (already present on main via the real-footage work).
- Added `WS_TABSTOP` to the interactive `MainWindow` controls so the `IsDialogMessageW` keyboard navigation actually moves focus between fields.
- Dropped the pinned Visual Studio 17 2022 generator from the `build-windows` CI job: current `windows-latest` runners ship Visual Studio 2026 only, so CMake now selects the default MSVC generator.

Verified:
- MSVC 19.44 Release and MinGW-w64 GCC 13.2 builds clean with zero compiler warnings; window-handle smoke passed for both executables (title `ChromaInvert`, graceful exit code 0).
- `JobRunner` harness against a Unicode output directory (accented and CJK characters): exactly one `WM_JOB_DONE` on success (exit code 0, `.cube` and report written, ASCII-only `job.json`, strength round-trips) and exactly one on cancel (`Cancelled.`, no orphan engine process).
- `python -m pytest engine/tests -q`: 46 passed. `python scripts/validate_cube.py`: PASS. Workflow YAML parses.

## 2026-10-29: Wonder review findings on the GUI host

Completed:
- Addressed the independent Muse Wonder review of PR #24 (verdict: changes requested): reworked `JobRunner` process and thread ownership (atomic child handle, sole-owner close, prior thread reaped before reuse, exactly one terminal `WM_JOB_DONE` posted after the child is waited on), ASCII-safe `job.json` emission with wide-path file open, strength validation clamped to `[0, 1]` with empty and non-finite rejection, absolute path canonicalization, done summary from the known output path, failed-post cleanup, `hwnd_` set at `WM_NCCREATE`, dialog keyboard navigation with tri-state `GetMessage`, child-window creation checks, directory rejection, round-trippable strength formatting, final partial-line drain, MinGW `-municode` plus `WINVER` defines with brace struct init, system DPI awareness until layout scaling lands, corrected `docs/GUI_DECISION.md` claims, and a Windows MSVC build job in CI.
- Aligned the engine with the contract: `cli.py` reads the job file as UTF-8 and the omitted-key `fine_iterations` fallback is 30, matching `ARCHITECTURE.md` and `OptimizeConfig`.

Verified:
- MSVC 19.44 Release clean with zero warnings; pytest 46 passed.
- Pending rerun of the exe window-handle smoke and the FFmpeg acceptance checks before merge.

## 2026-10-29: GUI framework decision and Win32 main window skeleton

Completed:
- Added `docs/GUI_DECISION.md`: Qt 6 versus ImGui decision. Qt 6 is the product target; ImGui is the runner-up for scopes work. The shippable milestone is a native Win32 host with zero third party GUI deps, and the Qt port reuses the same `job.json` contract later.
- Added `app/CMakeLists.txt`, `app/src/main.cpp`, `app/src/MainWindow.h`, `app/src/MainWindow.cpp`, `app/src/JobRunner.h`, `app/src/JobRunner.cpp`, `app/README.md`: main window with source and reference file pickers, output `.cube` picker, Strength edit, LUT size and device combos, Match and Cancel buttons, progress bar, status label, and log pane. JobRunner writes `job.json` (contract v1), spawns `python -m chromainvert run`, and parses stdout JSONL into progress and done messages. Removed obsolete `app/.gitkeep`.
- Recorded the new files under Parts of the project in `AGENTS.md`.

Verified:
- `cmake -B build -S app -G "Visual Studio 17 2022" -A x64` plus `cmake --build build --config Release`: clean build with MSVC 19.44, zero warnings, `build/Release/ChromaInvert.exe` launches and shows its main window.
- `python -m pytest engine/tests -q`: 46 passed.
- `python scripts/validate_cube.py`: PASS.
- SampleFootage end to end on the JobRunner contract path: ffprobe confirms the Rec709 clip is BT.709 limited range, extracted source and reference frames, ran the engine (100 plus 10 iterations, GPU, 3.7 s) to `{"event": "done"}` with a valid `.cube`, and applied it with FFmpeg `lut3d`.

Notes:
- The skeleton grades still frames only; video decoding and frame sampling belong to issue #10 and scopes belong to issue #11, so no preview or scopes code was added here.
- The AGENTS.md council review step was skipped: child agents cannot spawn subagents, so a careful self review (warnings clean, tests green, contract fields cross checked against `cli.py`) stands in for it.

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

