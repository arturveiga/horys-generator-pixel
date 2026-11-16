"""VFX pelo pixelfx: recolor por luminância, amostragem, tamanho (puros) e a chamada ao node (pulada sem node/pixelfx)."""
import asyncio
import json

import numpy as np
import pytest
from PIL import Image

from horys_pixel import vfx as V

RAMPA = ["#1a1c2c", "#5d275d", "#b13e53", "#ef7d57", "#ffcd75"]


def _quadro(cinzas, alfa=255):
    """Uma linha de pixels cinza com os valores dados."""
    q = np.zeros((1, len(cinzas), 4), np.uint8)
    q[0, :, :3] = np.array(cinzas)[:, None]
    q[0, :, 3] = alfa
    return q


def test_recolorir_mapeia_luminancia_na_rampa_e_so_usa_cores_dela():
    q = _quadro([0, 64, 128, 191, 255])
    o = V.recolorir([q], RAMPA)[0]
    esperado = [V.hex_rgb(c) for c in RAMPA]
    assert [tuple(int(v) for v in p[:3]) for p in o[0]] == esperado
    assert (o[..., 3] == 255).all()


def test_recolorir_normaliza_no_conjunto_de_quadros_e_corta_alfa():
    a = _quadro([100, 100])
    b = _quadro([200, 200])
    b[0, 1, 3] = 50                                  # abaixo do alfa mínimo: some
    oa, ob = V.recolorir([a, b], ["#000000", "#ffffff"], alfa_minimo=128)
    assert tuple(oa[0, 0, :3]) == (0, 0, 0)            # o mais escuro do conjunto
    assert tuple(ob[0, 0, :3]) == (255, 255, 255)      # o mais claro do conjunto
    assert ob[0, 1, 3] == 0 and tuple(ob[0, 1, :3]) == (0, 0, 0)


def test_recolorir_ignora_cor_dos_pixels_transparentes():
    q = _quadro([0, 255, 128])
    q[0, 0, 3] = 0                                    # o preto transparente não puxa a escala
    o = V.recolorir([q], ["#000000", "#808080", "#ffffff"])[0]
    assert tuple(o[0, 2, :3]) == (0, 0, 0) and tuple(o[0, 1, :3]) == (255, 255, 255)


def test_hex_curto_e_invalido():
    assert V.hex_rgb("#fa0") == (255, 170, 0)
    with pytest.raises(V.ErroVfx):
        V.hex_rgb("#xyz123")


def test_amostrar_mantem_duracao_total():
    qs = list(range(10))
    sel, durs = V.amostrar(qs, [33] * 10, 4)
    assert sel == [0, 2, 5, 7] and sum(durs) == 330 and durs == [66, 99, 66, 99]
    assert V.amostrar(qs, [33] * 10, None) == (qs, [33] * 10)
    assert V.amostrar(qs, [33] * 10, 50)[0] == qs


def test_ajustar_tamanho_centraliza_ou_reduz():
    q = np.zeros((40, 40, 4), np.uint8)
    q[10:14, 20:26] = (255, 0, 0, 255)                # caixa 6x4
    (o,), piv, esc = V.ajustar_tamanho([q], 16, (23, 14))
    assert o.shape == (16, 16, 4) and esc == 1.0
    assert (o[..., 3] > 0).sum() == 24 and piv == (8, 10)
    q2 = np.zeros((40, 40, 4), np.uint8)
    q2[0:40, 0:20] = (0, 255, 0, 255)                 # caixa 20x40 num quadrado de 10
    (o2,), _, esc2 = V.ajustar_tamanho([q2], 10, (0, 0))
    assert esc2 == 0.25 and (o2[..., 3] > 0).sum() == 5 * 10


def test_ler_lista_da_saida_do_list_mjs():
    saida = ("fire/campfire                  loop 3s     128x128         Crossed logs on a bed of coals.\n"
             "holy/heal                      once 1.9s   80x104   actor  Petals of light bloom.\n\n244 effects\n")
    e = V.ler_lista(saida)
    assert [x["id"] for x in e] == ["fire/campfire", "holy/heal"]
    assert e[0]["loop"] and e[0]["tamanho"] == [128, 128] and not e[0]["com_boneco"]
    assert not e[1]["loop"] and e[1]["duracao_s"] == 1.9 and e[1]["com_boneco"]


def test_efeito_invalido_nao_chama_o_node():
    with pytest.raises(V.ErroVfx):
        V.renderizar("fire/*")


tem_pixelfx = pytest.mark.skipif(not (V.achar_node() and V.achar_pixelfx()), reason="sem node ou pixelfx")


@tem_pixelfx
def test_listar_pelo_pixelfx():
    efeitos = V.listar()
    assert len(efeitos) > 100
    assert any(e["id"] == "fire/campfire" for e in efeitos)
    assert all("fire" in e["id"] or "fire" in e["descricao"].lower() for e in V.listar("fire"))


@tem_pixelfx
def test_gerar_pela_ferramenta(tmp_path):
    from horys_pixel.ferramentas import registro, vfx as _  # noqa: F401  (registra as ferramentas)
    r = asyncio.run(registro.REGISTRO["horys_vfx_gerar"].funcao(None, {
        "efeito": "fire/campfire", "rampa": RAMPA, "saida": str(tmp_path), "quadros": 8, "tamanho": 64, "seed": 1}))
    assert r[1]["type"] == "image"
    tira = np.array(Image.open(tmp_path / "fire_campfire.png"))
    assert tira.shape == (64, 64 * 8, 4)
    vis = tira[..., 3] > 0
    assert vis.sum() > 200 and set(np.unique(tira[..., 3])) <= {0, 255}
    cores = {tuple(int(v) for v in c) for c in tira[vis][:, :3]}
    assert cores <= {V.hex_rgb(c) for c in RAMPA} and len(cores) >= 3
    d = json.loads((tmp_path / "fire_campfire.json").read_text(encoding="utf-8"))
    assert len(d["frames"]) == 8 and sum(f["duration"] for f in d["frames"]) == pytest.approx(3000, abs=40)
    assert "MIT" in d["meta"]["horys"]["credito"] and d["meta"]["horys"]["quadros_vazios"] == 0
