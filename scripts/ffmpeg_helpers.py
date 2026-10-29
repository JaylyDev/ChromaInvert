import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))


def _version(exe: str) -> Optional[str]:
    try:
        result = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=10)
    except FileNotFoundError:
        return None
    except subprocess.TimeoutExpired:
        return None
    line = (result.stderr or result.stdout or "").splitlines()
    return line[0] if line else None


def check_ffmpeg() -> dict:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    return {
        "ffmpeg_found": ffmpeg is not None,
        "ffprobe_found": ffprobe is not None,
        "ffmpeg_version": _version("ffmpeg"),
        "ffprobe_version": _version("ffprobe"),
        "error": None if (ffmpeg and ffprobe) else "ffmpeg/ffprobe not found on PATH",
    }


def check_python_env() -> dict:
    cuda_available = False
    cuda_device_name = "unknown"
    has_torch = False
    try:
        import torch

        has_torch = True
        cuda_available = bool(torch.cuda.is_available())
        if cuda_available:
            cuda_device_name = torch.cuda.get_device_name(0)
    except Exception:
        pass
    return {
        "python_exe": sys.executable,
        "python_version": sys.version.split()[0],
        "has_torch": has_torch,
        "cuda_available": cuda_available,
        "cuda_device_name": cuda_device_name,
        "error": None,
    }


def _run_ffprobe(path: str) -> dict:
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height,avg_frame_rate,r_frame_rate,duration,pix_fmt,color_primaries,color_transfer,color_space,color_range,bits_per_raw_sample",
        "-show_entries", "format=duration", "-of", "json", path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffprobe failed")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}


def _parse_fps(frac: str) -> str:
    if not frac or frac == "N/A":
        return "unknown"
    if "/" in frac:
        num, den = frac.split("/", 1)
        try:
            n = float(num)
            d = float(den)
            if d == 0:
                return "unknown"
            return str(round(n / d, 3))
        except ValueError:
            return "unknown"
    return frac


def probe_video(path: str) -> dict:
    raw = _run_ffprobe(path)
    streams = raw.get("streams", []) or []
    s = streams[0] if streams else {}
    fmt = raw.get("format", {}) or {}
    duration = s.get("duration") or fmt.get("duration")
    fps_raw = s.get("avg_frame_rate") or s.get("r_frame_rate") or "unknown"
    return {
        "codec": s.get("codec_name") or "unknown",
        "width": s.get("width") or "unknown",
        "height": s.get("height") or "unknown",
        "fps": _parse_fps(fps_raw),
        "duration": float(duration) if duration not in (None, "N/A") else "unknown",
        "pix_fmt": s.get("pix_fmt") or "unknown",
        "primaries": s.get("color_primaries") or "unknown",
        "transfer": s.get("color_transfer") or "unknown",
        "matrix": s.get("color_space") or "unknown",
        "color_range": s.get("color_range") or "unknown",
        "bit_depth": s.get("bits_per_raw_sample") or "unknown",
        "has_audio": False,
        "raw": raw,
    }


def probe_to_job_metadata(probe: dict) -> dict:
    return {
        "codec": probe.get("codec", "unknown"),
        "width": probe.get("width", "unknown"),
        "height": probe.get("height", "unknown"),
        "fps": probe.get("fps", "unknown"),
        "duration": probe.get("duration", "unknown"),
        "pix_fmt": probe.get("pix_fmt", "unknown"),
    }


def format_probe_human(probe: dict) -> str:
    return (
        f"{probe.get('width')}x{probe.get('height')} {probe.get('codec')} "
        f"{probe.get('fps')} fps {probe.get('duration')}s {probe.get('pix_fmt')}"
    )


def extract_frames(video: str, out_dir: str, count: int = 5, prefix: str = "src") -> list[str]:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise FileNotFoundError("ffmpeg not found on PATH")
    probe = probe_video(video)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    duration = probe.get("duration")
    if isinstance(duration, (int, float)) and duration and duration > 0:
        pcts = [0.05, 0.25, 0.5, 0.75, 0.95][:count] if count == 5 else [i / (count + 1) for i in range(1, count + 1)]
        times = [duration * p for p in pcts]
    else:
        times = [0.5 * (i + 1) for i in range(count)]
    paths: list[str] = []
    for i, t in enumerate(times):
        out_path = out / f"{prefix}_{i:03d}.png"
        cmd16 = ["ffmpeg", "-y", "-ss", str(round(t, 3)), "-i", video, "-frames:v", "1", "-pix_fmt", "rgb48be", str(out_path)]
        print(" ".join(cmd16))
        r = subprocess.run(cmd16, capture_output=True, text=True)
        if r.returncode != 0:
            print("16-bit PNG not supported, falling back to 8-bit")
            cmd8 = ["ffmpeg", "-y", "-ss", str(round(t, 3)), "-i", video, "-frames:v", "1", str(out_path)]
            print(" ".join(cmd8))
            subprocess.run(cmd8, check=True, capture_output=True)
        paths.append(str(out_path))
    return paths


def extract_thumbnails(video: str, out_dir: str) -> list[str]:
    return extract_frames(video, out_dir, count=3, prefix="thumb")


