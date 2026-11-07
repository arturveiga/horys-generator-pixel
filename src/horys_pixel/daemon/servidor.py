"""horysd: o servidor sempre ligado. Fala com a extensão do Aseprite e com as pontes MCP (Claude, Codex).

Uso: python -m horys_pixel.daemon.servidor [--porta N]   (ou `horys daemon`)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import traceback

from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

from .. import __version__, PROTOCOLO, auth, config
from ..ferramentas import registro
from .contexto import Contexto

log = logging.getLogger("horys.d")
MAX_MSG = 64 * 2 ** 20


async def _autenticar(ws, token: str) -> dict | None:
    n = auth.nonce()
    await ws.send(json.dumps({"t": "desafio", "nonce": n, "protocolo": PROTOCOLO}))
    try:
        ola = json.loads(await asyncio.wait_for(ws.recv(), 15))
    except (asyncio.TimeoutError, json.JSONDecodeError, ConnectionClosed) as e:
        log.info("handshake sem 'ola': %s: %s", type(e).__name__, e)
        return None
    if ola.get("t") != "ola" or not auth.confere(token, n, ola.get("prova")):
        log.info("handshake recusado: t=%s papel=%s (prova não confere com o token)", ola.get("t"), ola.get("papel"))
        try:
            await ws.send(json.dumps({"t": "recusado", "motivo": "token"}))
        except ConnectionClosed:
            pass
        return None
    return ola


async def _chamar(ctx: Contexto, nome: str, args: dict) -> tuple[list, bool]:
    registro.carregar_todas()
    f = registro.REGISTRO.get(nome)
    if f is None:
        return [registro.texto(f"ferramenta desconhecida: {nome}")], True
    try:
        return await f.funcao(ctx, args or {}), False
    except registro.ErroFerramenta as e:
        return [registro.texto(str(e))], True
    except Exception as e:  # erro inesperado: mensagem curta + log completo
        log.error("ferramenta %s falhou:\n%s", nome, traceback.format_exc())
        return [registro.texto(f"{type(e).__name__}: {e}")], True


async def _cliente_mcp(ws, ctx: Contexto):
    async for bruto in ws:
        msg = json.loads(bruto)
        t = msg.get("t")
        if t == "listar":
            await ws.send(json.dumps({"t": "ferramentas", "id": msg.get("id"), "ferramentas": registro.listar()}))
        elif t == "chamar":
            async def tarefa(m=msg):
                conteudo, erro = await _chamar(ctx, m.get("ferramenta"), m.get("args") or {})
                try:
                    await ws.send(json.dumps({"t": "resultado", "id": m.get("id"), "conteudo": conteudo,
                                              "erro": erro}))
                except ConnectionClosed:
                    pass
            asyncio.ensure_future(tarefa())


async def _cliente_aseprite(ws, ctx: Contexto, ola: dict):
    ctx.ponte.ligar(ws, ola.get("versao"))
    log.info("Aseprite conectado (extensão %s)", ola.get("versao"))

    async def pings():
        # a extensão usa isto para perceber conexão morta (o Aseprite nem sempre entrega o CLOSE)
        while True:
            await asyncio.sleep(10)
            try:
                await ws.send('{"t":"ping"}')
            except ConnectionClosed:
                return
    tarefa_ping = asyncio.ensure_future(pings())
    try:
        async for bruto in ws:
            msg = json.loads(bruto)
            t = msg.get("t")
            if t == "res":
                ctx.ponte.chegou(msg)
            elif t == "evt":
                try:
                    ctx.evento(msg)
                except Exception:
                    log.exception("evento falhou")
    finally:
        tarefa_ping.cancel()
        ctx.ponte.desligar(ws)
        log.info("Aseprite desconectou")


def fabrica(ctx: Contexto, token: str):
    async def atender(ws):
        ola = await _autenticar(ws, token)
        if ola is None:
            await ws.close()
            return
        papel = ola.get("papel")
        boas = {"t": "bem_vindo", "prova": auth.prova(token, str(ola.get("nonce") or "")), "versao": __version__}
        if papel == "aseprite":
            boas.update(ctx.config_extensao())
        await ws.send(json.dumps(boas))
        try:
            if papel == "aseprite":
                await _cliente_aseprite(ws, ctx, ola)
            elif papel == "mcp":
                await _cliente_mcp(ws, ctx)
        except ConnectionClosed:
            pass
    return atender


async def principal(porta: int, pronto: asyncio.Event | None = None, ctx: Contexto | None = None):
    token = config.token()
    ctx = ctx or Contexto()
    async with serve(fabrica(ctx, token), "127.0.0.1", porta, max_size=MAX_MSG, ping_interval=20,
                     ping_timeout=60) as srv:
        log.info("horysd %s ouvindo em 127.0.0.1:%d", __version__, porta)
        (config.casa() / "horysd.pid").write_text(str(os.getpid()))
        if pronto:
            pronto.set()
        await srv.serve_forever()


def configurar_log():
    arq = config.pasta("logs") / "horysd.log"
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s",
                        handlers=[logging.FileHandler(arq, encoding="utf-8"), logging.StreamHandler(sys.stderr)])


def main(argv=None):
    ap = argparse.ArgumentParser(prog="horysd", description=__doc__)
    ap.add_argument("--porta", type=int, default=0)
    a = ap.parse_args(argv)
    configurar_log()
    try:
        asyncio.run(principal(a.porta or config.porta()))
    except OSError as e:
        log.error("não consegui abrir a porta (%s). Outro horysd já está rodando? `horys status`", e)
        sys.exit(2)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
