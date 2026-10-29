import numpy as np

from chromainvert.color import (
    decode_apple_log,
    decode_input,
    decode_slog3,
    delta_e_2000,
    encode_apple_log,
    encode_slog3,
    linear_srgb_to_lab,
    linear_srgb_to_oklab,
    linear_to_srgb,
    oklab_to_linear_srgb,
    rec2020_to_rec709_linear,
    srgb_to_linear,
)


def test_srgb_roundtrip():
    rng = np.random.default_rng(0)
    c = rng.random((100, 3))
    np.testing.assert_allclose(linear_to_srgb(srgb_to_linear(c)), c, atol=1e-12)


def test_oklab_roundtrip():
    rng = np.random.default_rng(1)
    rgb = rng.random((100, 3))
    np.testing.assert_allclose(oklab_to_linear_srgb(linear_srgb_to_oklab(rgb)), rgb, atol=1e-9)


def test_white_lab():
    lab = linear_srgb_to_lab(np.ones((1, 3)))
    np.testing.assert_allclose(lab, [[100.0, 0.0, 0.0]], atol=1e-2)


def test_delta_e_2000_reference_pair():
    lab1 = np.array([[50.0000, 2.6772, -79.7751]])
    lab2 = np.array([[50.0000, 0.0000, -82.7485]])
    np.testing.assert_allclose(delta_e_2000(lab1, lab2), [2.0425], atol=1e-4)


def test_delta_e_2000_identity_and_symmetry():
    rng = np.random.default_rng(2)
    lab = rng.random((20, 3)) * np.array([100.0, 200.0, 200.0]) - np.array([0.0, 100.0, 100.0])
    np.testing.assert_allclose(delta_e_2000(lab, lab), np.zeros(20), atol=1e-12)
    other = rng.random((20, 3)) * 100.0
    np.testing.assert_allclose(delta_e_2000(lab, other), delta_e_2000(other, lab), rtol=1e-12)


def test_slog3_known_values():
    np.testing.assert_allclose(encode_slog3(np.array([0.18])), [420.0 / 1023.0], rtol=1e-9)
    np.testing.assert_allclose(encode_slog3(np.array([0.0])), [95.0 / 1023.0], rtol=1e-9)
    np.testing.assert_allclose(encode_slog3(np.array([0.9])), [598.0 / 1023.0], rtol=1e-3)
    np.testing.assert_allclose(decode_slog3(np.array([420.0 / 1023.0])), [0.18], rtol=1e-9)


def test_slog3_roundtrip():
    x = np.linspace(0.001, 1.0, 50)
    np.testing.assert_allclose(decode_slog3(encode_slog3(x)), x, rtol=1e-9)


def test_decode_input_profiles():
    pixels = np.array([[0.5, 0.25, 0.75]])
    np.testing.assert_allclose(decode_input(pixels, "rec709"), srgb_to_linear(pixels), rtol=1e-12)
    np.testing.assert_allclose(decode_input(pixels, "slog3"), decode_slog3(pixels), rtol=1e-12)


def test_apple_log_known_values():
    np.testing.assert_allclose(encode_apple_log(np.array([0.18])), [0.48827246], rtol=1e-6)
    np.testing.assert_allclose(decode_apple_log(np.array([0.48827246])), [0.18], rtol=1e-6)
    np.testing.assert_allclose(decode_apple_log(np.array([0.0])), [-0.05641088], rtol=1e-9)


def test_apple_log_roundtrip():
    x = np.linspace(-0.05, 1.0, 50)
    np.testing.assert_allclose(decode_apple_log(encode_apple_log(x)), x, rtol=1e-9)


def test_apple_log_below_r0_clamps():
    np.testing.assert_allclose(encode_apple_log(np.array([-0.1])), [0.0], atol=0.0)


def test_apple_log_primaries_to_rec709():
    np.testing.assert_allclose(rec2020_to_rec709_linear(np.ones((1, 3))), [[1.0, 1.0, 1.0]], atol=1e-9)
    np.testing.assert_allclose(rec2020_to_rec709_linear(np.zeros((1, 3))), [[0.0, 0.0, 0.0]], atol=1e-12)
    np.testing.assert_allclose(
        rec2020_to_rec709_linear(np.eye(3)),
        [[1.660491, -0.12455, -0.018151], [-0.587641, 1.1329, -0.100579], [-0.07285, -0.008349, 1.11873]],
        atol=1e-6,
    )


def test_decode_input_apple_log_bounded():
    codes = np.array([[0.48827246, 0.48827246, 0.48827246], [1.0, 1.0, 1.0], [-0.1, 0.0, 0.5]])
    out = decode_input(codes, "apple_log")
    assert out.min() >= 0.0 and out.max() <= 1.0
    np.testing.assert_allclose(out[0], [0.18, 0.18, 0.18], atol=1e-6)
    np.testing.assert_allclose(out[1], [1.0, 1.0, 1.0], atol=1e-12)
