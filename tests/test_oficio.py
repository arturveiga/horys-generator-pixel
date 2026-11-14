import asyncio

import numpy as np

from horys_pixel import oficio, pixels
from horys_pixel.ferramentas import registro


def test_base_completa():
    assert len(oficio.regras()) == 62
    assert len(oficio.modelos()) >= 400
    assert len(oficio._paletas()) >= 2000


def test_todo_modelo_e_valido_para_pixel_map():
    for m in oficio.modelos().values():
        assert m.legenda, m.nome
        letras = set("".join(m.linhas)) - {"."}
        assert letras <= set(m.legenda), (m.nome, letras - set(m.legenda))
        pixels.compor_mapa(m.paleta(), m.linhas)


def test_modelo_troca_cor_por_papel():
    m = oficio.achar_modelo("hands-16-front")
    pal = m.paleta({"skin-light": "#ffffff"})
    letra = next(k for k, (papel, _) in m.legenda.items() if papel == "skin-light")
    assert pal[letra] == "#ffffff"


def test_regra_secao_e_busca():
    assert "Mistakes" in oficio.ler_regra("34", "mistakes")
    assert oficio.buscar("hand 32")
    assert oficio.paleta("pico8")[1]["size"] == 16


def test_ferramenta_registrada():
    registro.carregar_todas()
    f = registro.REGISTRO["horys_oficio"].funcao
    out = asyncio.run(f(None, {"acao": "modelo", "nome": "hands-16-front"}))
    assert out[0]["type"] == "image"


def test_trava_de_paleta():
    nova, mov = pixels.travar_paleta({"a": "#fe0000", "b": "#00000000", "c": "#123456"}, ["#ff0000", "#000000"])
    assert nova["a"] == "#ff0000" and nova["b"] == "#00000000"
    assert any(k == "c" and dE > 12 for k, _, _, dE in mov)


def test_diff_onion_filmstrip():
    a = np.zeros((4, 4, 4), np.uint8)
    b = a.copy()
    b[1, 1] = (255, 0, 0, 255)
    txt, pal, n = pixels.diff_texto(a, b)
    assert n == 1 and txt.splitlines()[1][1] != "."
    txt2, _, _ = pixels.diff_texto(b, a)
    assert txt2.splitlines()[1][1] == "-"
    assert pixels.onion(b, [a]).shape == b.shape
    assert pixels.filmstrip([a, b]).width > 0
    assert pixels.lado_a_lado([a, b]).width > 0
