import argparse
import json
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
import torch

from chromainvert.cli import cmd_predict, cmd_run
from chromainvert.cube import read_cube
from chromainvert.lut_predictor import LutPredictor


def _write_reference(tmp_path: Path) -> None:
    rng = np.random.default_rng(11)
    reference = (rng.random((24, 24, 3)) * 255).astype(np.uint8)
    imageio.imwrite(tmp_path / "ref.png", reference)


def _write_weights(tmp_path: Path) -> str:
    weights = tmp_path / "weights.pt"
    model = LutPredictor(hidden=(8, 8))
    torch.save({"state_dict": model.state_dict(), "hidden": [8, 8]}, weights)
    return str(weights)


def test_cli_predict_writes_cube(tmp_path):
    _write_reference(tmp_path)
    out = tmp_path / "pred.cube"
    args = argparse.Namespace(image=str(tmp_path / "ref.png"), profile="rec709", weights=_write_weights(tmp_path), out=str(out))
    assert cmd_predict(args) == 0
    cube = read_cube(out)
    assert cube.size == 33
    assert np.all(np.isfinite(cube.lattice))


def test_cli_predict_rejects_unknown_profile(tmp_path):
    _write_reference(tmp_path)
    args = argparse.Namespace(image=str(tmp_path / "ref.png"), profile="vlog", weights=_write_weights(tmp_path), out=str(tmp_path / "p.cube"))
    try:
        cmd_predict(args)
    except ValueError:
        return
    raise AssertionError("expected ValueError for unknown profile")


def test_cli_reference_only_predicts(tmp_path):
    _write_reference(tmp_path)
    job = {
        "contract_version": 1,
        "reference_only": True,
        "reference_frames": ["ref.png"],
        "predict_weights": _write_weights(tmp_path),
        "input_profile": "rec709",
        "output_cube": "out.cube",
        "report_json": "report.json",
    }
    (tmp_path / "job.json").write_text(json.dumps(job))
    assert cmd_run(argparse.Namespace(job=str(tmp_path / "job.json"))) == 0
    cube = read_cube(tmp_path / "out.cube")
    assert cube.size == 33
    report = json.loads((tmp_path / "report.json").read_text())
    assert report["mode"] == "single_image"


def test_cli_reference_only_rejects_sources(tmp_path):
    _write_reference(tmp_path)
    job = {
        "contract_version": 1,
        "reference_only": True,
        "source_frames": ["ref.png"],
        "reference_frames": ["ref.png"],
        "predict_weights": _write_weights(tmp_path),
        "input_profile": "rec709",
        "output_cube": "out.cube",
        "report_json": "report.json",
    }
    (tmp_path / "job.json").write_text(json.dumps(job))
    try:
        cmd_run(argparse.Namespace(job=str(tmp_path / "job.json")))
    except ValueError:
        return
    raise AssertionError("expected ValueError when sources meet reference_only")


def test_cli_reference_only_requires_weights(tmp_path):
    _write_reference(tmp_path)
    job = {
        "contract_version": 1,
        "reference_only": True,
        "reference_frames": ["ref.png"],
        "input_profile": "rec709",
        "output_cube": "out.cube",
        "report_json": "report.json",
    }
    (tmp_path / "job.json").write_text(json.dumps(job))
    try:
        cmd_run(argparse.Namespace(job=str(tmp_path / "job.json")))
    except ValueError:
        return
    raise AssertionError("expected ValueError when predict_weights is missing")
