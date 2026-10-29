# ChromaInvert

Perceptual video and LUT reverse engineering engine. It recovers a smooth 3D LUT that matches source footage to a reference grade, then exports a portable `.cube` file.

## Layout

- `engine/`: Python color engine (differentiable LUT, losses, `.cube` I/O)
- `app/`: C++ desktop host (FFmpeg pipeline, preview UI)
- `assets/`: test footage and reference frames, sources noted in `assets/SOURCES.md`
- `scripts/`: validation and benchmark helpers
- `docs/`: architecture and planning documents
- `work/`: gitignored runtime scratch directory

## Quickstart

1. Install Python 3.10 or newer with `ffmpeg` on PATH.
2. `python -m venv .venv --system-site-packages`
3. `.venv\Scripts\Activate.ps1`
4. `python -m pip install -e ./engine`
5. `python -m pytest engine/tests -q`
6. `python scripts/validate_cube.py`

## Real footage quickstart

1. Extract frames from a Rec709 clip:
   `ffmpeg -y -ss 0 -i "C:\Users\lokwa\Documents\SampleFootage\Rec709\A001_10290006_C101.mov" -frames:v 1 -q:v 2 work/frames/source/source_001.png`
2. Build a warm graded reference (or extract one) and save to `work/frames/reference/ref_001.png`.
3. Create `work/job.json` (see `assets/job.json.example`) with `input_profile` set to `rec709`.
4. Run: `python -m chromainvert run work/job.json`
5. Validate: `python scripts/validate_cube.py` and `python scripts/validate_real_footage.py work/out.cube work/frames/source/source_001.png`
6. Apply the grade: `ffmpeg -y -i work/frames/source/source_001.png -vf lut3d=file=work/out.cube work/graded.png`

Or use the reusable driver: `python scripts/run_real_footage.py --source <video-or-dir> --reference <video-or-dir> --work-dir work`.

The venv reuses the system GPU PyTorch install via `--system-site-packages`, so no large CUDA download is needed.

## Status

See `docs/CHROMAINVERT_HACKATHON_PLAN.md` for the full plan and `docs/PROGRESS.md` for the build log.
