# ChromaInvert Demo Script: 3 Minute Run of Show

Goal: prove a judge can pick an ungraded clip plus a reference frame, click Match,
and export one `.cube` that grades video identically in FFmpeg, DaVinci Resolve,
and Premiere Pro, with zero per-frame AI.

Contract: engine contract v1 per `docs/ARCHITECTURE.md` is `rec709` only.
Log profiles (`slog3`, Apple Log) exist in `color.py` but have no bounded
working-space design yet, so the CLI refuses them rather than silently clipping.
The demo therefore decodes all frames as `rec709` (display-referred) and states
that limitation on the slide. True log working space is roadmap, not demo.

## Prerequisites (do before the clock)

- Windows PowerShell from the repo root.
- `.venv` created per `AGENTS.md` with the engine installed editable.
- FFmpeg 7 or 9 on PATH (`ffmpeg -version`, `ffprobe -version`).
- Sample footage on disk (local only, never committed):
  `C:\Users\lokwa\Documents\SampleFootage\Rec709\A001_10290006_C101.mov`
  `C:\Users\lokwa\Documents\SampleFootage\Apple Log\A001_10290006_C100.mov`
- Pre-run once: `python scripts/run_demo.py --help` and one full dry run.

## One command dry run (about 30 seconds on GPU)

```powershell
python scripts/run_demo.py --source "C:\Users\lokwa\Documents\SampleFootage\Rec709\A001_10290006_C101.mov" --reference "C:\Users\lokwa\Documents\SampleFootage\Apple Log\A001_10290006_C100.mov" --workdir work/demo
```

Outputs in `work/demo/`: `src_*.png`, `ref_000.png`, `job.json`, `out.cube`,
`report.json`, `graded.mp4`, `before.png`, `after.png`, `benchmark.json`,
`timings.json`. The script prints a timing table for the Numbers beat.

Fast smoke variant (CPU safe, about 15 seconds):

```powershell
python scripts/run_demo.py --source "C:\Users\lokwa\Documents\SampleFootage\Rec709\A001_10290006_C101.mov" --reference "C:\Users\lokwa\Documents\SampleFootage\Apple Log\A001_10290006_C100.mov" --workdir work/demo-fast --iterations 100 --fine-iterations 10 --preview-secs 2 --skip-benchmark
```

## Run of show

### Beat 1: Problem (0:00 to 0:20)

Say: hand-grading a log clip to a film reference takes hours of curves and wheels.
Per-frame AI style transfer flickers because every frame gets a different edit.
A 3D LUT is one fixed function of color applied to every frame, so temporal
stability holds by construction. ChromaInvert recovers that LUT in seconds.

Show: title slide with the three input thumbnails (`src_000.png`,
`ref_000.png`, `after.png` side by side). No live action.

### Beat 2: Live run (0:20 to 1:20, 60 seconds)

Say: this is the ungraded Rec.709 clip, this is the reference frame from a
different shoot. Contract v1 decodes both as Rec.709 display-referred.

Do:

```powershell
python scripts/run_demo.py --source "C:\Users\lokwa\Documents\SampleFootage\Rec709\A001_10290006_C101.mov" --reference "C:\Users\lokwa\Documents\SampleFootage\Apple Log\A001_10290006_C100.mov" --workdir work/demo
```

Narrate while it runs: frames sampled at fixed fractions, lattice starts at
identity, Adam minimizes quantile plus moment plus covariance with TV smoothing
and skin plus shadow anchors, coarse 17 upsampled to 33 with clamped
Catmull-Rom. Point at the JSONL progress lines (`iter`, `loss`) as the loss falls.
End on the before and after wipe: open `work/demo/before.png` and
`work/demo/after.png`, then play `work/demo/graded.mp4`.

### Beat 3: Portability proof (1:20 to 2:05, 45 seconds)

Say: there is no hidden per-frame AI in the app. The file that graded that clip
is `work/demo/out.cube`, and the same file grades in third party tools.

Do: show the equivalent FFmpeg command (repo root paths; the script runs the
same filter with cwd `work/demo` plus explicit encode flags):

