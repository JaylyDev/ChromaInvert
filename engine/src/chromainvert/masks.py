import numpy as np
from numpy.typing import NDArray


def rgb_to_ycbcr(rgb: NDArray[np.floating]) -> NDArray[np.float64]:
    rgb255 = np.asarray(rgb, dtype=np.float64) * 255.0
    r, g, b = rgb255[..., 0], rgb255[..., 1], rgb255[..., 2]
    y = 0.299 * r + 0.587 * g + 0.114 * b
    cb = 128.0 - 0.168736 * r - 0.331264 * g + 0.5 * b
    cr = 128.0 + 0.5 * r - 0.418688 * g - 0.081312 * b
    return np.stack([y, cb, cr], axis=-1)


def skin_mask_rgb(rgb: NDArray[np.floating]) -> NDArray[np.bool_]:
    rgb255 = np.asarray(rgb, dtype=np.float64) * 255.0
    r, g, b = rgb255[..., 0], rgb255[..., 1], rgb255[..., 2]
    ycbcr = rgb_to_ycbcr(rgb)
    cb, cr = ycbcr[..., 1], ycbcr[..., 2]
    return (
        (r > 95.0)
        & (g > 40.0)
        & (b > 20.0)
        & ((rgb255.max(axis=-1) - rgb255.min(axis=-1)) > 15.0)
        & (np.abs(r - g) > 15.0)
        & (r > g)
        & (r > b)
        & (cb > 77.0)
        & (cb < 127.0)
        & (cr > 133.0)
        & (cr < 173.0)
    )


def shadow_mask_l(oklab_l: NDArray[np.floating], percentile: float = 10.0) -> NDArray[np.bool_]:
    l = np.asarray(oklab_l, dtype=np.float64)
    return l <= np.quantile(l, percentile / 100.0)
