import numpy as np
import pytest
import torch

from chromainvert.benchmark import (
    commercial_style_lattice,
    heldout_probe_metrics,
    is_probe_gate_pass,
    random_rgb_probe,
    run_benchmark,
)
from chromainvert.cube import identity_lattice
from chromainvert.optimize import OptimizeConfig, enable_deterministic, optimize_lut


def test_random_rgb_probe_deterministic_and_shape():
    a = random_rgb_probe(100, seed=1)
    b = random_rgb_probe(100, seed=1)
    c = random_rgb_probe(100, seed=2)
    np.testing.assert_array_equal(a, b)
    assert not np.array_equal(a, c)
    assert a.shape == (100, 3)
    assert a.dtype == np.float32
    assert bool((a >= 0.0).all() and (a <= 1.0).all())


def test_random_rgb_probe_defaults():
    p = random_rgb_probe()
    assert p.shape == (10000, 3)
    assert p.dtype == np.float32


def test_random_rgb_probe_rejects_nonpositive():
    with pytest.raises(ValueError):
        random_rgb_probe(0)


def test_heldout_gate_fails_for_identity():
    truth = commercial_style_lattice(9).astype(np.float32)
    identity = identity_lattice(9).astype(np.float32)
    probe = random_rgb_probe(256, seed=5)
    metrics = heldout_probe_metrics(probe, truth, identity)
    assert metrics["improvement_probe"] <= 0.0 + 1e-9
    assert not is_probe_gate_pass(
        metrics["baseline_probe_de00"],
        metrics["recovered_probe_de00"],
        metrics["improvement_probe"],
    )


def test_probe_gate_absolute_requires_no_regression():
    assert is_probe_gate_pass(4.0, 2.0, 0.5)
    assert is_probe_gate_pass(4.0, 2.5, 0.1)
    assert not is_probe_gate_pass(0.434, 0.434, -1.4e-07)
    assert not is_probe_gate_pass(4.0, 5.0, -0.25)


def test_optimize_config_deterministic_default():
    cfg = OptimizeConfig()
    assert cfg.deterministic is False
    cfg2 = OptimizeConfig(deterministic=True)
    assert cfg2.deterministic is True


def test_enable_deterministic_cpu():
    status = enable_deterministic(7)
    assert status["seed"] == 7
    assert status["deterministic_warn_only"] is True
    assert status["cublas_workspace_config"] != ""
    assert torch.are_deterministic_algorithms_enabled()
    assert torch.backends.cudnn.deterministic is True
    assert torch.backends.cudnn.benchmark is False


def test_optimize_lut_deterministic_cpu_repeat():
    rng = np.random.default_rng(11)
    source = [rng.random((32, 32, 3))]
    reference = [np.clip(rng.random((32, 32, 3)) * 0.6 + 0.2, 0.0, 1.0)]
    config = OptimizeConfig(
        coarse_size=5,
        fine_size=7,
        iterations=2,
        fine_iterations=1,
        pixel_budget=256,
        seed=0,
        device="cpu",
        deterministic=True,
    )
    _, report_a = optimize_lut(source, reference, config)
    lut_b, report_b = optimize_lut(source, reference, config)
    _, report_c = optimize_lut(source, reference, config)
    del report_a, report_c
    assert report_b["deterministic"] is True
    assert report_b["deterministic_warn_only"] is True
    assert report_b["deterministic_algorithms_enabled"] is True
    rng2 = np.random.default_rng(12)
    source2 = [rng2.random((32, 32, 3))]
    reference2 = [np.clip(rng2.random((32, 32, 3)) * 0.6 + 0.2, 0.0, 1.0)]
    lut_c, _ = optimize_lut(source2, reference2, config)
    lut_d, _ = optimize_lut(source2, reference2, config)
    np.testing.assert_array_equal(lut_c.lattice, lut_d.lattice)
    assert bool(np.all(np.isfinite(lut_b.lattice)))


def test_run_benchmark_includes_probe_keys():
    metrics = run_benchmark(
        coarse_size=5,
        fine_size=7,
        iterations=2,
        fine_iterations=1,
        seed=1,
        device="cpu",
        pixel_budget=256,
        probe_count=64,
    )
    for key in (
        "baseline_probe_de00",
        "recovered_probe_de00",
        "improvement_probe",
        "probe_count",
        "probe_seed",
        "heldout_gate_pass",
        "probe_gate_pass",
        "chart_gate_pass",
        "benchmark_gate_pass",
        "heldout_gate_threshold",
        "heldout_gate_absolute",
    ):
        assert key in metrics
    assert metrics["probe_count"] == 64
    assert metrics["probe_seed"] == 101
    assert metrics["heldout_gate_threshold"] == 0.4
    assert metrics["heldout_gate_absolute"] == 3.0
    assert isinstance(metrics["heldout_gate_pass"], bool)
    assert metrics["heldout_gate_pass"] == metrics["probe_gate_pass"]
    assert metrics["benchmark_gate_pass"] == bool(metrics["chart_gate_pass"] and metrics["probe_gate_pass"])
    assert metrics["heldout_gate_pass"] == is_probe_gate_pass(
        metrics["baseline_probe_de00"],
        metrics["recovered_probe_de00"],
        metrics["improvement_probe"],
    )


def test_run_benchmark_forwards_deterministic_and_seed():
    metrics = run_benchmark(
        coarse_size=5,
        fine_size=7,
        iterations=1,
        fine_iterations=1,
        seed=3,
        device="cpu",
        pixel_budget=256,
        deterministic=True,
        probe_count=32,
        probe_seed=500,
    )
    assert metrics["probe_seed"] == 500
    assert metrics["optimizer_report"]["deterministic"] is True
    assert metrics["optimizer_report"]["deterministic_warn_only"] is True


def test_cmd_benchmark_wiring(monkeypatch):
    import argparse

    import chromainvert.benchmark as bench
    from chromainvert import cli

    seen: dict[str, object] = {}

    def fake_run_benchmark(**kwargs: object) -> dict[str, object]:
        seen.update(kwargs)
        return {
            "baseline_heldout_de00": 4.0,
            "recovered_heldout_de00": 2.0,
            "improvement_heldout": 0.5,
            "baseline_probe_de00": 4.0,
            "recovered_probe_de00": 2.0,
            "improvement_probe": 0.5,
            "heldout_gate_pass": True,
            "benchmark_gate_pass": True,
            "seconds": 0.1,
        }

    monkeypatch.setattr(bench, "run_benchmark", fake_run_benchmark)
    args = argparse.Namespace(
        coarse=5,
        fine=7,
        iterations=2,
        fine_iterations=1,
        seed=9,
        device="cpu",
        pixels=256,
        deterministic=True,
        probe_count=32,
        probe_seed=77,
        out="work/benchmark.json",
    )
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        args.out = str(Path(tmp) / "benchmark.json")
        assert cli.cmd_benchmark(args) == 0
    assert seen["deterministic"] is True
    assert seen["probe_count"] == 32
    assert seen["probe_seed"] == 77
    assert seen["seed"] == 9
