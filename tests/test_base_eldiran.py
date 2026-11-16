"""Corpo-base Eldiran: fatiar a folha, mapas de partes e animar uma pele (smoke)."""
from __future__ import annotations

import json

import numpy as np
import pytest
from PIL import Image

from horys_pixel import base_eldiran as B
from horys_pixel import mapa_partes as M

K, W, P = (0, 0, 0, 255), (255, 255, 255, 255), (255, 0, 255, 255)


def _boneco(desloc_perna: int = 0, lado: bool = False) -> np.ndarray:
    """Boneco 32x32 de contorno preto e enchimento branco: cabeça, tronco, braços soltos, duas pernas."""
    c = np.zeros((32, 32, 4), np.uint8)
    c[...] = P

    def caixa(x0, y0, x1, y1):
        c[y0:y1, x0:x1] = K
        c[y0 + 1:y1 - 1, x0 + 1:x1 - 1] = W
    if lado:
        caixa(10, 1, 22, 13)
        caixa(11, 12, 21, 24)
        caixa(10 + desloc_perna, 23, 15 + desloc_perna, 32)
        caixa(16, 23, 21, 32)
        return c
    caixa(10, 1, 22, 13)
    caixa(9, 12, 23, 25)
    caixa(5, 14, 10, 23)
    caixa(22, 14, 27, 23)
    caixa(10, 24 - desloc_perna, 15, 32 - desloc_perna)
    caixa(17, 24, 22, 32)
    return c


def _folha(tmp_path):
    f = np.zeros((32 * 2, 32 * 12, 4), np.uint8)
    f[...] = P
    for col in range(12):
        lado = col >= 8
        if 4 <= col < 8:
            continue                       # como na Eldiran: a linha nua não tem costas
        f[:32, col * 32:(col + 1) * 32] = _boneco(col % 2, lado)
    p = tmp_path / "folha.png"
    Image.fromarray(f).save(p)
    return p


def test_extrair_e_animar_sintetico(tmp_path):
    info = B.extrair(tmp_path / "base", _folha(tmp_path))
    out = tmp_path / "base"
    assert (out / "base.png").is_file() and (out / "base.json").is_file()
    base = np.array(Image.open(out / "base.png"))
    assert base.shape == (40, 120, 4)
    nomes = [q["nome"] for q in info["quadros"]]
    assert len(nomes) == 15 and "andar_n_03" in nomes and "idle_e_00" in nomes
    assert info["derivados"] and info["licenca"] == "CC0"
    chao = None
    for n in nomes:
        q = np.array(Image.open(out / "quadros" / f"{n}.png"))
        assert q.shape == (40, 40, 4)
        assert (out / "partes" / f"{n}.png").is_file()
        pe = int(np.nonzero(q[..., 3])[0].max())
        chao = pe if chao is None else chao
        assert pe == chao
    js = json.loads((out / "base.json").read_text(encoding="utf-8"))
    assert [v["x"] for v in js["vistas"]] == [0, 40, 80]

    # pele: tronco recolorido de vermelho em base.png
    rot = np.concatenate([M.rotulos(np.array(Image.open(out / "partes" / f"idle_{d}_00.png").convert("RGBA")))
                          for d in "sne"], 1)
    pele = np.zeros_like(base)
    sel = (rot == M._id("tronco")) & (base[..., :3].sum(-1) > 600)
    pele[sel] = (200, 30, 30, 255)
    Image.fromarray(pele).save(tmp_path / "pele.png")
    r = B.animar_pele(out, tmp_path / "pele.png", tmp_path / "anim")
    assert set(r["folhas"]) == {f"{a}_{d}" for a in ("idle", "andar") for d in "snew"}
    tira = np.array(Image.open(r["folhas"]["andar_s"]["png"]).convert("RGBA"))
    assert tira.shape == (40, 160, 4)
    assert ((tira[..., :3] == (200, 30, 30)).all(-1)).sum() > 4 * 50


REAL = B.FOLHA_PADRAO


@pytest.mark.skipif(not REAL.is_file(), reason="folha Eldiran ausente")
def test_extrair_real(tmp_path):
    info = B.extrair(tmp_path / "eldiran")
    assert info["canvas"] == [40, 40] and len(info["quadros"]) == 15
    assert not info["partes_falhas"], info["partes_falhas"]
