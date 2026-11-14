import numpy as np
import pytest
from PIL import Image

from horys_pixel import referencia as R


def test_angulo_obrigatorio_e_apelidos():
    with pytest.raises(ValueError):
        R.normalizar_angulo("")
    with pytest.raises(ValueError):
        R.normalizar_angulo("de qualquer jeito")
    assert R.normalizar_angulo("pixel top") == "top-down"
    assert R.normalizar_angulo("Top Down 3/4") == "3/4 top-down"
    assert R.normalizar_angulo("isométrico") == "isometrico"


def test_pixel_art_ampliada_passa(tmp_path):
    rng = np.random.default_rng(1)
    nat = rng.choice([0, 80, 160, 240], size=(24, 24, 3)).astype(np.uint8)
    img = np.repeat(np.repeat(nat, 8, 0), 8, 1)
    p = tmp_path / "px.png"
    Image.fromarray(img).save(p)
    r = R.checar_pixel_art(p)
    assert r["ok"] and r["escala"] == 8


def test_ilustracao_lisa_e_recusada(tmp_path):
    y, x = np.mgrid[0:400, 0:400]
    img = np.stack([x * 255 // 399, y * 255 // 399, (x + y) * 255 // 798], -1).astype(np.uint8)
    p = tmp_path / "liso.png"
    Image.fromarray(img).save(p)
    assert not R.checar_pixel_art(p)["ok"]
