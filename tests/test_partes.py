"""partes.py: preset, contratos de junção, validador, vista explodida, recorte e extensão (sem Aseprite)."""
from pathlib import Path

import numpy as np
import pytest

from horys_pixel import partes as P

RAIZ = Path(__file__).resolve().parents[1]
VERMELHO = (200, 60, 60, 255)
AZUL = (60, 60, 200, 255)
BEGE = (200, 170, 120, 255)
CELESTE = (120, 170, 200, 255)
ESCURO = (20, 20, 40, 255)


def imagem(n=24):
    return np.zeros((n, n, 4), np.uint8)


def ret(im, x0, y0, x1, y1, cor):
    """Retângulo com x0..x1 e y0..y1 inclusivos."""
    im[y0:y1 + 1, x0:x1 + 1] = cor
    return im


def duo(inferior, superior, movel="superior"):
    """(partes, juncoes) de um par base/topo; `movel`: 'superior' ou 'inferior'."""
    j = P.Juncao("base-topo", "base", "topo", "topo" if movel == "superior" else "base")
    return ["base", "topo"], [j]


def codigos(rel, gravidade):
    return {p.codigo for p in rel.problemas if p.gravidade == gravidade}


# ------------------------------------------------------------------ preset e contratos

def test_preset_humanoide_ferreiro():
    pr = P.preset("humanoide-ferreiro")
    assert pr.partes == ("perna-traseira", "corpo-base", "avental-torso", "cabelo", "barba", "braco-traseiro",
                         "braco-frente", "martelo", "oculos")
    assert 9 <= len(pr.juncoes) <= 11
    assert P.validar_contratos(pr.partes, pr.juncoes) == []
    assert not set(pr.partes) & set(P.RESERVADAS_PARTES)          # contorno/sombra nunca são partes
    for j in pr.juncoes:                                          # cada contrato tem inferior, superior e móvel
        assert j.movel in (j.inferior, j.superior)
        assert pr.partes.index(j.inferior) < pr.partes.index(j.superior)
    assert set(pr.oculto) == {j.inferior for j in pr.juncoes}
    with pytest.raises(ValueError):
        P.preset("não-existe")


def test_preset_humanoide_base_sem_extras_e_ordem_kiln():
    pr = P.preset("humanoide")
    assert not {"oculos", "barba", "martelo", "avental-torso"} & set(pr.partes)
    assert pr.partes.index("braco-traseiro") < pr.partes.index("corpo") < pr.partes.index("braco-frente")
    assert P.validar_contratos(pr.partes, pr.juncoes) == []


def test_oculos_duas_lentes_permitido_tres_reprova():
    def quadro(n):
        im = imagem(16)
        for x in range(n):
            im[2, 2 + x * 3] = ESCURO
        return {"oculos": im}
    ok = P.checar(None, [quadro(2)], partes=["oculos"], componentes_max={"oculos": 2}, ignorar_linha=True)
    ruim = P.checar(None, [quadro(3)], partes=["oculos"], componentes_max={"oculos": 2}, ignorar_linha=True)
    assert "parte-desconexa" not in codigos(ok, "erro")
    assert "parte-desconexa" in codigos(ruim, "erro")


def test_estender_nao_propaga_linha_escura():
    base, topo = imagem(12), imagem(12)
    base[4:8, 2:5] = VERMELHO
    base[4:8, 4] = ESCURO
    topo[3:9, 5:9] = AZUL
    r = P.estender({"base": base, "topo": topo}, ["base", "topo"], "base", "topo", 2,
                   cores_linha={tuple(ESCURO[:3])})
    novos = (r.novo[..., 3] > 0) & ~(base[..., 3] > 0)
    assert novos.any() and np.all(r.novo[novos, :3] == VERMELHO[:3])


def test_campos_ficha_modular():
    c = P.campos_ficha_modular("humanoide-ferreiro")
    assert c["modular"] is True and c["preset_partes"] == "humanoide-ferreiro"
    assert len(c["partes"]) == 9 and len(c["juncoes"]) == len(P.HUMANOIDE_FERREIRO.juncoes)
    partes, juncoes, oculto = P.contratos_da_ficha(c)
    assert partes == c["partes"] and oculto == c["partes_oculto"] and len(juncoes) == len(c["juncoes"])
    assert P.contratos_da_ficha({"preset_partes": "humanoide-ferreiro"})[0] == list(P.HUMANOIDE_FERREIRO.partes)