```powershell
ffmpeg -y -ss 2 -t 3 -i "C:\Users\lokwa\Documents\SampleFootage\Rec709\A001_10290006_C101.mov" -vf lut3d=file=work/demo/out.cube -c:v libx264 -pix_fmt yuv420p -color_primaries bt709 -color_trc bt709 -colorspace bt709 work/demo/graded.mp4
```

Show: pre-opened DaVinci Resolve with `out.cube` in the LUT folder applied to
the same clip, plus the Premiere Pro still from `docs` validation if available.
Stress: no plugin of ours is installed in either tool.

### Beat 4: Numbers (2:05 to 2:35, 30 seconds)

Read from the script output and `report.json`:

- Synthetic recovery: baseline vs recovered mean DeltaE2000 and percent
  improvement from `work/demo/benchmark.json` (gate: 40 percent improvement).
- Speed: `extract_s`, `optimize_s`, `export_s`, `benchmark_s`, `total_s` from
  the timing table and `timings.json`.
- Smoothness: `max_neighbor_delta`, `lattice_min`, `lattice_max` from `report.json`.
- Stability: frame-to-frame mapping delta is 0.00 by construction (one fixed LUT).
- Skin and shadow: anchors on, term values in `report.json` `final_loss_terms`.

Dry-run reference (RTX GPU, canonical 400 plus 30, measured 2026-10-29 on
SampleFootage Rec709 source plus Apple Log reference): extract 2.9 s,
optimize 12.5 s, export 6.9 s, benchmark 6.3 s, total 31.1 s. Benchmark
recovery on the same run: baseline 4.04, recovered 2.06 mean DeltaE2000,
improvement 48.9 percent (gate 40 percent). Re-measure on the demo machine
and replace these numbers before showtime.

### Beat 5: Close (2:35 to 3:00, 25 seconds)

Say: for creators, mobile shooters, and small post houses. Roadmap: bounded log
working space (S-Log3, Apple Log), per-shot LUTs, ACES and HDR pipeline,
embedded engine. The `.cube` in your hand loads everywhere today.

## Failure lines (rehearse, do not improvise)

- Live optimization stalls: stop the run, open the precomputed `work/demo`
  folder from rehearsal, play `graded.mp4`, continue at Beat 3 with the line:
  this is the identical command with the precomputed cube for these assets.
- GPU absent: rerun with `--device cpu --iterations 100 --fine-iterations 10`.
  State the CPU degraded mode and the reduced iteration count out loud.
- Reference looks wrong: state the rec709-only contract limit, switch the
  reference to a Rec.709 frame from the same clip at a different timestamp,
  rerun the fast smoke variant.
- No network or segmentation: nothing in this demo needs the network or
  segmentation weights. Skin uses the YCbCr heuristic only.
- GUI fails: the CLI pipeline is the demo surface. The script output plus
  `graded.mp4` is the backup demo.

## Real-footage quickstart

Grafted from the `jayly/real-footage` branch: run the engine on hand-picked
frames without the demo script.

1. `New-Item -ItemType Directory -Force work/frames/source, work/frames/reference`
2. `ffmpeg -y -ss 0 -i <clip> -frames:v 1 -q:v 2 work/frames/source/source_001.png`
3. Create the warm reference at `work/frames/reference/ref_001.png` (grade one
   manually, or run `ffmpeg -y -i work/frames/source/source_001.png -vf "colorbalance=rs=0.15:bs=-0.15,eq=saturation=1.2" -frames:v 1 -q:v 2 work/frames/reference/ref_001.png`).
4. `python -m chromainvert run work/job.json` (see `assets/job.json.example`).
5. `python scripts/validate_real_footage.py work/out.cube work/frames/source/source_001.png`
   (`scripts/validate_cube.py` only checks generic FFmpeg `lut3d` acceptance).

Fallbacks: if frame extraction fails, use synthetic frames via
`python scripts/run_real_footage.py` with no video arguments. If CUDA is
unavailable, set `device` to `cpu` in job.json.

## After the demo

- Keep `work/demo/out.cube`, `work/demo/graded.mp4`, and `work/demo/report.json`.
- Record the timing table into `docs/PROGRESS.md` with the dry-run entry.
- File issues for anything that needed a failure line.
