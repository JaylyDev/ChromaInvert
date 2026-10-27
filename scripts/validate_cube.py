import argparse
import subprocess
import sys
from pathlib import Path

import imageio.v2 as imageio
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

from chromainvert.cube import CubeLut, identity_lattice, write_cube


def run(cmd: list[str], workdir: Path) -> None:
    subprocess.run(cmd, check=True, cwd=workdir)


def read_rgb(path: Path) -> np.ndarray:
    return imageio.imread(path)[..., :3].astype(np.float32) / 255.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, default=33)
    parser.add_argument("--workdir", type=Path, default=ROOT / "work")
    args = parser.parse_args()
    args.workdir.mkdir(parents=True, exist_ok=True)

    identity = args.workdir / "identity.cube"
    write_cube(identity, CubeLut(size=args.size, lattice=identity_lattice(args.size), title="Identity"))
    src = args.workdir / "src.png"
    graded = args.workdir / "graded.png"
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=256x256:rate=1:duration=1", "-frames:v", "1", "src.png"], args.workdir)
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", "src.png", "-vf", "lut3d=file=identity.cube", "-frames:v", "1", "graded.png"], args.workdir)
    peak = float(np.max(np.abs(read_rgb(src) - read_rgb(graded))))
    print(f"identity peak diff: {peak}")
    assert peak == 0.0

    swap = args.workdir / "swap_rb.cube"
    write_cube(swap, CubeLut(size=9, lattice=identity_lattice(9)[..., ::-1], title="SwapRB"))
    red_src = args.workdir / "red.png"
    red_graded = args.workdir / "red_graded.png"
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=color=red:size=64x64:rate=1:duration=1", "-frames:v", "1", "red.png"], args.workdir)
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", "red.png", "-vf", "lut3d=file=swap_rb.cube", "-frames:v", "1", "red_graded.png"], args.workdir)
    mean_color = read_rgb(red_graded).reshape(-1, 3).mean(axis=0)
    print(f"swap_rb red->mean rgb: {mean_color.tolist()}")
    assert bool(np.all(np.abs(mean_color - np.array([0.0, 0.0, 1.0], dtype=np.float32)) < 0.01))
    print("PASS")


main()
