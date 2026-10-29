import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))


def log(message: str) -> None:
    print(message, flush=True)


def run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, check=True, cwd=cwd)


def probe_duration(video: Path) -> float:
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
        check=False,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    text = proc.stdout.strip()
    duration = float(text) if text else 0.0
    if duration <= 0.0:
        return 10.0
    return duration


def sample_times(duration: float, count: int) -> list[float]:
    fracs = [(i + 1.0) / (count + 1.0) for i in range(count)]
    usable = max(duration - 0.5, 0.5)
    return [round(f * usable, 3) for f in fracs]


def extract_frame(video: Path, timestamp: float, out: Path) -> None:
    run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-ss",
            str(timestamp),
            "-i",
            str(video),
            "-frames:v",
            "1",
            str(out),
        ],
        ROOT,
    )


def is_video(path: Path) -> bool:
    return path.suffix.lower() in (".mov", ".mp4", ".m4v", ".avi", ".mkv")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ChromaInvert demo: extract, optimize, export, benchmark with timing.")
    parser.add_argument("--source", type=Path, required=True, help="Source video file (ungraded clip).")
    parser.add_argument("--reference", type=Path, required=True, help="Reference video file or still image (target grade).")
    parser.add_argument("--workdir", type=Path, default=ROOT / "work" / "demo")
    parser.add_argument("--source-count", type=int, default=3)
    parser.add_argument("--reference-time", type=float, default=1.0)
    parser.add_argument("--coarse-size", type=int, default=17)
    parser.add_argument("--lut-size", type=int, default=33)
    parser.add_argument("--iterations", type=int, default=400)
    parser.add_argument("--fine-iterations", type=int, default=30)
    parser.add_argument("--strength", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--preview-secs", type=float, default=3.0)
    parser.add_argument("--preview-start", type=float, default=2.0)
    parser.add_argument("--skip-benchmark", action="store_true")
    parser.add_argument("--benchmark-iterations", type=int, default=400)
    parser.add_argument("--benchmark-fine-iterations", type=int, default=30)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source: Path = Path(args.source)
    reference: Path = Path(args.reference)
    workdir_arg: Path = Path(args.workdir)
    workdir: Path = workdir_arg if workdir_arg.is_absolute() else (ROOT / workdir_arg)
    if not source.is_absolute():
        source = (Path.cwd() / source).resolve()
    if not reference.is_absolute():
        reference = (Path.cwd() / reference).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    timings: dict[str, float] = {}
    total_start = time.monotonic()

    log(f"source: {source}")
    log(f"reference: {reference}")
    log(f"workdir: {workdir}")
    log("contract v1 decodes all frames as rec709 display-referred; log footage is demo only until a bounded log working space lands.")

    stage_start = time.monotonic()
    source_times = sample_times(probe_duration(source), int(args.source_count))
    source_files: list[str] = []
    for i, t in enumerate(source_times):
        out = workdir / f"src_{i:03d}.png"
        extract_frame(source, t, out)
        source_files.append(out.name)
    if is_video(reference):
        ref_out = workdir / "ref_000.png"
        extract_frame(reference, float(args.reference_time), ref_out)
        reference_files = [ref_out.name]
    else:
        ref_out = workdir / "ref_000.png"
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(reference), "-frames:v", "1", str(ref_out)], ROOT)
        reference_files = [ref_out.name]
    timings["extract_s"] = time.monotonic() - stage_start
    log(f"extracted {len(source_files)} source frames at {source_times} plus reference {reference_files} in {timings['extract_s']:.1f}s")

    job = {
        "contract_version": 1,
        "source_frames": source_files,
        "reference_frames": reference_files,
        "input_profile": "rec709",
        "coarse_size": int(args.coarse_size),
        "lut_size": int(args.lut_size),
        "iterations": int(args.iterations),
        "fine_iterations": int(args.fine_iterations),
        "strength": float(args.strength),
        "seed": int(args.seed),
        "device": str(args.device),
        "output_cube": "out.cube",
        "report_json": "report.json",
    }
    job_path = workdir / "job.json"
    job_path.write_text(json.dumps(job, indent=2))
    log(f"wrote {job_path}")

    stage_start = time.monotonic()
    run([sys.executable, "-m", "chromainvert", "run", str(job_path)], ROOT)
    timings["optimize_s"] = time.monotonic() - stage_start
    report = json.loads((workdir / "report.json").read_text())
    log(f"optimized in {timings['optimize_s']:.1f}s on {report.get('device')} with final loss {report['final_loss_terms']['total']:.4f}")

    stage_start = time.monotonic()
    cube = workdir / "out.cube"
    before = workdir / "before.png"
    after = workdir / "after.png"
    graded = workdir / "graded.mp4"
    extract_frame(source, float(args.preview_start), before)
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(before), "-vf", f"lut3d=file={cube.name}", str(after)], workdir)
    run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-ss",
            str(float(args.preview_start)),
            "-t",
            str(float(args.preview_secs)),
            "-i",
            str(source),
            "-vf",
            f"lut3d=file={cube.name}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-color_primaries",
            "bt709",
            "-color_trc",
            "bt709",
            "-colorspace",
            "bt709",
            str(graded),
        ],
        workdir,
    )
    timings["export_s"] = time.monotonic() - stage_start
    log(f"exported graded preview {graded} in {timings['export_s']:.1f}s")

    if bool(args.skip_benchmark):
        timings["benchmark_s"] = 0.0
        log("benchmark skipped")
    else:
        from chromainvert.benchmark import run_benchmark

        stage_start = time.monotonic()
        metrics = run_benchmark(
            coarse_size=int(args.coarse_size),
            fine_size=int(args.lut_size),
            iterations=int(args.benchmark_iterations),
            fine_iterations=int(args.benchmark_fine_iterations),
            seed=int(args.seed),
            device=str(args.device),
        )
        timings["benchmark_s"] = time.monotonic() - stage_start
        (workdir / "benchmark.json").write_text(json.dumps(metrics, indent=2, default=str))
        log(f"benchmark: baseline {metrics['baseline_heldout_de00']:.2f} recovered {metrics['recovered_heldout_de00']:.2f} improvement {100.0 * metrics['improvement_heldout']:.1f}% in {timings['benchmark_s']:.1f}s")

    timings["total_s"] = time.monotonic() - total_start
    (workdir / "timings.json").write_text(json.dumps(timings, indent=2))
    log("timings (s): " + ", ".join(f"{k}={v:.1f}" for k, v in timings.items()))
    log(f"done: cube={cube} graded={graded} report={workdir / 'report.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
