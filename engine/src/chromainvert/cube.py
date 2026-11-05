from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray


@dataclass
class CubeLut:
    size: int
    lattice: NDArray[np.float32]
    title: str = ""
    domain_min: tuple[float, float, float] = (0.0, 0.0, 0.0)
    domain_max: tuple[float, float, float] = (1.0, 1.0, 1.0)


def identity_lattice(size: int) -> NDArray[np.float32]:
    if size < 2:
        raise ValueError("size must be at least 2")
    coords = np.linspace(0.0, 1.0, size, dtype=np.float32)
    grid = np.stack(np.meshgrid(coords, coords, coords, indexing="ij"), axis=-1)
    return np.ascontiguousarray(grid[..., ::-1], dtype=np.float32)


def write_cube(path: str | Path, lut: CubeLut) -> None:
    _check_lut(lut)
    if '"' in lut.title or "\n" in lut.title:
        raise ValueError("title must not contain quotes or newlines")
    lines = []
    if lut.title:
        lines.append(f'TITLE "{lut.title}"')
    lines.append(f"LUT_3D_SIZE {lut.size}")
    if lut.domain_min != (0.0, 0.0, 0.0) or lut.domain_max != (1.0, 1.0, 1.0):
        lines.append("DOMAIN_MIN {} {} {}".format(*lut.domain_min))
        lines.append("DOMAIN_MAX {} {} {}".format(*lut.domain_max))
    for red, green, blue in np.clip(lut.lattice, 0.0, 1.0).reshape(-1, 3):
        lines.append(f"{red:.6f} {green:.6f} {blue:.6f}")
    Path(path).write_text("\n".join(lines) + "\n")


def read_cube(path: str | Path) -> CubeLut:
    title = ""
    size = 0
    domain_min: tuple[float, float, float] = (0.0, 0.0, 0.0)
    domain_max: tuple[float, float, float] = (1.0, 1.0, 1.0)
    data: list[list[float]] = []
    for raw in Path(path).read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("TITLE"):
            title = _parse_title(line)
        elif line.startswith("LUT_3D_SIZE"):
            size = _parse_size(line)
        elif line.startswith("DOMAIN_MIN"):
            domain_min = _parse_triplet(line)
        elif line.startswith("DOMAIN_MAX"):
            domain_max = _parse_triplet(line)
        elif line.startswith("LUT_1D_SIZE"):
            raise ValueError("1D LUTs are not supported")
        elif line[0].isalpha():
            raise ValueError(f"unsupported keyword line: {line}")
        else:
            data.append(_parse_row(line))
    if size < 2:
        raise ValueError("missing LUT_3D_SIZE")
    if len(data) != size**3:
        raise ValueError(f"expected {size**3} lattice rows, found {len(data)}")
    lattice = np.array(data, dtype=np.float32).reshape(size, size, size, 3)
    return CubeLut(size=size, lattice=lattice, title=title, domain_min=domain_min, domain_max=domain_max)


def _check_lut(lut: CubeLut) -> None:
    if lut.size < 2:
        raise ValueError("size must be at least 2")
    if not isinstance(lut.lattice, np.ndarray):
        raise ValueError("lattice must be a numpy array")
    if lut.lattice.shape != (lut.size, lut.size, lut.size, 3):
        raise ValueError(f"lattice shape {lut.lattice.shape} does not match size {lut.size}")
    if not bool(np.all(np.isfinite(lut.lattice))):
        raise ValueError("lattice must be finite")


def _parse_title(line: str) -> str:
    rest = line[len("TITLE"):].strip()
    if len(rest) >= 2 and rest.startswith('"') and rest.endswith('"'):
        return rest[1:-1]
    return rest


def _parse_size(line: str) -> int:
    parts = line.split()
    if len(parts) != 2:
        raise ValueError(f"bad LUT_3D_SIZE line: {line}")
    return int(parts[1])


def _parse_triplet(line: str) -> tuple[float, float, float]:
    parts = line.split()
    if len(parts) != 4:
        raise ValueError(f"bad domain line: {line}")
    return (float(parts[1]), float(parts[2]), float(parts[3]))


def _parse_row(line: str) -> list[float]:
    parts = line.split()
    if len(parts) != 3:
        raise ValueError(f"bad lattice row: {line}")
    return [float(parts[0]), float(parts[1]), float(parts[2])]
