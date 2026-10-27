import numpy as np
import pytest

from chromainvert.cube import CubeLut, identity_lattice, read_cube, write_cube


def test_identity_roundtrip(tmp_path):
    for size in (2, 17, 33):
        lut = CubeLut(size=size, lattice=identity_lattice(size), title="Identity")
        path = tmp_path / f"identity_{size}.cube"
        write_cube(path, lut)
        back = read_cube(path)
        assert back.size == size
        assert back.title == "Identity"
        np.testing.assert_allclose(back.lattice, lut.lattice, atol=1e-6)


def test_red_varies_fastest(tmp_path):
    size = 4
    path = tmp_path / "order.cube"
    write_cube(path, CubeLut(size=size, lattice=identity_lattice(size)))
    rows = [line for line in path.read_text().splitlines() if line and not line[0].isalpha() and not line.startswith("#")]
    assert len(rows) == size**3
    step = 1.0 / (size - 1)
    first = [float(v) for v in rows[0].split()]
    second = [float(v) for v in rows[1].split()]
    assert first == [0.0, 0.0, 0.0]
    assert second == [pytest.approx(step), 0.0, 0.0]


def test_domain_preserved(tmp_path):
    lut = CubeLut(
        size=2,
        lattice=identity_lattice(2),
        domain_min=(0.1, 0.1, 0.1),
        domain_max=(0.9, 0.9, 0.9),
    )
    path = tmp_path / "domain.cube"
    write_cube(path, lut)
    back = read_cube(path)
    assert back.domain_min == (pytest.approx(0.1), pytest.approx(0.1), pytest.approx(0.1))
    assert back.domain_max == (pytest.approx(0.9), pytest.approx(0.9), pytest.approx(0.9))


def test_rejects_bad_files(tmp_path):
    missing_size = tmp_path / "missing.cube"
    missing_size.write_text('TITLE "No size"\n0.0 0.0 0.0\n')
    with pytest.raises(ValueError):
        read_cube(missing_size)
    short_data = tmp_path / "short.cube"
    short_data.write_text("LUT_3D_SIZE 2\n0.0 0.0 0.0\n")
    with pytest.raises(ValueError):
        read_cube(short_data)
    one_d = tmp_path / "oned.cube"
    one_d.write_text("LUT_1D_SIZE 4\n")
    with pytest.raises(ValueError):
        read_cube(one_d)


def test_write_validates(tmp_path):
    wrong_shape = CubeLut(size=2, lattice=np.zeros((3, 3, 3, 3), dtype=np.float32))
    with pytest.raises(ValueError):
        write_cube(tmp_path / "shape.cube", wrong_shape)
    lattice = identity_lattice(2)
    lattice[0, 0, 0, 0] = np.nan
    with pytest.raises(ValueError):
        write_cube(tmp_path / "nan.cube", CubeLut(size=2, lattice=lattice))