def test_contratos_invalidos():
    erros = P.validar_contratos(["a", "contorno"], [P.Juncao("x", "a", "contorno", "a")])
    assert any("reservada" in e for e in erros)
    erros = P.validar_contratos(["a", "b"], [P.Juncao("x", "b", "a", "a"), P.Juncao("y", "a", "z", "a"),
                                             P.Juncao("w", "a", "b", "c")])
    assert any("não está abaixo" in e for e in erros)
    assert any("'z'" in e for e in erros)
    assert any("móvel" in e for e in erros)


# ------------------------------------------------------------------ validador

def test_checar_aprovado():
    base = ret(imagem(), 4, 4, 13, 13, BEGE)
    topo = ret(imagem(), 10, 6, 17, 11, CELESTE)
    partes, juncoes = duo(base, topo)
    rel = P.checar(None, [{"base": base, "topo": topo}], partes=partes, juncoes=juncoes, ignorar_linha=True)
    assert rel.ok, rel.texto()
    assert rel.medidas["juncoes"]["base-topo"]["profundidade"] >= 2
    assert rel.medidas["juncoes"]["base-topo"]["buraco_1px"] == 0
    assert rel.texto().startswith("PARTES APROVADAS")


def test_sem_sobreposicao_e_buraco_em_1px_sao_erros():
    base = ret(imagem(), 5, 2, 10, 9, BEGE)           # inferior
    topo = ret(imagem(), 2, 2, 4, 9, CELESTE)         # encostada, sem entrar por baixo
    partes, juncoes = duo(base, topo)
    rel = P.checar(None, [{"base": base, "topo": topo}], partes=partes, juncoes=juncoes, ignorar_linha=True)
    erros = codigos(rel, "erro")
    assert "sem-sobreposicao" in erros and "buraco-1px" in erros and "buraco-2px" in codigos(rel, "aviso")
    assert not rel.ok and rel.texto().startswith("PARTES REPROVADAS")
    buraco = next(p for p in rel.problemas if p.codigo == "buraco-1px")
    assert buraco.pontos and buraco.juncao == "base-topo" and buraco.quadro == 0


def test_sobreposicao_de_1px_so_avisa():
    base = ret(imagem(), 5, 2, 10, 9, BEGE)
    topo = ret(imagem(), 2, 2, 5, 9, CELESTE)         # base entra 1 px (coluna 5) sob a topo
    partes, juncoes = duo(base, topo)
    rel = P.checar(None, [{"base": base, "topo": topo}], partes=partes, juncoes=juncoes, ignorar_linha=True,
                   oculto=[])
    assert rel.ok, rel.texto()
    avisos = codigos(rel, "aviso")
    assert "sobreposicao-curta" in avisos and "buraco-2px" in avisos


def test_partes_nao_se_tocam():
    base = ret(imagem(), 2, 2, 5, 5, BEGE)
    topo = ret(imagem(), 12, 12, 16, 16, CELESTE)
    partes, juncoes = duo(base, topo)
    rel = P.checar(None, [{"base": base, "topo": topo}], partes=partes, juncoes=juncoes, ignorar_linha=True)
    assert "nao-tocam" in codigos(rel, "erro")


def test_parte_vazia_desconexa_e_camada_faltando():
    base = ret(imagem(), 2, 2, 5, 5, BEGE)
    base = ret(base, 12, 12, 14, 14, BEGE)            # segundo pedaço, longe
    rel = P.checar(None, [{"base": base, "topo": imagem()}], partes=["base", "topo"], juncoes=[],
                   ignorar_linha=True)
    assert {"parte-desconexa", "parte-vazia"} <= codigos(rel, "erro")
    rel = P.checar(None, [{"base": base}], partes=["base", "topo"], juncoes=[], ignorar_linha=True)
    assert "camada-faltando" in codigos(rel, "erro")


def test_cobertura_da_anatomia_oculta_abaixo_de_90():
    base = ret(imagem(), 7, 2, 12, 3, BEGE)           # entra sob a topo só nas linhas 2–3
    base = ret(base, 8, 4, 12, 9, BEGE)
    topo = ret(imagem(), 4, 2, 7, 9, CELESTE)
    partes, juncoes = duo(base, topo)
    rel = P.checar(None, [{"base": base, "topo": topo}], partes=partes, juncoes=juncoes, ignorar_linha=True)
    assert "cobertura-oculta-1px" in codigos(rel, "erro")
    # a parte fora de `oculto` não é cobrada
    rel = P.checar(None, [{"base": base, "topo": topo}], partes=partes, juncoes=juncoes, ignorar_linha=True,
                   oculto=[])
    assert "cobertura-oculta-1px" not in codigos(rel, "erro")


