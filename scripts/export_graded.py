import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

from chromainvert.cube import read_cube


def check_ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe is None:
        print("error: FFmpeg not found on PATH: install FFmpeg and ensure 'ffmpeg' is on PATH", file=sys.stderr)
        sys.exit(1)
    return exe


def escape_lut3d_path(path: Path) -> str:
    raw = str(path.resolve()).replace("\\", "/")
    specials = "\\':,;=[]"
    escaped = "".join("\\" + c if c in specials else c for c in raw)
    return f"'{escaped}'"


def lut3d_filter(path: Path, interp: str) -> str:
    return f"lut3d=file={escape_lut3d_path(path)}:interp={interp}"


def validate_cube(path: Path) -> None:
    if not path.is_file():
        print(f"error: cube not found: {path}", file=sys.stderr)
        sys.exit(1)
    lut = read_cube(path)
    if lut.size < 2:
        print(f"error: invalid cube {path}: size must be at least 2, got {lut.size}", file=sys.stderr)
        sys.exit(1)
    if lut.lattice.shape != (lut.size, lut.size, lut.size, 3):
        print(f"error: invalid cube {path}: unexpected lattice shape {lut.lattice.shape}", file=sys.stderr)
        sys.exit(1)


def resolve_job_cube(job_path: Path) -> Path:
    data = json.loads(job_path.read_text(encoding="utf-8-sig"))
    raw = data.get("output_cube")
    if raw is None:
        print(f"error: job file {job_path} is missing 'output_cube'", file=sys.stderr)
        sys.exit(1)
    cube = Path(raw)
    if not cube.is_absolute():
        cube = job_path.parent / cube
    return cube


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="export_graded",
        description="Apply a .cube LUT to a video or still image via FFmpeg lut3d and export a Rec.709 tagged MP4",
    )
    p.add_argument("input_pos", nargs="?", help="input video or image path (positional)")
    p.add_argument("cube_pos", nargs="?", help=".cube LUT path (positional)")
    p.add_argument("output_pos", nargs="?", help="output video path (positional)")
    p.add_argument("--input", dest="input", default=None, help="input video or image path")
    p.add_argument("--cube", dest="cube", default=None, help=".cube LUT path")
    p.add_argument("--output", dest="output", default=None, help="output video path")
    p.add_argument("--job", dest="job", default=None, help="work/job.json to read output_cube from (cube may be omitted if job is given)")
    p.add_argument("--fps", type=float, default=None, help="override output fps (default: keep input fps)")
    p.add_argument("--crf", type=int, default=18, help="x264 CRF quality, lower is higher quality (default: 18)")
    p.add_argument("--preset", default="medium", help="x264 preset (default: medium)")
    p.add_argument("--interp", choices=["trilinear", "tetrahedral", "nearest"], default="tetrahedral", help="lut3d interpolation (default: tetrahedral)")
    p.add_argument("--colorspace", default="bt709", help="output colorspace tag (default: bt709)")
    p.add_argument("--color-primaries", dest="color_primaries", default="bt709", help="output color primaries tag (default: bt709)")
    p.add_argument("--color-trc", dest="color_trc", default="bt709", help="output color transfer tag (default: bt709)")
    p.add_argument("--color-range", dest="color_range", default="tv", help="output color range tag, tv or pc (default: tv)")
    p.add_argument("--overwrite", action="store_true", help="overwrite output if it exists (default: refuse)")
    p.add_argument("--no-audio", action="store_true", help="drop audio from output")
    p.add_argument("--dry-run", action="store_true", help="print the FFmpeg command and exit without running")
    p.add_argument("--ffmpeg", default=None, help="path to ffmpeg binary (default: auto from PATH)")
    return p


def resolve_paths(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    input_raw = args.input or args.input_pos
    cube_raw = args.cube or args.cube_pos
    output_raw = args.output or args.output_pos
    if args.job is not None:
        job_path = Path(args.job)
        if not job_path.is_file():
            print(f"error: job file not found: {job_path}", file=sys.stderr)
            sys.exit(1)
        if cube_raw is None:
            cube_raw = str(resolve_job_cube(job_path))
    if input_raw is None:
        print("error: input is required: pass <input> positionally or --input <path>", file=sys.stderr)
        sys.exit(1)
    if cube_raw is None:
        print("error: cube is required: pass <cube> positionally or --cube <path> or --job <job.json>", file=sys.stderr)
        sys.exit(1)
    if output_raw is None:
        print("error: output is required: pass <output> positionally or --output <path>", file=sys.stderr)
        sys.exit(1)
    return Path(input_raw), Path(cube_raw), Path(output_raw)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    input_path, cube_path, output_path = resolve_paths(args)
    if not input_path.is_file():
        print(f"error: input not found: {input_path}", file=sys.stderr)
        return 1
    validate_cube(cube_path)
    if output_path.exists() and not args.overwrite:
        print(f"error: output exists, pass --overwrite to replace: {output_path}", file=sys.stderr)
        return 1
    if output_path.exists() and output_path.resolve() == input_path.resolve():
        print("error: output must differ from input", file=sys.stderr)
        return 1
    if args.crf < 0 or args.crf > 51:
        print("error: --crf must be in [0, 51]", file=sys.stderr)
        return 1
    ffmpeg = args.ffmpeg or check_ffmpeg()
    if args.ffmpeg is not None and not Path(ffmpeg).is_file() and shutil.which(ffmpeg) is None:
        print(f"error: FFmpeg not found: {ffmpeg}", file=sys.stderr)
        return 1
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lut_filter = lut3d_filter(cube_path, args.interp)
    cmd: list[str] = [str(ffmpeg), "-y" if args.overwrite else "-n", "-loglevel", "error", "-i", str(input_path), "-vf", lut_filter]
    if args.fps is not None:
        cmd += ["-r", str(args.fps)]
    cmd += ["-c:v", "libx264", "-preset", args.preset, "-crf", str(args.crf), "-pix_fmt", "yuv420p"]
    cmd += ["-colorspace", args.colorspace, "-color_primaries", args.color_primaries, "-color_trc", args.color_trc, "-color_range", args.color_range]
    if args.no_audio:
        cmd += ["-an"]
    else:
        cmd += ["-c:a", "aac", "-b:a", "128k"]
    if args.fps is not None:
        cmd += ["-vsync", "1"]
    cmd += [str(output_path)]
    if args.dry_run:
        print(" ".join(cmd))
        return 0
    subprocess.run(cmd, check=True)
    print(f"wrote {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
