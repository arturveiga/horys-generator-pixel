import json

import numpy as np
import pytest

from horys_pixel import anticintilacao as A
from horys_pixel import aprovacao as AP
from horys_pixel import asset as AS
from horys_pixel import cor as C
from horys_pixel import gabarito as G
from horys_pixel import jogo as J
from horys_pixel import paleta as P
from horys_pixel import portoes as PT
from horys_pixel import pos
from horys_pixel import prompt as PR


# ------------------------------------------------------------------ cor e paleta

def test_hex_ida_e_volta():
    assert C.rgb_hex(C.hex_rgb("#1A2b3C")) == "#1a2b3c"
    with pytest.raises(ValueError):
        C.hex_rgb("#123")


def test_rampa_vai_do_escuro_ao_claro_e_mantem_a_base():
    r = P.rampa_material("#4a7bd1", 3)
    assert r[1] == "#4a7bd1"
    lum = [C.luminancia(h) for h in r]
    assert lum == sorted(lum)


def test_montar_paleta_com_tinta_e_avisos():
    pal = P.montar([{"nome": "pele", "base": "#d9a066"}, {"nome": "roupa", "base": "#3b6ea8", "tons": 2}])
    assert len(pal["familias"]["pele"]["rampa"]) == 3 and len(pal["familias"]["roupa"]["rampa"]) == 2
    assert pal["tinta"] in pal["cores"]
    assert P.familia_mais_proxima(pal, pal["familias"]["roupa"]["rampa"][0]) == "roupa"


def test_propor_paleta_ignora_fundo():
    im = np.zeros((40, 40, 4), np.uint8)
    im[10:30, 10:30] = (200, 50, 50, 255)
    im[10:30, 10:12] = (20, 20, 20, 255)
    fams = P.propor(im, 3)
    assert any(f["base"] == "#c83232" for f in fams)


# ------------------------------------------------------------------ contrato e asset

def test_jogo_padrao_e_mescla(tmp_path):
    (tmp_path / "jogo.json").write_text(json.dumps({"angulo": 35, "portoes": {"pisca_max": 0.05}}), encoding="utf-8")
    j = J.carregar(tmp_path)
    assert j["angulo"] == 35 and j["portoes"]["pisca_max"] == 0.05 and "gabarito" in j["portoes"]
    assert J.checar_asset({"camera": {}, "rig": {}}) == ["camera"]


def test_jogo_recusa_vista_sem_direcao(tmp_path):
    (tmp_path / "jogo.json").write_text(json.dumps({"direcoes": {"sul": 0}}), encoding="utf-8")
    with pytest.raises(ValueError, match="vista"):
        J.carregar(tmp_path)


def test_asset_novo_abrir_e_prompt(tmp_path):
    (tmp_path / "assets").mkdir()
    a = AS.novo("goblin", tmp_path, descricao="goblin verde com lança", altura_px=36)
    assert AS.listar(tmp_path) == ["goblin"]
    b = AS.abrir("goblin", tmp_path)
    assert b.alvo_px(J.carregar(tmp_path)) == 36
    txt = PR.gerar(b, J.carregar(tmp_path))
    assert "exatamente 36 pixels" in txt and "#FF00FF" in txt and "goblin verde" in txt
    with pytest.raises(FileExistsError):
        AS.novo("goblin", tmp_path)


# ------------------------------------------------------------------ aprovação

def test_aprovacao_presa_ao_conteudo(tmp_path):
    (tmp_path / "paleta.json").write_text("{}", encoding="utf-8")
    with pytest.raises(AP.Travado, match="falta aprovar"):
        AP.exigir(tmp_path, "paleta")
    AP.aprovar(tmp_path, "paleta", "paleta.json", comentario="sim")
    AP.exigir(tmp_path, "paleta")
    (tmp_path / "paleta.json").write_text('{"x": 1}', encoding="utf-8")
    with pytest.raises(AP.Travado, match="mudou"):
        AP.exigir(tmp_path, "paleta")


# ------------------------------------------------------------------ gabarito

PAL = P.montar([{"nome": "pele", "base": "#d9a066"}, {"nome": "roupa", "base": "#3b6ea8"}], tinta="#1a1420")


def _boneco(larg=8, alt=16, cor=(217, 160, 102)):
    im = np.zeros((alt, larg, 4), np.uint8)
    im[...] = cor + (255,)
    return im


def test_gabarito_identico_passa():
    a = _boneco()
    r = G.avaliar({"frente": a}, {"frente": a.copy()}, PAL, J.PADRAO["portoes"]["gabarito"])
    assert r["ok"] and r["vistas"]["frente"]["iou"] == 1.0 and r["vistas"]["frente"]["familia"] == 1.0


