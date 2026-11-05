# ChromaInvert

Perceptual video and LUT reverse engineering engine. It recovers a smooth 3D LUT that matches source footage to a reference grade, then exports a portable `.cube` file.

Built using Meta's proprietary and open weights models for the Meta Global AI Developer Hackathon (Oct 26 – Nov 4, 2026), Indie Dev Track.

## Layout

- `engine/`: Python color engine (differentiable LUT, losses, `.cube` I/O)
- `app/`: Electron + React product GUI (video import, Match, progress, `.cube` export)
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

1. Create the frame directories: `New-Item -ItemType Directory -Force work/frames/source, work/frames/reference`
2. Extract a source frame from a Rec709 clip: `ffmpeg -y -ss 0 -i <clip> -frames:v 1 -q:v 2 work/frames/source/source_001.png`
3. Build a warm graded reference with FFmpeg (or extract one from a graded clip) and save to `work/frames/reference/ref_001.png`: `ffmpeg -y -i work/frames/source/source_001.png -vf "colorbalance=rs=0.15:bs=-0.15,eq=saturation=1.2" -frames:v 1 -q:v 2 work/frames/reference/ref_001.png`
4. Create `work/job.json` (see `assets/job.json.example`; frame names match `source_001.png` and `ref_001.png`) with `input_profile` set to `rec709`.
5. Run: `python -m chromainvert run work/job.json`
6. Validate the exported cube: `python scripts/validate_real_footage.py work/out.cube work/frames/source/source_001.png` (`scripts/validate_cube.py` is the generic FFmpeg `lut3d` acceptance check, not the run validator)
7. Apply the grade: `ffmpeg -y -i work/frames/source/source_001.png -vf lut3d=file=work/out.cube work/graded.png`

Or use the reusable driver: `python scripts/run_real_footage.py --source <video-or-dir> --reference <video-or-dir> --work-dir work`.

The venv reuses the system GPU PyTorch install via `--system-site-packages`, so no large CUDA download is needed.

## Use the app (GUI)

Download the installer from GitHub Releases, run it, and launch ChromaInvert: pick a source clip and a reference frame, choose the output `.cube` path, then press Match.

The packaged app bundles its own FFmpeg and ffprobe, so no FFmpeg install is needed. The engine resolves from the `chromainvert` PyPI install: press Install in the app's Environment setup, or install it yourself with:

```powershell
python -m pip install chromainvert
```

Or with uv:

```powershell
uv pip install chromainvert
```

Engine installs still need Python 3.10 or newer plus PyTorch `torch>=2.0` on the machine. The easiest PyTorch path is the selector at https://pytorch.org/ : pick Windows, Python, and your CUDA build (or CPU), then run the install command it suggests. Install PyTorch first so the resolver keeps your CUDA build; a CUDA build is faster, CPU works in degraded mode. The published package lives at https://pypi.org/project/chromainvert/.

### Build the GUI app as an exe

To build the installer yourself you need Node 22:

```powershell
cd app/gui
npm ci
npm run typecheck
npm run build
npm run dist:win
```

Installers land under `app/gui/release/` (NSIS installer plus portable exe). `npm run dist` builds for the current platform; `dist:mac` and `dist:linux` target those platforms. For development, `npm run dev` plus `npm run electron:dev` runs without packaging (see `app/README.md`).

## Status

See `docs/CHROMAINVERT_HACKATHON_PLAN.md` for the full plan and `docs/PROGRESS.md` for the build log.
