from pathlib import Path

import numpy as np
import pytest
from PIL import Image

AQUI = Path(__file__).parent


@pytest.fixture
def boneco() -> np.ndarray:
    """Pixel art 1x de verdade (3 vistas: frente, lado, costas), fundo transparente."""
    return np.asarray(Image.open(AQUI / "boneco_ref.png").convert("RGBA")).copy()


def ampliar_irregular(rgba: np.ndarray, bloco=(11, 15), borrar=True, semente=0, chave=(255, 0, 255),
                      margem=40) -> np.ndarray:
    """Imita o gerador de imagem: cada pixel vira um bloco de tamanho VARIÁVEL, borda suavizada e ruído leve, sobre
    fundo magenta. Devolve RGB."""
    rng = np.random.default_rng(semente)
    h, w = rgba.shape[:2]
    larg = rng.integers(bloco[0], bloco[1] + 1, w)
    alt = rng.integers(bloco[0], bloco[1] + 1, h)
    xs = np.repeat(np.arange(w), larg)
    ys = np.repeat(np.arange(h), alt)
    big = rgba[ys][:, xs].astype(np.float64)
    a = big[..., 3:4] / 255.0
    rgb = big[..., :3] * a + np.array(chave, np.float64) * (1 - a)
    rgb = np.pad(rgb, ((margem, margem), (margem, margem), (0, 0)), constant_values=0)
    rgb[:margem], rgb[-margem:], rgb[:, :margem], rgb[:, -margem:] = chave, chave, chave, chave
    if borrar:
        from scipy import ndimage
        rgb = ndimage.uniform_filter(rgb, size=(3, 3, 1))
        rgb += rng.normal(0, 2.0, rgb.shape)
    return np.clip(np.rint(rgb), 0, 255).astype(np.uint8)
