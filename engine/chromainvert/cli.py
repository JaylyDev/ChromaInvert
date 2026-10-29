import argparse
import json
import sys
import time
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
import torch

from chromainvert.color import decode_input
from chromainvert.cube import CubeLut, identity_lattice, write_cube
from chromainvert.optimize import OptimizeConfig, optimize_lut

_ALLOWED_PROFILES = {"rec709", "slog3", "slog3_sgamut3cine", "slog3_sgamut3.cine", "slog3_sgamut3_cine"}


def resolve(base: Path, p: str) -> Path:
    path = Path(p)
    return path if path.is_absolute() else base / path


def load_frames(paths: list[str], profile: str, workdir: Path) -> list[np.ndarray]:
    frames: list[np.ndarray] = []
    for p in paths:
        raw = imageio.imread(resolve(workdir, p))
        if raw.ndim == 2:
            raw = np.stack((raw, raw, raw), axis=-1)
        if raw.ndim != 3 or raw.shape[-1] not in (3, 4):
            raise ValueError(f"expected an RGB or RGBA image, got shape {raw.shape}")
        if np.issubdtype(raw.dtype, np.integer):
            scale = float(np.iinfo(raw.dtype).max)
        elif np.issubdtype(raw.dtype, np.floating):
            scale = 1.0
        else:
            raise ValueError(f"unsupported image dtype: {raw.dtype}")
        image = raw[..., :3].astype(np.float64) / scale
        frames.append(decode_input(image, profile))
    return frames


def blend_toward_identity(lut: CubeLut, strength: float) -> CubeLut:
    if not 0.0 <= strength <= 1.0:
        raise ValueError("strength must be in [0, 1]")
    lattice = (strength * lut.lattice + (1.0 - strength) * identity_lattice(lut.size)).astype(np.float32)
    return CubeLut(size=lut.size, lattice=lattice, title=lut.title)


def cmd_run(args: argparse.Namespace) -> int:
    job_path = Path(args.job)
    workdir = job_path.parent
    job = json.loads(job_path.read_text())
    contract_version = job.get("contract_version")
    if type(contract_version) is not int or contract_version not in (1, 2):
        raise ValueError("unsupported contract_version, expected 1 or 2")
    for key in ("source_frames", "reference_frames", "output_cube", "report_json"):
        if key not in job:
            raise ValueError(f"job is missing required key: {key}")
    config = OptimizeConfig(
        coarse_size=int(job.get("coarse_size", 17)),
        fine_size=int(job.get("lut_size", 33)),
        iterations=int(job.get("iterations", 400)),
        fine_iterations=int(job.get("fine_iterations", 20)),
        seed=int(job.get("seed", 42)),
        device=str(job.get("device", "auto")),
        deterministic=bool(job.get("deterministic", False)),
    )
    profile = str(job.get("input_profile", "rec709"))
    if profile not in _ALLOWED_PROFILES:
        raise ValueError(f"unsupported input_profile {profile!r}, expected one of {sorted(_ALLOWED_PROFILES)}")
    if contract_version == 1 and profile != "rec709":
        raise ValueError(f"input_profile {profile!r} requires contract_version 2")
    strength = float(job.get("strength", 1.0))
    if not 0.0 <= strength <= 1.0:
        raise ValueError("strength must be in [0, 1]")
    source = load_frames(job["source_frames"], profile, workdir)
    reference = load_frames(job["reference_frames"], profile, workdir)
    started = time.monotonic()

    def progress(i: int, total: int, loss: float, elapsed: float) -> None:
        print(json.dumps({"event": "progress", "iter": i, "iters": total, "loss": loss, "elapsed_s": elapsed}), flush=True)

    lut, report = optimize_lut(source, reference, config, progress=progress)
    lut = blend_toward_identity(lut, strength)
    cube_path = resolve(workdir, job["output_cube"])
    write_cube(cube_path, lut)
    report["contract_version"] = contract_version
    report["input_profile"] = profile
    report["strength"] = strength
    report["versions"] = {"python": sys.version.split()[0], "numpy": np.__version__, "torch": torch.__version__}
    resolve(workdir, job["report_json"]).write_text(json.dumps(report, indent=2))
    print(json.dumps({"event": "done", "cube": str(cube_path), "seconds": time.monotonic() - started}), flush=True)
    return 0


def cmd_benchmark(args: argparse.Namespace) -> int:
    from chromainvert.benchmark import run_benchmark

    metrics = run_benchmark(
        coarse_size=args.coarse,
        fine_size=args.fine,
        iterations=args.iterations,
        fine_iterations=args.fine_iterations,
        seed=args.seed,
        device=args.device,
        pixel_budget=args.pixels,
        deterministic=args.deterministic,
        probe_count=args.probe_count,
        probe_seed=args.probe_seed,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(metrics, indent=2))
    print(f"baseline held-out mean dE00: {metrics['baseline_heldout_de00']:.3f}")
    print(f"recovered held-out mean dE00: {metrics['recovered_heldout_de00']:.3f}")
    print(f"improvement: {100.0 * metrics['improvement_heldout']:.1f}%")
    print(f"baseline probe dE00: {metrics['baseline_probe_de00']:.3f}")
    print(f"recovered probe dE00: {metrics['recovered_probe_de00']:.3f}")
    print(f"probe improvement: {100.0 * metrics['improvement_probe']:.1f}%")
    print(f"probe gate: {'PASS' if metrics['heldout_gate_pass'] else 'FAIL'}")
    print(f"seconds: {metrics['seconds']:.1f}")
    return 0 if bool(metrics.get("benchmark_gate_pass", False)) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="chromainvert")
    sub = parser.add_subparsers(dest="command", required=True)
    p_run = sub.add_parser("run", help="optimize a LUT from a job file")
    p_run.add_argument("job")
    p_run.set_defaults(func=cmd_run)
    p_bench = sub.add_parser("benchmark", help="synthetic ground-truth recovery check")
    p_bench.add_argument("--out", default="work/benchmark.json")
    p_bench.add_argument("--coarse", type=int, default=17)
    p_bench.add_argument("--fine", type=int, default=33)
    p_bench.add_argument("--iterations", type=int, default=400)
    p_bench.add_argument("--fine-iterations", type=int, default=30)
    p_bench.add_argument("--seed", type=int, default=123)
    p_bench.add_argument("--device", default="auto")
    p_bench.add_argument("--pixels", type=int, default=65536)
    p_bench.add_argument("--deterministic", action="store_true")
    p_bench.add_argument("--probe-count", type=int, default=10000, dest="probe_count")
    p_bench.add_argument("--probe-seed", type=int, default=None, dest="probe_seed")
    p_bench.set_defaults(func=cmd_benchmark)
    parsed = parser.parse_args(argv)
    return parsed.func(parsed)


if __name__ == "__main__":
    sys.exit(main())
