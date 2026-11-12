"""Grade nativa: pixel quadrado e fase pelo Sobel numa grade rígida (portado do Pixelate)."""
import numpy as np

from horys_pixel.motor import conceito as C


def _pseudo(passo=13.5, fase=5.0, w=60, h=64, seed=3):
    rng = np.random.default_rng(seed)
    cores = np.array([[30, 25, 40], [200, 110, 90], [240, 220, 190], [90, 120, 90]])
    arte = cores[rng.integers(0, 4, (h, w))]
    W, H = int(w * passo + fase), int(h * passo + fase)
    xi = np.clip(((np.arange(W) - fase) // passo).astype(int), 0, w - 1)
    yi = np.clip(((np.arange(H) - fase) // passo).astype(int), 0, h - 1)
    img = arte[yi][:, xi] + rng.integers(-6, 7, (H, W, 3))
    return np.clip(img, 0, 255).astype(np.uint8), arte


def test_fase_sobel_acha_a_fase():
    img, _ = _pseudo()
    sx, _ = C._sobel_eixos(img)
    f = C.fase_sobel(sx, 13.5)
    assert min(abs(f - 5.0), abs(f - 5.0 - 13.5)) <= 1.0


def test_grade_nativa_quadrada_e_recupera_arte():
    img, arte = _pseudo()
    gx, gy = C.grade_nativa(img)
    assert abs(gx[1] - gy[1]) < 1e-9 and abs(gx[1] - 13.5) < 0.2
    peq = C.amostrar_nativo(img, gx, gy)
    alvo = arte[:peq.shape[0], :peq.shape[1]]
    ok = (np.abs(peq[:alvo.shape[0], :alvo.shape[1]] - alvo).sum(-1) < 40).mean()
    assert ok > 0.97


def test_fase_invalida():
    img, _ = _pseudo(w=20, h=20)
    try:
        C.grade_nativa(img, fase="x")
    except ValueError:
        return
    raise AssertionError
