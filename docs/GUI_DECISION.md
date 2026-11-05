# GUI Framework Decision

Date: 2026-10-29
Status: updated 2026-11-05: Electron + React UI, old native hosts removed (bundled FFmpeg supersedes the sidecar)
Related: Section 8.1 of docs/CHROMAINVERT_HACKATHON_PLAN.md, docs/ARCHITECTURE.md, issue #9

## Decision 2026-11-05 (current): Electron + React UI, no native hosts

The old desktop fallback and console driver were
deleted: the GUI ships its own FFmpeg binaries via `ffmpeg-static` and
`ffprobe-static`, so the old FFmpeg sidecar has no role left. The Python
mirror of the old helpers lives in `scripts/ffmpeg_helpers.py`. Earlier
decision history below is kept as a record.

## Decision 2026-11-01 (superseded): Electron + React UI, native helpers retained

Per the issue #9 comment, the product UI is Electron + React. Native helpers covered FFmpeg and math at the time. The new GUI lives in `app/gui/` and drives the same `job.json` contract (ARCHITECTURE.md v2) by spawning `python -m chromainvert run`, then parsing stdout JSONL progress.

- Qt 6 framework: rejected. Mixed LGPL, GPLv3, and commercial licensing makes this project risky.
- Dear ImGui: rejected for the product UI. It looks too developer focused for a consumer product. May be revisited only for internal debug views.
- Old native desktop fallback: removed 2026-11-05 with the console driver. It proved file pickers, Match and Cancel, progress from engine JSONL, and the log pane. No replacement native widgets are planned.

## Options evaluated (history)

### Qt 6 + CMake + vcpkg (rejected 2026-11-01 per issue #9)
Pros:
- Real file dialogs, sliders, image panes, cross platform.
- Good video widget story, stylesheets, high-DPI support.
- Mature progress and threading model, LGPL is fine for hackathon.

Cons:
- Heavier setup: vcpkg bootstrap, Qt 6 SDK (about 1 GB), CMake toolchain file, build time 10 to 30 minutes first install.
- Not available on the build agent without vcpkg. The current demo machine has MSVC 19.44 and MinGW 13.2 but no vcpkg or Qt dev packages.
- Would block the vertical slice if we waited for it.

Verdict: rejected. Mixed LGPL, GPLv3, and commercial licensing is risky for this project. See issue #9 comment. No Qt widgets in tree.

### Dear ImGui + GLFW or SDL (rejected for product UI per issue #9)
Pros:
- Fastest to first window, excellent for scopes and plots via ImPlot.
- Single source vendor, no MOC, tiny build.

Cons:
- File dialogs and video preview are DIY; need native dialogs via tinyfiledialogs or manual platform dialogs.
- Looks like a debug tool, not a product; extra work to polish.
- Still needs GLFW or SDL via vcpkg or vendored source, so similar bootstrapping as Qt.

Verdict: rejected for the product UI per issue #9: looks too developer focused for a consumer product. The Electron GUI in `app/gui/` is the product path.

### CLI only + web demo page (fallback)
Pros: zero GUI risk, contract stays CLI.
Cons: weaker demo, no scrub or wipe story, judges expect a desktop app.

Verdict: kept as fallback; the console host for issue #3 provides this.

### Legacy note: native desktop fallback (removed 2026-11-05)

The earlier pragmatic choice for issue #9 was a native desktop fallback that satisfied the one-screen spec without extra dependencies. It proved file pickers, Match and Cancel buttons, a progress bar driven by engine JSONL, Strength plus LUT size plus device controls, and a log pane. It was deleted with the console driver once the GUI bundled FFmpeg; the Electron GUI in `app/gui/` is the only product path.

## Consequences

- Package: `cd app/gui && npm run dist` produces the per-OS installer in `release/` (Windows setup plus portable, macOS dmg plus zip, Linux AppImage plus deb).
- Runtime deps: system Python with `chromainvert` installed via pip. Missing engine shows the Environment setup panel with an Install button, per Section 8.4. FFmpeg and ffprobe ship inside the app; in-app preview arrives with #10.
- No embedded Python: subprocess plus files, per Section 4.1. The log pane shows the engine JSONL tail.
- Next issues: #10 (FFmpeg decode and preview link) and #11 (scopes) build on this GUI without framework churn.

## Build steps (documented here and in app/README.md)

Prerequisites:
- Node 22
- Python 3.10 or newer (the app installs `chromainvert` from PyPI on first run)

Electron GUI (product path, in `app/gui/`):
```
cd app/gui
npm install
npm run dev
```

No Qt port. Qt was rejected per issue #9 for licensing risk.

The Electron GUI spawns the same engine entry points and parses the same stdout JSONL protocol.

Notes:
- Electron main writes `job.json` and `report.json` next to the chosen output `.cube` path; all job paths may be absolute (relative typed paths are canonicalized first).
- Progress is JSONL on stdout; cancellation kills the child process.
