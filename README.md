# ChromaInvert

Perceptual video and LUT reverse engineering engine. It recovers a smooth 3D LUT that matches source footage to a reference grade, then exports a portable `.cube` file that grades identically in FFmpeg, DaVinci Resolve, and Premiere Pro.

Built for the Meta Global AI Developer Hackathon (Oct 26 to Nov 4, 2026), Indie Dev Track. Team JaylyDev. License: Apache-2.0.

## Meta Global AI Hackathon 2026: Submission Overview

- **Track and Problem Statement**: Indie Developer, Build for Your World (portable color grading for creators, mobile shooters, and small post houses).
- **Provenance (Oct 26 to Nov 4, 2026)**: Built 100 percent from scratch during the hackathon window.
- **Meta AI usage**: Muse Spark series powered development (Python engine, C++ hosts, GUI, scripts, including open weights endpoints via Baseten and Meta); Muse Wonder powered review and complex tasks (architecture decisions and council reviews, see `docs/PROGRESS.md`). The grading runtime itself is local and deterministic (PyTorch plus FFmpeg, no model API calls at inference).
- **Bonus Prize Category Targeted**: Best Creative Build.
- **3-Minute Demo Video**: https://www.youtube.com/watch?v=0d8jhrCcYSA
- **Repo**: https://github.com/JaylyDev/ChromaInvert (single self-contained public repository).
- **Quickstart and keyless replay**: Quickstart below; no API keys and no login needed; `python scripts/run_benchmark.py` verifies the core claim with no footage and no GPU.
- **X post (Most Viral entry)**: link to be added.

## Demo video

Watch the 3 minute demo: https://www.youtube.com/watch?v=0d8jhrCcYSA

The 3 minute run of show is scripted in `docs/DEMO_SCRIPT.md`: problem (20s), live run (60s), portability proof in third party tools (45s), numbers (30s), close (25s). Failure lines for stalled optimization, missing GPU, and GUI failure are in the same file.

## Why this exists

Hand grading a log clip to a film reference takes hours of curves, wheels, and hue qualifiers. Per frame AI style transfer is fast but temporally unstable: identical colors in adjacent frames map differently, so video flickers. A 3D LUT is the opposite: one fixed function of input color only, applied identically to every frame. If ChromaInvert recovers a good LUT, temporal stability holds by construction (frame to frame mapping delta 0.00), and the result is portable to any editor with no plugin.

Core claims proven in the demo:

1. Differentiable optimization recovers a smooth 3D LUT from reference frames in seconds, not a neural per pixel edit.
2. The exported `.cube` alone reproduces the look in FFmpeg, Resolve, and Premiere Pro. The demo shows the third party result, not just the in app preview.
3. Skin tones and shadows survive: the grade does not push faces orange or green and does not crush shadow detail.

## Built with Meta AI

| Model | How it was used |
|---|---|
| Muse Spark series (proprietary API plus open weights endpoints via Baseten and Meta) | Coding across the stack: Python color engine, C++ hosts, Electron plus React GUI, validation and benchmark scripts |
| Muse Wonder | Review and complex tasks: architecture decisions, council reviews on PRs, debugging hard failures |

