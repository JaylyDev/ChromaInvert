import os
import random
import time
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import torch
from numpy.typing import NDArray

from chromainvert.cube import CubeLut, identity_lattice
from chromainvert.losses import (
    covariance_loss,
    gamut_loss,
    identity_prior_loss,
    moment_loss,
    quantile_loss,
    rgb_to_oklab,
    shadow_quantile_loss,
    skin_anchor_loss,
    tv_loss,
)
from chromainvert.lut_module import DifferentiableLUT3D
from chromainvert.masks import shadow_mask_l, skin_mask_rgb
from chromainvert.spline import catmull_rom_upsample


@dataclass
class OptimizeConfig:
    coarse_size: int = 17
    fine_size: int = 33
    iterations: int = 400
    fine_iterations: int = 30
    lr: float = 0.01
    fine_lr: float = 0.005
    pixel_budget: int = 65536
    seed: int = 42
    device: str = "auto"
    weight_quantile: float = 1.0
    weight_moment: float = 1.0
    weight_covariance: float = 10.0
    weight_tv: float = 0.1
    weight_identity: float = 0.0
    weight_skin: float = 0.05
    weight_shadow: float = 0.25
    weight_gamut: float = 1.0
    deterministic: bool = False

    def __post_init__(self) -> None:
        if self.coarse_size < 2 or self.fine_size < 2:
            raise ValueError("lattice sizes must be at least 2")
        if self.iterations < 0 or self.fine_iterations < 0 or self.iterations + self.fine_iterations == 0:
            raise ValueError("at least one optimization stage must run")
        if self.pixel_budget <= 0:
            raise ValueError("pixel_budget must be positive")
        if self.lr <= 0.0 or self.fine_lr <= 0.0:
            raise ValueError("learning rates must be positive")


def sample_pixels(frames: list[NDArray[np.floating]], budget: int, seed: int) -> NDArray[np.float32]:
    arrays = [np.asarray(f, dtype=np.float32) for f in frames]
    for a in arrays:
        if a.ndim != 3 or a.shape[-1] != 3:
            raise ValueError(f"expected (H, W, 3) frames, got shape {a.shape}")
    flat = np.concatenate([a.reshape(-1, 3) for a in arrays], axis=0)
    rng = np.random.default_rng(seed)
    if flat.shape[0] > budget:
        flat = flat[rng.choice(flat.shape[0], budget, replace=False)]
    return np.ascontiguousarray(np.clip(flat, 0.0, 1.0), dtype=np.float32)


def resolve_device(requested: str) -> str:
    if requested == "cpu":
        return "cpu"
    if requested == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    if requested == "cuda":
        if not torch.cuda.is_available():
            raise ValueError("device=cuda was requested but CUDA is not available")
        return "cuda"
    raise ValueError(f"unknown device: {requested}")


def affine_warm_start(source: NDArray[np.floating], reference: NDArray[np.floating], size: int) -> NDArray[np.float32]:
    source = np.asarray(source, dtype=np.float64)
    reference = np.asarray(reference, dtype=np.float64)
    gain = reference.std(axis=0) / np.clip(source.std(axis=0), 1e-6, None)
    bias = reference.mean(axis=0) - gain * source.mean(axis=0)
    return np.clip(identity_lattice(size).astype(np.float64) * gain + bias, 0.0, 1.0).astype(np.float32)


def enable_deterministic(seed: int) -> dict[str, str | bool | int]:
    if "CUBLAS_WORKSPACE_CONFIG" not in os.environ:
        os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
    # warn_only: grid_sample backward has no deterministic CUDA kernel, so strict mode raises.
    # Sticky process-global mode: once enabled it stays on for later calls in the same process.
    torch.use_deterministic_algorithms(True, warn_only=True)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    torch.manual_seed(seed)
    np.random.seed(seed)
    random.seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    status: dict[str, str | bool | int] = {
        "cublas_workspace_config": os.environ.get("CUBLAS_WORKSPACE_CONFIG", ""),
        "deterministic_algorithms": True,
        "deterministic_warn_only": True,
        "cudnn_deterministic": True,
        "cudnn_benchmark": False,
        "seed": seed,
    }
    return status


