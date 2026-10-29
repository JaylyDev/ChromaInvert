import argparse
import subprocess
import sys
from pathlib import Path

import imageio.v2 as imageio
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

from chromainvert.color import delta_e_2000, linear_srgb_to_lab, srgb_to_linear
from chromainvert.cube import read_cube


def _escape_filter_path(path: str) -> str:
    out = path.replace("\\", "/")
    for ch in (":", ",", ";", "[", "]", "'", "="):
        out = out.replace(ch, "\\" + ch)
    return out


def read_rgb_file(path: Path) -> np.ndarray:
    raw = imageio.imread(path)
    if raw.ndim == 2:
        raw = np.stack((raw, raw, raw), axis=-1)
    if raw.dtype.kind in "iu":
        scale = float(np.iinfo(raw.dtype).max)
    else:
        scale = 1.0
    return raw[..., :3].astype(np.float64) / scale


def run_ffmpeg_lut3d(cube: Path, image: Path, out: Path) -> tuple[int, str]:
    cmd = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(image),
        "-vf",
        "lut3d=file=" + _escape_filter_path(cube.name),
        "-frames:v",
        "1",
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(cube.parent))
    return proc.returncode, (proc.stderr or "").strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cube", type=Path)
    parser.add_argument("image", type=Path)
    parser.add_argument("--expected-size", type=int, default=33)
    args = parser.parse_args()

    cube_path = args.cube.resolve()
    image_path = args.image.resolve()
    out_path = cube_path.parent / "real_graded.png"

    lut = read_cube(cube_path)

    size_ok = lut.size == args.expected_size
    finite_ok = bool(np.all(np.isfinite(lut.lattice)))
    lmin = float(lut.lattice.min())
    lmax = float(lut.lattice.max())
    min_ok = 0.0 <= lmin <= 1.0
    max_ok = 0.0 <= lmax <= 1.0
    diffs = [float(np.abs(np.diff(lut.lattice, axis=a)).max()) for a in (0, 1, 2)]
    neighbor = max(diffs) if diffs else 0.0
    neighbor_ok = neighbor < 0.5
    neighbor_warn = neighbor >= 0.2
    title_ok = isinstance(lut.title, str) and len(lut.title) > 0
    domain_ok = lut.domain_min == (0.0, 0.0, 0.0) and lut.domain_max == (1.0, 1.0, 1.0)

    print(f"LUT_3D_SIZE: {lut.size} ({'PASS' if size_ok else 'FAIL'})")
    print(f"finite: {finite_ok} ({'PASS' if finite_ok else 'FAIL'})")
    print(f"lattice_min: {lmin:.6f} ({'PASS' if min_ok else 'FAIL'})")
    print(f"lattice_max: {lmax:.6f} ({'PASS' if max_ok else 'FAIL'})")
    print(f"max_neighbor_delta: {neighbor:.6f} ({'PASS' if neighbor_ok else 'FAIL'}{' WARN: high' if neighbor_warn else ''})")
    print(f"title: {lut.title!r} ({'PASS' if title_ok else 'FAIL'})")
    print(f"domain: {lut.domain_min} {lut.domain_max} ({'PASS' if domain_ok else 'FAIL'})")

    ok = size_ok and finite_ok and min_ok and max_ok and neighbor_ok and title_ok and domain_ok

    code, err = run_ffmpeg_lut3d(cube_path, image_path, out_path)
    ffmpeg_ok = code == 0 and out_path.exists()
    print(f"ffmpeg lut3d: code={code} out={out_path} ({'PASS' if ffmpeg_ok else 'FAIL'})")
    if err:
        print(f"ffmpeg stderr: {err}")
    ok = ok and ffmpeg_ok

    if ffmpeg_ok:
        src = read_rgb_file(image_path)
        grd = read_rgb_file(out_path)
        src_lin = srgb_to_linear(src.reshape(-1, 3))[::16]
        grd_lin = srgb_to_linear(grd.reshape(-1, 3))[::16]
        de = float(delta_e_2000(linear_srgb_to_lab(src_lin), linear_srgb_to_lab(grd_lin)).mean())
        print(f"effect_magnitude_dE00 (informational): {de:.4f}")

    if ok:
        print("PASS")
        return 0
    print("FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