Review evidence lives in `docs/PROGRESS.md`: Wonder council reviews for the GUI host (PR #24, verdict changes requested, all findings applied), the FFmpeg decode link (Issue #10, 17 findings applied), the `export_graded` script, deterministic GPU mode and the random RGB probe heldout gate, the synthetic benchmark, and CI workflow majors. The repo workflow requires a Wonder council review before every commit, documented in `AGENTS.md`.

Runtime note: at inference the engine runs fully locally (PyTorch plus FFmpeg) with no model API calls, no accounts, and no network access. Meta models were the development and review stack described above.

## Results

Measured on SampleFootage, RTX GPU, canonical 400 plus 30 iterations (2026-10-29 dry run, re measure on the demo machine):

| Check | Result | Gate |
|---|---|---|
| Synthetic recovery, held out frames | Baseline 4.04, recovered 2.06 mean DeltaE2000, improvement 48.9 percent | 40 percent improvement |
| End to end time | Extract 2.9s, optimize 12.5s, export 6.9s, benchmark 6.3s, total 31.1s | Click to graded preview under 30s target; report the measured number |
| Smoothness | `max_neighbor_delta` 0.161 in demo run, 0.1395 in real footage run; no banding on ramp test | Reported in `report.json` |
| Python vs FFmpeg trilinear | Mean DeltaE2000 0.22 to 0.26 on chart and Rec.709 frames | At or under 1.0 |
| Trilinear vs tetrahedral gap | Mean 0.008 to 0.015, max 1.9 on smooth grades | Reported, not gated |
| Single image predictor (reference only) | Unseen commercial LUT 4.6 style probe DeltaE2000 against 14.0 baseline; mild Premiere Lumetri grade 7.0 against 8.4 baseline (plus 16 percent); inference 0.08s | Informational |
| Apple Log host domain fix (2026-11-04) | Premiere still vs FFmpeg 7.28 after host domain bake (legacy working cube 26.0); paired loss config 9.08 to 5.45 on held out frame; final Premiere cube 6.06 with chroma within 3 percent | Measured workflow in `docs/PREMIERE_VALIDATION.md` |

If a target is missed, the number still goes in the README. Measured honesty beats adjectives.

Run the numbers yourself:

```powershell
python scripts/run_benchmark.py
python scripts/premiere_validation.py
python scripts/premiere_validation.py --cube work/out.cube --source work/src_frame.png
```

## Quickstart (reproducible)

Prerequisites: Windows PowerShell from the repo root, Python 3.10 or newer, FFmpeg 7 or newer plus ffprobe on PATH, a CUDA PyTorch install for GPU speed (CPU works in degraded mode).

```powershell
python -m venv .venv --system-site-packages
.venv\Scripts\Activate.ps1
python -m pip install -e ./engine
python -m pytest engine/tests -q
python scripts/validate_cube.py
```

The venv reuses the system GPU PyTorch install via `--system-site-packages`, so no large CUDA download is needed.

One command demo (writes `work/demo/` with `out.cube`, `graded.mp4`, `before.png`, `after.png`, `report.json`, `benchmark.json`, `timings.json`):

```powershell
python scripts/run_demo.py --source "<clip.mov>" --reference "<reference.mov>" --workdir work/demo
```

Fast smoke variant (CPU safe, about 15 seconds):

```powershell
python scripts/run_demo.py --source "<clip.mov>" --reference "<reference.mov>" --workdir work/demo-fast --iterations 100 --fine-iterations 10 --preview-secs 2 --skip-benchmark
```

## Real footage quickstart

1. Create the frame directories: `New-Item -ItemType Directory -Force work/frames/source, work/frames/reference`
2. Extract a source frame from a Rec709 clip: `ffmpeg -y -ss 0 -i <clip> -frames:v 1 -q:v 2 work/frames/source/source_001.png`
3. Build a warm graded reference with FFmpeg (or extract one from a graded clip) and save to `work/frames/reference/ref_001.png`: `ffmpeg -y -i work/frames/source/source_001.png -vf "colorbalance=rs=0.15:bs=-0.15,eq=saturation=1.2" -frames:v 1 -q:v 2 work/frames/reference/ref_001.png`
4. Create `work/job.json` (see `assets/job.json.example`; frame names match `source_001.png` and `ref_001.png`) with `input_profile` set to `rec709`.
5. Run: `python -m chromainvert run work/job.json`
6. Validate the exported cube: `python scripts/validate_real_footage.py work/out.cube work/frames/source/source_001.png` (`scripts/validate_cube.py` is the generic FFmpeg `lut3d` acceptance check, not the run validator)
7. Apply the grade: `ffmpeg -y -i work/frames/source/source_001.png -vf lut3d=file=work/out.cube work/graded.png`

Or use the reusable driver: `python scripts/run_real_footage.py --source <video-or-dir> --reference <video-or-dir> --work-dir work`.

Reference only prediction (no source frames; you must train weights on LUTs you own, see `data/README.md`):

```powershell
python -m chromainvert predict <graded.png> --profile rec709 --weights <path\to\your\checkpoint.pt> --out out.cube
```

## App and CLI

Product GUI (Electron plus React in `app/gui`): inputs, Match and Cancel, progress bar, status, log tail. C++ stays for FFmpeg and math helpers only. Qt rejected for licensing, ImGui rejected as too developer focused; see `docs/GUI_DECISION.md`. Win32 host kept as legacy fallback.

```powershell
cd app/gui
npm install
npm run typecheck
npm run build
npm run dev
```

C++ console driver (`chromainvert-host`, C++17 standard library only): extracts frames, writes `job.json`, spawns the engine, encodes previews. See `app/README.md` for build and run commands.

Engine CLI:

```powershell
python -m chromainvert run work/job.json
python -m chromainvert benchmark
```

Graded video export:

```powershell
python scripts/export_graded.py --help
```

## Build and dependencies

Most users only need the consumer set: Python plus FFmpeg grades footage with no compilation, no accounts, and no API keys. Node and the C++ toolchain are only for contributors building the GUI or desktop hosts from source.

To use ChromaInvert (consumers):

| Dependency | Required | Notes |
|---|---|---|
| OS | Windows 10 or newer | Engine and scripts run wherever Python and FFmpeg run; Ubuntu and macOS are covered by CI |
| Python | 3.10 or newer (CI runs 3.11) | `requires-python = ">=3.10"` in `engine/pyproject.toml` |
| Python packages | `torch>=2.0`, `numpy>=1.26`, `imageio>=2.30`, plus `pytest>=8` for tests | Installed with `pip install -e ./engine` (dev extras via `./engine[dev]`) |
| CUDA | Optional | The venv reuses the system GPU PyTorch install via `--system-site-packages`, so no large CUDA download is needed; without a GPU the engine runs in CPU degraded mode |
| FFmpeg plus ffprobe | FFmpeg 7 or newer on PATH | Frame extraction, `lut3d` preview and graded export |

Install the engine from the repo root:

```powershell
python -m pip install -e ./engine
```

To build the apps from source (contributors):

| Dependency | Required | Notes |
|---|---|---|
| CMake and C++ toolchain | CMake 3.20 or newer, MSVC 2022 or MinGW-w64 GCC 13 plus, C++17 | Only needed for the Win32 host and `chromainvert-host`; standard library only, no extra packages |
| Node.js and npm | Node 22, `npm ci` with the lockfile | Only needed for the Electron GUI in `app/gui` (CI pins Node 22) |

```powershell
cd app/gui
npm ci
npm run typecheck
npm run build
```

```powershell
cmake -B build -S app
cmake --build build --config Release
```

Binaries land under `build/` (`Release/ChromaInvert.exe` with the Visual Studio generator). Full per host instructions live in `app/README.md`.

## How it works

Subprocess plus files. No shared memory, no embedded interpreter, no sockets. The C++ host or Electron main writes `work/job.json`, spawns `python -m chromainvert run`, parses stdout JSONL progress, and applies the exported cube with FFmpeg `lut3d`.

```
app --writes--> work/job.json --reads--> chromainvert run work/job.json
                                   --writes--> work/out.cube, work/report.json
app --reads--> work/out.cube --applies--> FFmpeg lut3d preview and encode
```

Optimization: identity init lattice (coarse 17, Catmull-Rom spline upsample to 33), Adam on distribution losses (quantile, moment, covariance) plus total variation smoothness, identity prior, skin and shadow anchors, and gamut penalty. Pixel budget is seeded sampling (about 65k pixels per frame). Full contract in `docs/ARCHITECTURE.md` (`contract_version` 1 and 2, stdout JSONL protocol, `report.json` fields, color pipeline for `rec709`, `rec2020`, `apple_log`, `slog3`).

## Layout

- `engine/chromainvert/`: Python color engine (`cube.py` read and write, `lut_module.py` differentiable LUT, `color.py` transfers and log decoders, `losses.py`, `masks.py`, `spline.py`, `optimize.py`, `lut_predictor.py`, `benchmark.py`, `cli.py`)
- `engine/tests/`: one test module per engine module; full suite must stay green
- `app/gui/`: Electron plus React product GUI (Vite renderer, TypeScript, no Qt)
- `app/src/`: C++17 Win32 fallback plus `chromainvert-host` console driver, shared `ffmpeg` module, `Preview`
- `scripts/`: 13 helpers (`run_demo`, `run_benchmark`, `run_real_footage`, `premiere_validation`, `export_graded`, `ffmpeg_helpers`, `make_reference_pairs`, `evaluate_single_image`, `make_training_data`, `train_lut_predictor`, `validate_cube`, `validate_real_footage`, `extract_frames`)
- `docs/`: `CHROMAINVERT_HACKATHON_PLAN.md`, `ARCHITECTURE.md`, `DEMO_SCRIPT.md`, `PREMIERE_VALIDATION.md`, `GUI_DECISION.md`, `PROGRESS.md`
- `data/`: bring your own training frames, LUTs, and weights (gitignored outputs; no checkpoint is shipped since a checkpoint distills its training LUTs)
- `assets/`: `job.json.example`, test footage notes in `assets/SOURCES.md`
- `work/`: gitignored runtime scratch directory

## Validation and CI

- `python -m pytest engine/tests -q`: full engine suite, must be green before any commit.
- `python scripts/validate_cube.py`: FFmpeg `lut3d` acceptance check, must print `PASS`.
- `python scripts/run_benchmark.py`: synthetic ground truth recovery plus seeded random RGB probe heldout gate, gates on 40 percent DeltaE2000 improvement.
- `python scripts/premiere_validation.py`: Python trilinear vs FFmpeg trilinear vs tetrahedral, optional Premiere still scoring; thresholds and SampleFootage steps in `docs/PREMIERE_VALIDATION.md`.
- CI: `.github/workflows/tests.yml` runs pytest on Ubuntu; `.github/workflows/gui.yml` runs GUI typecheck, build, and per platform packaging on Windows, macOS, and Linux.
- History: active window development with PR review and a build log in `docs/PROGRESS.md`.

## Limitations and roadmap

- Log profiles (`slog3`, Apple Log) use a bounded working space with a host domain bake; saturated log colors carry some interpolation error versus per pixel decode (mean abs error under 0.02 on random codes). See `docs/ARCHITECTURE.md` step 4 and `docs/PREMIERE_VALIDATION.md`.
- Premiere Pro color manages Apple Log clips toward Rec.709 before Lumetri, so cubes must be trained on Premiere exported stills or the host domain path; the MCP `apply_lut` path is unavailable on CEP and is a test harness only.
- Roadmap: per shot LUTs, ACES and HDR pipeline, embedded engine, multi frame reference, batch mode.

## License

Apache-2.0, see `LICENSE`. This is a single self-contained public repository; `work/`, `.venv/`, training checkpoints (`*.pt`), and local footage are gitignored and never committed.

## Status and links

See `docs/CHROMAINVERT_HACKATHON_PLAN.md` for the full plan and `docs/PROGRESS.md` for the build log. Engine version `0.1.0` in `engine/pyproject.toml`.
