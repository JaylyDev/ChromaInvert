import torch
import torch.nn.functional as F


def rgb_to_oklab(rgb: torch.Tensor) -> torch.Tensor:
    m1 = torch.tensor(
        [
            [0.4122214708, 0.5363325363, 0.0514459929],
            [0.2119034982, 0.6806995451, 0.0963969566],
            [0.0883024619, 0.2817188376, 0.6299787005],
        ],
        dtype=rgb.dtype,
        device=rgb.device,
    )
    m2 = torch.tensor(
        [
            [0.2104542553, 0.7936177850, -0.0040720468],
            [1.9779984951, -2.4285922050, 0.4505937099],
            [0.0259040371, 0.7827717662, -0.8086757660],
        ],
        dtype=rgb.dtype,
        device=rgb.device,
    )
    lms = rgb @ m1.T
    return (torch.sign(lms) * torch.abs(lms).pow(1.0 / 3.0)) @ m2.T


def quantile_loss(graded: torch.Tensor, reference: torch.Tensor, levels: int = 64) -> torch.Tensor:
    q = torch.linspace(0.0, 1.0, levels, dtype=graded.dtype, device=graded.device)
    return torch.mean(torch.abs(torch.quantile(graded, q, dim=0) - torch.quantile(reference, q, dim=0)))


def moment_loss(graded: torch.Tensor, reference: torch.Tensor) -> torch.Tensor:
    mean_term = torch.mean(torch.abs(graded.mean(dim=0) - reference.mean(dim=0)))
    std_term = torch.mean(torch.abs(graded.std(dim=0) - reference.std(dim=0)))
    return mean_term + std_term


def tv_loss(volume: torch.Tensor) -> torch.Tensor:
    d = torch.mean(torch.abs(volume[:, :, 1:, :, :] - volume[:, :, :-1, :, :]))
    h = torch.mean(torch.abs(volume[:, :, :, 1:, :] - volume[:, :, :, :-1, :]))
    w = torch.mean(torch.abs(volume[:, :, :, :, 1:] - volume[:, :, :, :, :-1]))
    return d + h + w


def identity_prior_loss(volume: torch.Tensor, identity: torch.Tensor) -> torch.Tensor:
    return F.mse_loss(volume, identity)


def gamut_loss(image: torch.Tensor) -> torch.Tensor:
    return torch.mean(F.relu(-image)) + torch.mean(F.relu(image - 1.0))


def skin_anchor_loss(graded_oklab: torch.Tensor, source_oklab: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    if not bool(mask.any()):
        return torch.zeros((), dtype=graded_oklab.dtype, device=graded_oklab.device)
    drift = graded_oklab[..., 1:3] - source_oklab[..., 1:3]
    return torch.mean(drift[mask] ** 2)


def shadow_quantile_loss(
    graded_l: torch.Tensor,
    reference_l: torch.Tensor,
    source_mask: torch.Tensor,
    reference_mask: torch.Tensor,
    levels: int = 16,
) -> torch.Tensor:
    if not bool(source_mask.any()) or not bool(reference_mask.any()):
        return torch.zeros((), dtype=graded_l.dtype, device=graded_l.device)
    q = torch.linspace(0.0, 1.0, levels, dtype=graded_l.dtype, device=graded_l.device)
    g = torch.quantile(graded_l[source_mask], q)
    r = torch.quantile(reference_l[reference_mask], q)
    return torch.mean(torch.abs(g - r))
