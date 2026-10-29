import numpy as np
from numpy.typing import NDArray

_SRGB_TO_XYZ = np.array(
    [
        [0.4124564, 0.3575761, 0.1804375],
        [0.2126729, 0.7151522, 0.0721750],
        [0.0193339, 0.1191920, 0.9503041],
    ]
)
_XYZ_TO_SRGB = np.linalg.inv(_SRGB_TO_XYZ)
_D65_WHITE = np.array([0.95047, 1.0, 1.08883])

_M1 = np.array(
    [
        [0.4122214708, 0.5363325363, 0.0514459929],
        [0.2119034982, 0.6806995451, 0.0963969566],
        [0.0883024619, 0.2817188376, 0.6299787005],
    ]
)
_M2 = np.array(
    [
        [0.2104542553, 0.7936177850, -0.0040720468],
        [1.9779984951, -2.4285922050, 0.4505937099],
        [0.0259040371, 0.7827717662, -0.8086757660],
    ]
)
_M1_INV = np.linalg.inv(_M1)
_M2_INV = np.linalg.inv(_M2)

_SLOG_A = 0.01125
_SLOG_B = 420.0
_SLOG_C = 261.5
_SLOG_D = 171.2102946929
_SLOG_E = 95.0
_SLOG_MID = 0.18
_SLOG_OFF = 0.01

# Apple Log Profile specification constants.
_APPLE_R0 = -0.05641088
_APPLE_RT = 0.01
_APPLE_C = 47.28711236
_APPLE_BETA = 0.00964052
_APPLE_GAMMA = 0.08550479
_APPLE_DELTA = 0.69336945
_APPLE_PT = _APPLE_C * (_APPLE_RT - _APPLE_R0) ** 2

_BT2020_TO_SRGB_LINEAR = np.array(
    [
        [1.6604910021, -0.5876411388, -0.0728498633],
        [-0.1245504745, 1.1328998971, -0.0083494226],
        [-0.0181507634, -0.1005788980, 1.1187296614],
    ]
)


def srgb_to_linear(c: NDArray[np.floating]) -> NDArray[np.float64]:
    c = np.asarray(c, dtype=np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c: NDArray[np.floating]) -> NDArray[np.float64]:
    c = np.asarray(c, dtype=np.float64)
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * (c ** (1.0 / 2.4)) - 0.055)


def linear_srgb_to_oklab(rgb: NDArray[np.floating]) -> NDArray[np.float64]:
    rgb = np.asarray(rgb, dtype=np.float64)
    lms = rgb @ _M1.T
    lms_prime = np.cbrt(lms)
    return lms_prime @ _M2.T


def oklab_to_linear_srgb(lab: NDArray[np.floating]) -> NDArray[np.float64]:
    lab = np.asarray(lab, dtype=np.float64)
    lms_prime = lab @ _M2_INV.T
    return (lms_prime**3) @ _M1_INV.T


def linear_srgb_to_xyz(rgb: NDArray[np.floating]) -> NDArray[np.float64]:
    return np.asarray(rgb, dtype=np.float64) @ _SRGB_TO_XYZ.T


def xyz_to_lab(xyz: NDArray[np.floating]) -> NDArray[np.float64]:
    xyz = np.asarray(xyz, dtype=np.float64) / _D65_WHITE
    delta = 6.0 / 29.0
    f = np.where(xyz > delta**3, np.cbrt(xyz), xyz / (3.0 * delta**2) + 4.0 / 29.0)
    fx, fy, fz = f[..., 0], f[..., 1], f[..., 2]
    return np.stack([116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz)], axis=-1)


def linear_srgb_to_lab(rgb: NDArray[np.floating]) -> NDArray[np.float64]:
    return xyz_to_lab(linear_srgb_to_xyz(rgb))


