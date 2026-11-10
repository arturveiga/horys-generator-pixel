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


def _png(caminho, cor=(200, 40, 40, 255)):
    from PIL import Image
    caminho.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (8, 8), cor).save(caminho)


def test_esperar_imagem_pela_pasta_e_pelo_painel(ambiente):
    async def corpo():
        ctx, ase, chamar, fim = await _ambiente(ambiente)
        try:
            pasta = config.casa() / "pedidos" / "macaco"
            trad = pasta / "traducao" / "prompt.md"
            trad.parent.mkdir(parents=True, exist_ok=True)
            trad.write_text("1. gorila de pedra\n2. fundo verde liso", encoding="utf-8")
            _png(pasta / "entrada" / "velha.png")          # já estava lá: não conta
            r = await chamar("horys_esperar_imagem", arquivo_prompt=str(trad))
            assert not r["erro"], r
            i = _txt(r).split("id: ")[1].split()[0]
            cmd, a = ase.ui[-1]
            assert cmd == "ui_imagem" and a["id"] == i and "gorila de pedra" in a["prompt"]
            assert a["pasta"] == str(pasta / "entrada")
            r = await chamar("horys_aguardar", id=i, segundos=1)
            assert "pendente" in _txt(r)
            _png(pasta / "entrada" / "gerada.png")
            r = await chamar("horys_aguardar", id=i, segundos=10)
            resp = json.loads(_txt(r))["resposta"]
            assert resp["imagem"] == str(pasta / "entrada" / "gerada.png") and resp["origem"] == "pasta"
            await asyncio.sleep(0.2)
            assert ("ui_fechar", {"id": i}) in ase.ui
            # pelo painel: o arquivo escolhido fora é copiado para entrada/
            r = await chamar("horys_esperar_imagem", prompt="outro", pasta=str(pasta))
            i = _txt(r).split("id: ")[1].split()[0]
            fora = config.casa() / "downloads" / "chatgpt.png"
            _png(fora)
            await ase.evento(tipo="imagem", id=i, caminho=str(fora))
            resp = json.loads(_txt(await chamar("horys_aguardar", id=i, segundos=5)))["resposta"]
            assert resp["origem"] == "painel" and resp["imagem"] == str(pasta / "entrada" / "chatgpt.png")
            assert (pasta / "entrada" / "chatgpt.png").exists()
            r = await chamar("horys_esperar_imagem", pasta=str(pasta))
            assert r["erro"] and "prompt" in _txt(r)
        finally:
            await fim()
    rodar(corpo())


def test_novas_imagens_ignora_as_antigas(tmp_path):
    from horys_pixel.daemon.conversa import novas_imagens, retrato_pasta
    _png(tmp_path / "a.png")
    (tmp_path / "nota.txt").write_text("x")
    antes = retrato_pasta(tmp_path)
    assert novas_imagens(tmp_path, antes) == []
    _png(tmp_path / "b.webp")
    assert [p.name for p in novas_imagens(tmp_path, antes)] == ["b.webp"]


def test_entrega_mostra_acabamento_no_painel(ambiente):
    async def corpo():
        ctx, ase, chamar, fim = await _ambiente(ambiente)
        try:
            await chamar("horys_sprite_novo", largura=16, altura=16)
            res = {"aceitacao": 85, "criterios": [
                {"id": "L5", "resultado": "falha", "severidade": "leve", "classe": "acabamento", "onde": "3,4",
                 "correcao": "pelo do ombro em degraus"},
                {"id": "L2", "resultado": "passa", "severidade": "grave"}]}
            r = await chamar("horys_entrega", resultado=res)
            assert not r["erro"], r
            t = _txt(r)
            assert "PRONTO PARA ENTREGA" in t
            i = t.split("id: ")[1].split()[0]
            cmd, a = next(x for x in reversed(ase.ui) if x[0] == "ui_acabamento")
            assert a["id"] == i and a["itens"] == [{"id": "L5", "onde": "3,4", "correcao": "pelo do ombro em degraus"}]
            await ase.evento(tipo="acabamento", id=i, feitos=["L5"], total=1, comentario="feito")
            resp = json.loads(_txt(await chamar("horys_aguardar", id=i, segundos=5)))["resposta"]
            assert resp == {"feitos": ["L5"], "total": 1, "comentario": "feito"}
            # não pronto: sem lista no painel
            n = sum(1 for c, _ in ase.ui if c == "ui_acabamento")
            res["aceitacao"] = 60
            await chamar("horys_entrega", resultado=res)
            assert sum(1 for c, _ in ase.ui if c == "ui_acabamento") == n
        finally:
            await fim()
    rodar(corpo())
