# ChromaInvert Progress Log

## 2026-10-29: Review follow-up, Wonder re-review fixes on FFmpeg decode link (Issue #10)

Completed:
- Fixed lut3d path escaping in `scripts/ffmpeg_helpers.py` and `app/src/Ffmpeg.cpp`: replaced the broken quoted `\'` scheme with unquoted double-level escaping (`:` as `\\:`, `'` as `\\\'`, `,` `;` `[` `]` single-escaped), verified by brute force against FFmpeg 9. The old scheme dropped apostrophes (`lut's dir` became `luts dir`); the new scheme passes colon, space, apostrophe, comma, semicolon, and bracket paths in both the Python helper and the compiled C++ harness.
- `app/src/main.cpp` now stores absolute frame, cube, report, and job paths in `job.json`, so the engine no longer resolves `work/work/src_0.png`. The shared `JobRunner::jsonEscape` replaces the duplicated helper in `main.cpp`.
- `Ffmpeg::extractFrames` and `Preview::generatePreview` now create their output directories, so the exe works on a fresh cwd. Removed dead `JobRunner::childHandle`, added the missing trailing newline in `JobRunner.cpp`/`JobRunner.h`.
- Minors: `ffmpeg_helpers probe` on a missing file prints one `error:` line with exit 1 instead of a traceback; `_pixel_format_error` no longer treats any `not supported` message as a pixel-format failure.

Verified:
- `python -m pytest engine/tests -q`: 46 passed.
- `python scripts/validate_cube.py`: PASS.
- Python `apply_lut_preview` and C++ `applyLutPreview` harness: PASS on plain, space, apostrophe, and `,;[]` cube paths; missing cube cleanly rejected.
- `chromainvert_app.exe` no-args exits 0, missing file exits 1, fresh-temp-dir run creates `work/`, extracts 3 frames, writes absolute-path `job.json`; an absolute-path job runs the engine to `done` with a cube written.
- CMake Release build green.

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

## 2026-10-29: Feature, Native FFmpeg decode and preview link (Issue #10)

Completed:
- Added `scripts/ffmpeg_helpers.py`: FFmpeg Level 1 subprocess helpers (ffprobe parse, 16-bit PNG frame extraction, lut3d preview, before/after, EngineRunner, error surfaces).
- Added C++ desktop host under `app/`: `CMakeLists.txt`, `app/src/Ffmpeg.h/cpp`, `app/src/JobRunner.h/cpp`, `app/src/Preview.h/cpp`, `app/src/main.cpp` (probe, extract, lut3d preview, job runner).
- Added `app/README.md`: app host docs.
- Updated AGENTS.md Parts of the project with the new files.

Verified:
- `python -m pytest engine/tests -q`: 46 passed.
- CMake build green: `app/build/chromainvert_app.exe` built.
- FFmpeg probe and frame extraction validated on sample footage.
- lut3d preview encode validated on extracted cube.

## 2026-10-29: Review follow-up, Wonder findings on FFmpeg decode link (Issue #10)

Completed:
- Applied the Muse Wonder council review (verdict: changes requested, 17 findings) as follow-up fixes on top of PR #22.
- `scripts/ffmpeg_helpers.py`: lut3d path escaping for Windows drive colons and quotes, output existence checks after every extraction and grab, fps fallback when `avg_frame_rate` is `0/0`, explicit `rgb24` 8-bit fallback only for pixel format errors, `sys.executable` plus `PYTHONPATH` for the engine subprocess, stderr redirected to a temp file to avoid pipe deadlock, temp job and stderr cleanup on all wait paths, nonzero CLI exit on failed preview or run, job-relative path resolution for the `run` subcommand, strict ffprobe JSON errors with timeouts.
- `app/`: `JobRunner` now writes `contract_version` 1 with `fine_iterations` and `device` and drops invented keys; JSON string escaping for all interpolated paths; engine command quoted with separate stderr capture, `done` event required for success, elapsed timeout surfaced; `cancel` no longer kills every Python process. `Ffmpeg` drops the Unix `head` pipe, checks ffprobe exit status and video stream presence, verifies output files are non-empty, escapes lut3d filter paths, rejects unsafe path characters. `main` validates probe and frames, checks job write, gates preview on an existing cube, returns nonzero on failure. `Preview` validates inputs and only assigns output on success.
- Known limits kept for the prototype: C++ `runEngine` still streams progress only after exit (Level 1 `std::system` design) and timeout is surfaced from elapsed time rather than a process kill; full `CreateProcess` job control is future work.

Verified:
- `python -m pytest engine/tests -q`: 46 passed.
- `python scripts/validate_cube.py`: PASS.
- CMake Release build green; `chromainvert_app.exe` with no args exits 0, with a missing file exits 1 with `ffprobe failed`; helper `probe` on a missing file exits 1 with a clear error.

## 2026-10-29: Fix, FFmpeg decode host crash and runner contract (Issue #10)

Completed:
- Fixed `app/src/Ffmpeg.cpp` crash on real footage: ffprobe emits quoted numbers (`"duration": "9.43"`) and `std::stoi`/`std::stod` threw on the quotes. Parsing now strips quotes and uses no-throw `strtol`/`strtod`. Probe prefers `avg_frame_rate` with `r_frame_rate` fallback and reads `bits_per_raw_sample` with `bit_depth` fallback, matching `scripts/ffmpeg_helpers.py`.
- `extractFrames` now probes duration and extracts at even fractions, so count 3 gives 25/50/75 percent, with 16-bit PNG plus 8-bit fallback. `applyLutPreview` now uses the same encode flags as the Python helper (libx264, yuv420p, bt709 tags, faststart).
- `has_audio` is now probed for real in both helpers instead of hardcoded false.
- Fixed `EngineRunner.start`: the CLI only accepts a job file path, so the old stdin `-` invocation always failed. The runner now writes a temp job file with absolute paths and runs `chromainvert run <file>`. `run_engine_stream` returns an error dict with return code and stderr tail when no `done` event arrives, per the contract failure rule.
- Removed scratch `work_make_job.py` from the repo root; the helper CLI covers its flow.

Verified:
- `python -m pytest engine/tests -q`: 46 passed.
- `python scripts/validate_cube.py`: PASS.
- `app/build/chromainvert_app.exe` on Rec709 4K HEVC and S-log3 ProRes samples: probe, 25/50/75 extraction, and job.json written with no crash; audio correctly detected on the Rec709 clip.
- End-to-end on Rec709 frames via fixed `run_engine_stream` (10 plus 2 iterations): 12 progress events plus done in 2.7 s on GPU, report written; `lut3d` preview and before/after frames encoded from the recovered cube.

## 2026-10-27: Feature 1, .cube read/write engine

Completed:
- Added `engine/chromainvert/cube.py` with `CubeLut`, `identity_lattice`, `write_cube`, `read_cube`. Red varies fastest in file order, matching FFmpeg `lut3d` expectations. Writer clamps to [0, 1].
- Added `engine/tests/test_cube_roundtrip.py`, `scripts/validate_cube.py`, plus project skeleton (`README.md`, `.gitignore`, `engine/pyproject.toml`, `assets/SOURCES.md`).

Verified:
- `python -m pytest engine/tests -q`: 5 passed (round trip at sizes 2, 17, 33, axis order, domain, rejection of bad files, writer validation).
- `python scripts/validate_cube.py`: PASS. Identity 33 LUT applied with FFmpeg `lut3d` gives pixel-identical output (peak diff 0.0). Channel-swap LUT turns pure red into blue, confirming lattice axis order matches FFmpeg.

