# ChromaInvert console host

C++17 console driver for the ChromaInvert engine. It extracts frames with
FFmpeg, writes `job.json` (contract v1), spawns the Python engine, streams
JSONL progress, prints the `report.json` summary, and applies the exported
`.cube` with FFmpeg `lut3d`.

## Build (Windows)

Requires CMake 3.16+ and a C++17 compiler. No libraries beyond the standard
library.

```powershell
cmake -S app -B build -G "MinGW Makefiles"
cmake --build build
```

The binary is `build/chromainvert-host.exe`. `ffmpeg`, `ffprobe`, and
`python` (with the engine installed, see repo `AGENTS.md`) must be on PATH,
or pass `--ffmpeg`, `--ffprobe`, `--python` explicitly.

## Run

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
