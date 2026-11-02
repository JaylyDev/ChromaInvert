import json

import numpy as np
import torch

from chromainvert.cube import read_cube, write_cube
from chromainvert.lut_predictor import FEATURE_DIM, LutPredictor, grade_features, lattice_to_cube


def test_grade_features_shape_and_determinism():
    rng = np.random.default_rng(0)
    image = rng.random((32, 32, 3))
    first = grade_features(image)
    assert first.shape == (FEATURE_DIM,)
    assert np.all(np.isfinite(first))
    assert np.array_equal(first, grade_features(image))
    gray = np.full((8, 8, 3), 0.5)
    assert np.all(np.isfinite(grade_features(gray)))


def test_predictor_initializes_near_identity():
    from chromainvert.cube import identity_lattice

    model = LutPredictor()
    with torch.no_grad():
        lattice = model(torch.zeros(2, FEATURE_DIM))
    assert lattice.shape == (2, 17, 17, 17, 3)
    expected = torch.from_numpy(identity_lattice(17))
    assert bool(((lattice[0] - expected).abs().max() < 1e-5).item())


def test_predictor_overfits_single_sample():
    rng = np.random.default_rng(1)
    target = np.clip(np.stack(np.meshgrid(*[np.linspace(0.0, 1.0, 17)] * 3, indexing="ij"), axis=-1)[..., ::-1] * 1.1 - 0.05, 0.0, 1.0).astype(np.float32)
    features = torch.from_numpy(rng.random((4, FEATURE_DIM), dtype=np.float32))
    goal = torch.from_numpy(target).unsqueeze(0).expand(4, -1, -1, -1, -1)
    model = LutPredictor()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    first_loss = None
    for _ in range(30):
        optimizer.zero_grad()
        loss = torch.mean((model(features) - goal) ** 2)
        if first_loss is None:
            first_loss = loss.item()
        loss.backward()
        optimizer.step()
    assert loss.item() < first_loss


def test_lattice_to_cube_upsamples(tmp_path):
    lattice = np.stack(np.meshgrid(*[np.linspace(0.0, 1.0, 17)] * 3, indexing="ij"), axis=-1)[..., ::-1].astype(np.float32)
    cube = lattice_to_cube(lattice)
    assert cube.size == 33
    write_cube(tmp_path / "pred.cube", cube)
    assert read_cube(tmp_path / "pred.cube").size == 33
