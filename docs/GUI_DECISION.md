# GUI Framework Decision

Date: 2026-10-29
Status: decided, implemented as Win32 fallback with Qt 6 target
Related: Section 8.1 of docs/CHROMAINVERT_HACKATHON_PLAN.md, docs/ARCHITECTURE.md, issue #9

## Options evaluated

### Qt 6 + CMake + vcpkg (recommended product path)
Pros:
- Real file dialogs, sliders, image panes, cross platform.
- Good video widget story, stylesheets, high-DPI support.
- Mature progress and threading model, LGPL is fine for hackathon.

Cons:
- Heavier setup: vcpkg bootstrap, Qt 6 SDK (about 1 GB), CMake toolchain file, build time 10 to 30 minutes first install.
- Not available on the build agent without vcpkg. The current demo machine has MSVC 19.44 and MinGW 13.2 but no vcpkg or Qt dev packages.
- Would block the vertical slice if we waited for it.

Verdict: chosen as the product target for the Qt follow-up port. This is the long term GUI.

### Dear ImGui + GLFW or SDL (fastest to first window)
Pros:
- Fastest to first window, excellent for scopes and plots via ImPlot.
- Single source vendor, no MOC, tiny build.

Cons:
- File dialogs and video preview are DIY; need native dialogs via tinyfiledialogs or manual Win32.
- Looks like a debug tool, not a product; extra work to polish.
- Still needs GLFW or SDL via vcpkg or vendored source, so similar bootstrapping as Qt.

Verdict: strong runner-up. Revisit if scope panel needs ImPlot performance. The Win32 host below can embed ImGui later without changing the JobRunner contract.

### CLI only + web demo page (fallback)
Pros: zero GUI risk, contract stays CLI.
Cons: weaker demo, no scrub or wipe story, judges expect a desktop app.

Verdict: kept as fallback; the console host for issue #3 provides this.

### Decision for this milestone: native Win32 host (pragmatic hackathon build)

The pragmatic choice for issue #9 is a native Win32 host that satisfies the one-screen spec without external dependencies:

- Why now: builds with only the Windows SDK and C++17. Works with MSVC (vcvars64) and MinGW-w64 GCC 13+ already on the machine. No vcpkg, no Qt download, cmake builds in seconds.
- What it proves: file pickers, Match and Cancel buttons, progress bar driven by engine JSONL, Strength plus LUT size plus device controls, log pane, and a JobRunner that writes `job.json` (contract v1) and spawns `chromainvert run`. These are exactly the acceptance criteria for #9. Preview with wipe slider, scopes, and a device badge are follow-up issues, not part of this skeleton.
- Migration path: the window class and JobRunner use the same job.json contract as the Qt design. Swapping the Win32 MainWindow for a QMainWindow is a follow-up: same fields, same signals, same FFmpeg subprocess layer. That follow-up adds the Qt sources plus a `CHROMAINVERT_USE_QT` CMake switch.

If Qt 6 is found, the build can be switched on; until then the Win32 host is the shippable demo artifact.

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

Win32 host:
```
cmake -B build -S app
cmake --build build --config Release
.\build\Release\ChromaInvert.exe   (MSVC multi-config)
.\build\ChromaInvert.exe           (MinGW single-config)
```

Qt host (follow-up, not in tree yet):
```
cmake -B build -S app -DCHROMAINVERT_USE_QT=ON -DCMAKE_PREFIX_PATH=C:/Qt/6.9.0/msvc2022_64
cmake --build build
```

The Qt port adds the QMainWindow sources and the switch above; until then the Win32 host is the shippable demo artifact.

Notes:
- The app opts into system DPI awareness at startup so the fixed-pixel layout scales as a unit; per-monitor layout scaling is a follow-up. No external manifest needed.
- JobRunner writes `job.json` and `report.json` next to the chosen output `.cube` path; all job paths may be absolute (relative typed paths are canonicalized first).
- Progress is JSONL on stdout; cancellation kills the child process.
