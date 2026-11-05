import numpy as np
import torch
import torch.nn.functional as F
from numpy.typing import NDArray
from torch import nn

from chromainvert.cube import identity_lattice


class DifferentiableLUT3D(nn.Module):
    def __init__(self, size: int, lattice: NDArray[np.float32] | None = None) -> None:
        super().__init__()
        if size < 2:
            raise ValueError("size must be at least 2")
        if lattice is None:
            lattice = identity_lattice(size)
        if lattice.shape != (size, size, size, 3):
            raise ValueError(f"lattice shape {lattice.shape} does not match size {size}")
        volume = torch.from_numpy(np.ascontiguousarray(lattice, dtype=np.float32)).permute(3, 0, 1, 2).unsqueeze(0).clone()
        self.size = size
        self.volume = nn.Parameter(volume)

    def forward(self, pixels: torch.Tensor) -> torch.Tensor:
        shape = pixels.shape
        grid = pixels.reshape(-1, 3).unsqueeze(0).unsqueeze(2).unsqueeze(2) * 2.0 - 1.0
        sampled = F.grid_sample(self.volume, grid, mode="bilinear", padding_mode="border", align_corners=True)
        return sampled.squeeze(0).squeeze(-1).squeeze(-1).permute(1, 0).reshape(shape)

    def lattice(self) -> NDArray[np.float32]:
        return self.volume.detach().cpu().permute(0, 2, 3, 4, 1).reshape(self.size, self.size, self.size, 3).numpy()
