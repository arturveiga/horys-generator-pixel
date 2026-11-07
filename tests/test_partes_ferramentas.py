"""Ferramentas de partes com o Aseprite falso: asset modular, checagem, recorte, extensão e portão."""
import base64
import numpy as np
import pytest

from horys_pixel import partes as P
from horys_pixel.ferramentas import registro
from horys_pixel.ferramentas.registro import ErroFerramenta
from test_nucleo import _ambiente, _txt, rodar

VERMELHO = (200, 60, 60, 255)
AZUL = (60, 60, 200, 255)
JUNCAO = [{"nome": "base-topo", "inferior": "base", "superior": "topo", "movel": "topo"}]


async def _duo(chamar, tmp_path, **extra):
    r = await chamar("horys_asset_novo", estilo="exemplo", nome="duo", tipo="prop", quadro=64, modular=True,
                     partes=["base", "topo"], juncoes=JUNCAO, contorno="nenhum", pasta=str(tmp_path / "duo"),
                     estados=[{"nome": "idle", "quadros": 1, "ms": 100}], **extra)
    assert not r["erro"], _txt(r)


def _cena(ase):
    ase.atual.img("base", 0)[4:14, 4:14] = VERMELHO
    ase.atual.img("topo", 0)[6:12, 12:20] = AZUL
    return ase.atual.composto(0).copy()


def test_asset_novo_com_preset_cria_partes_referencia_e_ficha(ambiente, tmp_path):
    async def corpo():
        ctx, ase, chamar, fim = await _ambiente(ambiente)
        try:
            r = await chamar("horys_asset_novo", estilo="exemplo", nome="ferreiro", tipo="personagem", quadro=64,
                             preset_partes="humanoide-ferreiro", pasta=str(tmp_path / "fer"))
            assert not r["erro"], _txt(r)
            assert "MODULAR" in _txt(r)
            nomes = [c["nome"] for c in ase.atual.camadas]
            assert nomes == ["sombra", "contorno", *P.HUMANOIDE_FERREIRO.partes, "referencia", "revisao"]
            visiveis = {c["nome"]: c["visivel"] for c in ase.atual.camadas}
            assert not visiveis["referencia"] and not visiveis["revisao"]
            f = ctx.ficha(ase.atual.arquivo)
            assert f["modular"] is True and f["preset_partes"] == "humanoide-ferreiro"
            assert f["partes"] == list(P.HUMANOIDE_FERREIRO.partes) and len(f["juncoes"]) == 10
            assert set(f["partes_oculto"]) == set(P.HUMANOIDE_FERREIRO.oculto)
            # partes conflitantes com o preset são recusadas
            r = await chamar("horys_asset_novo", estilo="exemplo", preset_partes="humanoide-ferreiro",
                             partes=["a", "b"])
            assert r["erro"] and "preset" in _txt(r)
            r = await chamar("horys_asset_novo", estilo="exemplo", preset_partes="nao-existe")
            assert r["erro"]
        finally:
            await fim()
    rodar(corpo())


def test_checar_sem_desenho_reprova_e_devolve_vista_explodida(ambiente, tmp_path):
    async def corpo():
        ctx, ase, chamar, fim = await _ambiente(ambiente)
        try:
            await chamar("horys_asset_novo", estilo="exemplo", nome="ferreiro", quadro=64,
                         preset_partes="humanoide-ferreiro", pasta=str(tmp_path / "fer"))
            r = await chamar("horys_partes_checar", salvar=str(tmp_path / "saida"))
            assert not r["erro"], _txt(r)
            assert "PARTES REPROVADAS" in _txt(r) and "parte-vazia" in _txt(r)
            assert any(c["type"] == "image" for c in r["conteudo"])
            assert (tmp_path / "saida" / "partes_checagem.txt").exists()
            assert (tmp_path / "saida" / "medidas" / "partes.json").exists()
            assert (tmp_path / "saida" / "ferreiro_partes.png").exists()
            assert ctx.ficha(ase.atual.arquivo)["partes_checagem"]["ok"] is False
            # asset modular com checagem reprovada não pode ir para a animação
            with pytest.raises(ErroFerramenta):
                await registro.REGISTRO["horys_pedido_atualizar"].funcao(ctx, {"id": "x", "etapa": "animacao"})
        finally:
            await fim()
    rodar(corpo())


def test_camada_faltando_em_asset_modular_e_erro_explicito(ambiente, tmp_path):
    async def corpo():
        ctx, ase, chamar, fim = await _ambiente(ambiente)
        try:
            await chamar("horys_asset_novo", estilo="exemplo", nome="ferreiro", quadro=64,
                         preset_partes="humanoide-ferreiro", pasta=str(tmp_path / "fer"))
            await chamar("horys_camada", acao="remover", nome="oculos")
            for ferramenta in ("horys_partes_checar", "horys_contorno", "horys_portao"):
                r = await chamar(ferramenta)
                assert r["erro"] and "faltam as camadas" in _txt(r) and "'oculos'" in _txt(r), (ferramenta, _txt(r))
            await chamar("horys_camada", acao="criar", nome="oculos")        # volta, mas no topo; 'referencia' some
            await chamar("horys_camada", acao="remover", nome="referencia")
            r = await chamar("horys_partes_checar")
            assert r["erro"] and "'referencia'" in _txt(r)
        finally:
            await fim()
    rodar(corpo())


