"""Build the single-file chromainvert-engine executable and stage it for the GUI.

Dev-machine command (run from the repo root):

    python scripts/build_engine_bundle.py

This runs PyInstaller on engine/chromainvert-engine.spec, then copies the
binary to app/gui/engine-bin/<platform>/ (win, mac, or linux), which
electron-builder ships inside the installed app via extraResources (see
app/gui/package.json). The GUI prefers the bundled binary, then
chromainvert-engine on PATH, then `python -m chromainvert`.

Requires a dev machine with the engine env plus PyInstaller:

    pip install -e ./engine
    pip install pyinstaller

PyInstaller cannot cross-compile, so run this on each release platform.
"""

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE_DIR = ROOT / "engine"
SPEC = ENGINE_DIR / "chromainvert-engine.spec"
STAGE_ROOT = ROOT / "app" / "gui" / "engine-bin"
HOST_PLATFORMS = {"Windows": "win", "Darwin": "mac", "Linux": "linux"}


def resolve_platform(raw: str) -> str:
    if raw != "auto":
        return raw
    host = HOST_PLATFORMS.get(platform.system(), "")
    if host == "":
        raise SystemExit(f"unsupported build host: {platform.system()}")
    return host


def find_binary(dist_dir: Path) -> Path:
    exe = dist_dir / "chromainvert-engine.exe"
    if exe.is_file():
        return exe
    plain = dist_dir / "chromainvert-engine"
    if plain.is_file():
        return plain
    raise SystemExit(f"no chromainvert-engine binary in {dist_dir}: build first without --skip-build")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", choices=("auto", "win", "mac", "linux"), default="auto")
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()
    staged = resolve_platform(args.platform)
    if not args.skip_build:
        subprocess.run(
            [sys.executable, "-m", "PyInstaller", SPEC.name, "--noconfirm", "--clean"],
            cwd=ENGINE_DIR,
            check=True,
        )
    binary = find_binary(ENGINE_DIR / "dist")
    dest_dir = STAGE_ROOT / staged
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / binary.name
    shutil.copy2(binary, dest)
    print(f"staged {dest}")
    print("next: cd app/gui && npm run dist")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
