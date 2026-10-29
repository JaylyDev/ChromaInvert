import json

import imageio.v2 as imageio
import numpy as np
import pytest

from chromainvert.cli import blend_toward_identity, cmd_run, load_frames
from chromainvert.cube import CubeLut, identity_lattice


def test_load_frames_uint16_and_grayscale(tmp_path):
    rgb16 = (np.linspace(0.0, 1.0, 64 * 32).reshape(32, 64, 1) * np.array([65535.0, 32768.0, 16384.0])).astype(np.uint16)
    imageio.imwrite(tmp_path / "rgb16.tif", rgb16)
    gray = (np.linspace(0.0, 255.0, 64 * 32).reshape(32, 64)).astype(np.uint8)
    imageio.imwrite(tmp_path / "gray.png", gray)
    frames = load_frames(["rgb16.tif", "gray.png"], "rec709", tmp_path)
    assert frames[0].shape == (32, 64, 3)
    assert frames[0].max() <= 1.0
    np.testing.assert_allclose(frames[0][31, 63, 0], 1.0, atol=1e-2)
    np.testing.assert_allclose(frames[0][0, 0, 0], 0.0, atol=1e-6)
    assert frames[1].shape == (32, 64, 3)
    np.testing.assert_allclose(frames[1][..., 0], frames[1][..., 1], atol=0.0)


def test_load_frames_slog3_bounded(tmp_path):
    code = (np.array([420.0 / 1023.0, 598.0 / 1023.0, 1.0]) * 255).astype(np.uint8)
    img = np.tile(code.reshape(1, 1, 3), (4, 4, 1))
    imageio.imwrite(tmp_path / "slog3.png", img)
    frames = load_frames(["slog3.png"], "slog3", tmp_path)
    assert frames[0].shape == (4, 4, 3)
    assert bool(np.all(frames[0] >= 0.0))
    assert bool(np.all(frames[0] <= 1.0))
    assert bool(np.all(np.isfinite(frames[0])))
    assert frames[0][0, 0, 0] < 0.3
    assert frames[0][0, 0, 2] > 0.9
    assert frames[0][0, 0, 2] < 1.0


def test_load_frames_rejects_bad_shapes(tmp_path):
    flat = np.zeros((16, 16, 2), dtype=np.uint8)
    imageio.imwrite(tmp_path / "bad.png", flat)
    with pytest.raises(ValueError):
        load_frames(["bad.png"], "rec709", tmp_path)


def test_blend_strength_bounds():
    lut = CubeLut(size=5, lattice=np.ones((5, 5, 5, 3), dtype=np.float32))
    with pytest.raises(ValueError):
        blend_toward_identity(lut, 2.0)
    full = blend_toward_identity(lut, 1.0)
    np.testing.assert_allclose(full.lattice, 1.0, atol=1e-6)
    none = blend_toward_identity(lut, 0.0)
    np.testing.assert_allclose(none.lattice, identity_lattice(5), atol=1e-6)


def write_job(tmp_path, **overrides):
    image = (np.random.default_rng(9).random((16, 16, 3)) * 255).astype(np.uint8)
    imageio.imwrite(tmp_path / "src.png", image)
    imageio.imwrite(tmp_path / "ref.png", image)
    job = {
        "contract_version": 2,
        "source_frames": ["src.png"],
        "reference_frames": ["ref.png"],
        "iterations": 1,
        "fine_iterations": 0,
        "coarse_size": 5,
        "lut_size": 7,
        "seed": 0,
        "device": "cpu",
        "output_cube": "out.cube",
        "report_json": "report.json",
    }
    job.update(overrides)
    path = tmp_path / "job.json"
    path.write_text(json.dumps(job))
    return path


def test_run_rejects_bad_strength_before_work(tmp_path):
    import argparse

    args = argparse.Namespace(job=str(write_job(tmp_path, strength=2.0)))
    with pytest.raises(ValueError):
        cmd_run(args)
    assert not (tmp_path / "out.cube").exists()


def test_run_rejects_unknown_profile(tmp_path):
    import argparse

    args = argparse.Namespace(job=str(write_job(tmp_path, input_profile="vlog")))
    with pytest.raises(ValueError):
        cmd_run(args)


def test_run_accepts_slog3(tmp_path):
    import argparse

    args = argparse.Namespace(job=str(write_job(tmp_path, input_profile="slog3")))
    cmd_run(args)
    assert (tmp_path / "out.cube").exists()
    assert (tmp_path / "report.json").exists()
    report = json.loads((tmp_path / "report.json").read_text())
    assert report["input_profile"] == "slog3"


def test_run_accepts_slog3_sgamut3cine_alias(tmp_path):
    import argparse

    args = argparse.Namespace(job=str(write_job(tmp_path, input_profile="slog3_sgamut3cine")))
    cmd_run(args)
    assert (tmp_path / "out.cube").exists()


def test_run_contract_version_1_still_works(tmp_path):
    import argparse

    args = argparse.Namespace(job=str(write_job(tmp_path, contract_version=1, input_profile="rec709")))
    cmd_run(args)
    assert (tmp_path / "out.cube").exists()
    report = json.loads((tmp_path / "report.json").read_text())
    assert report["contract_version"] == 1
    assert report["input_profile"] == "rec709"


def test_run_rejects_slog3_under_contract_version_1(tmp_path):
    import argparse

    args = argparse.Namespace(job=str(write_job(tmp_path, contract_version=1, input_profile="slog3")))
    with pytest.raises(ValueError):
        cmd_run(args)
    assert not (tmp_path / "out.cube").exists()


def test_run_rejects_bad_contract_version(tmp_path):
    import argparse

    for bad in (0, 3, "2", 2.0, True):
        args = argparse.Namespace(job=str(write_job(tmp_path, contract_version=bad)))
        with pytest.raises(ValueError):
            cmd_run(args)
