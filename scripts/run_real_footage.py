import argparse
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

from extract_frames import extract_frames

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".mxf"}


def _is_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTS


def _make_synthetic_source(out_dir: Path, num_frames: int) -> None:
    import imageio.v2 as imageio
    import numpy as np

    out_dir.mkdir(parents=True, exist_ok=True)
    for i in range(num_frames):
        arr = np.zeros((64, 64, 3), dtype=np.uint8)
        gradient = (np.arange(64) / 63.0 * 255).astype(np.uint8)
        arr[:, :, 0] = gradient[None, :]
        arr[:, :, 1] = gradient[:, None]
        arr[:, :, 2] = 128
        imageio.imwrite(out_dir / f"synthetic_src_{i:03d}.png", arr)


def _make_synthetic_reference(out_dir: Path, num_frames: int) -> None:
    import imageio.v2 as imageio
    import numpy as np

    out_dir.mkdir(parents=True, exist_ok=True)
    for i in range(num_frames):
        arr = np.zeros((64, 64, 3), dtype=np.uint8)
        gradient = (np.arange(64) / 63.0 * 255).astype(np.uint8)
        arr[:, :, 0] = np.clip(gradient[None, :] * 1.15 + 8, 0, 255).astype(np.uint8)
        arr[:, :, 1] = gradient[:, None]
        arr[:, :, 2] = np.clip(gradient[None, :] * 0.85, 0, 255).astype(np.uint8)
        imageio.imwrite(out_dir / f"synthetic_ref_{i:03d}.png", arr)


def _collect_images(
    inp: Path | None,
    out_dir: Path,
    num_frames: int,
    synthetic_fn: Callable[[Path, int], None],
    allow_synthetic: bool,
) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    if inp is None:
        if not allow_synthetic:
            raise ValueError("missing required input")
        print("WARNING: using synthetic fallback")
        synthetic_fn(out_dir, num_frames)
        return sorted(out_dir.glob("*.png"))[:num_frames]
    path = Path(inp)
    if not path.exists():
        raise FileNotFoundError(f"input not found: {path}")
    if path.is_dir():
        images = sorted(x for x in path.iterdir() if x.is_file() and _is_image(x))[:num_frames]
        if images:
            for idx, src in enumerate(images, start=1):
                shutil.copy2(src, out_dir / f"frame_{idx:03d}{src.suffix}")
            return sorted(out_dir.glob("frame_*"))[:num_frames]
        videos = sorted(x for x in path.iterdir() if x.is_file() and x.suffix.lower() in VIDEO_EXTS)
        if videos:
            extract_frames(videos[0], out_dir, num_frames)
            return sorted(out_dir.glob("*.png"))[:num_frames]
        raise FileNotFoundError(f"no images or videos found in directory: {path}")
    if path.is_file():
        if _is_image(path):
            shutil.copy2(path, out_dir / f"frame_001{path.suffix}")
            return [out_dir / f"frame_001{path.suffix}"]
        extract_frames(path, out_dir, num_frames)
        return sorted(out_dir.glob("*.png"))[:num_frames]
    raise FileNotFoundError(f"unsupported input: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ChromaInvert on real or synthetic footage.")
    parser.add_argument("--source", type=Path, default=None)
    parser.add_argument("--reference", type=Path, default=None)
    parser.add_argument("--output-cube", type=Path, default=None)
    parser.add_argument("--work-dir", type=Path, default=ROOT / "work")
    parser.add_argument("--iterations", type=int, default=150)
    parser.add_argument("--fine-iterations", type=int, default=30)
    parser.add_argument("--coarse-size", type=int, default=17)
    parser.add_argument("--lut-size", type=int, default=33)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--strength", type=float, default=1.0)
    parser.add_argument("--num-frames", type=int, default=3)
    args = parser.parse_args()

    work_dir = args.work_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    if args.output_cube is None:
        args.output_cube = work_dir / "out.cube"
    output_cube = args.output_cube.resolve()

    source_dir = work_dir / "frames" / "source"
    reference_dir = work_dir / "frames" / "reference"

    # Resolve inputs before wiping any directories.
    source_input = args.source
    reference_input = args.reference
    both_none = source_input is None and reference_input is None
    if (source_input is None) != (reference_input is None):
        raise ValueError("source and reference must both be set or both be omitted")
    # refuse if an input lives under a directory we are about to wipe
    resolved_inputs = [Path(p).resolve() for p in (source_input, reference_input) if p is not None]
    for inp in resolved_inputs:
        for d in (source_dir, reference_dir):
            if inp.is_relative_to(d.resolve()):
                raise ValueError(f"input must not be inside the output directory: {inp}")

    for d in (source_dir, reference_dir):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)

    allow_synthetic = both_none
    source_files = _collect_images(source_input, source_dir, args.num_frames, _make_synthetic_source, allow_synthetic)
    reference_files = _collect_images(reference_input, reference_dir, args.num_frames, _make_synthetic_reference, allow_synthetic)

    job = {
        "contract_version": 1,
        "source_frames": [p.relative_to(work_dir).as_posix() for p in source_files],
        "reference_frames": [p.relative_to(work_dir).as_posix() for p in reference_files],
        "input_profile": "rec709",
        "coarse_size": args.coarse_size,
        "lut_size": args.lut_size,
        "iterations": args.iterations,
        "fine_iterations": args.fine_iterations,
        "strength": args.strength,
        "seed": args.seed,
        "device": args.device,
        "output_cube": output_cube.as_posix(),
        "report_json": (work_dir / "report.json").as_posix(),
    }
    job_path = work_dir / "job.json"
    job_path.write_text(json.dumps(job, indent=2))

    output_cube.parent.mkdir(parents=True, exist_ok=True)

    print(f"job written: {job_path}", flush=True)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "engine") + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run(
        [sys.executable, "-m", "chromainvert", "run", str(job_path)],
        cwd=str(ROOT),
        env=env,
    )
    if result.returncode != 0:
        print(f"chromainvert run failed with code {result.returncode}")
        return result.returncode

    if not output_cube.exists():
        print(f"output cube missing: {output_cube}")
        return 1

    validate_script = ROOT / "scripts" / "validate_real_footage.py"
    if not both_none and source_files:
        v = subprocess.run(
            [
                sys.executable,
                str(validate_script),
                str(output_cube),
                str(source_files[0].resolve()),
                "--expected-size",
                str(args.lut_size),
            ],
            env=env,
        )
        if v.returncode != 0:
            print("validation failed", flush=True)
            return v.returncode
    elif both_none:
        print("synthetic fallback: skipping real-footage validation", flush=True)

    print(f"output cube: {output_cube}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
