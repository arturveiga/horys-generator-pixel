"""Ponte horysd <-> extensão: espera de conexão, prazo por comando, queda no meio do pedido, teste ao vivo.

Regressões das quedas de 13/11 (horysd.log): "o Aseprite não está conectado" e "não respondeu 'salvar' em 60 s".
"""
import asyncio

import pytest

from horys_pixel import config, teste_vivo
from horys_pixel.daemon import ponte as P
from horys_pixel.daemon import servidor
from horys_pixel.daemon.contexto import Contexto

from aseprite_falso import AsepriteFalso
from test_nucleo import _ambiente, rodar


async def _so_servidor(porta):
    ctx = Contexto()
    pronto = asyncio.Event()
    srv = asyncio.ensure_future(servidor.principal(porta, pronto, ctx))
    await pronto.wait()
    return ctx, srv


async def _parar(srv, *ases):
    for a in ases:
        await a.fechar()
    srv.cancel()
    try:
        await srv
    except BaseException:
        pass


def test_pedido_espera_o_aseprite_conectar(ambiente):
    """Antes falhava na hora; agora espera a extensão (que tenta a cada 5 s) conectar."""
    async def corpo():
        ctx, srv = await _so_servidor(ambiente)
        ase = AsepriteFalso(ambiente, config.token())
        try:
            pedido = asyncio.ensure_future(ctx.aseprite("status"))
            await asyncio.sleep(0.3)
            assert not pedido.done()
            await ase.conectar()
            st = await asyncio.wait_for(pedido, 5)
            assert st["versao_aseprite"] == "falso"
        finally:
            await _parar(srv, ase)
    rodar(corpo())


def test_sem_aseprite_desiste_depois_da_espera(ambiente):
    async def corpo():
        ctx, srv = await _so_servidor(ambiente)
        try:
            with pytest.raises(P.AsepriteDesconectado, match="não está conectado"):
                await ctx.ponte.pedir("status", espera_conexao=0.2)
            # o painel (ui) é opcional: não espera nada
            assert await ctx.ui("ui_progresso", {}) is False
        finally:
            await _parar(srv)
    rodar(corpo())


def test_prazo_por_comando_salvar_tem_mais_tempo(ambiente, monkeypatch):
    monkeypatch.setattr(P, "PRAZO_PADRAO", 0.3)
    monkeypatch.setitem(P.PRAZOS, "salvar", 5.0)
    assert P.prazo("salvar") == 5.0 and P.prazo("status") == 0.3

    async def corpo():
        ctx, ase, chamar, fim = await _ambiente(ambiente)
        try:
            await ctx.aseprite("sprite_novo", {"largura": 4, "altura": 4})
            ase.atrasos = {"salvar": 0.8, "status": 0.8}
            d = await ctx.aseprite("salvar", {"arquivo": "x.aseprite"})
            assert d["arquivo"] == "x.aseprite"
            with pytest.raises(P.ErroAseprite, match="alerta aberto no Aseprite"):
                await ctx.aseprite("status")
            ase.atrasos = {}
            await asyncio.sleep(0.6)   # a resposta atrasada chega e é ignorada
            assert (await ctx.aseprite("status"))["sprite"]
            assert not ctx.ponte._espera
        finally:
            await fim()
    rodar(corpo())


def test_queda_no_meio_do_pedido_falha_na_hora(ambiente):
    async def corpo():
        ctx, ase, chamar, fim = await _ambiente(ambiente)
        try:
            ase.atrasos = {"status": 30}
            pedido = asyncio.ensure_future(ctx.aseprite("status"))
            await asyncio.sleep(0.2)
            await ase.ws.close()
            with pytest.raises(P.AsepriteDesconectado, match="desconectou"):
                await asyncio.wait_for(pedido, 5)
            assert not ctx.ponte.conectado
        finally:
            await fim()
    rodar(corpo())


def test_comando_desconhecido_avisa_extensao_desatualizada():
    """13/11: 'ui_imagem falhou: comando desconhecido' — a extensão instalada era de 05/11."""
    async def corpo():
        ponte = P.Ponte()
        f = asyncio.get_running_loop().create_future()
        ponte._espera[7] = f
        ponte.chegou({"t": "res", "id": 7, "ok": False, "erro": "comando desconhecido: ui_imagem"})
        with pytest.raises(P.ErroAseprite, match="horys instalar"):
            await f
    rodar(corpo())


def test_salvar_relata_sequencia(ambiente, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "caminho_permitido", lambda p: True)

    async def corpo():
        ctx, ase, chamar, fim = await _ambiente(ambiente)
        try:
            await chamar("horys_sprite_novo", largura=4, altura=4)
            orig = ase.tratar

            def tratar(cmd, a):
                if cmd == "salvar":
                    return {"arquivo": a["arquivo"], "sequencia": ["a1.png", "a2.png"]}
                return orig(cmd, a)
            ase.tratar = tratar
            r = await chamar("horys_salvar", arquivo=str(tmp_path / "a.png"))
            t = "\n".join(c.get("text", "") for c in r["conteudo"])
            assert not r["erro"] and "sequência (2 arquivos" in t
        finally:
            await fim()
    rodar(corpo())


def test_teste_vivo_contra_o_falso(ambiente, tmp_path):
    async def corpo():
        ctx, ase, chamar, fim = await _ambiente(ambiente)
        linhas = []
        orig = ase.tratar

        def tratar(cmd, a):  # o falso não grava arquivo: simula a gravação
            r = orig(cmd, a)
            if cmd == "salvar":
                (tmp_path / "tv.aseprite").write_bytes(b"ase")
            return r
        ase.tratar = tratar
        try:
            ok = await teste_vivo.rodar(chamar, arquivo=tmp_path / "tv.aseprite", espera_conexao=1,
                                        imprimir=linhas.append)
            assert ok, linhas
            assert [l.split()[1] for l in linhas[:5]] == ["conectar", "criar", "desenhar", "ler", "salvar"]
            assert linhas[-1].startswith("TUDO OK: 5/5")
            # sem Aseprite: para no primeiro passo e diz FALHA
            await ase.fechar()
            await asyncio.sleep(0.2)
            linhas.clear()
            ok = await teste_vivo.rodar(chamar, arquivo=tmp_path / "tv2.aseprite", espera_conexao=0.5,
                                        imprimir=linhas.append)
            assert not ok and linhas[0].startswith("FALHA conectar") and linhas[-1].startswith("FALHOU: 0/5")
        finally:
            await fim()
    rodar(corpo())