def apply_lut_preview(src_video: str, cube_path: str, out_video: str) -> dict:
    cmd = [
        "ffmpeg", "-y", "-i", src_video, "-vf", f"lut3d=file='{cube_path}':interp=tetrahedral",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-colorspace", "bt709",
        "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
        "-movflags", "+faststart", out_video,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return {"command": " ".join(cmd), "success": result.returncode == 0, "stderr": result.stderr}


def grab_frame_at(video: str, timestamp: float, out_path: str) -> str:
    cmd16 = ["ffmpeg", "-y", "-ss", str(timestamp), "-i", video, "-frames:v", "1", "-pix_fmt", "rgb48be", out_path]
    print(" ".join(cmd16))
    r = subprocess.run(cmd16, capture_output=True, text=True)
    if r.returncode != 0:
        print("16-bit PNG not supported, falling back to 8-bit")
        cmd8 = ["ffmpeg", "-y", "-ss", str(timestamp), "-i", video, "-frames:v", "1", out_path]
        print(" ".join(cmd8))
        subprocess.run(cmd8, check=True, capture_output=True)
    return out_path


def preview_before_after(src_video: str, cube_path: str, workdir: str, timestamps: Optional[list[float]] = None) -> dict:
    out = Path(workdir)
    out.mkdir(parents=True, exist_ok=True)
    if timestamps is None:
        probe = probe_video(src_video)
        dur = probe.get("duration")
        if isinstance(dur, (int, float)) and dur:
            timestamps = [dur * 0.25, dur * 0.5, dur * 0.75]
        else:
            timestamps = [0.5, 1.0, 1.5]
    before: list[str] = []
    after: list[str] = []
    graded_video = str(out / "graded.mp4")
    apply_lut_preview(src_video, cube_path, graded_video)
    for i, t in enumerate(timestamps):
        bp = str(out / f"before_{i:03d}.png")
        ap = str(out / f"after_{i:03d}.png")
        grab_frame_at(src_video, t, bp)
        grab_frame_at(graded_video, t, ap)
        before.append(bp)
        after.append(ap)
    return {"before_frames": before, "after_frames": after, "preview_video": graded_video}


def build_job_json(
    source_frames: list[str],
    reference_frames: list[str],
    output_cube: str,
    report_json: str,
    input_profile: str = "rec709",
    coarse_size: int = 17,
    lut_size: int = 33,
    iterations: int = 400,
    fine_iterations: int = 30,
    strength: float = 1.0,
    seed: int = 42,
    device: str = "auto",
) -> dict:
    return {
        "contract_version": 1,
        "source_frames": source_frames,
        "reference_frames": reference_frames,
        "input_profile": input_profile,
        "coarse_size": coarse_size,
        "lut_size": lut_size,
        "iterations": iterations,
        "fine_iterations": fine_iterations,
        "strength": strength,
        "seed": seed,
        "device": device,
        "output_cube": output_cube,
        "report_json": report_json,
    }


class EngineRunner:
    def __init__(self, job_json: dict, timeout: Optional[int] = None) -> None:
        self.job_json = job_json
        self.timeout = timeout
        self.process: Optional[subprocess.Popen] = None

    def start(self) -> None:
        job_str = json.dumps(self.job_json)
        self.process = subprocess.Popen(
            ["python", "-m", "chromainvert", "run", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert self.process.stdin is not None
        self.process.stdin.write(job_str)
        self.process.stdin.close()

    def iter_events(self):
        if self.process is None or self.process.stdout is None:
            return
        for line in self.process.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue

    def cancel(self) -> None:
        if self.process is not None:
            self.process.kill()

    def wait(self) -> int:
        if self.process is None:
            return 0
        try:
            return self.process.wait(timeout=self.timeout)
        except subprocess.TimeoutExpired:
            self.process.kill()
            return -1


def run_engine_stream(job_json: dict, timeout: Optional[int] = None, on_event=None) -> dict:
    runner = EngineRunner(job_json, timeout=timeout)
    runner.start()
    report: dict = {}
    for event in runner.iter_events():
        if on_event is not None:
            on_event(event)
        if event.get("event") == "done":
            report = event
    runner.wait()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(prog="ffmpeg_helpers")
    sub = parser.add_subparsers(dest="command", required=True)
    p_check = sub.add_parser("check")
    p_check.add_argument("--json", action="store_true")
    p_probe = sub.add_parser("probe")
    p_probe.add_argument("video")
    p_probe.add_argument("--json", action="store_true")
    p_extract = sub.add_parser("extract")
    p_extract.add_argument("video")
    p_extract.add_argument("out_dir")
    p_preview = sub.add_parser("preview")
    p_preview.add_argument("src_video")
    p_preview.add_argument("cube_path")
    p_preview.add_argument("out_video")
    p_run = sub.add_parser("run")
    p_run.add_argument("job")
    args = parser.parse_args()
    if args.command == "check":
        info = {"ffmpeg": check_ffmpeg(), "python": check_python_env()}
        print(json.dumps(info, indent=2) if getattr(args, "json", False) else info)
        return 0
    if args.command == "probe":
        probe = probe_video(args.video)
        print(json.dumps(probe, indent=2) if getattr(args, "json", False) else format_probe_human(probe))
        return 0
    if args.command == "extract":
        paths = extract_frames(args.video, args.out_dir)
        print(json.dumps(paths))
        return 0
    if args.command == "preview":
        result = apply_lut_preview(args.src_video, args.cube_path, args.out_video)
        print(json.dumps(result))
        return 0
    if args.command == "run":
        job = json.loads(Path(args.job).read_text())
        report = run_engine_stream(job)
        print(json.dumps(report))
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())