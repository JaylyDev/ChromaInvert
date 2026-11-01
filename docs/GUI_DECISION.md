# GUI Framework Decision

Date: 2026-10-29
Status: superseded 2026-11-01 by issue #9 comment: Electron + React UI, C++ kept for FFmpeg and math helpers
Related: Section 8.1 of docs/CHROMAINVERT_HACKATHON_PLAN.md, docs/ARCHITECTURE.md, issue #9

## Decision 2026-11-01 (current): Electron + React UI, C++ helpers retained

Per the issue #9 comment, the product UI is Electron + React. C++ stays for FFmpeg and math helpers (`app/src/job_runner.*`, `app/src/ffmpeg.*`, `app/src/Preview.*`, `app/src/host_main.cpp`). The new GUI lives in `app/gui/` and drives the same `job.json` contract (ARCHITECTURE.md v2) by spawning `python -m chromainvert run` or `chromainvert-host`, then parsing stdout JSONL progress.

- Qt 6 C++ framework: rejected. Mixed LGPL, GPLv3, and commercial licensing makes this project risky.
- Dear ImGui: rejected for the product UI. It looks too developer focused for a consumer product. May be revisited only for internal debug views.
- Native Win32 host (`app/src/MainWindow.*`, `app/src/JobRunner.*`, `app/src/main.cpp`): legacy fallback. It still builds, but it is not the product path. No new Win32 or Qt widgets.

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
- File dialogs and video preview are DIY; need native dialogs via tinyfiledialogs or manual Win32.
- Looks like a debug tool, not a product; extra work to polish.
- Still needs GLFW or SDL via vcpkg or vendored source, so similar bootstrapping as Qt.

Verdict: rejected for the product UI per issue #9: looks too developer focused for a consumer product. The Electron GUI in `app/gui/` is the product path.

### CLI only + web demo page (fallback)
Pros: zero GUI risk, contract stays CLI.
Cons: weaker demo, no scrub or wipe story, judges expect a desktop app.

Verdict: kept as fallback; the console host for issue #3 provides this.

### Legacy note: native Win32 host (kept, not the product path)

The earlier pragmatic choice for issue #9 was a native Win32 host that satisfies the one-screen spec without external dependencies:

- Why it existed: builds with only the Windows SDK and C++17. Works with MSVC (vcvars64) and MinGW-w64 GCC 13+ already on the machine. No vcpkg, no Qt download, cmake builds in seconds.
- What it proves: file pickers, Match and Cancel buttons, progress bar driven by engine JSONL, Strength plus LUT size plus device controls, log pane, and a JobRunner that writes `job.json` (contract v1) and spawns `chromainvert run`. Preview with wipe slider, scopes, and a device badge are follow-up issues, not part of this skeleton.
- Product path: the Electron + React GUI in `app/gui/` reuses the same `job.json` contract. No QMainWindow follow-up; the `CHROMAINVERT_USE_QT` switch will not be added.

If the Electron GUI is unavailable, the Win32 host remains a shippable fallback artifact.

## Consequences

- Build: `cmake -B build -S app` then `cmake --build build` produces `build/Release/ChromaInvert.exe`.
- Runtime deps: Python with `chromainvert` installed on PATH. Missing tools show a plain language dialog and a log line, per Section 8.4. FFmpeg and ffprobe are used by the validation scripts; host-driven preview arrives with #10.
- No embedded Python: subprocess plus files, per Section 4.1. The log pane shows the engine JSONL tail.
- Next issues: #10 (FFmpeg decode and preview link) and #11 (scopes) build on this host without framework churn.

## Build steps for Windows (documented here and in app/README.md)

Prerequisites:
- CMake 3.20 or newer
- MSVC 2022 (run `vcvars64.bat`) or MinGW-w64 GCC 13+
- FFmpeg on PATH (winget `Gyan.FFmpeg`)
- Python 3.10+ with `pip install -e ./engine`

Electron GUI (product path, in `app/gui/`):
```
cd app/gui
npm install
npm run dev
```

Win32 host (legacy fallback):
```
cmake -B build -S app
cmake --build build --config Release
.\build\Release\ChromaInvert.exe   (MSVC multi-config)
.\build\ChromaInvert.exe           (MinGW single-config)
```

No Qt port. Qt was rejected per issue #9 for licensing risk.

The Electron GUI spawns the same engine entry points as the C++ hosts and parses the same stdout JSONL protocol.

Notes:
- The app opts into system DPI awareness at startup so the fixed-pixel layout scales as a unit; per-monitor layout scaling is a follow-up. No external manifest needed.
- JobRunner writes `job.json` and `report.json` next to the chosen output `.cube` path; all job paths may be absolute (relative typed paths are canonicalized first).
- Progress is JSONL on stdout; cancellation kills the child process.
