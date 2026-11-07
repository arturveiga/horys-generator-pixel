"""Preparo do conjunto com imagens sintéticas: dedupe, recorte, fundo, ampliação sem suavizar, legendas, manifesto."""

import json

import numpy as np
import pytest
from PIL import Image

from horys_pixel.treino import ErroTreino, conjunto

PRETO, VERMELHO, AZUL = (20, 20, 30), (200, 40, 50), (40, 60, 200)


def sprite(cor_corpo=VERMELHO, w=10, h=12):
    """Sprite RGBA com contorno, corpo e um pixel semitransparente (que deve virar opaco ou sumir)."""
    a = np.zeros((h, w, 4), np.uint8)
    a[1:-1, 1:-1] = (*PRETO, 255)
    a[2:-2, 2:-2] = (*cor_corpo, 255)
    a[3, 3] = (*AZUL, 255)
    a[0, 0] = (255, 255, 0, 60)  # quase transparente: some
    return a


def em_tela(arr, tela=(32, 32), pos=(5, 7), escala=1):
    """Põe o sprite numa tela transparente maior (e opcionalmente ampliado)."""
    t = np.zeros((tela[1], tela[0], 4), np.uint8)
    h, w = arr.shape[:2]
    t[pos[1]: pos[1] + h, pos[0]: pos[0] + w] = arr
    if escala > 1:
        t = np.repeat(np.repeat(t, escala, 0), escala, 1)
    return t


def salvar(arr, caminho, meta=None):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr, "RGBA").save(caminho)
    if meta is not None:
        caminho.with_suffix(".json").write_text(json.dumps(meta), encoding="utf-8")
    return caminho


@pytest.fixture
def estilo(tmp_path):
    aprov = tmp_path / "estilo" / "gosto" / "aprovados"
    salvar(em_tela(sprite()), aprov / "a_heroi.png", {"descricao": "herói de capa", "tipo": "personagem"})
    # mesma arte com outra margem e ampliada 4× → duplicada
    salvar(em_tela(sprite(), tela=(20, 20), pos=(1, 2), escala=4), aprov / "b_heroi_4x.png",
           {"descricao": "cópia", "tipo": "personagem"})
    salvar(em_tela(sprite(AZUL)), aprov / "c_slime.png", {"descricao": "slime\nazul", "tipo": "inimigo"})
    return tmp_path / "estilo"


def cores(caminho):
    with Image.open(caminho) as im:
        a = np.array(im.convert("RGB")).reshape(-1, 3)
    return {tuple(c) for c in np.unique(a, axis=0)}


def test_preparar_basico(estilo, tmp_path):
    usuario = salvar(em_tela(sprite((30, 160, 60))), tmp_path / "minhas" / "arvore_grande.png")
    man = conjunto.preparar(estilo / "conjunto", "hpxliso", pasta_gosto=estilo / "gosto",
                            imagens=[tmp_path / "minhas"], licenca="minha arte", tipo="prop",
                            resolucao=512, cor_fundo="#ffffff", margem=2, repeticoes=10)
    c = man["contagem"]
    assert (c["total"], c["gosto"], c["usuario"], c["duplicadas"]) == (3, 2, 1, 1)
    assert man["duplicadas"][0]["fonte"].endswith("b_heroi_4x.png")

    pasta = estilo / "conjunto" / "img" / "10_hpxliso"
    assert pasta.is_dir() and man["pasta_imagens"] == str(pasta.resolve())
    pngs = sorted(pasta.glob("*.png"))
    assert len(pngs) == 3 and len(list(pasta.glob("*.txt"))) == 3

    # legendas
    leg = {p.stem: p.with_suffix(".txt").read_text(encoding="utf-8").strip() for p in pngs}
    assert leg["0001_gosto_a-heroi"] == "hpxliso, pixel art, character, herói de capa"
    assert leg["0002_gosto_c-slime"] == "hpxliso, pixel art, enemy, slime azul"
    assert leg["0003_usuario_arvore-grande"] == "hpxliso, pixel art, prop, arvore grande"

    # manifesto com origem e licença
    salvo = json.loads((estilo / "conjunto" / "manifesto.json").read_text(encoding="utf-8"))
    assert salvo["trigger"] == "hpxliso" and salvo["repeticoes"] == 10 and salvo["resolucao"] == 512
    por_origem = {i["origem"]: i["licenca"] for i in salvo["imagens"]}
    assert por_origem["usuario"] == "minha arte"
    assert por_origem["gosto"] == conjunto.LICENCA_GOSTO
    assert "minha arte" in salvo["licencas"]
    lotes = json.loads((estilo / "conjunto" / "lotes.json").read_text(encoding="utf-8"))
    assert lotes[0]["licenca"] == "minha arte"


