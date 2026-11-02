# Predictor weights

This folder is where the app looks for trained single-image predictor checkpoints.
Weights files are **not** shipped in this repo: a checkpoint distills the LUTs
it was trained on, so training on commercial LUTs or unlicensed footage can
produce a file you have no right to redistribute.

To enable reference-only mode:

1. Collect `.cube` files you own or that are openly licensed.
2. Extract frames with `scripts/extract_frames.py` (any footage you own).
3. Build training data: `python scripts/make_training_data.py --frames-dir <frames> --lut-dir <your LUTs>`.
4. Train: `python scripts/train_lut_predictor.py --data work/training_data.npz --heldout-lut <one LUT stem>`.
5. Copy the output weights here as `predictor_rec709.pt`.

The GUI searches this folder (plus the packaged app resources) automatically.
To ship reference-only mode in the packaged app, place the file here before
running `npm run dist`: `extraResources` copies it into the app resources.
See `docs/ARCHITECTURE.md` section 3b for the model and training details.
