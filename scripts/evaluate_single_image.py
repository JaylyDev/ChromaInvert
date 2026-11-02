import argparse
import json
import sys
import time
from pathlib import Path

import imageio.v2 as imageio
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

from chromainvert.benchmark import apply_lut, mean_de00_full, random_rgb_probe, style_probe_metrics
from chromainvert.cli import load_frames, predict_for_frames
from chromainvert.color import decode_input
from chromainvert.cube import read_cube
from chromainvert.optimize import OptimizeConfig, optimize_lut


def read_working(path: str) -> np.ndarray:
    raw = imageio.imread(path)
    if np.issubdtype(raw.dtype, np.integer):
        pixels = raw[..., :3].astype(np.float64) / float(np.iinfo(raw.dtype).max)
    else:
        pixels = raw[..., :3].astype(np.float64)
    return pixels


def main() -> int:
    parser = argparse.ArgumentParser(description="Paired recovery and predictor check on one pair")
    parser.add_argument("--manifest", default="work/pairs/manifest.json")
    parser.add_argument("--pair-index", type=int, default=0)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--fine-iterations", type=int, default=10)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--weights", default=None)
    parser.add_argument("--out", default="work/single_image_eval.json")
    args = parser.parse_args()

    manifest = json.loads(Path(args.manifest).read_text())
    pair = manifest[args.pair_index]
    if pair.get("synthesis", "display") != "working":
        raise SystemExit("error: this check needs working-space pairs (rebuild the manifest with --working-synthesis)")
    profile = pair["profile"]
    truth = read_cube(pair["lut"])

    source = load_frames(pair["source_frames"], profile, ROOT)
    reference = load_frames(pair["graded_frames"], profile, ROOT)
    config = OptimizeConfig(
        iterations=args.iterations,
        fine_iterations=args.fine_iterations,
        device=args.device,
    )

    started = time.monotonic()
    paired_lut, _ = optimize_lut(source, reference, config)
    paired_seconds = time.monotonic() - started

    probe = random_rgb_probe(10000, seed=99)
    paired_style = style_probe_metrics(probe, truth.lattice, paired_lut.lattice)

    heldout = np.asarray(decode_input(read_working(pair["heldout_source"]), profile), dtype=np.float32).reshape(-1, 3)
    truth_heldout = apply_lut(heldout, truth.lattice)
    paired_heldout = apply_lut(heldout, paired_lut.lattice)
    result = {
        "profile": profile,
        "lut": pair["lut"],
        "synthesis": pair["synthesis"],
        "baseline_style_probe_de00": paired_style["style_baseline_de00"],
        "style_improvement": paired_style["style_improvement"],
        "baseline_heldout_de00": float(mean_de00_full(truth_heldout, heldout)),
        "paired_style_probe_de00": paired_style["style_probe_de00"],
        "paired_heldout_de00": float(mean_de00_full(truth_heldout, paired_heldout)),
        "paired_seconds": paired_seconds,
    }
    if args.weights is not None:
        predicted = predict_for_frames(reference, args.weights, profile)
        predicted_heldout = apply_lut(heldout, predicted.lattice)
        predicted_style = style_probe_metrics(probe, truth.lattice, predicted.lattice)
        result["predicted_style_probe_de00"] = predicted_style["style_probe_de00"]
        result["predicted_heldout_de00"] = float(mean_de00_full(truth_heldout, predicted_heldout))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    print(f"profile: {profile}")
    print(f"paired style probe dE00: {result['paired_style_probe_de00']:.3f}")
    if "predicted_style_probe_de00" in result:
        print(f"predicted style probe dE00: {result['predicted_style_probe_de00']:.3f}")
    print(f"paired heldout dE00: {result['paired_heldout_de00']:.3f}")
    if "predicted_heldout_de00" in result:
        print(f"predicted heldout dE00: {result['predicted_heldout_de00']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
