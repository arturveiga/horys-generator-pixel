"""Ponte com a extensão do Aseprite: pedidos (req/res) com id e espera."""
from __future__ import annotations

import asyncio
import itertools
import json
import logging

log = logging.getLogger("horys.ponte")


class AsepriteDesconectado(Exception):
    pass


class ErroAseprite(Exception):
    pass


class Ponte:
    def __init__(self):
        self.ws = None
        self.versao = None
        self._ids = itertools.count(1)
        self._espera: dict[int, asyncio.Future] = {}

    @property
    def conectado(self) -> bool:
        return self.ws is not None

    def ligar(self, ws, versao):
        if self.ws is not None and self.ws is not ws:
            log.info("outro Aseprite conectou; o anterior sai")
            asyncio.ensure_future(self._fechar(self.ws))
        self.ws = ws
        self.versao = versao

    async def _fechar(self, ws):
        try:
            await ws.close()
        except Exception:
            pass

    def desligar(self, ws):
        if self.ws is ws:
            self.ws = None
            for f in self._espera.values():
                if not f.done():
                    f.set_exception(AsepriteDesconectado("o Aseprite desconectou"))
            self._espera.clear()

    def chegou(self, msg: dict):
        f = self._espera.pop(msg.get("id"), None)
        if f is None or f.done():
            return
        if msg.get("ok"):
            f.set_result(msg.get("data") or {})
        else:
            f.set_exception(ErroAseprite(msg.get("erro") or "erro no Aseprite"))

    async def pedir(self, cmd: str, args: dict | None = None, timeout: float = 60.0) -> dict:
        if self.ws is None:
            raise AsepriteDesconectado(
                "o Aseprite não está conectado: abra o Aseprite com a extensão Horys "
                "(menu Horys › Conexão e painel) e confira o status")
        i = next(self._ids)
        f = asyncio.get_running_loop().create_future()
        self._espera[i] = f
        try:
            await self.ws.send(json.dumps({"t": "req", "id": i, "cmd": cmd, "args": args or {}}))
            return await asyncio.wait_for(f, timeout)
        except asyncio.TimeoutError:
            self._espera.pop(i, None)
            raise ErroAseprite(f"o Aseprite não respondeu '{cmd}' em {timeout:.0f} s. Se for a primeira vez, veja se há "
                               "uma janela 'Security' do Aseprite pedindo permissão para a extensão (Allow / "
                               "'Give full trust'); ou rode `horys instalar --confiar` com o Aseprite fechado")
        finally:
            self._espera.pop(i, None)
            if not f.done():
                f.cancel()
