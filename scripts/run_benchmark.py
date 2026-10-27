import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

from chromainvert.benchmark import run_benchmark


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "work" / "benchmark.json")
    parser.add_argument("--coarse", type=int, default=17)
    parser.add_argument("--fine", type=int, default=33)
    parser.add_argument("--iterations", type=int, default=400)
    parser.add_argument("--fine-iterations", type=int, default=30)
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--pixels", type=int, default=65536)
    args = parser.parse_args()
    metrics = run_benchmark(
        coarse_size=args.coarse,
        fine_size=args.fine,
        iterations=args.iterations,
        fine_iterations=args.fine_iterations,
        seed=args.seed,
        device=args.device,
        pixel_budget=args.pixels,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(metrics, indent=2, default=str))
    print(f"baseline held-out mean dE00: {metrics['baseline_heldout_de00']:.3f}")
    print(f"recovered held-out mean dE00: {metrics['recovered_heldout_de00']:.3f}")
    print(f"improvement: {100.0 * metrics['improvement_heldout']:.1f}%")
    print(f"held-out PSNR: {metrics['heldout_psnr']:.1f} dB")
    print(f"seconds: {metrics['seconds']:.1f}")
    return 0 if metrics["improvement_heldout"] >= 0.4 else 1


if __name__ == "__main__":
    sys.exit(main())
