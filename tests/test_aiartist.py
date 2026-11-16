"""Peças portadas do aseprite-ai-artist (MIT): tileset Godot 4/blob47, rampa e análise de paleta, guarda do loop de
correção e tween/oscilação de camada (dados sintéticos; o Aseprite é o falso em memória, sem websocket)."""
import asyncio

import numpy as np
import pytest
from PIL import Image

from aseprite_falso import AsepriteFalso
from horys_pixel import aiartist as AI
from horys_pixel import paleta_ops as PO
from horys_pixel import tileset as TS
from horys_pixel.ferramentas import aiartist as F  # noqa: F401  (registra as ferramentas)
from horys_pixel.ferramentas import registro
from horys_pixel.ferramentas.registro import ErroFerramenta


class Ctx:
    """Contexto mínimo: fala direto com o Aseprite falso."""

    def __init__(self, w=16, h=16):
        self.falso = AsepriteFalso(0, "")
        self.falso.tratar("sprite_novo", {"largura": w, "altura": h})

    async def aseprite(self, cmd, args=None, timeout=60.0):
        return self.falso.tratar(cmd, dict(args or {}))

    async def sprite_atual(self):
        return self.falso.status()

    @property
    def sprite(self):
        return self.falso.atual


def chamar(ctx, nome, **a):
    return asyncio.run(registro.REGISTRO[nome].funcao(ctx, a))


# ------------------------------------------------------------------ tileset

def test_blob47_tem_47_mascaras_reduzidas():
    ms = TS.blob47_mascaras()
    assert len(ms) == 47 and ms[0] == 0 and ms[-1] == 255
    assert all(TS.reduzir_mascara(m) == m for m in ms)
    assert TS.reduzir_mascara(TS.NE) == 0                       # canto sem lados não conta
    assert TS.reduzir_mascara(TS.N | TS.E | TS.NE) == TS.N | TS.E | TS.NE


def test_mascara_de_vizinhos():
    cheio = np.zeros((3, 3), bool)
    cheio[0, :] = True
    cheio[1, 1] = True
    assert TS.mascara_de_vizinhos(cheio, 1, 1) == TS.N             # NE e NW caem: falta E e W
    cheio[1, 2] = True
    assert TS.mascara_de_vizinhos(cheio, 1, 1) == TS.N | TS.NE | TS.E


def test_tres_blob47_com_terreno(tmp_path):
    guia = TS.guia_blob47(8, colunas=8)
    assert guia.shape == (6 * 8, 8 * 8, 4)
    Image.fromarray(guia).save(tmp_path / "grama.png")
    r = chamar(None, "horys_tileset", folha=str(tmp_path / "grama.png"), saida=str(tmp_path / "grama.tres"),
               tile=8, layout="blob47", res="res://tiles/grama.png")
    assert "47 tiles" in r[0]["text"]
    t = (tmp_path / "grama.tres").read_text(encoding="utf-8")
    assert t.startswith('[gd_resource type="TileSet" load_steps=3 format=3]')
    assert 'path="res://tiles/grama.png"' in t and "texture_region_size = Vector2i(8, 8)" in t
    assert t.count("/terrain_set = 0") == 47 and "terrain_set_0/mode = 0" in t
    # slot 0 = máscara 0 (nenhum vizinho); o último (46 -> 6:5) = 255 (os 8 bits)
    assert "0:0/0/terrains_peering_bit" not in t
    assert sum(1 for ln in t.splitlines() if ln.startswith("6:5/0/terrains_peering_bit/")) == 8
    # máscara 1 (só N) no slot 1
    assert "1:0/0/terrains_peering_bit/top_side = 0" in t
    assert sum(1 for ln in t.splitlines() if ln.startswith("1:0/0/terrains_peering_bit/")) == 1
    assert (tmp_path / "grama.json").is_file()


def test_tres_grid_pula_vazios_e_blob47_recusa_folha_curta():
    folha = np.zeros((16, 48, 4), np.uint8)
    folha[:, :16, 3] = 255
    folha[:, 32:, 3] = 255
    f = TS.fatiar(folha, 16, 16)
    assert (f.colunas, f.linhas, f.vazios) == (3, 1, [1])
    r = TS.godot_tres(f, "res://a.png")
    assert r.tiles == 2 and "0:0/0 = 0" in r.texto and "1:0/0 = 0" not in r.texto and "2:0/0 = 0" in r.texto
    with pytest.raises(ValueError):
        TS.godot_tres(f, "res://a.png", "blob47")


