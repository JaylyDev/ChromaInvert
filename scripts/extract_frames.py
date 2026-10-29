import argparse
import subprocess
from pathlib import Path


def _probe_duration(video: Path) -> float | None:
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if proc.returncode != 0:
        return None
    token = (proc.stdout or "").strip().split()[0] if (proc.stdout or "").strip() else ""
    try:
        value = float(token)
    except ValueError:
        return None
    return value if value > 0 else None


def extract_frames(video: Path | str, out_dir: Path | str, num_frames: int = 3) -> list[Path]:
    video = Path(video)
    out_dir = Path(out_dir)
    if num_frames < 1:
        raise ValueError("num_frames must be positive")
    out_dir.mkdir(parents=True, exist_ok=True)
    duration = _probe_duration(video)
    if duration is not None:
        if num_frames > 1:
            timestamps = [duration * i / (num_frames + 1) for i in range(1, num_frames + 1)]
        else:
            timestamps = [duration / 2]
    else:
        timestamps = [float(i) for i in range(num_frames)]
    results: list[Path] = []
    for idx, ts in enumerate(timestamps, start=1):
        out_path = out_dir / f"frame_{idx:03d}.png"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-ss",
                f"{ts:.3f}",
                "-i",
                str(video),
                "-frames:v",
                "1",
                "-q:v",
                "2",
                str(out_path),
            ],
            check=True,
        )
        if not out_path.exists():
            raise RuntimeError(f"ffmpeg did not produce {out_path}")
        results.append(out_path)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract N frames from a video via FFmpeg.")
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--num-frames", type=int, default=3)
    args = parser.parse_args()
    frames = extract_frames(args.video, args.out_dir, args.num_frames)
    for f in frames:
        print(f)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
