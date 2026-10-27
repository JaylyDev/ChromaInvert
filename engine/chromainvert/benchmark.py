import time

import numpy as np
import torch
from numpy.typing import NDArray

from chromainvert.color import delta_e_2000, linear_srgb_to_lab
from chromainvert.cube import CubeLut
from chromainvert.lut_module import DifferentiableLUT3D
from chromainvert.optimize import OptimizeConfig, optimize_lut


def hsv_to_rgb(hsv: NDArray[np.floating]) -> NDArray[np.float64]:
    hsv = np.asarray(hsv, dtype=np.float64)
    h = (hsv[..., 0] * 6.0) % 6.0
    s = hsv[..., 1]
    v = hsv[..., 2]
    i = np.floor(h).astype(np.int64)
    f = h - np.floor(h)
    p = v * (1.0 - s)
    q = v * (1.0 - f * s)
    t = v * (1.0 - (1.0 - f) * s)
    out = np.empty(hsv.shape)
    table = [
        (v, t, p),
        (q, v, p),
        (p, v, t),
        (p, q, v),
        (t, p, v),
        (v, p, q),
    ]
    for k, (r, g, b) in enumerate(table):
        m = i == k
        out[m, 0], out[m, 1], out[m, 2] = r[m], g[m], b[m]
    return out


def make_chart(width: int = 1536, height: int = 512, seed: int = 7) -> NDArray[np.float64]:
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float64)
    chart = np.zeros((height, width, 3))
    chart[..., 0] = 0.05 + 0.9 * xx / width
    chart[..., 1] = 0.05 + 0.9 * yy / height
    chart[..., 2] = 0.05 + 0.9 * ((xx + yy) / (width + height))
    rows, cols = 4, 8
    ph, pw = height * 3 // 4 // rows, width // cols
    for r in range(rows):
        for c in range(cols):
            hue = (r * cols + c) / (rows * cols)
            patch = hsv_to_rgb(np.array([[[hue, 0.85, 0.45 + 0.5 * ((r + c) % 2)]]]))
            chart[r * ph : (r + 1) * ph, c * pw : (c + 1) * pw] = patch
    cy, cx, ry, rx = height // 3, width // 6, height // 8, width // 20
    ellipse = ((yy - cy) / ry) ** 2 + ((xx - cx) / rx) ** 2 <= 1.0
    chart[ellipse] = (0.78, 0.57, 0.47)
    ramp = np.linspace(0.0, 1.0, width).reshape(1, width, 1)
    chart[height * 7 // 8 :, :, :] = ramp
    chart = chart + rng.normal(0.0, 0.005, chart.shape)
    return np.clip(chart, 0.0, 1.0)


def commercial_style_lattice(size: int = 33) -> NDArray[np.float64]:
    coords = np.linspace(0.0, 1.0, size)
    grid = np.stack(np.meshgrid(coords, coords, coords, indexing="ij"), axis=-1)[..., ::-1]
    rgb = grid * np.array([1.08, 1.0, 0.92]) + np.array([0.02, 0.01, 0.03])
    luma = rgb @ np.array([0.2126, 0.7152, 0.0722])
    scale = (luma + 0.5 * luma * (1.0 - luma) * (luma - 0.5)) / np.clip(luma, 1e-6, None)
    rgb = rgb * scale[..., None]
    luma = np.clip(rgb @ np.array([0.2126, 0.7152, 0.0722]), 0.0, 1.0)
    rgb = luma[..., None] + 1.25 * (rgb - luma[..., None])
    shadow_w = (1.0 - luma) ** 2
    highlight_w = luma**2
    rgb = rgb + shadow_w[..., None] * np.array([-0.03, 0.01, 0.04])
    rgb = rgb + highlight_w[..., None] * np.array([0.04, 0.01, -0.03])
    return np.ascontiguousarray(np.clip(rgb, 0.0, 1.0), dtype=np.float64)


def apply_lut(image: NDArray[np.floating], lattice: NDArray[np.floating]) -> NDArray[np.float32]:
    module = DifferentiableLUT3D(int(lattice.shape[0]), lattice=np.asarray(lattice, dtype=np.float32))
    with torch.no_grad():
        return module(torch.from_numpy(np.asarray(image, dtype=np.float32))).numpy()


def mean_de00(a: NDArray[np.floating], b: NDArray[np.floating]) -> float:
    a = np.asarray(a).reshape(-1, 3)[::16]
    b = np.asarray(b).reshape(-1, 3)[::16]
    return float(delta_e_2000(linear_srgb_to_lab(a), linear_srgb_to_lab(b)).mean())


def run_benchmark(
    coarse_size: int = 17,
    fine_size: int = 33,
    iterations: int = 400,
    fine_iterations: int = 30,
    seed: int = 123,
    device: str = "auto",
    pixel_budget: int = 65536,
) -> dict:
    started = time.monotonic()
    chart = make_chart(seed=seed)
    other = make_chart(seed=seed + 1)
    heldout = make_chart(seed=seed + 2)
    source = chart
    truth = CubeLut(size=33, lattice=commercial_style_lattice(33).astype(np.float32))
    reference = apply_lut(other, truth.lattice)
    config = OptimizeConfig(
        coarse_size=coarse_size,
        fine_size=fine_size,
        iterations=iterations,
        fine_iterations=fine_iterations,
        seed=seed,
        device=device,
        pixel_budget=pixel_budget,
    )
    lut, report = optimize_lut([source], [reference], config)
    graded_heldout = apply_lut(heldout, lut.lattice)
    truth_heldout = apply_lut(heldout, truth.lattice)
    baseline = mean_de00(truth_heldout, heldout)
    recovered = mean_de00(truth_heldout, graded_heldout)
    rmse = float(np.sqrt(np.mean((truth_heldout - graded_heldout) ** 2)))
    return {
        "seed": seed,
        "coarse_size": coarse_size,
        "fine_size": fine_size,
        "iterations": iterations,
        "fine_iterations": fine_iterations,
        "baseline_heldout_de00": baseline,
        "recovered_heldout_de00": recovered,
        "improvement_heldout": (baseline - recovered) / baseline if baseline > 0 else 0.0,
        "heldout_psnr": 20.0 * np.log10(1.0 / rmse) if rmse > 0 else float("inf"),
        "seconds": time.monotonic() - started,
        "optimizer_report": report,
    }
