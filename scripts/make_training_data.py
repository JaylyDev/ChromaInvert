import argparse
import json
import sys
from pathlib import Path

import imageio.v2 as imageio
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

from chromainvert.benchmark import apply_lut
from chromainvert.color import decode_input
from chromainvert.cube import read_cube
from chromainvert.lut_predictor import grade_features


def main() -> int:
    parser = argparse.ArgumentParser(description="Build predictor training data in working space")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--frames-dir", default=None)
    parser.add_argument("--lut-dir", default=None)
    parser.add_argument("--profile", default="rec709")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    frames_dir = args.frames_dir or str(data_dir / "videos")
    if args.lut_dir is None:
        raise SystemExit("error: pass --lut-dir with LUTs you own")
    out = Path(args.out) if args.out else data_dir / "training_data.npz"

    cubes = sorted(Path(args.lut_dir).rglob("*33x*.cube"), key=lambda p: p.stem)
    if not cubes:
        raise SystemExit(f"error: no 33x cubes under {args.lut_dir}")
    frames = sorted(Path(frames_dir).rglob("*.png"))
    if not frames:
        raise SystemExit(f"error: no frames under {frames_dir}")

    rng = np.random.default_rng(1234)
    truths = [read_cube(str(c)).lattice for c in cubes]
    names = [c.stem for c in cubes]
    coords = np.stack(np.meshgrid(*[np.linspace(0.0, 1.0, 33)] * 3, indexing="ij"), axis=-1)[..., ::-1]
    luma_weights = np.array([0.2126, 0.7152, 0.0722])
    for i in range(12):
        gains = rng.uniform(0.85, 1.18, size=3)
        saturation = rng.uniform(0.8, 1.3)
        graded = np.clip(coords * gains, 0.0, 1.0)
        luma = (graded * luma_weights).sum(axis=-1, keepdims=True)
        mild = np.clip(luma + saturation * (graded - luma), 0.0, 1.0).astype(np.float32)
        truths.append(mild)
        names.append(f"mild_{i:02d}")
    truths.append(np.stack(np.meshgrid(*[np.linspace(0.0, 1.0, 33)] * 3, indexing="ij"), axis=-1)[..., ::-1].astype(np.float32))
    names.append("identity")
    feats: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    lut_ids: list[int] = []
    names_out: list[str] = []
    for frame in frames:
        raw = imageio.imread(str(frame))[..., :3].astype(np.float64) / 255.0
        stride = max(1, int((raw.shape[0] * raw.shape[1] / 200000) ** 0.5))
        raw = raw[::stride, ::stride, :]
        working = np.asarray(decode_input(raw, args.profile), dtype=np.float32)
        for i, (lut_name, truth) in enumerate(zip(names, truths)):
            graded = apply_lut(working, truth)
            feats.append(grade_features(graded))
            targets.append(np.ascontiguousarray(truth[::2, ::2, ::2], dtype=np.float32))
            lut_ids.append(i)
            names_out.append(f"{frame.name}@{lut_name}")
    features = np.stack(feats).astype(np.float32)
    target_arr = np.stack(targets).astype(np.float32)
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, features=features, targets=target_arr,
                        lut_ids=np.array(lut_ids), names=np.array(names_out),
                        profile=np.array(args.profile))
    meta = {"samples": len(names_out), "luts": names, "frames": len(frames), "profile": args.profile}
    out.with_suffix(".json").write_text(json.dumps(meta, indent=2))
    print(f"wrote {out}: {len(names_out)} samples from {len(frames)} frames x {len(names)} LUTs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
