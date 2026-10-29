# ChromaInvert App Hosts

This folder ships two C++ hosts that share the same `job.json` contract
(see `docs/ARCHITECTURE.md`): a native Win32 desktop host and a C++17 console
driver. Both write `job.json`, spawn the Python engine, and parse its stdout
JSONL progress protocol.

## Desktop host (Win32)

Native Win32 skeleton for issue #9: file pickers, Match button, progress bar
driven by the engine JSONL protocol, device and strength controls, and a log
pane. See `docs/GUI_DECISION.md` for the Qt 6 versus ImGui decision and
`docs/ARCHITECTURE.md` for the `job.json` contract.

### Prerequisites

- CMake 3.20 or newer
- MSVC 2022 (`vcvars64.bat`) or MinGW-w64 GCC 13+
- FFmpeg and ffprobe on PATH (validation scripts and later preview work)
- Python 3.10+ with `pip install -e ./engine` from the repo root

### Build

```
cmake -B build -S app -G "Visual Studio 17 2022" -A x64
cmake --build build --config Release
```

The binary lands at `build/Release/ChromaInvert.exe`. With MinGW, replace the
generator flags with `-G "MinGW Makefiles"` and the binary lands at
`build/ChromaInvert.exe`.

### Run

Open `ChromaInvert.exe`, pick a source frame image, a reference frame image,
and an output `.cube` path, then press Match. The host writes `job.json` next
to the output cube, runs `python -m chromainvert run job.json`, and parses the
stdout JSONL progress lines into the progress bar. Cancel kills the engine
process. The log pane shows the engine output tail for debugging.

Contract v1 only grades still frames in the `rec709` profile. Video file
decoding and frame sampling land with issue #10; scopes land with issue #11.

## Console host (`chromainvert-host`)

C++17 console driver for the ChromaInvert engine. It extracts frames with
FFmpeg, writes `job.json` (contract v1), spawns the Python engine, streams
JSONL progress, prints the `report.json` summary, and applies the exported
`.cube` with FFmpeg `lut3d`. The entry point is `app/src/host_main.cpp`;
`app/src/main.cpp` stays the Win32 GUI entry point so both targets build
from this folder.

### Build (Windows)

Requires CMake 3.16+ and a C++17 compiler. No libraries beyond the standard
library.

```powershell
cmake -S app -B build -G "MinGW Makefiles"
cmake --build build
```

The binary is `build/chromainvert-host.exe`. `ffmpeg`, `ffprobe`, and
`python` (with the engine installed, see repo `AGENTS.md`) must be on PATH,
or pass `--ffmpeg`, `--ffprobe`, `--python` explicitly.

### Run

Grade a clip against a reference frame and encode a preview:

```powershell
.\build\chromainvert-host.exe run --source-video clip.mov --reference ref.png `
  --workdir work --preview-out work\preview.mp4
```

Use explicit frames (no extraction) and a short smoke run:

```powershell
.\build\chromainvert-host.exe run --source-frames a.png,b.png --reference-frames r.png `
  --workdir work --iterations 5 --fine-iterations 2 --preview-out work\graded.png
```

Apply an existing `.cube` without running the engine:

```powershell
.\build\chromainvert-host.exe preview --input clip.mov --cube work\out.cube --output work\graded.mp4
```

Notes:

- `run` writes `job.json` with `contract_version` 1 into `--workdir`.
  Relative frame paths in the job file resolve against the job file
  directory, matching `docs/ARCHITECTURE.md`.
- `--job-file`, `--output-cube`, and `--report-json` take plain file names,
  not paths; they always live next to the job file.
- Frame lists are comma separated; spaces around items are ignored. File
  names must not contain commas.
- Arguments with shell expansion characters (`%` and `"` on Windows) are
  refused rather than quoted; rename such files before grading them.
- Contract v1 accepts `rec709` only; other profiles are rejected up front.
- Progress lines from the engine (`progress` events) stream to stdout;
  anything else the engine prints is echoed with an `engine:` prefix.
