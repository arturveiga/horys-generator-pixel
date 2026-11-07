"""Núcleo: horysd + Aseprite falso + ponte MCP, de ponta a ponta (sem interface)."""
import asyncio
import json

import numpy as np

from horys_pixel import auth, config, pixels
from horys_pixel.daemon import servidor
from horys_pixel.daemon.contexto import Contexto
from horys_pixel.mcp_ponte import Daemon

from aseprite_falso import AsepriteFalso


def rodar(coro, limite=240):
    return asyncio.run(asyncio.wait_for(coro, limite))


def test_hmac_rfc4231_caso2():
    import hashlib, hmac
    esperado = "5bdcc146bf60754e6a042426089575c75a003f089d2739839dec58b964ec3843"
    assert hmac.new(b"Jefe", b"what do ya want for nothing?", hashlib.sha256).hexdigest() == esperado
    t, n = "ab" * 24, auth.nonce()
    assert auth.confere(t, n, auth.prova(t, n)) and not auth.confere(t, n, "00")


def test_mapa_ida_e_volta():
    pal = {"k": "#18122c", "r": "#b13e53", "x": "#00000000"}
    rgba, m = pixels.compor_mapa(pal, ["..kk", ".krk", "x.k."])
    assert rgba.shape == (3, 4, 4) and m.sum() == 7
    assert tuple(rgba[1, 2]) == (0xb1, 0x3e, 0x53, 255)
    assert m[2, 0] == 1 and rgba[2, 0, 3] == 0          # apagar
    pal2, linhas, _ = pixels.para_linhas(rgba, {"k": "#18122c"})
    assert linhas[0] == "..kk" and pal2["k"] == "#18122c"


def test_carimbos_espelhados():
    rgba, m = pixels.compor_mapa({"a": "#ffffff"}, [], {"o": {"rows": ["a.", "aa"]}}, [["o", 0, 0], ["o", 3, 0, "h"]])
    assert m[0].tolist() == [1, 0, 0, 0, 1] and m[1].tolist() == [1, 1, 0, 1, 1]


async def _ambiente(porta):
    ctx = Contexto()
    pronto = asyncio.Event()
    srv = asyncio.ensure_future(servidor.principal(porta, pronto, ctx))
    await pronto.wait()
    ase = AsepriteFalso(porta, config.token())
    await ase.conectar()
    for _ in range(50):
        if ctx.ponte.conectado:
            break
        await asyncio.sleep(0.02)
    cli = Daemon()
    await cli.garantir()

    async def chamar(_ferramenta, **args):
        r = await cli.enviar({"t": "chamar", "ferramenta": _ferramenta, "args": args})
        return r

    async def fim():
        await cli.fechar()
        await ase.fechar()
        srv.cancel()
        try:
            await srv
        except BaseException:
            pass

    return ctx, ase, chamar, fim


def _txt(r):
    return "\n".join(c.get("text", "") for c in r["conteudo"] if c["type"] == "text")


def test_ponta_a_ponta_desenho(ambiente):
    async def corpo():
        ctx, ase, chamar, fim = await _ambiente(ambiente)
        try:
            assert ase.config["tipos"] and "motores" in ase.config
            cli = Daemon()
            lst = await cli.enviar({"t": "listar"})
            await cli.fechar()
            nomes = {f["name"] for f in lst["ferramentas"]}
            assert {"horys_pixel_map", "horys_perguntar", "horys_aguardar", "horys_ver"} <= nomes
            r = await chamar("horys_sprite_novo", largura=16, altura=16)
            assert not r["erro"], r
            r = await chamar("horys_pixel_map", paleta={"k": "#18122c", "r": "#b13e53"},
                             linhas=["kkk", "krk", "kkk"], x=2, y=3, camada="corpo")
            assert not r["erro"] and "9 pixels" in _txt(r)
            r = await chamar("horys_ler_pixels", camada="corpo", paleta={"k": "#18122c"})
            t = _txt(r)
            assert "..kkk" in t and "..k" in t
            r = await chamar("horys_ver", critica=True)
            assert any(c["type"] == "image" for c in r["conteudo"])
            # mudanças: 1ª marca, depois o "usuário" pinta
            await chamar("horys_mudancas")
            s = ase.atual
            s.img("corpo", 0)[0, 0] = (255, 255, 255, 255)
            r = await chamar("horys_mudancas")
            assert "'corpo' quadro 0: 1 px" in _txt(r)
            # desfazer
            await chamar("horys_desfazer")
            # erro vira isError com mensagem
            r = await chamar("horys_pixel_map", paleta={}, linhas=["z"])
            assert r["erro"] and "sem cor" in _txt(r)
        finally:
            await fim()
    rodar(corpo())


