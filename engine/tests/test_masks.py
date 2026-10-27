import numpy as np

from chromainvert.masks import rgb_to_ycbcr, shadow_mask_l, skin_mask_rgb


def test_skin_mask_accepts_skin_rejects_other():
    skin = np.array([[[0.85, 0.60, 0.50]]])
    assert skin_mask_rgb(skin)[0, 0]
    assert not skin_mask_rgb(np.array([[[0.0, 0.0, 1.0]]]))[0, 0]
    assert not skin_mask_rgb(np.array([[[1.0, 1.0, 1.0]]]))[0, 0]
    assert not skin_mask_rgb(np.array([[[0.1, 0.1, 0.1]]]))[0, 0]


def test_skin_mask_shape_and_dtype():
    rng = np.random.default_rng(3)
    rgb = rng.random((8, 12, 3))
    mask = skin_mask_rgb(rgb)
    assert mask.shape == (8, 12)
    assert mask.dtype == np.bool_


def test_ycbcr_neutral_gray():
    ycbcr = rgb_to_ycbcr(np.array([[0.5, 0.5, 0.5]]))
    np.testing.assert_allclose(ycbcr, [[127.5, 128.0, 128.0]], atol=1e-9)


def test_shadow_mask_bottom_decile():
    l = np.linspace(0.0, 1.0, 100).reshape(10, 10)
    mask = shadow_mask_l(l, percentile=10.0)
    assert mask.sum() == 10
    assert mask[0, :].all()
    assert not mask[5, 5]
