# Train predictor weights on your own LUTs

Build a checkpoint from LUTs and frames you own, then point the app at it.
No checkpoint is shipped; reference-only mode requires a weights file you trained yourself.

## Organize your files

Put frames you own under `data/videos`, sorted by profile:

```
data
├── luts
├── videos
│   ├── apple_log
│   ├── rec709
│   └── s-log3
└── weights
```

Put frames you own under `data/videos`, sorted by profile.
Put `.cube` files you own under `data/luts`.
Train only on LUTs you own or that carry an open license.
A checkpoint distills its training LUTs.

## Build the training set

Run from the repo root. To use a Rec.709 frame folder and your LUT folder:

```powershell
.venv\Scripts\python.exe scripts/make_training_data.py --data-dir data
```

To use LUTs outside the workspace, pass `--lut-dir` directly.

To override a default, pass it directly. `--frames-dir` replaces
`data/videos`, and `--out` replaces `data/training_data.npz`.

The script applies each LUT in decoded working space and writes one `.npz`
with grade statistics and target lattices. It also adds mild synthetic
grades plus identity, so the model learns weak looks as well as strong ones.

## Train the model

Hold out one LUT to validate against:

```powershell
.venv\Scripts\python.exe scripts/train_lut_predictor.py --data-dir data --heldout-lut <one LUT stem>
```

Training takes seconds on a GPU. The script prints `mean_style_de00`
against `mean_baseline_de00` for the held-out LUT. Ship the checkpoint
when the style error is well under half the baseline. The reference run
reached 4.6 against a 14.0 baseline.

For final weights, retrain on all data with `--heldout-lut none`.
The checkpoint lands at `data/weights/predictor_rec709.pt` by default.
Override the path with `--out-weights`.

## Point the app at your checkpoint

Pick the checkpoint file you just trained in the app weights field (Browse), or pass it to the CLI explicitly:

```powershell
.venv\Scripts\python.exe -m chromainvert predict <graded.png> --profile rec709 --weights <path\to\your\checkpoint.pt> --out out.cube
```

There is no fallback weights file; the app will refuse a reference-only run until you select one. `data/weights/predictor_rec709.pt` is just the default output path for `train_lut_predictor.py` (override with `--out-weights`). Never commit a `.pt` file; `*.pt` is gitignored and no packaged app ships with weights.
