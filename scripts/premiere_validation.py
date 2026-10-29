import argparse
import json
import shutil
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
from chromainvert.color import delta_e_2000, linear_srgb_to_lab, srgb_to_linear
from chromainvert.cube import CubeLut, read_cube, write_cube
from chromainvert.lut_module import DifferentiableLUT3D


def read_rgb(path: Path) -> NDArray[np.float32]:
    raw = imageio.imread(path)
    if raw.ndim == 2:
        raw = np.stack((raw, raw, raw), axis=-1)
    if raw.ndim != 3 or raw.shape[-1] not in (3, 4):
        raise ValueError(f"expected an RGB image, got shape {raw.shape}")
    if np.issubdtype(raw.dtype, np.integer):
        scale = float(np.iinfo(raw.dtype).max)
    elif np.issubdtype(raw.dtype, np.floating):
        scale = 1.0
    else:
        raise ValueError(f"unsupported image dtype: {raw.dtype}")
    return (raw[..., :3].astype(np.float32) / scale)


def write_rgb(path: Path, image: NDArray[np.floating]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pixels = np.clip(np.asarray(image), 0.0, 1.0)
    if pixels.ndim == 2:
        pixels = np.stack((pixels, pixels, pixels), axis=-1)
    if pixels.ndim != 3 or pixels.shape[-1] not in (3, 4):
        raise ValueError(f"expected an RGB image, got shape {pixels.shape}")
    pixels = pixels[..., :3]
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
    arr_a = np.asarray(a)
    arr_b = np.asarray(b)
    if arr_a.shape != arr_b.shape:
        raise ValueError(f"shape mismatch in de00_stats: {arr_a.shape} vs {arr_b.shape}")
    if arr_a.size == 0:
        raise ValueError("empty input in de00_stats")
    flat_a = arr_a.reshape(-1, 3)[::16]
    flat_b = arr_b.reshape(-1, 3)[::16]
    if flat_a.shape[0] == 0:
        raise ValueError("no samples after subsampling in de00_stats")
    de = delta_e_2000(linear_srgb_to_lab(srgb_to_linear(flat_a)), linear_srgb_to_lab(srgb_to_linear(flat_b)))
    return {
        "mean": float(de.mean()),
        "p50": float(np.percentile(de, 50)),
        "p95": float(np.percentile(de, 95)),
        "max": float(de.max()),
    }


def rgb_stats(a: NDArray[np.floating], b: NDArray[np.floating]) -> dict:
    arr_a = np.asarray(a, dtype=np.float64)
    arr_b = np.asarray(b, dtype=np.float64)
    if arr_a.shape != arr_b.shape:
        raise ValueError(f"shape mismatch in rgb_stats: {arr_a.shape} vs {arr_b.shape}")
    if arr_a.size == 0:
        raise ValueError("empty input in rgb_stats")
    diff = np.abs(arr_a - arr_b)
    mse = float(np.mean((arr_a - arr_b) ** 2))
    psnr = float(20.0 * np.log10(1.0 / np.sqrt(mse))) if mse > 0 else 99.0
    return {"mean_abs": float(diff.mean()), "max_abs": float(diff.max()), "psnr_db": psnr}


def compare_pair(name: str, a: NDArray[np.floating], b: NDArray[np.floating]) -> dict:
    arr_a = np.asarray(a)
    arr_b = np.asarray(b)
    if arr_a.shape != arr_b.shape:
        raise ValueError(f"shape mismatch for {name}: {arr_a.shape} vs {arr_b.shape}")
    if arr_a.size == 0:
        raise ValueError(f"empty input for {name}")
    report: dict = {"pair": name}
    report.update(de00_stats(arr_a, arr_b))
    report.update(rgb_stats(arr_a, arr_b))
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
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    if shutil.which("ffmpeg") is None:
        print("FAIL: ffmpeg not found on PATH")
        return 1

    if args.source is not None:
        source = read_rgb(args.source)
        src_png = args.workdir / "premiere_src.png"
        write_rgb(src_png, source)
    else:
        source = make_chart().astype(np.float32)
        src_png = args.workdir / "premiere_src.png"
        write_rgb(src_png, source)
    source = read_rgb(src_png)

    if args.cube is not None:
        lut = read_cube(args.cube)
        cube_path = args.cube
        if lut.domain_min != (0.0, 0.0, 0.0) or lut.domain_max != (1.0, 1.0, 1.0):
            print("FAIL: non-default DOMAIN_MIN/DOMAIN_MAX is not supported by this validation")
            return 1
    else:
        lattice = commercial_style_lattice(33).astype(np.float32)
        lut = CubeLut(size=33, lattice=lattice, title="PremiereValidation")
        cube_path = args.workdir / "premiere_test.cube"
        write_cube(cube_path, lut)

    python_graded = apply_python(source, lut.lattice)
    write_rgb(args.workdir / "premiere_python.png", python_graded)
    python_graded = read_rgb(args.workdir / "premiere_python.png")

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
        if premiere.shape != ffmpeg_tetrahedral.shape:
            print(f"FAIL: premiere still shape {premiere.shape} != ffmpeg tetrahedral shape {ffmpeg_tetrahedral.shape}")
            report = {
                "cube": str(cube_path),
                "cube_size": int(lut.size),
                "source": str(args.source) if args.source is not None else "synthetic_chart",
                "comparisons": comparisons,
                "premiere": None,
                "premiere_tested": True,
                "pass": False,
                "error": f"shape mismatch: {premiere.shape} vs {ffmpeg_tetrahedral.shape}",
            }
            out_path.write_text(json.dumps(report, indent=2, allow_nan=False))
            return 1
        premiere_report = compare_pair("premiere_vs_ffmpeg_tetrahedral", premiere, ffmpeg_tetrahedral)

    tril_gap = comparisons[0]
    tetra_gap = comparisons[2]
    passed = bool(tril_gap["mean"] <= args.threshold)
    if premiere_report is not None:
        passed = bool(passed and premiere_report["mean"] < args.premiere_threshold)

    report = {
        "cube": str(cube_path),
        "cube_size": int(lut.size),
        "source": str(args.source) if args.source is not None else "synthetic_chart",
        "threshold_python_trilinear_mean_de00": float(args.threshold),
        "premiere_threshold_mean_de00": float(args.premiere_threshold),
        "comparisons": comparisons,
        "premiere": premiere_report,
        "premiere_tested": premiere_report is not None,
        "pass": passed,
    }
    out_path.write_text(json.dumps(report, indent=2, allow_nan=False))
    print(f"source: {report['source']}")
    print(f"cube: {report['cube']} (size {report['cube_size']})")
    for entry in comparisons:
        print(f"{entry['pair']}: mean dE00 {entry['mean']:.3f}, p95 {entry['p95']:.3f}, max {entry['max']:.3f}, PSNR {entry['psnr_db']:.1f} dB")
    print(f"tetrahedral gap (trilinear vs tetrahedral): mean dE00 {tetra_gap['mean']:.3f}, max {tetra_gap['max']:.3f}")
    if premiere_report is not None:
        print(f"premiere vs ffmpeg tetrahedral: mean dE00 {premiere_report['mean']:.3f}, max {premiere_report['max']:.3f}")
    if premiere_report is None:
        print("note: Premiere not tested (no --premiere-still); result covers FFmpeg/Python only")
    print("PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