def optimize_lut(
    source_frames: list[NDArray[np.floating]],
    reference_frames: list[NDArray[np.floating]],
    config: OptimizeConfig,
    progress: Callable[[int, int, float, float], None] | None = None,
) -> tuple[CubeLut, dict]:
    started = time.monotonic()
    det_status: dict[str, str | bool | int] | None = None
    if config.deterministic:
        det_status = enable_deterministic(config.seed)
    device = torch.device(resolve_device(config.device))
    source = sample_pixels(source_frames, config.pixel_budget, config.seed)
    reference = sample_pixels(reference_frames, config.pixel_budget, config.seed + 1)
    source_mask = skin_mask_rgb(source)
    dither_rng = np.random.default_rng(config.seed + 2)
    noise_scale = 0.5 / 255.0
    source = np.clip(source + dither_rng.normal(0.0, noise_scale, source.shape), 0.0, 1.0).astype(np.float32)
    reference = np.clip(reference + dither_rng.normal(0.0, noise_scale, reference.shape), 0.0, 1.0).astype(np.float32)
    reference_oklab = rgb_to_oklab(torch.from_numpy(reference).to(device))

    def run_stage(lut: DifferentiableLUT3D, iters: int, lr: float, offset: int, total: int) -> dict[str, float]:
        optimizer = torch.optim.Adam(lut.parameters(), lr=lr)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max(iters, 1))
        identity = torch.from_numpy(identity_lattice(lut.size)).permute(3, 0, 1, 2).unsqueeze(0).to(device=device, dtype=lut.volume.dtype)
        src = torch.from_numpy(source).to(device)
        src_oklab = rgb_to_oklab(src)
        ref_l = reference_oklab[..., 0]
        src_shadow = torch.from_numpy(shadow_mask_l(src_oklab.detach().cpu().numpy()[..., 0])).to(device)
        ref_shadow = torch.from_numpy(shadow_mask_l(reference_oklab.detach().cpu().numpy()[..., 0])).to(device)
        skin = torch.from_numpy(source_mask).to(device)
        terms: dict[str, float] = {}
        for i in range(iters):
            optimizer.zero_grad()
            graded = lut(src)
            graded_oklab = rgb_to_oklab(graded)
            l_quantile = quantile_loss(graded_oklab, reference_oklab)
            l_moment = moment_loss(graded_oklab, reference_oklab)
            l_covariance = covariance_loss(graded_oklab, reference_oklab)
            l_tv = tv_loss(lut.volume)
            l_identity = identity_prior_loss(lut.volume, identity)
            l_skin = skin_anchor_loss(graded_oklab, src_oklab, skin)
            l_shadow = shadow_quantile_loss(graded_oklab[..., 0], ref_l, src_shadow, ref_shadow)
            l_gamut = gamut_loss(graded)
            total_loss = (
                config.weight_quantile * l_quantile
                + config.weight_moment * l_moment
                + config.weight_covariance * l_covariance
                + config.weight_tv * l_tv
                + config.weight_identity * l_identity
                + config.weight_skin * l_skin
                + config.weight_shadow * l_shadow
                + config.weight_gamut * l_gamut
            )
            total_loss.backward()
            optimizer.step()
            scheduler.step()
            terms = {
                "quantile": l_quantile.item(),
                "moment": l_moment.item(),
                "covariance": l_covariance.item(),
                "tv": l_tv.item(),
                "identity": l_identity.item(),
                "skin": l_skin.item(),
                "shadow": l_shadow.item(),
                "gamut": l_gamut.item(),
                "total": total_loss.item(),
            }
            if progress is not None:
                progress(offset + i + 1, total, total_loss.item(), time.monotonic() - started)
        return terms

    total_iters = config.iterations + config.fine_iterations
    coarse = DifferentiableLUT3D(config.coarse_size, lattice=affine_warm_start(source, reference, config.coarse_size)).to(device)
    coarse_terms = run_stage(coarse, config.iterations, config.lr, 0, total_iters)
    coarse_lattice = coarse.lattice()
    fine_init = catmull_rom_upsample(coarse_lattice, config.fine_size)
    fine = DifferentiableLUT3D(config.fine_size, lattice=fine_init).to(device)
    fine_terms = run_stage(fine, config.fine_iterations, config.fine_lr, config.iterations, total_iters)
    lattice = fine.lattice()
    seconds = time.monotonic() - started
    neighbor = max(
        float(np.abs(np.diff(lattice, axis=0)).max()),
        float(np.abs(np.diff(lattice, axis=1)).max()),
        float(np.abs(np.diff(lattice, axis=2)).max()),
    )
    report = {
        "device": str(device),
        "deterministic": bool(config.deterministic),
        "deterministic_warn_only": bool(det_status["deterministic_warn_only"]) if det_status else False,
        "deterministic_cublas": str(det_status["cublas_workspace_config"]) if det_status else "",
        "deterministic_algorithms_enabled": bool(torch.are_deterministic_algorithms_enabled()),
        "variance_note": "Deterministic requested: best effort only. CPU repeats exactly; CUDA grid_sample backward has no deterministic kernel so identical seeds may still vary. Mode is process-global and sticky with 10-30pct slowdown" if config.deterministic else "GPU atomic nondeterminism causes 4-5pct spread in improvement without deterministic mode; enable deterministic for best-effort reproducibility with 10-30pct slowdown",
        "seed": config.seed,
        "coarse_size": config.coarse_size,
        "fine_size": config.fine_size,
        "iterations": config.iterations,
        "fine_iterations": config.fine_iterations,
        "source_pixels": int(source.shape[0]),
        "reference_pixels": int(reference.shape[0]),
        "seconds": seconds,
        "final_loss_terms": fine_terms if config.fine_iterations else coarse_terms,
        "lattice_min": float(lattice.min()),
        "lattice_max": float(lattice.max()),
        "max_neighbor_delta": float(neighbor),
    }
    return CubeLut(size=config.fine_size, lattice=lattice), report
