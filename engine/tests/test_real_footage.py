import json
from pathlib import Path

import imageio.v2 as imageio
import numpy as np

from chromainvert.cli import cmd_run, load_frames
from chromainvert.cube import read_cube, write_cube
from chromainvert.optimize import OptimizeConfig, optimize_lut


def _write_images(tmp_path: Path) -> None:
    rng = np.random.default_rng(3)
    source = (rng.random((16, 16, 3)) * 255).astype(np.uint8)
    reference = source.copy()
    reference[..., 0] = np.clip(reference[..., 0].astype(int) + 20, 0, 255).astype(np.uint8)
    reference[..., 2] = np.clip(reference[..., 2].astype(int) - 20, 0, 255).astype(np.uint8)
    imageio.imwrite(tmp_path / "src.png", source)
    imageio.imwrite(tmp_path / "ref.png", reference)


def test_load_frames_handles_8bit_png(tmp_path):
    _write_images(tmp_path)
    frames = load_frames(["src.png", "ref.png"], "rec709", tmp_path)
    assert frames[0].shape == (16, 16, 3)
    assert frames[0].dtype.kind == "f"
    assert 0.0 <= float(frames[0].min()) and float(frames[0].max()) <= 1.0


def test_optimize_real_footage_produces_valid_cube(tmp_path):
    _write_images(tmp_path)
    source = [imageio.imread(tmp_path / "src.png")[..., :3].astype(np.float64) / 255.0]
    reference = [imageio.imread(tmp_path / "ref.png")[..., :3].astype(np.float64) / 255.0]
    # decode through srgb_to_linear like CLI does
    from chromainvert.color import srgb_to_linear

    source = [srgb_to_linear(np.asarray(s)) for s in source]
    reference = [srgb_to_linear(np.asarray(r)) for r in reference]
    config = OptimizeConfig(
        coarse_size=5,
        fine_size=7,
        iterations=10,
        fine_iterations=5,
        pixel_budget=256,
        seed=1,
        device="cpu",
    )
    lut, report = optimize_lut(source, reference, config)
    assert lut.size == 7
    assert np.all(np.isfinite(lut.lattice))
    write_cube(tmp_path / "opt.cube", lut)
    cube = read_cube(tmp_path / "opt.cube")
    assert np.all(np.isfinite(cube.lattice))
    assert 0.0 <= float(cube.lattice.min()) <= 1.0
    assert 0.0 <= float(cube.lattice.max()) <= 1.0
    assert report["lattice_min"] <= report["lattice_max"]


def test_cli_real_footage_run(tmp_path):
    _write_images(tmp_path)
    job = {
        "contract_version": 1,
        "source_frames": ["src.png"],
        "reference_frames": ["ref.png"],
        "input_profile": "rec709",
        "coarse_size": 5,
        "lut_size": 7,
        "iterations": 10,
        "fine_iterations": 5,
        "strength": 1.0,
        "seed": 1,
        "device": "cpu",
        "output_cube": "out.cube",
        "report_json": "report.json",
    }
    (tmp_path / "job.json").write_text(json.dumps(job))
    import argparse

    args = argparse.Namespace(job=str(tmp_path / "job.json"))
    assert cmd_run(args) == 0
    cube = read_cube(tmp_path / "out.cube")
    assert cube.size == 7
    assert cube.title == "ChromaInvert"
    assert np.all(np.isfinite(cube.lattice))
    assert 0.0 <= float(cube.lattice.min()) <= 1.0
    assert 0.0 <= float(cube.lattice.max()) <= 1.0
    report = json.loads((tmp_path / "report.json").read_text())
    assert report["contract_version"] == 1
    assert report["input_profile"] == "rec709"


def test_python_m_chromainvert_run(tmp_path):
    _write_images(tmp_path)
    job = {
        "contract_version": 1,
        "source_frames": ["src.png"],
        "reference_frames": ["ref.png"],
        "input_profile": "rec709",
        "coarse_size": 5,
        "lut_size": 7,
        "iterations": 10,
        "fine_iterations": 5,
        "strength": 1.0,
        "seed": 1,
        "device": "cpu",
        "output_cube": "out.cube",
        "report_json": "report.json",
    }
    (tmp_path / "job.json").write_text(json.dumps(job))
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, "-m", "chromainvert", "run", str(tmp_path / "job.json")],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert (tmp_path / "out.cube").exists()
    assert read_cube(tmp_path / "out.cube").title == "ChromaInvert"