def test_perguntar_aguardar_e_gosto(ambiente):
    async def corpo():
        ctx, ase, chamar, fim = await _ambiente(ambiente)
        try:
            r = await chamar("horys_perguntar", perguntas=[{"pergunta": "Como ataca?", "cabecalho": "Ataque",
                                                            "opcoes": [{"rotulo": "Machado (recomendado)"},
                                                                       {"rotulo": "Lança"}]}])
            i = _txt(r).split("id: ")[1].split()[0]
            assert ase.ui and ase.ui[-1][0] == "ui_perguntar" and ase.ui[-1][1]["id"] == i
            r = await chamar("horys_aguardar", id=i, segundos=1)
            assert "pendente" in _txt(r)
            await ase.evento(tipo="resposta", id=i, respostas={"Como ataca?": "Lança"})
            r = await chamar("horys_aguardar", id=i, segundos=5)
            assert json.loads(_txt(r))["resposta"] == {"Como ataca?": "Lança"}
            # aprovação com estilo vira memória de gosto
            await chamar("horys_sprite_novo", largura=8, altura=8)
            r = await chamar("horys_aprovar", titulo="Silhueta", estilo="teste", etapa="silhueta", sprite=True)
            i = _txt(r).split("id: ")[1].split()[0]
            assert ase.ui[-1][0] == "ui_aprovar" and "imagem_rgba" in ase.ui[-1][1]
            await ase.evento(tipo="aprovacao", id=i, aprovado=False, comentario="olho de 1 px")
            await chamar("horys_aguardar", id=i, segundos=5)
            r = await chamar("horys_gosto_consultar", estilo="teste")
            assert "1 recusas" in _txt(r) and "olho de 1 px" in _txt(r)
        finally:
            await fim()
    rodar(corpo())


def test_pedido_atualizar_vai_ao_painel(ambiente):
    async def corpo():
        ctx, ase, chamar, fim = await _ambiente(ambiente)
        try:
            r = await chamar("horys_pedido_novo", descricao="viking", motor="claude", iniciar=False)
            pid = _txt(r).split("pedido ")[1].split()[0]
            r = await chamar("horys_pedido_atualizar", id=pid, etapa="briefing", texto="perguntando", nota=10)
            await asyncio.sleep(0.2)
            assert any(c == "ui_progresso" and a["pedido"] == pid for c, a in ase.ui)
            r = await chamar("horys_pedido", id=pid)
            assert json.loads(_txt(r))["etapa"] == "briefing"
        finally:
            await fim()
    rodar(corpo())


def test_token_errado_recusado(ambiente):
    async def corpo():
        ctx = Contexto()
        pronto = asyncio.Event()
        srv = asyncio.ensure_future(servidor.principal(ambiente, pronto, ctx))
        await pronto.wait()
        ase = AsepriteFalso(ambiente, "errado" * 8)
        try:
            await ase.conectar()
            assert False, "devia recusar"
        except AssertionError as e:
            assert "recusado" in str(e)
        finally:
            srv.cancel()
    rodar(corpo())


def test_pedido_sem_motor_usa_o_padrao(casa_temp):
    from horys_pixel.daemon.contexto import Contexto
    ctx = Contexto()
    p = ctx.pedidos.novo({"descricao": "revisar", "motor": None, "estilo": ""}, "revisao")
    assert p["motor"] == config.preferencias()["motor_padrao"]
    assert p["estilo"] == config.preferencias()["estilo_padrao"]
