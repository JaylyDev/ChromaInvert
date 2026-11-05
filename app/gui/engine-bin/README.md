# Bundled engine binaries (gitignored, built per platform)

Each release platform ships its own single-file `chromainvert-engine`
binary inside the installed app. Build on each release machine from the
repo root (PyInstaller cannot cross-compile):

```
python scripts/build_engine_bundle.py
```

Expected layout (`chromainvert-engine.exe` on Windows, no extension elsewhere):

```
app/gui/engine-bin/win/chromainvert-engine.exe
app/gui/engine-bin/mac/chromainvert-engine
app/gui/engine-bin/linux/chromainvert-engine
```

`electron-builder` copies `engine-bin/${os}` into `<resources>/engine-bin/`
(see the `extraResources` entry in `app/gui/package.json`), so the packaged
GUI finds the binary next to `process.resourcesPath` with no Python required.
Binaries are gitignored; only the `.gitkeep` placeholders are committed, so
packaging still succeeds when no binary was staged.
