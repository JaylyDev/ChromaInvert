import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine" / "src"))

from chromainvert.benchmark import random_rgb_probe, style_probe_metrics
from chromainvert.cube import identity_lattice
from chromainvert.losses import tv_loss
from chromainvert.lut_predictor import LutPredictor, lattice_to_cube


def main() -> int:
    parser = argparse.ArgumentParser(description="Train the single-image LUT predictor")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--data", default=None)
    parser.add_argument("--lut-dir", default=None)
    parser.add_argument("--heldout-lut", default="Vision iPhone_15_33x")
    parser.add_argument("--epochs", type=int, default=300)
    parser.add_argument("--hidden", type=int, nargs=2, default=[128, 256])
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out-weights", default=None)
    parser.add_argument("--out-metrics", default=None)
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    data_path = args.data or str(data_dir / "training_data.npz")
    out_weights = Path(args.out_weights) if args.out_weights else data_dir / "weights" / "predictor_rec709.pt"
    out_metrics = Path(args.out_metrics) if args.out_metrics else data_dir / "predictor_metrics.json"
    lut_dir = Path(args.lut_dir) if args.lut_dir else data_dir / "luts"

    device = torch.device("cuda" if (args.device == "auto" and torch.cuda.is_available()) or args.device == "cuda" else "cpu")
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    try:
        data = np.load(data_path, allow_pickle=True)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"error: cannot read training data {data_path}: {exc}")
    names = [str(n) for n in data["names"]]
    lut_ids = data["lut_ids"]
    heldout = np.array([args.heldout_lut in n for n in names]) if args.heldout_lut != "none" else np.zeros(len(names), dtype=bool)
    if args.heldout_lut != "none" and not heldout.any():
        raise SystemExit(f"heldout LUT {args.heldout_lut!r} matched no samples")
    train = ~heldout

    train_x = torch.from_numpy(data["features"][train]).to(device)
    train_y = torch.from_numpy(data["targets"][train]).to(device)
    held_x = data["features"][heldout]

    model = LutPredictor(feature_dim=int(data["features"].shape[1]), hidden=tuple(args.hidden)).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)

    started = time.monotonic()
    for epoch in range(args.epochs):
        model.train()
        optimizer.zero_grad()
        pred = model(train_x)
        volume = pred.permute(0, 4, 1, 2, 3)
        loss_lattice = torch.mean((pred - train_y) ** 2)
        loss_tv = tv_loss(volume)
        loss = loss_lattice + 0.01 * loss_tv
        loss.backward()
        optimizer.step()
        if (epoch + 1) % 100 == 0:
            print(f"epoch {epoch + 1}: {loss.item():.5f}", flush=True)

    model.eval()
    with torch.no_grad():
        held_pred = model(torch.from_numpy(held_x).to(device)).cpu().numpy()
    from chromainvert.cube import read_cube

    style_scores: list[float] = []
    baseline_scores: list[float] = []
    probe = random_rgb_probe(10000, seed=99)
    for j, i in enumerate(np.where(heldout)[0][:8]):
        lut_name = str(names[i]).split("@")[1]
        cube_path = next(lut_dir.rglob(f"{lut_name}.cube"), None)
        if cube_path is None:
            continue
        truth = read_cube(str(cube_path)).lattice
        pred33 = lattice_to_cube(held_pred[j]).lattice
        style_scores.append(style_probe_metrics(probe, truth, pred33)["style_probe_de00"])
        baseline_scores.append(style_probe_metrics(probe, truth, identity_lattice(33))["style_baseline_de00"])
    metrics = {
        "heldout_lut": args.heldout_lut,
        "heldout_samples": int(heldout.sum()),
        "train_samples": int(train.sum()),
        "epochs": args.epochs,
        "seconds": time.monotonic() - started,
        "mean_style_de00": float(np.mean(style_scores)) if style_scores else None,
        "mean_baseline_de00": float(np.mean(baseline_scores)) if baseline_scores else None,
        "device": str(device),
    }
    if args.heldout_lut != "none" and heldout.any() and not style_scores:
        raise SystemExit(f"error: held-out LUT {args.heldout_lut!r} has no .cube under {lut_dir}")
    out_weights.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": model.state_dict(), "hidden": list(args.hidden)}, out_weights)
    out_metrics.parent.mkdir(parents=True, exist_ok=True)
    out_metrics.write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
