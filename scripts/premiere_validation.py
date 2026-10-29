import argparse
import json
import subprocess
import sys
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
import torch
from numpy.typing import NDArray

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

from chromainvert.benchmark import commercial_style_lattice, make_chart
from chromainvert.color import delta_e_2000, linear_srgb_to_lab
from chromainvert.cube import CubeLut, read_cube, write_cube
from chromainvert.lut_module import DifferentiableLUT3D


def read_rgb(path: Path) -> NDArray[np.float32]:
    return imageio.imread(path)[..., :3].astype(np.float32) / 255.0


def write_rgb(path: Path, image: NDArray[np.floating]) -> None:
    pixels = np.clip(np.asarray(image), 0.0, 1.0)
    imageio.imwrite(path, (pixels * 255.0 + 0.5).astype(np.uint8))


def apply_python(image: NDArray[np.floating], lattice: NDArray[np.floating]) -> NDArray[np.float32]:
    module = DifferentiableLUT3D(int(lattice.shape[0]), lattice=np.asarray(lattice, dtype=np.float32))
    with torch.no_grad():
        return module(torch.from_numpy(np.asarray(image, dtype=np.float32))).numpy()


def apply_ffmpeg(src: Path, cube: Path, dst: Path, interp: str, workdir: Path) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            src.name,
            "-vf",
            f"lut3d=file={cube.name}:interp={interp}",
            "-frames:v",
            "1",
            dst.name,
        ],
        check=True,
        cwd=workdir,
    )


def de00_stats(a: NDArray[np.floating], b: NDArray[np.floating]) -> dict:
    flat_a = np.asarray(a).reshape(-1, 3)[::16]
    flat_b = np.asarray(b).reshape(-1, 3)[::16]
    de = delta_e_2000(linear_srgb_to_lab(flat_a), linear_srgb_to_lab(flat_b))
    return {
        "mean": float(de.mean()),
        "p50": float(np.percentile(de, 50)),
        "p95": float(np.percentile(de, 95)),
        "max": float(de.max()),
    }


def rgb_stats(a: NDArray[np.floating], b: NDArray[np.floating]) -> dict:
    diff = np.abs(np.asarray(a, dtype=np.float64) - np.asarray(b, dtype=np.float64))
    mse = float(np.mean((np.asarray(a, dtype=np.float64) - np.asarray(b, dtype=np.float64)) ** 2))
    psnr = float(20.0 * np.log10(1.0 / np.sqrt(mse))) if mse > 0 else float("inf")
    return {"mean_abs": float(diff.mean()), "max_abs": float(diff.max()), "psnr_db": psnr}


def compare_pair(name: str, a: NDArray[np.floating], b: NDArray[np.floating]) -> dict:
    report: dict = {"pair": name}
    report.update(de00_stats(a, b))
    report.update(rgb_stats(a, b))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cube", type=Path, default=None)
    parser.add_argument("--source", type=Path, default=None)
    parser.add_argument("--premiere-still", type=Path, default=None)
    parser.add_argument("--workdir", type=Path, default=ROOT / "work")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--threshold", type=float, default=1.0)
    parser.add_argument("--premiere-threshold", type=float, default=2.0)
    args = parser.parse_args()
    args.workdir.mkdir(parents=True, exist_ok=True)
    out_path = args.out if args.out is not None else args.workdir / "premiere_validation.json"

    if args.source is not None:
        source = read_rgb(args.source)
        src_png = args.workdir / "premiere_src.png"
        write_rgb(src_png, source)
    else:
        source = make_chart().astype(np.float32)
        src_png = args.workdir / "premiere_src.png"
        write_rgb(src_png, source)

    if args.cube is not None:
        lut = read_cube(args.cube)
        cube_path = args.cube
    else:
        lattice = commercial_style_lattice(33).astype(np.float32)
        lut = CubeLut(size=33, lattice=lattice, title="PremiereValidation")
        cube_path = args.workdir / "premiere_test.cube"
        write_cube(cube_path, lut)

    python_graded = apply_python(source, lut.lattice)
    write_rgb(args.workdir / "premiere_python.png", python_graded)

    tril_png = args.workdir / "premiere_ffmpeg_trilinear.png"
    tetra_png = args.workdir / "premiere_ffmpeg_tetrahedral.png"
    ffmpeg_cube = args.workdir / "premiere_ffmpeg.cube"
    if cube_path.resolve() != ffmpeg_cube.resolve():
        ffmpeg_cube.write_bytes(cube_path.read_bytes())
    apply_ffmpeg(src_png, ffmpeg_cube, tril_png, "trilinear", args.workdir)
    apply_ffmpeg(src_png, ffmpeg_cube, tetra_png, "tetrahedral", args.workdir)
    ffmpeg_trilinear = read_rgb(tril_png)
    ffmpeg_tetrahedral = read_rgb(tetra_png)

    comparisons = [
        compare_pair("python_vs_ffmpeg_trilinear", python_graded, ffmpeg_trilinear),
        compare_pair("python_vs_ffmpeg_tetrahedral", python_graded, ffmpeg_tetrahedral),
        compare_pair("ffmpeg_trilinear_vs_tetrahedral", ffmpeg_trilinear, ffmpeg_tetrahedral),
    ]

    premiere_report: dict | None = None
    if args.premiere_still is not None:
        premiere = read_rgb(args.premiere_still)
        premiere_report = compare_pair("premiere_vs_ffmpeg_tetrahedral", premiere, ffmpeg_tetrahedral)

    tril_gap = comparisons[0]
    tetra_gap = comparisons[2]
    passed = bool(tril_gap["mean"] <= args.threshold)
    if premiere_report is not None:
        passed = bool(passed and premiere_report["mean"] <= args.premiere_threshold)

    report = {
        "cube": str(cube_path),
        "cube_size": int(lut.size),
        "source": str(args.source) if args.source is not None else "synthetic_chart",
        "threshold_python_trilinear_mean_de00": float(args.threshold),
        "premiere_threshold_mean_de00": float(args.premiere_threshold),
        "comparisons": comparisons,
        "premiere": premiere_report,
        "pass": passed,
    }
    out_path.write_text(json.dumps(report, indent=2))
    print(f"source: {report['source']}")
    print(f"cube: {report['cube']} (size {report['cube_size']})")
    for entry in comparisons:
        print(f"{entry['pair']}: mean dE00 {entry['mean']:.3f}, p95 {entry['p95']:.3f}, max {entry['max']:.3f}, PSNR {entry['psnr_db']:.1f} dB")
    print(f"tetrahedral gap (trilinear vs tetrahedral): mean dE00 {tetra_gap['mean']:.3f}, max {tetra_gap['max']:.3f}")
    if premiere_report is not None:
        print(f"premiere vs ffmpeg tetrahedral: mean dE00 {premiere_report['mean']:.3f}, max {premiere_report['max']:.3f}")
    print("PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