def test_estender_preserva_a_composicao(ambiente, tmp_path):
    async def corpo():
        ctx, ase, chamar, fim = await _ambiente(ambiente)
        try:
            await _duo(chamar, tmp_path)
            antes = _cena(ase)
            n0 = int((ase.atual.img("base", 0)[..., 3] > 0).sum())
            r = await chamar("horys_partes_estender", juncao="base-topo", px=2)
            assert not r["erro"], _txt(r)
            assert int((ase.atual.img("base", 0)[..., 3] > 0).sum()) == n0 + 12      # 2 colunas × 6 linhas sob a topo
            assert np.array_equal(ase.atual.composto(0), antes)
            r = await chamar("horys_partes_estender", inferior="base", superior="topo", px=3)
            assert r["erro"]
            r = await chamar("horys_partes_estender", juncao="nao-existe")
            assert r["erro"]
        finally:
            await fim()
    rodar(corpo())


def test_composto_ignora_revisao_e_referencia(ambiente, tmp_path):
    async def corpo():
        ctx, ase, chamar, fim = await _ambiente(ambiente)
        try:
            await _duo(chamar, tmp_path)
            ase.atual.img("base", 0)[5, 5] = VERMELHO
            ase.atual.img("revisao", 0)[5, 5] = (255, 0, 255, 255)
            ase.atual.img("referencia", 0)[6, 6] = AZUL
            lido = await ctx.aseprite("ler", {"quadro": 0})
            arr = np.frombuffer(base64.b64decode(lido["rgba"]), np.uint8).reshape(64, 64, 4)
            assert tuple(arr[5, 5]) == VERMELHO and arr[6, 6, 3] == 0
        finally:
            await fim()
    rodar(corpo())


def test_estender_reverte_e_aborta_se_a_composicao_mudar(ambiente, tmp_path, monkeypatch):
    original = P.estender

    def estragada(partes, ordem, inferior, superior, px=2):
        r = original(partes, ordem, inferior, superior, px)
        novo = r.novo.copy()
        novo[40, 40] = (1, 2, 3, 255)                   # pixel visível, fora de qualquer parte: muda a composição
        return P.Resultado(novo, r.alterados + 1, 0)
    monkeypatch.setattr(P, "estender", estragada)

    async def corpo():
        ctx, ase, chamar, fim = await _ambiente(ambiente)
        try:
            await _duo(chamar, tmp_path)
            antes = _cena(ase)
            base_antes = ase.atual.img("base", 0).copy()
            r = await chamar("horys_partes_estender", juncao="base-topo")
            assert r["erro"] and "revertido" in _txt(r)
            assert np.array_equal(ase.atual.img("base", 0), base_antes)
            assert np.array_equal(ase.atual.composto(0), antes)
        finally:
            await fim()
    rodar(corpo())


def test_recortar_copia_so_onde_a_composicao_nao_muda(ambiente, tmp_path):
    async def corpo():
        ctx, ase, chamar, fim = await _ambiente(ambiente)
        try:
            await _duo(chamar, tmp_path)
            ase.atual.img("base", 0)[4:14, 4:14] = VERMELHO              # figura toda na base
            ref = ase.atual.img("referencia", 0)
            ref[4:14, 4:14] = VERMELHO
            ref[20, 20] = VERMELHO                                       # só existe na referência
            antes = ase.atual.composto(0).copy()
            r = await chamar("horys_partes_recortar", parte="topo", regiao={"x": 10, "y": 6, "w": 12, "h": 16})
            assert not r["erro"], _txt(r)
            assert "32 px copiados" in _txt(r) and "1 px recusados" in _txt(r)
            topo = ase.atual.img("topo", 0)
            assert int((topo[..., 3] > 0).sum()) == 32 and topo[20, 20, 3] == 0
            assert np.array_equal(ase.atual.composto(0), antes)
            r = await chamar("horys_partes_recortar", parte="desenho", regiao={"x": 0, "y": 0, "w": 4, "h": 4})
            assert r["erro"]
            r = await chamar("horys_partes_recortar", parte="topo", regiao="tudo")
            assert r["erro"]
        finally:
            await fim()
    rodar(corpo())


def test_portao_reprova_e_exportar_recusa_com_erros_nas_partes(ambiente, tmp_path):
    async def corpo():
        ctx, ase, chamar, fim = await _ambiente(ambiente)
        try:
            await _duo(chamar, tmp_path)
            ase.atual.img("base", 0)[4:14, 4:14] = VERMELHO
            ase.atual.img("topo", 0)[30:36, 30:36] = AZUL                # longe da base: partes não se tocam
            r = await chamar("horys_portao")
            assert not r["erro"], _txt(r)
            assert "REPROVADO" in _txt(r) and "nao-tocam" in _txt(r)
            v01 = tmp_path / "duo" / "v01"
            assert (v01 / "partes_checagem.txt").exists()
            assert (v01 / "medidas" / "partes.json").exists()
            assert (v01 / "duo_partes.png").exists()
            destino = tmp_path / "entrega"
            r = await chamar("horys_exportar", destino=str(destino))
            assert r["erro"] and "REPROVADA" in _txt(r)
            assert not destino.exists() or not list(destino.iterdir())
        finally:
            await fim()
    rodar(corpo())


def test_ferramentas_de_partes_registradas():
    registro.carregar_todas()
    for nome in ("horys_partes_checar", "horys_partes_recortar", "horys_partes_estender"):
        assert nome in registro.REGISTRO
    assert {"modular", "preset_partes", "juncoes", "partes_oculto"} <= \
        set(registro.REGISTRO["horys_ficha"].esquema["properties"])
