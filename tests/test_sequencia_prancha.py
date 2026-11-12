"""Prancha por componentes, franja de fundo, snapper opcional e auto-ajuste ranqueado."""
import numpy as np
import pytest
from PIL import Image

from horys_pixel import sequencia as S
from horys_pixel.sequencia import entradas, fundo, snapper

VERDE = (0, 255, 0)


def _prancha():
    """2 linhas: em cima 3 poses de alturas diferentes, embaixo 2; uma pose tem uma 'arma' solta a 3 px."""
    im = np.zeros((200, 300, 4), np.uint8)
    im[..., :3] = VERDE
    im[..., 3] = 255
    cor = (180, 60, 50)
    im[20:80, 20:40, :3] = cor      # linha 1, pose A (alta)
    im[40:80, 120:140, :3] = cor    # pose B (baixa, mesma linha)
    im[30:80, 220:240, :3] = cor    # pose C
    im[30:40, 243:250, :3] = cor    # arma solta da C, 3 px de vão
    im[120:180, 60:80, :3] = cor    # linha 2
    im[130:180, 180:200, :3] = cor
    return im


def test_prancha_acha_poses_em_ordem_de_leitura(tmp_path):
    im = _prancha()
    caixas = entradas.achar_poses(im, juntar=4)
    assert len(caixas) == 5, caixas
    xs = [c[0] for c in caixas]
    assert xs[:3] == sorted(xs[:3]) and xs[3:] == sorted(xs[3:])
    assert caixas[2][0] + caixas[2][2] >= 250  # a arma ficou junto da pose C
    Image.fromarray(im, "RGBA").save(tmp_path / "p.png")
    qs = entradas.carregar(tmp_path / "p.png", prancha=True)
    assert len(qs) == 5 and all(q[..., 3].min() == 255 for q in qs)


def test_prancha_vazia_explica():
    im = np.zeros((50, 50, 4), np.uint8)
    im[..., 1] = 255
    im[..., 3] = 255
    with pytest.raises(entradas.ErroEntrada):
        entradas.achar_poses(im)


def test_franja_tira_anel_escuro_e_preserva_verde_no_corpo():
    q = np.zeros((40, 40, 4), np.uint8)
    q[..., :3] = VERDE
    q[..., 3] = 255
    q[10:30, 10:30, :3] = (180, 60, 50)
    q[9, 10:30, :3] = (20, 225, 20)     # anel quase-verde colado no contorno
    q[18:22, 18:22, :3] = (40, 160, 40)  # verde de verdade no meio do corpo
    sem = fundo.tirar_fundo([q], franja=False)[0]
    com = fundo.tirar_fundo([q], franja=True)[0]
    assert sem[9, 15, 3] == 255 and com[9, 15, 3] == 0
    assert com[20, 20, 3] == 255 and com[15, 15, 3] == 255


def test_snapper_ausente_explica(monkeypatch):
    monkeypatch.delenv("HORYS_SNAPPER", raising=False)
    monkeypatch.setattr(snapper.shutil, "which", lambda _n: None)
    assert not snapper.disponivel()
    with pytest.raises(snapper.ErroSnapper, match="PATH"):
        snapper.recuperar("x.png", "y.png")
    assert snapper.pixel_detectado("Detected\nPixel size: 6.25 px\n") == 6.25


def _fig(h, x, y, W=200, H=200):
    q = np.zeros((H, W, 4), np.uint8)
    w = max(2, h // 3)
    q[y - h + 1:y + 1, x - w // 2:x + w // 2 + 1] = (200, 80, 60, 255)
    return q


def test_autoajuste_descarta_quem_nao_cabe_e_ranqueia_pela_altura():
    qs = [_fig(100, 80, 150) for _ in range(3)]
    r = S.autoajustar(qs, ["#c8503c", "#202020"], [90, 60, 40], (64, 64), (32, 60), altura_neutra=40,
                      fator=2, limpar_min=1, regularizar=False)
    alts = [c["altura_alvo"] for c in r["candidatos"]]
    assert 90 not in alts and any(d["altura_alvo"] == 90 for d in r["descartados"])
    assert alts[0] == 40


def test_buraco_verde_preso_sai_e_fundo_escuro_nao_mexe():
    q = np.zeros((40, 40, 4), np.uint8)
    q[..., :3] = VERDE
    q[..., 3] = 255
    q[8:32, 8:32, :3] = (20, 20, 30)    # contorno escuro
    q[10:30, 10:30, :3] = (180, 60, 50)
    q[16:24, 16:24, :3] = VERDE         # fundo preso entre braço e corpo
    com = fundo.tirar_fundo([q])[0]
    assert com[20, 20, 3] == 0 and com[8, 20, 3] == 255
    e = q.copy()
    e[(e[..., :3] == VERDE).all(-1), :3] = (30, 22, 45)  # mesmo desenho em fundo roxo-escuro
    assert np.array_equal(fundo.tirar_fundo([e])[0], fundo.tirar_fundo([e], franja=False)[0])
