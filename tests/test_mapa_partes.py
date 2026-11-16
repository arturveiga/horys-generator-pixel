"""Mapa de partes (C2), animação por tabela e pedido ao Codex (C3), sem Aseprite e sem Codex."""
import numpy as np
from PIL import Image

from horys_pixel import mapa_partes as M
from horys_pixel import pedido_codex as PC


def _boneco():
    """Humanoide 1x de 14x24: cabeça 6x7 em cima, pescoço 2 px, tronco 8 px, braços soltos, duas pernas."""
    v = np.zeros((24, 14, 4), np.uint8)
    def r(x0, y0, x1, y1, c):
        v[y0:y1, x0:x1] = (*c, 255)
    r(4, 0, 10, 7, (200, 170, 150))     # cabeça
    r(6, 7, 8, 8, (200, 170, 150))      # pescoço
    r(3, 8, 11, 16, (40, 60, 160))      # tronco
    r(0, 8, 2, 15, (40, 60, 160))       # braço esq. (solto)
    r(12, 8, 14, 15, (40, 60, 160))     # braço dir. (solto)
    r(2, 8, 3, 10, (40, 60, 160))       # ombro liga braço esq
    r(11, 8, 12, 10, (40, 60, 160))     # ombro liga braço dir
    r(3, 16, 6, 24, (30, 30, 50))       # perna esq.
    r(8, 16, 11, 24, (30, 30, 50))      # perna dir.
    return v


def test_mapa_auto_separa_partes_e_fecha():
    v = _boneco()
    rot = M.mapa_auto(v)
    nomes = {M.NOMES[i - 1] for i in np.unique(rot) if i > 0}
    assert {"cabeca", "tronco", "perna-esq", "perna-dir", "braco-esq", "braco-dir"} <= nomes
    assert rot[2, 6] == M._id("cabeca")
    assert rot[20, 4] == M._id("perna-esq") and rot[20, 9] == M._id("perna-dir")
    assert rot[12, 0] == M._id("braco-esq")
    ch = M.checar(v, rot)
    assert ch.ok, ch.problemas


def test_checar_acha_pedaco_solto_e_buraco_de_cobertura():
    v = _boneco()
    rot = M.mapa_auto(v)
    rot[20, 4] = M._id("cabeca")            # pedaço de cabeça perdido na perna
    rot[12, 6] = 0                           # pixel da figura sem parte
    ch = M.checar(v, rot)
    assert not ch.ok
    txt = " ".join(ch.problemas)
    assert "cabeca: 2 pedaços" in txt and "sem parte" in txt


def test_rotulos_ida_e_volta():
    rot = M.mapa_auto(_boneco())
    assert (M.rotulos(M.pintar(rot)) == rot).all()


def test_animar_idle_preserva_pixels_e_fecha_emenda():
    v = _boneco()
    rot = M.mapa_auto(v)
    r = M.animar(v, rot, "idle", folga=False)
    assert len(r.quadros) == 4
    assert (r.quadros[0] == v).all()                       # quadro 0 = vista
    q1 = r.quadros[1]
    # cabeça desceu 1 px idêntica
    assert (q1[1:8, 4:10] == v[0:7, 4:10]).all()
    # pernas não mexem: sem vão entre tronco (desceu) e perna
    assert (q1[16:24, 3:6, 3] == 255).all()


def test_animar_andar_lado_nao_tapa_rastro_da_perna():
    v = _boneco()
    rot = M.mapa_auto(v)
    r = M.animar(v, rot, "andar-lado")
    q0 = r.quadros[0]
    assert q0.shape[:2] == (24 + 4, 14 + 4)                  # folga de 2 px (o maior deslocamento)
    # perna esq. (x 3..5) andou 2 px para a esquerda: x 1..3 na vista, +2 de folga; o rastro (x 5) é fundo
    assert (q0[2 + 22, 2 + 1:2 + 4, 3] == 255).all()
    assert q0[2 + 22, 2 + 5, 3] == 0


def test_pedido_vestir_amplia_base_sobre_chave(tmp_path):
    base = np.zeros((10, 8, 4), np.uint8)
    base[2:9, 2:6] = (10, 20, 30, 255)
    Image.fromarray(base).save(tmp_path / "base.png")
    p = PC.preparar(tmp_path / "ped", "vestir", imagem=str(tmp_path / "base.png"), ficha="a knight", escala=4,
                    paleta=["#141427", "#ffffff"])
    txt = p.prompt.read_text(encoding="utf-8")
    assert "THE ONLY CHANGE" in txt and "a knight" in txt and "#ff00ff" in txt
    an = np.asarray(Image.open(p.anexos[0]).convert("RGB"))
    assert an.shape == ((10 + 12) * 4, (8 + 12) * 4, 3)
    assert tuple(an[0, 0]) == (255, 0, 255)
    assert tuple(an[(6 + 3) * 4, (6 + 3) * 4]) == (10, 20, 30)


def test_pedido_master_exige_ficha_e_lista_vistas(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        PC.montar_prompt("master")
    t = PC.montar_prompt("master", ficha="robot", altura=48, paleta=["#000000"], extras=["sword"])
    assert "48 sprite pixels" in t and "front" in t and "back" in t and "sword" in t