def delta_e_2000(lab1: NDArray[np.floating], lab2: NDArray[np.floating]) -> NDArray[np.float64]:
    lab1 = np.asarray(lab1, dtype=np.float64)
    lab2 = np.asarray(lab2, dtype=np.float64)
    l1, a1, b1 = lab1[..., 0], lab1[..., 1], lab1[..., 2]
    l2, a2, b2 = lab2[..., 0], lab2[..., 1], lab2[..., 2]
    c1 = np.hypot(a1, b1)
    c2 = np.hypot(a2, b2)
    c_bar = (c1 + c2) / 2.0
    c_bar7 = c_bar**7
    g = 0.5 * (1.0 - np.sqrt(c_bar7 / (c_bar7 + 25.0**7)))
    a1p = (1.0 + g) * a1
    a2p = (1.0 + g) * a2
    c1p = np.hypot(a1p, b1)
    c2p = np.hypot(a2p, b2)
    c_barp = (c1p + c2p) / 2.0
    h1p = np.where(c1p == 0.0, 0.0, np.degrees(np.arctan2(b1, a1p)) % 360.0)
    h2p = np.where(c2p == 0.0, 0.0, np.degrees(np.arctan2(b2, a2p)) % 360.0)
    dh = h2p - h1p
    dhp = np.where(
        c1p * c2p == 0.0,
        0.0,
        np.where(np.abs(dh) <= 180.0, dh, np.where(dh > 0.0, dh - 360.0, dh + 360.0)),
    )
    d_hp = 2.0 * np.sqrt(c1p * c2p) * np.sin(np.radians(dhp) / 2.0)
    d_lp = l2 - l1
    d_cp = c2p - c1p
    h_sum = h1p + h2p
    h_barp = np.where(
        c1p * c2p == 0.0,
        h_sum,
        np.where(
            np.abs(dh) <= 180.0,
            h_sum / 2.0,
            np.where(h_sum < 360.0, (h_sum + 360.0) / 2.0, (h_sum - 360.0) / 2.0),
        ),
    )
    h_rad = np.radians(h_barp)
    t = (
        1.0
        - 0.17 * np.cos(h_rad - np.radians(30.0))
        + 0.24 * np.cos(2.0 * h_rad)
        + 0.32 * np.cos(3.0 * h_rad + np.radians(6.0))
        - 0.20 * np.cos(4.0 * h_rad - np.radians(63.0))
    )
    l_bar = (l1 + l2) / 2.0
    s_l = 1.0 + 0.015 * (l_bar - 50.0) ** 2 / np.sqrt(20.0 + (l_bar - 50.0) ** 2)
    s_c = 1.0 + 0.045 * c_barp
    s_h = 1.0 + 0.015 * c_barp * t
    c_barp7 = c_barp**7
    r_t = -2.0 * np.sqrt(c_barp7 / (c_barp7 + 25.0**7)) * np.sin(np.radians(60.0 * np.exp(-(((h_barp - 275.0) / 25.0) ** 2))))
    return np.sqrt((d_lp / s_l) ** 2 + (d_cp / s_c) ** 2 + (d_hp / s_h) ** 2 + r_t * (d_cp / s_c) * (d_hp / s_h))


def encode_slog3(reflection: NDArray[np.floating]) -> NDArray[np.float64]:
    x = np.asarray(reflection, dtype=np.float64)
    hi = (_SLOG_B + np.log10((x + _SLOG_OFF) / (_SLOG_MID + _SLOG_OFF)) * _SLOG_C) / 1023.0
    lo = (x * (_SLOG_D - _SLOG_E) / _SLOG_A + _SLOG_E) / 1023.0
    return np.where(x >= _SLOG_A, hi, lo)


def decode_slog3(code: NDArray[np.floating]) -> NDArray[np.float64]:
    y = np.asarray(code, dtype=np.float64)
    hi = (10.0 ** ((y * 1023.0 - _SLOG_B) / _SLOG_C)) * (_SLOG_MID + _SLOG_OFF) - _SLOG_OFF
    lo = (y * 1023.0 - _SLOG_E) * _SLOG_A / (_SLOG_D - _SLOG_E)
    return np.where(y >= _SLOG_D / 1023.0, hi, lo)


def encode_apple_log(reflection: NDArray[np.floating]) -> NDArray[np.float64]:
    x = np.asarray(reflection, dtype=np.float64)
    quad = _APPLE_C * (x - _APPLE_R0) ** 2
    with np.errstate(invalid="ignore", divide="ignore"):
        log = _APPLE_GAMMA * np.log2(x + _APPLE_BETA) + _APPLE_DELTA
    return np.where(x < _APPLE_R0, 0.0, np.where(x < _APPLE_RT, quad, log))


def decode_apple_log(code: NDArray[np.floating]) -> NDArray[np.float64]:
    y = np.asarray(code, dtype=np.float64)
    quad = np.sqrt(np.maximum(y, 0.0) / _APPLE_C) + _APPLE_R0
    log = 2.0 ** ((y - _APPLE_DELTA) / _APPLE_GAMMA) - _APPLE_BETA
    return np.where(y < 0.0, _APPLE_R0, np.where(y < _APPLE_PT, quad, log))


def rec2020_to_rec709_linear(rgb: NDArray[np.floating]) -> NDArray[np.float64]:
    return np.asarray(rgb, dtype=np.float64) @ _BT2020_TO_SRGB_LINEAR.T


def decode_input(pixels: NDArray[np.floating], profile: str) -> NDArray[np.float64]:
    if profile == "rec709":
        return srgb_to_linear(pixels)
    if profile == "slog3":
        return decode_slog3(pixels)
    if profile == "apple_log":
        linear2020 = decode_apple_log(pixels)
        return np.clip(rec2020_to_rec709_linear(linear2020), 0.0, 1.0)
    raise ValueError(f"unknown input profile: {profile}")
