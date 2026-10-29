import importlib.util
import json
import math
import shutil
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("premiere_validation", ROOT / "scripts" / "premiere_validation.py")
pv = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(pv)


def test_de00_stats_identical_is_zero_and_finite():
    a = np.full((4, 4, 3), 0.5, dtype=np.float32)
    stats = pv.de00_stats(a, a.copy())
    assert stats["mean"] == 0.0
    assert stats["max"] == 0.0
    assert math.isfinite(stats["mean"])


def test_rgb_stats_identical_psnr_finite_and_json_serializable():
    a = np.full((4, 4, 3), 0.5, dtype=np.float32)
    stats = pv.rgb_stats(a, a.copy())
    assert stats["mean_abs"] == 0.0
    assert stats["max_abs"] == 0.0
    assert math.isfinite(stats["psnr_db"])
    json.dumps(stats)


def test_compare_pair_shape_mismatch_raises():
    a = np.zeros((4, 4, 3), dtype=np.float32)
    b = np.zeros((2, 2, 3), dtype=np.float32)
    with pytest.raises(ValueError):
        pv.compare_pair("mismatch", a, b)


def test_compare_pair_empty_raises():
    a = np.zeros((0, 3), dtype=np.float32)
    b = np.zeros((0, 3), dtype=np.float32)
    with pytest.raises(ValueError):
        pv.compare_pair("empty", a, b)


def test_de00_stats_decodes_srgb():
    # A dark step should score differently than raw gamma values; just ensure finite.
    a = np.full((2, 2, 3), 0.04, dtype=np.float32)
    b = np.full((2, 2, 3), 0.055, dtype=np.float32)
    stats = pv.de00_stats(a, b)
    assert stats["mean"] > 0.0
    assert math.isfinite(stats["mean"])


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not available")
def test_script_main_synthetic_passes(tmp_path, monkeypatch):
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.setattr("sys.argv", ["premiere_validation.py", "--workdir", str(workdir)])
    rc = pv.main()
    assert rc == 0
    report = json.loads((workdir / "premiere_validation.json").read_text())
    assert report["pass"] is True
    assert report["premiere_tested"] is False
