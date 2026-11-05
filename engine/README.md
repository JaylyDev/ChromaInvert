# ChromaInvert engine

Perceptual video and LUT reverse-engineering engine. It recovers a smooth 3D LUT that matches source footage to a reference grade, then exports a portable `.cube` file ready for Premiere Pro, DaVinci Resolve, FFmpeg, or mobile camera apps.

## Install

Requires Python 3.10 or newer.

```
python -m pip install chromainvert
```

For development from this repo (from the repo root):

```
python -m pip install -e ./engine
```

## Quickstart

Optimize a LUT from a job file (see `docs/ARCHITECTURE.md` in the repo for the job schema):

```
python -m chromainvert run work/job.json
```

Predict a LUT from a single reference image (needs weights trained with `scripts/train_lut_predictor.py`):

```
python -m chromainvert predict reference.png --weights data/weights/predictor_rec709.pt --output out.cube
```

Run the synthetic recovery benchmark:

```
python -m chromainvert benchmark
```

## Layout

```
engine/
├── LICENSE
├── pyproject.toml
├── README.md
├── src/
│   └── chromainvert/
└── tests/
```

## License

Apache-2.0. See `LICENSE`.