def test_gabarito_pega_altura_e_forma_erradas():
    r = G.avaliar({"frente": _boneco(alt=16)}, {"frente": _boneco(larg=14, alt=12)}, PAL,
                  J.PADRAO["portoes"]["gabarito"])
    assert not r["ok"]
    assert any("silhueta" in f for f in r["falhas"]) and any("render tem 12 px" in f for f in r["falhas"])


def test_gabarito_lado_espelhado():
    a = _boneco(larg=10)
    a[:, :3] = (59, 110, 168, 255)
    r = G.comparar_vista(a, a[:, ::-1].copy(), PAL, testar_espelho=True)
    assert r["espelhado"] and r["familia"] == 1.0


# ------------------------------------------------------------------ pós e portões

def test_contorno_fora_e_soltos():
    idx = np.full((7, 7), -1)
    idx[1:6, 1:6] = 0
    idx[3, 3] = 1
    out, n = pos.limpar_soltos(idx, ["a", "a"], set(), tinta=2)
    assert n == 1 and out[3, 3] == 0
    c = pos.contorno(out, 2, "fora")
    assert c[0, 3] == 2 and c[3, 3] == 0


def test_anticintilacao_corta_pisca():
    base = np.zeros((6, 6), int)
    q = [base.copy(), base.copy(), base.copy(), base.copy()]
    q[1][2, 2] = 1
    q[3][4, 4] = 1
    assert A.pisca(q) > 0
    assert A.pisca(A.aplicar(q)) == 0


def test_detalhe_fino_acha_peca_de_1px():
    m = np.zeros((10, 10, 4), np.uint8)
    m[2:8, 2:8] = (255, 140, 0, 255)       # tronco grosso
    m[1:9, 9] = (0, 200, 0, 255)           # braço de 1 px
    assert pos.detalhe_fino(m, {"tronco": "#ff8c00", "braco-esq": "#00c800"}) == ["braco-esq"]


def _estado(tipo, **kw):
    e = {"acao": tipo, "tipo": tipo, "direcao": "sul", "quadros": 8, "pisca": 0.0, "mudanca_media": 0.2,
         "pe_linha": [50, 50], "altura_px": [40, 40]}
    e.update(kw)
    return e


def test_portoes():
    j = J.PADRAO
    ok = PT.avaliar({"estados": {"andar_sul": _estado("andar", pe_linha=[50, 53])}}, j)
    assert ok["ok"], ok                       # top-down: o pé da frente desce na tela andando
    r = PT.avaliar({"estados": {"idle_sul": _estado("idle", pe_linha=[50, 53], pisca=0.05)},
                    "avisos": ["NAO_CABE: x"]}, j)
    assert not r["ok"] and len(r["falhas"]) == 3
    r = PT.avaliar({"estados": {"andar_sul": _estado("andar", mudanca_media=0.01)}}, j)
    assert any("muda" in f for f in r["falhas"])
    r = PT.avaliar({"estados": {"idle_sul": _estado("idle", pisca=0.5)}}, j, previa=True)
    assert r["ok"]
    r = PT.avaliar({"estados": {"morte_sul": _estado("morte", pisca=0.025)}}, j)
    assert r["ok"]


def test_duracoes_somam_o_tempo():
    d = pos.duracoes(12, 12)
    assert sum(d) == 1000 and all(x % 10 == 0 for x in d)


# ------------------------------------------------------------------ projeção da arte no modelo

def test_projecao_so_com_projetar_e_com_angulo_da_vista(tmp_path):
    from horys_pixel import fluxo as F
    (tmp_path / "jogo.json").write_text("{}", encoding="utf-8")   # raiz do projeto = tmp_path
    a = AS.novo("proj", raiz=tmp_path)
    jogo = J.carregar(a.pasta)
    a.arte.mkdir(parents=True, exist_ok=True)
    for nome in ("frente", "lado"):
        (a.arte / f"{nome}.png").write_bytes(b"x")
    assert F.projecao(a, jogo) is None                     # desligada por padrão
    a.cfg["projetar"] = True
    pr = F.projecao(a, jogo)
    assert set(pr["vistas"]) == {"frente", "lado"}         # costas não existe: fica de fora
    assert pr["vistas"]["lado"]["angulo"] == jogo["direcoes"][jogo["vistas"]["lado"]]


# ------------------------------------------------------------------ casco visual

