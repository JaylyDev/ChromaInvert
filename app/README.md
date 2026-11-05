# ChromaInvert App Host

This folder holds the Electron + React product GUI in `gui/`, which writes
`job.json` (see `docs/ARCHITECTURE.md`), spawns the Python engine, and parses
its stdout JSONL progress protocol. See `docs/GUI_DECISION.md` for the
Electron decision (Qt rejected for licensing, ImGui rejected as too developer
focused).

The GUI ships its own FFmpeg binaries via `ffmpeg-static` and
`ffprobe-static`. The Python mirror of the old helpers lives in
`scripts/ffmpeg_helpers.py`.

## Product GUI (Electron + React, in `gui/`)

Product path per issue #9. React renderer for inputs, Match and Cancel,
progress bar, wipe preview, scopes, and export. Electron main writes
`job.json`, resolves the `chromainvert` PyPI install (`chromainvert` on PATH,
else `python -m chromainvert`, else press Install in the Environment setup
(installs the engine via pip)), and streams
stdout JSONL progress over the preload bridge.

```
cd app/gui
npm install
npm run dev
```
