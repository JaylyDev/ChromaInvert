# ChromaInvert GUI (Electron + React)

Product UI per issue #9 and `docs/GUI_DECISION.md`. React renderer plus Electron main driving the `job.json` contract (`docs/ARCHITECTURE.md`).

- UI: file fields, Match and Cancel, progress bar, status, log tail.
- Main: writes `job.json` next to the output cube, resolves the engine (`chromainvert` console script on PATH, else `python -m chromainvert`, else press Install in the Environment setup (installs the engine via pip)) and the `ffmpeg`/`ffprobe` binaries (static npm binaries unpacked beside the app, else PATH), spawns `run`, parses stdout JSONL `progress` lines, forwards them over the preload bridge. The engine is installed via pip, so the installer ships no Python engine binary; `ffmpeg`/`ffprobe` still ship inside the app.
- No Qt, no ImGui.

## Run in dev (two terminals)

Terminal 1, renderer with hot reload:

```
cd app
npm install
npm run dev
```

Terminal 2, Electron against the dev server:

```
cd app
npm run electron:dev
```

`electron:dev` sets `VITE_DEV_SERVER_URL=http://localhost:5173` via `cross-env`, so the same command works in PowerShell, cmd, macOS, and Linux shells.

## Run the production build locally

```
cd app
npm run build
npm start
```

## Package installers (any platform)

`electron-builder` reads the `build` section of `package.json`:

```
cd app
npm run dist:win
npm run dist:mac
npm run dist:linux
```

`npm run dist` builds for the current platform. `npm run dist:dir` produces an unpacked folder without an installer, useful for smoke testing. Output lands in `app/release/`, which is gitignored. Windows makers (`nsis`, `portable`), macOS (`dmg`, `zip`), and Linux (`AppImage`, `deb`) targets are all declared in `package.json`.

Platform matrix: `dist:win` builds on any Windows dev machine (signing off, no privileges needed). `dist:mac` only runs on a macOS host or mac CI runner; electron-builder refuses it elsewhere. `dist:linux` needs a Linux host or a running Docker daemon; with Docker Desktop stopped it fails in `app-builder`.

Tagged releases (`v*`) run the same steps per OS via `.github/workflows/release.yml` and attach every installer to one GitHub Release.

## Download and use the GUI

Prebuilt installers are attached to each GitHub Release: https://github.com/JaylyDev/ChromaInvert/releases

- Windows: run `ChromaInvert Setup <version>.exe` to install, or launch the portable `ChromaInvert <version>.exe` with no install. The builds are unsigned, so SmartScreen may ask for confirmation on first launch.
- macOS: open the `.dmg` and drag ChromaInvert to Applications. The build is unsigned, so if Gatekeeper blocks the first launch, right-click the app and choose Open.
- Linux: make the `.AppImage` executable and run it, or install the `.deb` with `dpkg -i`.

First run: FFmpeg ships inside the app. The engine installs once via the Environment panel: press Install engine with Python 3.10 or newer on PATH and internet access (installs `chromainvert` from PyPI with torch, numpy, and imageio; it can take several minutes). Reference-only predict mode additionally needs a weights `.pt` file: train one with `scripts/train_lut_predictor.py` and pick it in the weights field.

Basic Match workflow:

1. Footage: add ungraded source frames and graded reference frames, or import the source and reference videos, scrub to a frame, and capture it into the lists.
2. Output: pick the output `.cube` path (`job.json` and `report.json` land next to it).
3. Grade settings: the input profile decodes the source frames and the reference profile decodes the graded reference (Auto resolves log sources such as Apple Log to `rec709`). Strength blends the result back toward identity.
4. Run: press Match and watch the progress bar, status, and log; Cancel stops the engine.

## Verify

```
npm run typecheck
npm run build
```
