import torch

from chromainvert.losses import (
    _SafeCbrt,
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


def test_distribution_losses_zero_on_identical():
    torch.manual_seed(0)
    x = torch.rand(512, 3)
    assert quantile_loss(x, x).item() == 0.0
    assert moment_loss(x, x).item() == 0.0


def test_distribution_losses_positive_on_shift():
    x = torch.rand(512, 3) * 0.5
    y = x + 0.25
    assert quantile_loss(y, x).item() > 0.1
    assert moment_loss(y, x).item() > 0.1
    assert covariance_loss(y, x).item() < 1e-6


def test_covariance_loss_detects_saturation_change():
    torch.manual_seed(1)
    x = torch.rand(1024, 3)
    luma = x.mean(dim=1, keepdim=True)
    y = luma + 1.5 * (x - luma)
    assert covariance_loss(y, x).item() > 0.0
    assert covariance_loss(x, x).item() == 0.0


def test_tv_loss():
    n = 5
    assert tv_loss(torch.zeros(1, 3, n, n, n)).item() == 0.0
    coords = torch.linspace(0.0, 1.0, n)
    grid = torch.stack(torch.meshgrid(coords, coords, coords, indexing="ij"), dim=-1)
    volume = grid[..., [2, 1, 0]].permute(3, 0, 1, 2).unsqueeze(0)
    value = tv_loss(volume).item()
    assert value > 0.0


def test_gamut_loss():
    assert gamut_loss(torch.rand(64, 3) * 0.5 + 0.25).item() == 0.0
    bad = torch.rand(64, 3) * 0.5 + 0.25
    bad[0, 0] = 1.5
    assert gamut_loss(bad).item() > 0.0


def test_identity_prior_zero_at_identity():
    v = torch.rand(1, 3, 4, 4, 4)
    assert identity_prior_loss(v, v).item() == 0.0
    assert identity_prior_loss(v + 0.5, v).item() > 0.0


def test_skin_anchor_empty_mask_is_zero():
    g = torch.rand(32, 3)
    s = torch.rand(32, 3)
    mask = torch.zeros(32, dtype=torch.bool)
    assert skin_anchor_loss(g, s, mask).item() == 0.0
    full = torch.ones(32, dtype=torch.bool)
    assert skin_anchor_loss(s, s, full).item() == 0.0
    assert skin_anchor_loss(g, s, full).item() > 0.0


def test_shadow_quantile_empty_mask_is_zero():
    g = torch.rand(64)
    r = torch.rand(64)
    empty = torch.zeros(64, dtype=torch.bool)
    full = torch.ones(64, dtype=torch.bool)
    assert shadow_quantile_loss(g, r, empty, full).item() == 0.0
    assert shadow_quantile_loss(g, r, full, empty).item() == 0.0
    assert shadow_quantile_loss(r, r, full, full).item() == 0.0


def test_safe_cbrt_backward_sign_and_cap():
    for value, expected in ((-0.125, 4.0 / 3.0), (0.125, 4.0 / 3.0)):
        x = torch.tensor([value], requires_grad=True)
        _SafeCbrt.apply(x).backward()
        assert x.grad is not None
        assert abs(x.grad.item() - expected) < 1e-6
    x = torch.tensor([-1e-18], requires_grad=True)
    _SafeCbrt.apply(x).backward()
    assert x.grad is not None
    assert 0.0 <= x.grad.item() <= 1e4


def test_covariance_loss_unequal_sample_counts():
    torch.manual_seed(2)
    x = torch.rand(257, 3)
    assert covariance_loss(x, x.repeat(4, 1)).item() < 1e-6


def test_oklab_backward_finite_on_black():
    x = torch.zeros(16, 3, requires_grad=True)
    rgb_to_oklab(x).sum().backward()
    assert bool(torch.isfinite(x.grad).all())


def test_losses_differentiable():
    g = torch.rand(256, 3, requires_grad=True)
    r = torch.rand(256, 3)
    total = quantile_loss(g, r) + moment_loss(g, r) + gamut_loss(g)
    total.backward()
    assert g.grad is not None
