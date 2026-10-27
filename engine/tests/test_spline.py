import numpy as np
import pytest

from chromainvert.cube import identity_lattice
from chromainvert.spline import catmull_rom_upsample


def test_identity_upsample_is_identity():
    up = catmull_rom_upsample(identity_lattice(9), 33)
    assert up.shape == (33, 33, 33, 3)
    np.testing.assert_allclose(up[4:28, 4:28, 4:28], identity_lattice(33)[4:28, 4:28, 4:28], atol=1e-6)
    assert bool(np.max(np.abs(up - identity_lattice(33))) < 0.01)


def test_corners_preserved():
    rng = np.random.default_rng(4)
    lattice = rng.random((5, 5, 5, 3)).astype(np.float32)
    up = catmull_rom_upsample(lattice, 11)
    np.testing.assert_allclose(up[0, 0, 0], lattice[0, 0, 0], atol=1e-6)
    np.testing.assert_allclose(up[-1, -1, -1], lattice[-1, -1, -1], atol=1e-6)


def test_monotone_ramp_stays_in_range():
    n = 6
    ramp = np.linspace(0.0, 1.0, n, dtype=np.float64)
    lattice = np.zeros((n, n, n, 3))
    lattice[..., 0] = ramp.reshape(n, 1, 1)
    lattice[..., 1] = ramp.reshape(1, n, 1)
    lattice[..., 2] = ramp.reshape(1, 1, n)
    up = catmull_rom_upsample(lattice, 25)
    assert bool((up >= 0.0).all() and (up <= 1.0).all())


def test_same_size_returns_equal():
    lattice = identity_lattice(5)
    np.testing.assert_allclose(catmull_rom_upsample(lattice, 5), lattice, atol=1e-9)


def test_rejects_bad_input():
    with pytest.raises(ValueError):
        catmull_rom_upsample(np.zeros((4, 4, 3)), 9)
    with pytest.raises(ValueError):
        catmull_rom_upsample(identity_lattice(4), 1)
