from chromainvert.benchmark import commercial_style_lattice, make_chart, run_benchmark


def test_chart_and_truth_lut_are_valid():
    chart = make_chart()
    assert chart.shape == (512, 1536, 3)
    assert bool((chart >= 0.0).all() and (chart <= 1.0).all())
    lattice = commercial_style_lattice(9)
    assert lattice.shape == (9, 9, 9, 3)
    assert bool((lattice >= 0.0).all() and (lattice <= 1.0).all())


def test_synthetic_recovery_beats_baseline():
    metrics = run_benchmark(coarse_size=9, fine_size=17, iterations=150, fine_iterations=10, seed=123, device="cpu", pixel_budget=16384)
    assert metrics["baseline_heldout_de00"] > 0.0
    assert metrics["improvement_heldout"] > 0.4
