"""Colagem guiada: peças do mestre coladas exatas nos quadros-guia."""
import numpy as np

from horys_pixel.sequencia import colagem

PAL = ["#201828", "#c06850", "#f0d8b0", "#607850"]


def _boneco(dy=0, perna=0):
    """Boneco 20x30: cabeça (linhas 0-11), tronco, pernas que mudam."""
    q = np.zeros((30, 20, 4), np.uint8)
    q[0 + dy:12 + dy, 4:16] = [192, 104, 80, 255]
    q[4 + dy:8 + dy, 7:9] = [32, 24, 40, 255]
    q[12 + dy:22 + dy, 5:15] = [240, 216, 176, 255]
    q[22:30, 5 + perna:9 + perna] = [96, 120, 80, 255]
    q[22:30, 11 - perna:15 - perna] = [96, 120, 80, 255]
    return q


def test_montar_cola_cabeca_exata_e_segue_o_quique():
    mestre = _boneco()
    guias = []
    for k, (dy, perna) in enumerate([(0, 0), (1, 1), (0, 0), (1, -1)]):
        g = _boneco(dy, perna)
        g[2 + dy, 5 + k] = [240, 216, 176, 255]          # ruído do gerador na cabeça
        guias.append(g)
    r = colagem.montar(mestre, guias, [{"nome": "cabeca", "rect": [0, 0, 20, 12], "apagar": "faixa"}], raio=3)
    assert [x["dy"] for x in r["relatorio"]] == [0, 1, 0, 1]
    assert r["estabilidade"]["cabeca"] == [0, 0, 0, 0]
    assert all(x["colou"] for x in r["relatorio"])


def test_apagar_invalido():
    m = _boneco()
    try:
        colagem.montar(m, [m], [{"nome": "x", "rect": [0, 0, 20, 12], "apagar": "tudo"}])
    except ValueError:
        return
    raise AssertionError


def test_guias_na_escala_altura_do_mais_alto():
    a = np.zeros((300, 200, 4), np.uint8); a[:, 50:150] = [192, 104, 80, 255]
    b = np.zeros((300, 200, 4), np.uint8); b[30:, 50:150] = [192, 104, 80, 255]
    g = colagem.guias_na_escala([a, b], 30, PAL, cor_fundo="nenhum")
    assert g[0].shape[0] == 30 and g[1].shape[0] == 27