# ------------------------------------------------------------------ paleta

def test_rampa_gira_matiz_e_vai_do_escuro_ao_claro():
    r = PO.rampa("#c03030", passos=5)
    assert len(r) == 5
    lum = [PO.luminancia(c) for c in r]
    assert lum == sorted(lum)
    h0 = PO._rgb_hsl(*PO.pixels.hex_rgba(r[0])[:3])[0]
    h4 = PO._rgb_hsl(*PO.pixels.hex_rgba(r[-1])[:3])[0]
    assert 300 < h0 < 360          # sombra do vermelho gira para o azul (magenta), não para o laranja
    assert 0 < h4 < 60             # luz gira para o amarelo
    assert PO.girar_matiz_para(350, 240, 25) == 325
    with pytest.raises(ValueError):
        PO.rampa("#c03030", passos=1)


def test_analisar_acha_quase_iguais_rampa_e_fora_da_paleta():
    rampa = PO.rampa("#3060c0", 5)
    pal = rampa + ["#3061c0", "#e0e0e0"]
    img = np.zeros((4, 4, 4), np.uint8)
    img[0, :] = (*PO.pixels.hex_rgba(rampa[0])[:3], 255)
    img[1, :] = (*PO.pixels.hex_rgba(rampa[4])[:3], 255)
    img[2, 0] = (255, 0, 255, 255)
    r = PO.analisar(pal, img)
    assert r["n"] == 7 and rampa[2] == "#3060c0"
    assert any({d["a"], d["b"]} >= {"#3061c0"} for d in r["quase_iguais"])
    assert any(len(rp["cores"]) >= 3 and not rp["neutra"] for rp in r["rampas"])
    assert r["fora_da_paleta"] == [{"cor": "#ff00ff", "pixels": 1}]
    assert "#e0e0e0" in r["sem_uso"]
    assert r["contraste"]["razao_extremos"] > 3
    assert "quase iguais" in r["veredito"]


def test_analisar_avisa_rampa_sem_giro():
    plana = ["#203a80", "#3050a0", "#4a6ac0", "#6a8ae0"]      # mesma matiz, só brilho
    hs = [round(PO._rgb_hsl(*PO.pixels.hex_rgba(c)[:3])[0]) for c in plana]
    assert max(hs) - min(hs) <= 3
    r = PO.analisar(plana)
    assert any("sem giro" in a for a in r["avisos"])


def test_ferramentas_paleta_ao_vivo():
    ctx = Ctx(4, 4)
    out = chamar(ctx, "horys_paleta_rampa", base="#30a050", passos=3, adicionar=True)
    assert len(ctx.sprite.paleta) == 3 and out[1]["type"] == "image"
    ctx.sprite.img("desenho", 0)[:2] = (*PO.pixels.hex_rgba(ctx.sprite.paleta[1])[:3], 255)
    out = chamar(ctx, "horys_paleta_analisar")
    assert "Paleta: 3 cores" in out[0]["text"]


# ------------------------------------------------------------------ guarda do loop de correção

def _camada():
    a = np.zeros((10, 10, 4), np.uint8)
    a[2:8, 2:8] = (200, 50, 50, 255)    # 36 opacos
    return a


def test_guarda_aceita_fix_pequeno_e_recusa_redesenho():
    g = AI.GuardaCorrecao(_camada())

    def fix(x):
        x[2, 2] = (10, 10, 10, 255)
        return x

    def redesenho(x):
        x[2:6, 2:8] = (10, 10, 10, 255)  # 24/36 = 67%
        return x

    novo, r = AI.aplicar_com_guarda(g, fix)
    assert r.aceita and r.mudados == 1 and (novo[2, 2, :3] == 10).all()
    novo, r = AI.aplicar_com_guarda(g, redesenho)
    assert not r.aceita and "redesenho" in r.motivo and (novo[3, 3, :3] == (200, 50, 50)).all()
    # transparente com RGB diferente não conta como mudança
    t = g.foto.copy()
    t[0, 0] = (5, 5, 5, 0)
    assert AI.pixels_mudados(g.foto, t).sum() == 0