def test_casco_esculpe_um_cubo_e_bate_a_silhueta_nas_tres_vistas():
    from horys_pixel import casco as K
    jogo = {"angulo": 43, "px_por_metro": 26.6, "contorno": "nenhum"}
    # silhuetas de um cubo de 0,6 m projetado pela câmera do jogo: retângulo 16 x 23 px nas três vistas
    rgba = np.zeros((27, 20, 4), np.uint8)
    rgba[2:25, 2:18] = (200, 120, 60, 255)
    c = K.Casco({"frente": (rgba, 0), "lado": (rgba, 90), "costas": (rgba, 180)}, jogo)
    o = c.esculpir()
    assert o.any()
    iou = c.iou()
    assert min(iou.values()) > 0.85, iou
    rot = c.partes()
    pecas = c.malhas(rot, {"m": {"rampa": ["#7a3a10", "#c87840", "#f0b080"]}})
    assert pecas and all(len(p["faces"]) == len(p["familias"]) for p in pecas)
    assert {f for p in pecas for f in p["familias"]} == {"m"}


def test_gabarito_nao_conta_tinta_da_arte_nos_materiais():
    arte = _boneco()
    arte[:, 3:5] = (0x1a, 0x14, 0x20, 255)                 # linha interna da arte, na cor da tinta
    render = _boneco()                                      # o render pinta o material ali
    r = G.avaliar({"frente": arte}, {"frente": render}, PAL, J.PADRAO["portoes"]["gabarito"])
    assert r["vistas"]["frente"]["familia"] == 1.0 and r["vistas"]["frente"]["iou"] == 1.0
    render[:, 0:2] = (59, 110, 168, 255)                    # material errado fora da linha ainda conta
    r = G.avaliar({"frente": arte}, {"frente": render}, PAL, J.PADRAO["portoes"]["gabarito"])
    assert r["vistas"]["frente"]["familia"] < 1.0


def test_ler_troca_so_uma_vista(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from PIL import Image
    from horys_pixel import fluxo as F
    from horys_pixel import leitura as L
    (tmp_path / "jogo.json").write_text("{}", encoding="utf-8")
    a = AS.novo("troca", raiz=tmp_path)
    cor = {"frente": (200, 0, 0), "lado": (0, 200, 0), "costas": (0, 0, 200)}

    def fake(cores):
        return SimpleNamespace(vistas={n: np.full((10, 6, 4), c + (255,), np.uint8) for n, c in cores.items()},
                               folha=np.zeros((10, 30, 4), np.uint8), relatorio={"altura": 10, "vistas": {}})

    (a.pasta / "gerada.png").write_bytes(b"x")
    (a.pasta / "outra.png").write_bytes(b"x")
    monkeypatch.setattr(L, "carregar", lambda p: p)
    monkeypatch.setattr(L, "ler", lambda img, *k, **kw: fake(cor) if img.name == "gerada.png"
                        else fake({n: (9, 9, 9) for n in cor}))
    F.ler_arte(a)
    rel = F.ler_arte(a, a.pasta / "outra.png", vista="costas")
    px = lambda n: tuple(np.asarray(Image.open(a.arte / f"{n}.png"))[0, 0, :3])
    assert px("frente") == (200, 0, 0) and px("lado") == (0, 200, 0) and px("costas") == (9, 9, 9)
    assert rel["fontes"]["costas"].endswith("outra.png") and rel["fontes"]["frente"].endswith("gerada.png")


def test_folha_confere_recortes(tmp_path):
    from horys_pixel import folha
    qs = [np.zeros((4, 3, 4), np.uint8) for _ in range(3)]
    for i, q in enumerate(qs):
        q[i, 1] = (10 * i, 20, 30, 255)
    out = folha.salvar(qs, tmp_path, "t", gif=False)
    folha.conferir(out["png"], qs)
    with pytest.raises(ValueError):
        folha.conferir(out["png"], qs[::-1])


def test_emenda_do_loop_avisa_pop_e_trava():
    assert pos.emenda([0.1, 0.1, 0.1]) is None
    em = pos.emenda([0.1, 0.1, 0.1, 0.5])
    assert em["razao"] == 5.0
    r = PT.avaliar({"estados": {"andar_sul": _estado("andar", emenda=em)}}, J.PADRAO)
    assert r["ok"] and any("pop" in a for a in r["avisos"])
    r = PT.avaliar({"estados": {"andar_sul": _estado("andar", emenda=pos.emenda([0.1, 0.1, 0.1, 0.0]))}}, J.PADRAO)
    assert any("repetido" in a for a in r["avisos"])
    r = PT.avaliar({"estados": {"andar_sul": _estado("andar", emenda=pos.emenda([0.1, 0.12, 0.1, 0.11]))}}, J.PADRAO)
    assert not r["avisos"]
