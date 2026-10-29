# ChromaInvert Desktop Host

Native Win32 skeleton for issue #9: file pickers, Match button, progress bar
driven by the engine JSONL protocol, device and strength controls, and a log
pane. See `docs/GUI_DECISION.md` for the Qt 6 versus ImGui decision and
`docs/ARCHITECTURE.md` for the `job.json` contract.

## Prerequisites

- CMake 3.20 or newer
- MSVC 2022 (`vcvars64.bat`) or MinGW-w64 GCC 13+
- FFmpeg and ffprobe on PATH
- Python 3.10+ with `pip install -e ./engine` from the repo root

## Build

```
cmake -B build -S app -G "Visual Studio 17 2022" -A x64
cmake --build build --config Release
```

The binary lands at `build/Release/ChromaInvert.exe`. With MinGW, replace the
generator flags with `-G "MinGW Makefiles"` and the binary lands at
`build/ChromaInvert.exe`.

## Run

Open `ChromaInvert.exe`, pick a source frame image, a reference frame image,
and an output `.cube` path, then press Match. The host writes `job.json` next
to the output cube, runs `python -m chromainvert run job.json`, and parses the
stdout JSONL progress lines into the progress bar. Cancel kills the engine
process. The log pane shows the engine output tail for debugging.

Contract v1 only grades still frames in the `rec709` profile. Video file
decoding and frame sampling land with issue #10; scopes land with issue #11.
