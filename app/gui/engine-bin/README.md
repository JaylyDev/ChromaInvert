# Bundled engine directory (gitignored, built per platform)

Each release platform ships its own `chromainvert-engine` directory bundle
inside the installed app. Directory mode (not single-file): torch ships
multi-hundred-megabyte cuDNN DLLs that the single-file bootloader cannot
reliably extract on Windows. Build on each release machine from the repo root
(PyInstaller cannot cross-compile):

```
python scripts/build_engine_bundle.py
```

Expected layout (bundle dir holding the exe plus its libraries):

```
app/gui/engine-bin/win/chromainvert-engine/chromainvert-engine.exe
app/gui/engine-bin/mac/chromainvert-engine/chromainvert-engine
app/gui/engine-bin/linux/chromainvert-engine/chromainvert-engine
```

`electron-builder` copies `engine-bin/${os}` into `<resources>/engine-bin/`
(see the `extraResources` entry in `app/gui/package.json`), so the packaged
GUI finds the binary next to `process.resourcesPath` with no Python required.
Binaries and staging dirs are gitignored; every `dist*` script runs
`scripts/ensure-engine-bin.js` first so packaging still succeeds when no
binary was staged.
