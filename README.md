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
2. `pip install -e ./engine`
3. `python -m pytest engine/tests -q`
4. `python scripts/validate_cube.py`

## Status

See `docs/CHROMAINVERT_HACKATHON_PLAN.md` for the full plan and `docs/PROGRESS.md` for the build log.