def test_cobertura_da_referencia():
    base = ret(imagem(), 4, 4, 13, 13, BEGE)
    topo = ret(imagem(), 10, 6, 17, 11, CELESTE)
    partes, juncoes = duo(base, topo)
    ref_boa = np.maximum(base, topo)
    rel = P.checar(None, [{"base": base, "topo": topo}], partes=partes, juncoes=juncoes, ignorar_linha=True,
                   referencias=[ref_boa])
    assert rel.ok, rel.texto()
    ref_ruim = ret(ref_boa.copy(), 18, 0, 23, 23, VERMELHO)          # referência com muito mais do que as partes
    rel = P.checar(None, [{"base": base, "topo": topo}], partes=partes, juncoes=juncoes, ignorar_linha=True,
                   referencias=[ref_ruim])
    assert "cobertura-referencia" in codigos(rel, "erro")


def test_linha_interna():
    base = ret(imagem(), 2, 2, 9, 9, BEGE)
    topo = ret(imagem(), 6, 4, 13, 11, CELESTE)
    partes, juncoes = duo(base, topo)
    sem = P.checar(None, [{"base": base, "topo": topo}], partes=partes, juncoes=juncoes)
    assert "sem-linha-interna" in codigos(sem, "erro")
    topo2 = topo.copy()
    for fatia in (np.s_[4, 6:14], np.s_[11, 6:14], np.s_[4:12, 6], np.s_[4:12, 13]):
        topo2[fatia] = ESCURO
    com = P.checar(None, [{"base": base, "topo": topo2}], partes=partes, juncoes=juncoes)
    assert "sem-linha-interna" not in codigos(com, "erro")
    # a cor da linha pode ser dada explicitamente
    com = P.checar(None, [{"base": base, "topo": topo2}], partes=partes, juncoes=juncoes,
                   cores_linha={ESCURO[:3]})
    assert "sem-linha-interna" not in codigos(com, "erro")


def test_checar_por_quadro_aponta_o_quadro_ruim():
    base = ret(imagem(), 4, 4, 13, 13, BEGE)
    topo = ret(imagem(), 10, 6, 17, 11, CELESTE)
    solto = ret(imagem(), 15, 15, 17, 17, CELESTE)        # topo longe da base no quadro 1
    partes, juncoes = duo(base, topo)
    rel = P.checar(None, [{"base": base, "topo": topo}, {"base": base, "topo": solto}], partes=partes,
                   juncoes=juncoes, ignorar_linha=True)
    assert rel.quadros == 2 and {p.quadro for p in rel.erros} == {1}


def test_relatorio_json():
    rel = P.checar(None, [{"base": imagem(), "topo": imagem()}], partes=["base", "topo"], juncoes=[])
    d = rel.como_dict()
    assert d["ok"] is False and d["erros"] == 2 and d["problemas"][0]["codigo"] == "parte-vazia"
    assert "parte-vazia" in rel.json()


# ------------------------------------------------------------------ vista explodida

def test_vista_explodida_pinta_ocultos_de_magenta():
    base = ret(imagem(), 4, 4, 13, 13, BEGE)
    topo = ret(imagem(), 10, 6, 17, 11, CELESTE)
    ordem = ["base", "topo"]
    oc = P.ocultos_da_parte({"base": base, "topo": topo}, ordem, "base")
    assert oc.sum() == 4 * 6 and not oc[4, 4]                 # colunas 10–13 × linhas 6–11
    vista = P.vista_explodida({"base": base, "topo": topo}, ordem, colunas=3, escala=2)
    assert vista.dtype == np.uint8 and vista.ndim == 3 and vista.shape[2] == 4
    assert (vista == np.array(P.MAGENTA, np.uint8)).all(-1).sum() == 4 * 6 * 4          # 24 px × escala²
    # a parte de cima não tem nada por cima: sem magenta nela
    so_topo = P.vista_explodida({"topo": topo}, ordem, colunas=3, escala=2)
    assert not (so_topo == np.array(P.MAGENTA, np.uint8)).all(-1).any()


