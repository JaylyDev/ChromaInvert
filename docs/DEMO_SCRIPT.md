# ChromaInvert Demo Script (3 minutes)

## Problem (20s)
Color matching a reference film frame onto raw footage takes hours of manual curve tweaking, and AI style transfer introduces flicker and pixel artifacts. ChromaInvert recovers one fixed 3D LUT function instead.

## Live run (60s)
1. Show the Rec709 source frame and the warm reference frame.
2. Run `python -m chromainvert run work/job.json` and watch the JSONL progress lines.
3. Open `work/report.json`: final loss terms, lattice_min, lattice_max, max_neighbor_delta, seconds.
4. Show `work/out.cube` (33 x 33 x 33, red-fastest).

## Portability proof (45s)
1. Run `python scripts/validate_cube.py` (prints PASS).
2. Run `ffmpeg -y -i work/frames/source/source_001.png -vf lut3d=file=work/out.cube work/graded.png`.
3. Show graded frame matches reference tone; same file opens in Premiere Pro / DaVinci Resolve.

## Numbers (30s)
- Synthetic benchmark: `python scripts/run_benchmark.py` reports baseline and recovered mean DeltaE2000 with >40 percent improvement.
- Real run completes in under 30 seconds on a laptop GPU.

## Close (25s)
ChromaInvert exports a smooth industry-standard `.cube` with zero AI artifacts, ready for Premiere Pro, DaVinci Resolve, FFmpeg, or mobile camera apps.

## Quickstart for real footage
1. `New-Item -ItemType Directory -Force work/frames/source, work/frames/reference`
2. `ffmpeg -y -ss 0 -i <clip> -frames:v 1 -q:v 2 work/frames/source/source_001.png`
3. Create warm reference at `work/frames/reference/ref_001.png` (grade one manually, or run `ffmpeg -y -i work/frames/source/source_001.png -vf "colorbalance=rs=0.15:bs=-0.15,eq=saturation=1.2" -frames:v 1 -q:v 2 work/frames/reference/ref_001.png`).
4. `python -m chromainvert run work/job.json` (see `assets/job.json.example`).
5. `python scripts/validate_real_footage.py work/out.cube work/frames/source/source_001.png` (`scripts/validate_cube.py` only checks generic FFmpeg `lut3d` acceptance).

## Fallback lines
- If frame extraction fails, use synthetic frames via `python scripts/run_real_footage.py` with no video arguments.
- If CUDA is unavailable, set `device` to `cpu` in job.json.
- If FFmpeg lut3d fails, verify the cube with `python scripts/validate_cube.py`.