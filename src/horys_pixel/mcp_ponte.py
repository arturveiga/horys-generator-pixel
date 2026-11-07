"""horys-mcp: ponte stdio fina entre um cliente MCP (Claude Code, Codex) e o horysd.

Cada cliente inicia a sua ponte; todas falam com o mesmo horysd (que é o único ligado ao Aseprite).
Se o horysd não estiver rodando, a ponte o inicia em segundo plano.
"""
from __future__ import annotations

import asyncio
import itertools
import json
import os
import subprocess
import sys
from pathlib import Path

import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from websockets.asyncio.client import connect

from . import auth, config

INSTRUCOES = """horys-pixel: pixel art desenhada AO VIVO no Aseprite do usuário, no estilo dele (pacotes de estilo).
Coordenadas 0-based, (0,0) no canto de cima à esquerda; quadros e camadas 0-based.
Fluxo de asset: siga a skill horys-pixel (SKILL.md do repo horys-pixel). Revisão avulsa: skill horys-pixel-review.
Barato em tokens: horys_pixel_map (paleta + linhas; dado grande em 'arquivo' .json), horys_lote para juntar passos,
horys_ver com critica para julgar (cor, cinza, silhueta, 1×), horys_ler_pixels para editar só as linhas erradas.
Perguntas e aprovações ao usuário: horys_perguntar / horys_aprovar + horys_aguardar (painel no Aseprite).
Estilo: horys_asset_novo, horys_contorno, horys_converter, horys_limpar, horys_portao, horys_exportar,
horys_revisar (revisor do outro motor). Personagem modular (horys_asset_novo preset_partes): referência oculta →
horys_partes_recortar → horys_partes_estender → horys_partes_checar (etapa 'partes', obrigatória antes de animar). Nunca invente forma por script: só limpeza mecânica."""

SRC = Path(__file__).resolve().parents[1]


class Daemon:
    def __init__(self):
        self.ws = None
        self._ids = itertools.count(1)
        self._espera: dict[int, asyncio.Future] = {}
        self._leitor = None
        self._lock = asyncio.Lock()

    async def _abrir(self):
        token = config.token()
        ws = await connect(f"ws://127.0.0.1:{config.porta()}/", max_size=64 * 2 ** 20, open_timeout=5)
        des = json.loads(await asyncio.wait_for(ws.recv(), 10))
        meu = auth.nonce()
        await ws.send(json.dumps({"t": "ola", "papel": "mcp", "versao": "ponte", "nonce": meu,
                                  "prova": auth.prova(token, des["nonce"])}))
        boas = json.loads(await asyncio.wait_for(ws.recv(), 10))
        if boas.get("t") != "bem_vindo" or not auth.confere(token, meu, boas.get("prova")):
            await ws.close()
            raise ConnectionError("o horysd recusou o token (ou não provou o dele). `horys token` nos dois lados.")
        self.ws = ws
        self._leitor = asyncio.ensure_future(self._ler())

    async def _ler(self):
        try:
            async for bruto in self.ws:
                m = json.loads(bruto)
                f = self._espera.pop(m.get("id"), None)
                if f and not f.done():
                    f.set_result(m)
        except Exception:
            pass
        finally:
            self.ws = None
            for f in self._espera.values():
                if not f.done():
                    f.set_exception(ConnectionError("o horysd caiu"))
            self._espera.clear()

    async def garantir(self):
        async with self._lock:
            if self.ws is not None:
                return
            try:
                await self._abrir()
                return
            except (OSError, asyncio.TimeoutError):
                iniciar_daemon()
            for _ in range(40):
                await asyncio.sleep(0.25)
                try:
                    await self._abrir()
                    return
                except (OSError, asyncio.TimeoutError):
                    continue
            raise ConnectionError("não consegui iniciar o horysd (veja ~/.horys-pixel/logs/horysd.log)")

    async def fechar(self):
        if self.ws is not None:
            try:
                await self.ws.close()
            except Exception:
                pass
        if self._leitor:
            self._leitor.cancel()

    async def enviar(self, msg: dict, timeout: float = 600) -> dict:
        for tentativa in (1, 2):
            await self.garantir()
            i = next(self._ids)
            f = asyncio.get_running_loop().create_future()
            self._espera[i] = f
            try:
                await self.ws.send(json.dumps({**msg, "id": i}))
                return await asyncio.wait_for(f, timeout)
            except ConnectionError:
                if tentativa == 2:
                    raise
            except Exception:
                self._espera.pop(i, None)
                if tentativa == 2 or self.ws is not None:
                    raise


def iniciar_daemon():
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
    exe = sys.executable
    kw = {}
    if os.name == "nt":
        pw = Path(exe).with_name("pythonw.exe")
        if pw.exists():
            exe = str(pw)
        kw["creationflags"] = 0x00000008 | 0x00000200 | 0x08000000  # DETACHED | NEW_GROUP | NO_WINDOW
    else:
        kw["start_new_session"] = True
    subprocess.Popen([exe, "-m", "horys_pixel.daemon.servidor"], env=env, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True, **kw)


def _conteudo(c: dict):
    if c.get("type") == "image":
        return types.ImageContent(type="image", data=c["data"], mimeType=c.get("mimeType", "image/png"))
    return types.TextContent(type="text", text=str(c.get("text", "")))


def criar_servidor(d: Daemon) -> Server:
    srv = Server("horys", instructions=INSTRUCOES)

    @srv.list_tools()
    async def listar():
        r = await d.enviar({"t": "listar"}, timeout=30)
        return [types.Tool(name=f["name"], description=f["description"], inputSchema=f["inputSchema"])
                for f in r["ferramentas"]]

    @srv.call_tool(validate_input=False)
    async def chamar(nome: str, args: dict):
        r = await d.enviar({"t": "chamar", "ferramenta": nome, "args": args or {}})
        conteudo = [_conteudo(c) for c in r.get("conteudo") or []]
        if r.get("erro"):
            raise RuntimeError("\n".join(c.text for c in conteudo if isinstance(c, types.TextContent)) or "erro")
        return conteudo

    return srv


async def _principal():
    d = Daemon()
    srv = criar_servidor(d)
    async with stdio_server() as (leitura, escrita):
        await srv.run(leitura, escrita, srv.create_initialization_options())


def main():
    asyncio.run(_principal())


if __name__ == "__main__":
    main()