def test_guarda_para_em_3_rodadas():
    g = AI.GuardaCorrecao(_camada())
    for i in range(3):
        _, r = AI.aplicar_com_guarda(g, lambda x, i=i: (x.__setitem__((3, 3 + i), (0, 0, 0, 255)), x)[1])
        assert r.aceita
    assert g.esgotada
    _, r = AI.aplicar_com_guarda(g, lambda x: (x.__setitem__((5, 5), (0, 0, 0, 255)), x)[1])
    assert not r.aceita and "rodadas" in r.motivo


def test_ferramenta_guarda_desfaz_redesenho_no_aseprite():
    ctx = Ctx(10, 10)
    ctx.sprite.img("desenho", 0)[:] = _camada()
    out = chamar(ctx, "horys_guarda_correcao", acao="aplicar", camada="desenho", passos=[
        {"ferramenta": "horys_set_pixels", "args": {"camada": "desenho", "pixels": [[2, 2, "#0a0a0a"]]}}])
    assert "aceita" in out[0]["text"]
    assert tuple(ctx.sprite.img("desenho", 0)[2, 2]) == (10, 10, 10, 255)
    linhas = ["k" * 6] * 5
    out = chamar(ctx, "horys_guarda_correcao", acao="aplicar", camada="desenho", passos=[
        {"ferramenta": "horys_pixel_map", "args": {"camada": "desenho", "paleta": {"k": "#000000"},
                                                  "linhas": linhas, "x": 2, "y": 2}}])
    assert "restaurada" in out[0]["text"]
    im = ctx.sprite.img("desenho", 0)
    assert tuple(im[2, 2]) == (10, 10, 10, 255) and tuple(im[4, 4]) == (200, 50, 50, 255)
    assert "1/3" in chamar(ctx, "horys_guarda_correcao", acao="estado", camada="desenho")[0]["text"]
    with pytest.raises(ErroFerramenta):
        chamar(ctx, "horys_guarda_correcao", acao="conferir", camada="desenho", quadro=0, max_rodadas=0) \
            if False else chamar(ctx, "horys_guarda_correcao", acao="conferir", camada="outra")


# ------------------------------------------------------------------ movimento de célula

def test_deslocamentos():
    assert AI.deslocamentos_tween(5, 8, -4) == [(0, 0), (2, -1), (4, -2), (6, -3), (8, -4)]
    ease = AI.deslocamentos_tween(5, 8, 0, "ease_in")
    assert ease[0] == (0, 0) and ease[-1] == (8, 0) and ease[1][0] < 2
    osc = AI.deslocamentos_oscilar(4, 0, 2)
    assert osc == [(0, 0), (0, 2), (0, 0), (0, -2)]
    with pytest.raises(ValueError):
        AI.deslocamentos_tween(1, 1, 1)
    a = np.zeros((4, 4, 4), np.uint8)
    a[0, 0] = 255
    b = AI.deslocar(a, 3, 1)
    assert b[1, 3, 3] == 255 and b.sum() == 255 * 4
    assert AI.deslocar(a, 5, 0).sum() == 0


def test_ferramenta_cel_tween_e_oscilar():
    ctx = Ctx(12, 12)
    ctx.sprite.img("desenho", 0)[1, 1] = (255, 0, 0, 255)
    out = chamar(ctx, "horys_cel_tween", camada="desenho", de=0, ate=3, dx=6, dy=3)
    assert len(ctx.sprite.quadros) == 4 and "q3(+6,+3)" in out[0]["text"]
    for q, (x, y) in enumerate([(1, 1), (3, 2), (5, 3), (7, 4)]):
        im = ctx.sprite.img("desenho", q)
        assert im[y, x, 3] == 255 and int((im[..., 3] > 0).sum()) == 1, q
    ctx.sprite.img("desenho", 0)[:] = 0
    ctx.sprite.img("desenho", 0)[4, 4] = (255, 0, 0, 255)
    chamar(ctx, "horys_cel_tween", camada="desenho", de=0, ate=3, modo="oscilar", amp_y=2)
    ys = [int(np.argwhere(ctx.sprite.img("desenho", q)[..., 3] > 0)[0][0]) for q in range(4)]
    assert ys == [4, 6, 4, 2]
    with pytest.raises(ErroFerramenta):
        chamar(ctx, "horys_cel_tween", camada="desenho", de=2, ate=2)
