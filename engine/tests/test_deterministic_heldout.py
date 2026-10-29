import numpy as np

from chromainvert.benchmark import (
    heldout_probe_metrics,
    random_rgb_probe,
    run_benchmark,
)
from chromainvert.cube import identity_lattice
from chromainvert.optimize import OptimizeConfig, enable_deterministic


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


def test_heldout_gate_fails_for_identity():
    from chromainvert.benchmark import commercial_style_lattice

    truth = commercial_style_lattice(9).astype(np.float32)
    identity = identity_lattice(9).astype(np.float32)
    probe = random_rgb_probe(256, seed=5)
    metrics = heldout_probe_metrics(probe, truth, identity)
    assert metrics["improvement_probe"] <= 0.0 + 1e-9
    # gate logic: improvement < 0.4 and recovered not < 3.0
    improvement = metrics["improvement_probe"]
    recovered = metrics["recovered_probe_de00"]
    gate_pass = bool(improvement >= 0.4 or recovered < 3.0)
    assert not gate_pass


def test_optimize_config_deterministic_default():
    cfg = OptimizeConfig()
    assert cfg.deterministic is False
    cfg2 = OptimizeConfig(deterministic=True)
    assert cfg2.deterministic is True


def test_enable_deterministic_cpu():
    status = enable_deterministic(7)
    assert status["seed"] == 7
    assert "cublas_workspace_config" in status


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
        "heldout_gate_threshold",
    ):
        assert key in metrics
    assert metrics["probe_count"] == 64
    assert metrics["heldout_gate_threshold"] == 0.4
    assert isinstance(metrics["heldout_gate_pass"], bool)


def test_random_rgb_probe_deterministic():
    a = random_rgb_probe(10, seed=7)
    b = random_rgb_probe(10, seed=7)
    np.testing.assert_array_equal(a, b)


def test_heldout_gate():
    # Placeholder logic; expanded once benchmark.py held-out probe lands.
    improvement = 0.0
    recovered = 5.0
    gate_pass = bool(improvement >= 0.4 or recovered < 3.0)
    assert gate_pass is False


def test_optimize_config_deterministic():
    cfg = OptimizeConfig(deterministic=True)
    assert cfg.deterministic is True