# ------------------------------------------------------------------ recorte e extensão preservam a composição

def _cena():
    base = ret(imagem(), 4, 4, 13, 13, VERMELHO)
    topo = ret(imagem(), 12, 6, 19, 11, AZUL)
    return {"base": base, "topo": topo}, ["base", "topo"]


@pytest.mark.parametrize("px, esperado", [(1, 6), (2, 12)])
def test_estender_so_pixels_cobertos(px, esperado):
    partes, ordem = _cena()
    antes = P.compor(partes, ordem)
    r = P.estender(partes, ordem, "base", "topo", px)
    assert r.alterados == esperado and r.recusados == 0
    depois = P.compor({**partes, "base": r.novo}, ordem)
    assert np.array_equal(antes, depois)
    novos = (r.novo[..., 3] > 0) & ~(partes["base"][..., 3] > 0)
    assert (partes["topo"][..., 3][novos] == 255).all()       # só sob a topo
    assert (r.novo[novos][:, :3] == VERMELHO[:3]).all()       # com a cor do vizinho


def test_estender_com_cima_semitransparente_nao_toca_em_nada():
    partes, ordem = _cena()
    partes["topo"][..., 3][partes["topo"][..., 3] > 0] = 128
    r = P.estender(partes, ordem, "base", "topo", 2)
    assert r.alterados == 0
    assert np.array_equal(r.novo, partes["base"])


def test_estender_argumentos_invalidos():
    partes, ordem = _cena()
    with pytest.raises(ValueError):
        P.estender(partes, ordem, "base", "topo", 3)
    with pytest.raises(ValueError):
        P.estender(partes, ordem, "topo", "base", 1)


def test_recortar_so_onde_a_composicao_nao_muda():
    partes, ordem = _cena()
    partes["topo"] = imagem()                                 # topo vazia; a figura está na base
    ref = partes["base"].copy()
    ref[20, 20] = VERMELHO                                    # pixel que só existe na referência
    antes = P.compor(partes, ordem)
    r = P.recortar(partes, ordem, "topo", ref, (10, 6, 12, 16))
    assert r.alterados == 32 and r.recusados == 1             # colunas 10–13 × linhas 6–13; e o (20, 20) recusado
    assert r.novo[20, 20, 3] == 0
    assert np.array_equal(P.compor({**partes, "topo": r.novo}, ordem), antes)


def test_recortar_nao_sobrescreve_sem_pedir_e_sobrescreve_com_pedido():
    partes, ordem = _cena()
    ref = partes["topo"].copy()
    ref[6:12, 12:20] = AZUL                                   # igual ao que a topo já tem
    ref[6, 12] = (10, 200, 10, 255)                           # um pixel diferente
    r = P.recortar(partes, ordem, "topo", ref, (12, 6, 8, 6))
    assert r.alterados == 0                                   # a topo já tem pixels ali
    r = P.recortar(partes, ordem, "topo", ref, (12, 6, 8, 6), sobrescrever=True)
    # trocar o pixel por verde mudaria a composição (a topo é o que se vê): recusado
    assert r.alterados == 0 and r.recusados == 1
    with pytest.raises(ValueError):
        P.recortar(partes, ordem, "nada", ref, (0, 0, 4, 4))


# ------------------------------------------------------------------ revisor e docs

def test_revisor_tem_criterio_de_partes_em_l7_e_agente_esta_sincronizado():
    prompt = (RAIZ / "src" / "horys_pixel" / "motor" / "revisor_prompt.md").read_text(encoding="utf-8")
    assert "L7 Práticas e partes" in prompt and "partes_checagem.txt" in prompt
    agente = (RAIZ / "agents" / "revisor.md").read_text(encoding="utf-8")
    assert agente.endswith(prompt)                            # o que scripts/gerar_agente.py produziria


def test_docs_de_ferramentas_citam_todas_as_ferramentas():
    from horys_pixel.ferramentas import registro
    registro.carregar_todas()
    docs = (RAIZ / "docs" / "ferramentas.md").read_text(encoding="utf-8")
    for nome in ("horys_partes_checar", "horys_partes_recortar", "horys_partes_estender"):
        assert nome in registro.REGISTRO
    faltam = [n for n in registro.REGISTRO if f"### `{n}`" not in docs]
    assert not faltam, f"rode scripts/gerar_docs_ferramentas.py: faltam {faltam}"
