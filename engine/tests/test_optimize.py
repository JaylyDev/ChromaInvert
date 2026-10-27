import numpy as np
import pytest

from chromainvert.optimize import OptimizeConfig, optimize_lut, resolve_device


def test_resolve_device_rejects_unknown():
    with pytest.raises(ValueError):
        resolve_device("banana")
    assert resolve_device("cpu") == "cpu"


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
