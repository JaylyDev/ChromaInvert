import numpy as np
import pytest

from chromainvert.optimize import OptimizeConfig, optimize_lut, resolve_device, sample_paired_pixels


def test_optimize_config_saturation_defaults():
    config = OptimizeConfig()
    assert config.weight_tv == 0.1
    assert config.weight_shadow == 0.25


def test_resolve_device_rejects_unknown():
    with pytest.raises(ValueError):
        resolve_device("banana")
    assert resolve_device("cpu") == "cpu"


def test_sample_paired_pixels_keeps_correspondence():
    rng = np.random.default_rng(5)
    source = [rng.random((16, 16, 3))]
    reference = [source[0] * 0.5]
    sampled_source, sampled_reference = sample_paired_pixels(source, reference, 64, 0)
    np.testing.assert_allclose(sampled_reference, sampled_source * 0.5, atol=1e-7)


def test_sample_paired_pixels_rejects_mismatched_frames():
    source = [np.zeros((16, 16, 3))]
    reference = [np.zeros((8, 16, 3))]
    with pytest.raises(ValueError):
        sample_paired_pixels(source, reference, 64, 0)


def test_optimize_paired_reports_paired_term():
    rng = np.random.default_rng(11)
    source = [rng.random((32, 32, 3))]
    reference = [np.clip(source[0] * 0.8 + 0.1, 0.0, 1.0)]
    config = OptimizeConfig(
        coarse_size=5, fine_size=7, iterations=2, fine_iterations=1, pixel_budget=256, seed=0, device="cpu", weight_paired=10.0
    )
    lut, report = optimize_lut(source, reference, config)
    assert bool(np.all(np.isfinite(lut.lattice)))
    assert "paired" in report["final_loss_terms"]


def test_optimize_smoke_produces_valid_cube():
    rng = np.random.default_rng(11)
    source = [rng.random((64, 64, 3))]
    reference = [np.clip(rng.random((64, 64, 3)) * 0.6 + 0.2, 0.0, 1.0)]
    seen: list[float] = []
    config = OptimizeConfig(coarse_size=5, fine_size=7, iterations=4, fine_iterations=2, pixel_budget=512, seed=0, device="cpu")
    lut, report = optimize_lut(source, reference, config, progress=lambda i, n, loss, e: seen.append(loss))
    assert lut.size == 7
    assert bool(np.all(np.isfinite(lut.lattice)))
    assert len(seen) == 6
    assert all(np.isfinite(seen))
    assert seen[-1] <= seen[0]
    assert report["source_pixels"] == 512
    assert report["device"] == "cpu"
    assert report["max_neighbor_delta"] >= 0.0
