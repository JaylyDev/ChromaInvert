import argparse
import json
import subprocess
import sys
from pathlib import Path

import imageio.v2 as imageio
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "engine" / "src"))

from chromainvert.benchmark import apply_lut
from chromainvert.color import decode_input, linear_to_srgb
from chromainvert.cube import CubeLut, read_cube
from ffmpeg_helpers import _check_output, _escape_lut3d_path, extract_frames

PROFILE_BY_FOLDER = {
    "Apple Log": "apple_log",
    "S-log3": "slog3",
    "Rec709": "rec709",
    "Rec2020": "rec2020",
}

VIDEO_EXTS = {".mov", ".mp4", ".mxf", ".avi"}


def grade_frame(src: Path, cube: Path, dst: Path) -> None:
    cmd = [
        "ffmpeg", "-y", "-i", str(src),
        "-vf", f"lut3d=file={_escape_lut3d_path(str(cube))}:interp=trilinear",
        "-pix_fmt", "rgb24", str(dst),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"lut3d grade failed: {(result.stderr or '')[-500:]}")
    _check_output(str(dst))


def grade_frame_working(src: Path, truth: CubeLut, dst: Path, profile: str) -> None:
    if profile != "rec709":
        raise ValueError("working-space synthesis currently supports rec709 only")
    raw = imageio.imread(str(src))
    if np.issubdtype(raw.dtype, np.integer):
        pixels = raw[..., :3].astype(np.float64) / float(np.iinfo(raw.dtype).max)
    else:
        pixels = raw[..., :3].astype(np.float64)
    working = np.asarray(decode_input(pixels, profile), dtype=np.float32)
    graded = apply_lut(working, truth.lattice)
    display = np.clip(np.asarray(linear_to_srgb(graded)) * 65535.0 + 0.5, 0, 65535).astype(np.uint16)
    imageio.imwrite(str(dst), display)
    _check_output(str(dst))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build graded eval pairs from footage and LUTs")
    parser.add_argument("--footage-root", default=str(Path.home() / "Documents" / "SampleFootage"))
    parser.add_argument("--lut", action="append", default=[], help="repeatable .cube path")
    parser.add_argument("--out", default="work/pairs")
    parser.add_argument("--frames-per-clip", type=int, default=3)
    parser.add_argument("--max-clips", type=int, default=4)
    parser.add_argument("--working-synthesis", action="store_true",
                        help="apply the LUT in decoded working space (rec709 clips only) instead of FFmpeg display domain")
    args = parser.parse_args()
    if args.frames_per_clip < 1:
        raise SystemExit("error: --frames-per-clip must be at least 1")
    if args.max_clips < 1:
        raise SystemExit("error: --max-clips must be at least 1")

    root = Path(args.footage_root)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cubes = [Path(p) for p in args.lut]
    if not cubes:
        raise SystemExit("error: pass at least one --lut .cube path")
    truths: list[CubeLut] = []
    for cube in cubes:
        try:
            truths.append(read_cube(str(cube)))
        except (OSError, ValueError) as exc:
            raise SystemExit(f"error: unreadable LUT {cube}: {exc}")

    clips: list[tuple[Path, str]] = []
    for folder, profile in PROFILE_BY_FOLDER.items():
        folder_path = root / folder
        if not folder_path.is_dir():
            continue
        for clip in sorted(folder_path.iterdir()):
            if clip.suffix.lower() in VIDEO_EXTS:
                clips.append((clip, profile))
                break
    clips = clips[: args.max_clips]
    if not clips:
        raise SystemExit(f"error: no clips found under {root}")

    manifest: list[dict] = []
    try:
        for clip, profile in clips:
            src_dir = out / clip.stem / "source"
            extracted = extract_frames(str(clip), str(src_dir), count=args.frames_per_clip + 1, prefix="src")
            sources, heldout_source = extracted[:-1], extracted[-1]
            synthesis = "working" if args.working_synthesis else "display"
            for cube, truth in zip(cubes, truths):
                if args.working_synthesis and profile != "rec709":
                    continue
                graded_dir = out / clip.stem / cube.stem
                graded_dir.mkdir(parents=True, exist_ok=True)
                graded: list[str] = []
                for src in sources:
                    if args.working_synthesis:
                        dst = graded_dir / f"graded_{Path(src).stem}.tif"
                        grade_frame_working(Path(src), truth, dst, profile)
                    else:
                        dst = graded_dir / f"graded_{Path(src).stem}.png"
                        grade_frame(Path(src), cube, dst)
                    graded.append(str(dst))
                manifest.append({
                    "clip": str(clip),
                    "profile": profile,
                    "lut": str(cube),
                    "synthesis": synthesis,
                    "source_frames": sources,
                    "graded_frames": graded,
                    "heldout_source": heldout_source,
                })
                print(f"pair: {clip.name} [{profile}] x {cube.stem}: {len(graded)} frames")
    except (OSError, RuntimeError, ValueError) as exc:
        raise SystemExit(f"error: {exc}")

    if not manifest:
        raise SystemExit("error: no pairs built (working synthesis needs rec709 clips)")
    manifest_path = out / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"wrote {manifest_path} with {len(manifest)} pairs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
