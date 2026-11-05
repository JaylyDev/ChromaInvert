# ChromaInvert GUI (Electron + React)

Product UI per issue #9 and `docs/GUI_DECISION.md`. React renderer plus Electron main driving the same `job.json` contract as the C++ hosts (`docs/ARCHITECTURE.md`).

- UI: file fields, Match and Cancel, progress bar, status, log tail.
- Main: writes `job.json` next to the output cube, resolves the engine binary (bundled `chromainvert-engine` in `engine-bin/`, else `chromainvert-engine` on PATH, else `python -m chromainvert`) and the `ffmpeg`/`ffprobe` binaries (static npm binaries unpacked beside the app, else PATH), spawns `run`, parses stdout JSONL `progress` lines, forwards them over the preload bridge. No Python or FFmpeg install is needed when the bundled release ships all three binaries (see `engine-bin/README.md`).
- C++ stays for FFmpeg and math helpers only. No Qt, no ImGui.

## Run in dev (two terminals)

Terminal 1, renderer with hot reload:

```
cd app/gui
npm install
npm run dev
```

Terminal 2, Electron against the dev server:

```
cd app/gui
npm run electron:dev
```

`electron:dev` sets `VITE_DEV_SERVER_URL=http://localhost:5173` via `cross-env`, so the same command works in PowerShell, cmd, macOS, and Linux shells.

## Run the production build locally

```
cd app/gui
npm run build
npm start
```

## Package installers (any platform)

`electron-builder` reads the `build` section of `package.json`:

```
cd app/gui
npm run dist:win
npm run dist:mac
npm run dist:linux
```

`npm run dist` builds for the current platform. `npm run dist:dir` produces an unpacked folder without an installer, useful for smoke testing. Output lands in `app/gui/release/`, which is gitignored. Windows makers (`nsis`, `portable`), macOS (`dmg`, `zip`), and Linux (`AppImage`, `deb`) targets are all declared in `package.json`.

Platform matrix: `dist:win` builds on any Windows dev machine (signing off, no privileges needed). `dist:mac` only runs on a macOS host or mac CI runner; electron-builder refuses it elsewhere. `dist:linux` needs a Linux host or a running Docker daemon; with Docker Desktop stopped it fails in `app-builder`.

## Verify

```
npm run typecheck
npm run build
```
