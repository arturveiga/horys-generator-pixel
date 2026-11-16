"""Smoke das boas práticas (horys_pixel.boas_praticas) com sprites sintéticos."""
import json

import numpy as np
from PIL import Image

from horys_pixel import boas_praticas as BP

CONT = (40, 30, 60)
TONS = [(200, 150, 90), (160, 110, 70), (120, 80, 60)]   # luz, base, sombra


def sprite(w=32, h=40, dy=0):
    """Blob oval de 20×28 com 3 tons em faixas (luz em cima à esquerda) e contorno de 1 px."""
    f = np.zeros((h, w, 4), np.uint8)
    yy, xx = np.mgrid[0:h, 0:w]
    cy, cx = 20 + dy, 16
    dentro = ((yy - cy) / 14.0) ** 2 + ((xx - cx) / 10.0) ** 2 <= 1.0
    d = (yy - cy) + (xx - cx)
    for i, t in enumerate(TONS):
        m = dentro & (d >= -30 + 14 * i) if i else dentro
        f[m] = (*t, 255)
    borda = np.zeros_like(dentro)
    for dy_, dx_ in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        borda |= np.roll(np.roll(dentro, dy_, 0), dx_, 1)
    f[borda & ~dentro] = (*CONT, 255)
    return f


def por_id(res):
    return {r["id"]: r for r in res}


def test_regras_carregam_e_doc_tem_todas():
    rs = BP.regras()
    assert len(rs) >= 40 and all(r["severidade"] in ("grave", "leve") for r in rs.values())
    assert "BP26" in BP.automaticas() and "BP01" not in BP.automaticas()


def test_sprite_limpo_passa_nas_graves():
    r = por_id(BP.checar_quadro(sprite(), {"contorno": "#281e3c"}))
    for i in ("BP04", "BP07", "BP08", "BP12", "BP15", "BP24", "BP25"):
        assert r[i]["passa"] is True, (i, r[i])


def test_pixel_orfao():
    f = sprite()
    f[20, 12] = (161, 111, 71, 255)    # quase igual ao vizinho: ruído de baixo contraste
    f[2, 2] = (*TONS[1], 255)          # pixel solto fora do corpo
    r = por_id(BP.checar_quadro(f, {"contorno": "#281e3c", "limites": {"BP25": 0}}))
    assert r["BP24"]["passa"] is False and [2, 2] in r["BP24"]["onde"]
    assert [12, 20] in r["BP25"]["onde"]


def test_contorno_duplo():
    f = sprite()
    op = f[..., 3] == 255
    from horys_pixel.motor.medir import aneis
    _r1, r2 = aneis(op, 2)
    f[r2] = (*CONT, 255)
    r = por_id(BP.checar_quadro(f, {"contorno": "#281e3c"}))
    assert r["BP08"]["passa"] is False and r["BP08"]["medida"] > 0.9


def test_detalhe_de_1px_e_protegida():
    f = sprite()
    f[14, 15] = (250, 250, 250, 255)   # brilho de 1 px
    f[24, 18] = (90, 200, 220, 255)    # outro detalhe de 1 px
    base = por_id(BP.checar_quadro(sprite(), {"contorno": "#281e3c"}))["BP26"]["medida"]
    r = por_id(BP.checar_quadro(f, {"contorno": "#281e3c", "limites": {"BP26": 0}}))
    assert r["BP26"]["medida"] == base + 2 and [15, 14] in r["BP26"]["onde"]
    r = por_id(BP.checar_quadro(f, {"contorno": "#281e3c", "limites": {"BP26": 0},
                                    "protegidas": ["#fafafa", "#5ac8dc"]}))
    assert r["BP26"]["medida"] == base


def test_mais_de_20_cores():
    f = sprite()
    ys, xs = np.nonzero(f[..., 3] == 255)
    for k in range(30):
        f[ys[k * 7], xs[k * 7]] = (k * 8, 255 - k * 8, 100, 255)
    r = por_id(BP.checar_quadro(f))
    assert r["BP12"]["passa"] is False and r["BP12"]["medida"] > 20


def test_linha_dos_pes_pulando_e_overlay(tmp_path):
    qs = [sprite(dy=d) for d in (0, -1, -3, -1)]
    r = por_id(BP.checar_animacao(qs, {"acao": "idle"}))
    assert r["BP32"]["passa"] is False and r["BP32"]["medida"] == 3
    assert any(o[2] == 2 for o in r["BP32"]["onde"])
    pasta = tmp_path / "idle"
    pasta.mkdir()
    for i, q in enumerate(qs):
        Image.fromarray(q).save(pasta / f"q{i}.png")
    rel = BP.checar_caminho(pasta, {"acao": "idle"}, saida=tmp_path)
    assert "BP32" in rel["graves"] and (tmp_path / "idle_praticas.png").is_file()
    assert json.loads((tmp_path / "idle_praticas.json").read_text(encoding="utf-8"))["aprovado"] is False
    im = BP.overlay(qs[0], BP.checar_quadro(qs[0]))
    assert im.width >= 32 * 8


def test_render3d_bp40_so_informa():
    qs = [sprite(dy=d) for d in (0, 0, 0, 0)]
    qs[1][10:14, 12:20] = (*TONS[0], 255)
    qs[3][26:30, 12:20] = (*TONS[2], 255)
    r = por_id(BP.checar_animacao(qs, {"acao": "andar", "render3d": True}))
    assert r["BP40"]["passa"] is None and r["BP41"]["passa"] is None
