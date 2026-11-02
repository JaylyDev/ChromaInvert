# Train predictor weights on your own LUTs

Build a checkpoint from LUTs and frames you own, then point the app at it.
Reference-only mode uses the checkpoint at `data/weights/predictor_rec709.pt`
unless you pass another path.

## Organize your files

Put frames you own under `data/videos`, sorted by profile:

```
data
├── videos
│   ├── apple_log
│   ├── rec709
│   └── s-log3
└── weights
```

Keep your `.cube` files in a separate folder. Train only on LUTs you own
or that carry an open license. A checkpoint distills its training LUTs.

## Build the training set

Run from the repo root. To use a Rec.709 frame folder and your LUT folder:

```powershell
.venv\Scripts\python.exe scripts/make_training_data.py --data-dir data --lut-dir <your LUTs>
```

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

Copy your checkpoint to `data/weights/predictor_rec709.pt`.
The GUI finds it there automatically. To use another file, set the custom
weights field in the app, or pass the path explicitly:

```powershell
.venv\Scripts\python.exe -m chromainvert predict <graded.png> --profile rec709 --weights <path> --out out.cube
```

Never commit a `.pt` file. `*.pt` is gitignored. To ship weights inside
the packaged app, place the file before running `npm run dist`.
