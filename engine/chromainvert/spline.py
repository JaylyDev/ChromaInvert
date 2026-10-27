import numpy as np
from numpy.typing import NDArray


def _weights(t: NDArray[np.floating]) -> NDArray[np.float64]:
    t = np.asarray(t, dtype=np.float64)
    t2 = t * t
    t3 = t2 * t
    w0 = -0.5 * t3 + t2 - 0.5 * t
    w1 = 1.5 * t3 - 2.5 * t2 + 1.0
    w2 = -1.5 * t3 + 2.0 * t2 + 0.5 * t
    w3 = 0.5 * t3 - 0.5 * t2
    return np.stack([w0, w1, w2, w3], axis=-1)


def _upsample_axis(values: NDArray[np.floating], new_n: int, axis: int) -> NDArray[np.float64]:
    values = np.asarray(values, dtype=np.float64)
    n = values.shape[axis]
    if new_n == n:
        return values.copy()
    if n == 1:
        return np.repeat(values, new_n, axis=axis)
    positions = np.linspace(0.0, float(n - 1), new_n)
    j = np.clip(np.floor(positions).astype(np.int64), 0, n - 2)
    t = positions - j
    w = _weights(t)
    shape = [1] * values.ndim
    shape[axis] = new_n
    out = np.zeros_like(values, shape=tuple(new_n if k == axis else values.shape[k] for k in range(values.ndim)))
    for d, offset in enumerate((-1, 0, 1, 2)):
        idx = np.clip(j + offset, 0, n - 1)
        out = out + np.take(values, idx, axis=axis) * w[:, d].reshape(shape)
    return out


def catmull_rom_upsample(lattice: NDArray[np.floating], new_size: int) -> NDArray[np.float32]:
    lattice = np.asarray(lattice, dtype=np.float64)
    if lattice.ndim != 4 or lattice.shape[0] != lattice.shape[1] or lattice.shape[0] != lattice.shape[2]:
        raise ValueError(f"expected cubic lattice, got shape {lattice.shape}")
    if new_size < 2:
        raise ValueError("new_size must be at least 2")
    out = lattice
    for axis in (0, 1, 2):
        out = _upsample_axis(out, new_size, axis)
    return np.ascontiguousarray(out, dtype=np.float32)
