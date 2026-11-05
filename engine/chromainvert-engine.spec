# -*- mode: python ; coding: utf-8 -*-
# ChromaInvert engine bundle: single-file executable exposing the same CLI
# as `python -m chromainvert` (run, predict, benchmark).
#
# Build on a dev machine with the engine env installed (torch, numpy, imageio):
#   cd engine
#   pyinstaller chromainvert-engine.spec --noconfirm
# Or from the repo root (builds plus stages into app/gui/engine-bin/<platform>/):
#   python scripts/build_engine_bundle.py
# PyInstaller cannot cross-compile: run the build on each release platform
# (win, mac, linux) and ship each binary in its own engine-bin subdir.

import os

from PyInstaller.utils.hooks import collect_submodules

SPECPATH = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    [os.path.join(SPECPATH, "chromainvert", "__main__.py")],
    pathex=[SPECPATH],
    binaries=[],
    datas=[],
    hiddenimports=collect_submodules("imageio.plugins"),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="chromainvert-engine",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
