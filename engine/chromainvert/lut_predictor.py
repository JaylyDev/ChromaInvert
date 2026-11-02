import numpy as np
import torch
from numpy.typing import NDArray
from torch import nn

from chromainvert.color import linear_srgb_to_oklab
from chromainvert.cube import CubeLut, identity_lattice

FEATURE_DIM = 38
PREDICT_SIZE = 17
EXPORT_SIZE = 33


def grade_features(working: NDArray[np.floating]) -> NDArray[np.float32]:
    pixels = np.asarray(working, dtype=np.float64).reshape(-1, 3)
    pixels = np.clip(pixels, 0.0, 1.0)
    mean = pixels.mean(axis=0)
    std = pixels.std(axis=0)
    levels = np.array([0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95])
    quantiles = np.quantile(pixels, levels, axis=0).reshape(-1)
    oklab = linear_srgb_to_oklab(np.clip(pixels, 0.0, 1.0))
    lab_mean = oklab.mean(axis=0)
    lab_std = oklab.std(axis=0)
    l_quantiles = np.quantile(oklab[:, 0], [0.1, 0.5, 0.9])
    sat = (pixels.max(axis=1) - pixels.min(axis=1)) / np.clip(pixels.max(axis=1), 1e-6, None)
    feats = np.concatenate([mean, std, quantiles, lab_mean, lab_std, l_quantiles, [sat.mean(), sat.std()]])
    return np.ascontiguousarray(feats, dtype=np.float32)


class LutPredictor(nn.Module):
    def __init__(self, feature_dim: int = FEATURE_DIM, size: int = PREDICT_SIZE, hidden: tuple[int, int] = (128, 256)) -> None:
        super().__init__()
        self.size = size
        self.net = nn.Sequential(
            nn.Linear(feature_dim, hidden[0]),
            nn.ReLU(),
            nn.Linear(hidden[0], hidden[1]),
            nn.ReLU(),
            nn.Linear(hidden[1], size**3 * 3),
        )
        with torch.no_grad():
            self.net[-1].weight.zero_()
            self.net[-1].bias.zero_()

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        raw = self.net(features).reshape(features.shape[0], self.size, self.size, self.size, 3)
        identity = torch.from_numpy(identity_lattice(self.size)).to(dtype=raw.dtype, device=raw.device)
        return torch.clamp(identity + 0.5 * torch.tanh(raw), 0.0, 1.0)


def lattice_to_cube(lattice: NDArray[np.floating], size: int = EXPORT_SIZE) -> CubeLut:
    from chromainvert.spline import catmull_rom_upsample

    lattice = np.asarray(lattice, dtype=np.float32)
    if lattice.shape[0] != size:
        lattice = catmull_rom_upsample(lattice, size).astype(np.float32)
    return CubeLut(size=size, lattice=np.ascontiguousarray(lattice, dtype=np.float32), title="ChromaInvert")
