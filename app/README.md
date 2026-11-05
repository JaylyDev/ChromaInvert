# ChromaInvert App

This folder holds the Electron + React product GUI in `gui/`, which writes
`job.json` (see `docs/ARCHITECTURE.md`), spawns the bundled engine, and parses
its stdout JSONL progress protocol. See `docs/GUI_DECISION.md` for the
Electron decision.

## Product GUI (Electron + React, in `gui/`)

React renderer for inputs, Match and Cancel, progress bar, and export.
Electron main writes `job.json`, spawns the bundled `chromainvert-engine`
(falling back to system Python), and streams stdout JSONL progress over the
preload bridge. FFmpeg and ffprobe resolve from the bundled static binaries
first, then PATH.

### Prerequisites

Running the packaged app needs nothing: the engine and FFmpeg ship inside
it. To build or develop the GUI you need Node 22. Engine development
additionally needs Python 3.10 or newer, PyTorch `torch>=2.0` (easiest via
the selector at https://pytorch.org/), and the engine installed
(`python -m pip install chromainvert` or `uv pip install chromainvert`).

### Develop

```
cd app/gui
npm ci
npm run dev
```

In a second terminal, `npm run electron:dev` opens the desktop shell
against the dev server.

### Build the exe

```
cd app/gui
npm ci
npm run typecheck
npm run build
npm run dist:win
```

Installers land under `app/gui/release/` (NSIS installer plus portable
exe). `npm run dist` builds for the current platform; `dist:mac` and
`dist:linux` target those platforms. The packaged app runs with no installs:
the engine and FFmpeg ship inside it.