def test_ampliacao_sem_cores_novas_e_blocos_inteiros(estilo):
    conjunto.preparar(estilo / "conjunto", "hpx", pasta_gosto=estilo / "gosto", resolucao=448, margem=2,
                      cor_fundo="#ffffff")
    png = sorted((estilo / "conjunto" / "img").rglob("0001_*.png"))[0]
    with Image.open(png) as im:
        assert im.size == (448, 448) and im.mode == "RGB"
        a = np.array(im)
    # nenhuma cor nova: só as do sprite + o fundo (o pixel semitransparente sumiu)
    assert cores(png) == {PRETO, VERMELHO, AZUL, (255, 255, 255)}
    # conteúdo 8×10 + margem 2 → 12×14 → quadrado 14 → fator 32 = 448 px; blocos 32×32 uniformes
    blocos = a.reshape(14, 32, 14, 32, 3)
    assert (blocos == blocos[:, :1, :, :1, :]).all()


def test_recorte_com_margem_e_fundo(tmp_path):
    arr = conjunto.binarizar_alfa(em_tela(sprite(), tela=(40, 40), pos=(20, 3)))
    rec = conjunto.recortar(arr, margem=3)
    assert rec.shape[:2] == (10 + 6, 8 + 6)  # conteúdo opaco 8×10 (o anel externo é transparente)
    assert (rec[:3, :, 3] == 0).all() and (rec[-3:, :, 3] == 0).all()
    rgb = conjunto.compor_fundo(rec, (1, 2, 3))
    assert tuple(rgb[0, 0]) == (1, 2, 3)
    q = conjunto.quadrar(rgb, (1, 2, 3))
    assert q.shape[:2] == (16, 16)
    assert conjunto.recortar(np.zeros((5, 5, 4), np.uint8)) is None


def test_fundo_opaco_vira_transparente_mas_tile_nao():
    s = conjunto.binarizar_alfa(sprite())
    opaco = s.copy()
    opaco[opaco[..., 3] == 0] = (0, 255, 0, 255)  # sprite em fundo verde liso, borda toda verde
    sem_fundo = conjunto.fundo_por_bordas(opaco)
    assert (sem_fundo[0, :, 3] == 0).all() and (sem_fundo[5, 5, 3] == 255)
    tile = np.full((8, 8, 4), 255, np.uint8)
    tile[..., :3] = (0, 255, 0)
    tile[0, 3] = (10, 10, 10, 255)  # borda não uniforme → é tile, fica intacto
    assert (conjunto.fundo_por_bordas(tile) == tile).all()


def test_escala_nativa():
    base = conjunto.binarizar_alfa(sprite())
    assert conjunto.escala_nativa(base) == 1
    assert conjunto.escala_nativa(np.repeat(np.repeat(base, 3, 0), 3, 1)) == 3


def test_fundo_configuravel_e_lotes_acumulam(estilo, tmp_path):
    salvar(em_tela(sprite((90, 90, 90))), tmp_path / "lote1" / "x.png")
    conjunto.preparar(estilo / "conjunto", "hpx", pasta_gosto=estilo / "gosto", imagens=[tmp_path / "lote1"],
                      licenca="CC0", resolucao=256, cor_fundo="#102030")
    # segundo preparo sem --imagens: o lote anterior continua entrando
    man = conjunto.preparar(estilo / "conjunto", "hpx", pasta_gosto=estilo / "gosto", resolucao=256,
                            cor_fundo="#102030")
    assert man["contagem"]["usuario"] == 1 and man["cor_fundo"] == "#102030"
    png = sorted((estilo / "conjunto" / "img").rglob("*.png"))[0]
    with Image.open(png) as im:
        assert im.getpixel((0, 0)) == (16, 32, 48)


def test_imagens_sem_licenca_recusadas(estilo, tmp_path):
    salvar(em_tela(sprite()), tmp_path / "x" / "a.png")
    with pytest.raises(ErroTreino, match="licença"):
        conjunto.preparar(estilo / "conjunto", "hpx", pasta_gosto=estilo / "gosto", imagens=[tmp_path / "x"])


def test_ignoradas_e_trigger_invalido(estilo, tmp_path):
    ruim = tmp_path / "ruins"
    ruim.mkdir()
    (ruim / "quebrada.png").write_bytes(b"nao e png")
    salvar(np.zeros((8, 8, 4), np.uint8), ruim / "vazia.png")
    man = conjunto.preparar(estilo / "conjunto", "hpx", pasta_gosto=estilo / "gosto", imagens=[ruim],
                            licenca="minha", resolucao=128)
    motivos = sorted(i["motivo"].split(":")[0] for i in man["ignoradas"])
    assert motivos == ["imagem toda transparente", "não abriu"]
    with pytest.raises(ErroTreino):
        conjunto.preparar(estilo / "conjunto", "Com Espaço", pasta_gosto=estilo / "gosto")


def test_repeticoes_sugeridas_e_legenda():
    assert conjunto.repeticoes_sugeridas(10) == 20
    assert conjunto.repeticoes_sugeridas(100) == 2
    assert conjunto.repeticoes_sugeridas(1000) == 1
    assert conjunto.legenda("t", "tile", "") == "t, pixel art, tile"
    assert conjunto.legenda("t", "personagem", "x", traduzir_tipo=False) == "t, pixel art, personagem, x"
