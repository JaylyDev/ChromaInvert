# ChromaInvert C++ Host (Level 1)

Level 1 uses FFmpeg/ffprobe executables as subprocesses. Commands are printed to the log pane for credibility.

## Build

```
cmake -S app -B app/build -G "Ninja"
cmake --build app/build
```

## Run

Ensure ffmpeg and ffprobe are on PATH. Then:

```
./app/build/chromainvert_app path/to/video.mp4
```

## Level 2 plan

Link libavformat/libavcodec/libswscale via vcpkg for in-app decode and real-time preview. Add find_package(FFmpeg) and link against the targets. No change to Level 1 commands.