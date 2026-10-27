import numpy as np
import torch

from chromainvert.cube import CubeLut, identity_lattice, read_cube, write_cube
from chromainvert.lut_module import DifferentiableLUT3D


def test_identity_forward_matches_input():
    torch.manual_seed(0)
    lut = DifferentiableLUT3D(17)
    image = torch.rand(32, 32, 3)
    out = lut(image)
    assert torch.max(torch.abs(out - image)).item() < 1e-5


def test_corners_exact_and_gradient_flows():
    lut = DifferentiableLUT3D(9)
    corners = torch.tensor([[0.0, 0.0, 0.0], [1.0, 1.0, 1.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    out = lut(corners)
    assert torch.max(torch.abs(out - corners)).item() < 1e-5
    out.sum().backward()
    assert lut.volume.grad is not None


def test_module_lattice_exports_to_cube(tmp_path):
    lut = DifferentiableLUT3D(5)
    path = tmp_path / "module.cube"
    write_cube(path, CubeLut(size=5, lattice=lut.lattice()))
    back = read_cube(path)
    np.testing.assert_allclose(back.lattice, identity_lattice(5), atol=1e-6)
