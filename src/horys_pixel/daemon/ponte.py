"""Ponte com a extensão do Aseprite: pedidos (req/res) com id e espera.

Diagnóstico das quedas de 13/11 (perfeicao.md, C10):
- "não está conectado": o pedido falhava na hora se a extensão ainda não tinha (re)conectado. A extensão tenta de
  novo a cada 5 s, então o pedido agora espera a conexão por `ESPERA_CONEXAO` segundos antes de desistir.
- "não respondeu 'salvar' em 60 s": salvar pode abrir um alerta modal do Aseprite (formato sem camadas, animação em
  sequência...). A extensão agora desliga esses alertas; e cada comando tem o seu prazo (`PRAZOS`).
"""
from __future__ import annotations

import asyncio
import itertools
import json
import logging

from websockets.exceptions import ConnectionClosed

log = logging.getLogger("horys.ponte")

PRAZO_PADRAO = 60.0
# Comandos que gravam ou leem arquivo podem demorar mais (o 1º GIF da sessão leva dezenas de segundos).
PRAZOS = {"salvar": 180.0, "abrir": 120.0}
# Tempo que um pedido espera a extensão (re)conectar: ela tenta a cada 5 s.
ESPERA_CONEXAO = 12.0


class AsepriteDesconectado(Exception):
    pass


class ErroAseprite(Exception):
    pass


def prazo(cmd: str) -> float:
    return PRAZOS.get(cmd, PRAZO_PADRAO)


class Ponte:
    def __init__(self):
        self.ws = None
        self.versao = None
        self._ids = itertools.count(1)
        self._espera: dict[int, asyncio.Future] = {}
        self._ligada: asyncio.Event | None = None

    @property
    def conectado(self) -> bool:
        return self.ws is not None

    def _evento(self) -> asyncio.Event:
        if self._ligada is None:
            self._ligada = asyncio.Event()
            if self.ws is not None:
                self._ligada.set()
        return self._ligada

    def ligar(self, ws, versao):
        if self.ws is not None and self.ws is not ws:
            log.info("outro Aseprite conectou; o anterior sai")
            asyncio.ensure_future(self._fechar(self.ws))
        self.ws = ws
        self.versao = versao
        self._evento().set()

    async def _fechar(self, ws):
        try:
            await ws.close()
        except Exception:
            pass

    def desligar(self, ws):
        if self.ws is ws:
            self.ws = None
            self._evento().clear()
            for f in self._espera.values():
                if not f.done():
                    f.set_exception(AsepriteDesconectado("o Aseprite desconectou no meio do pedido"))
            self._espera.clear()

    def chegou(self, msg: dict):
        f = self._espera.pop(msg.get("id"), None)
        if f is None or f.done():
            return
        if msg.get("ok"):
            f.set_result(msg.get("data") or {})
        else:
            erro = msg.get("erro") or "erro no Aseprite"
            if str(erro).startswith("comando desconhecido"):
                erro += (" — a extensão instalada no Aseprite é mais antiga que o horysd: rode `horys instalar` "
                         "(com o Aseprite fechado) e abra o Aseprite de novo")
            f.set_exception(ErroAseprite(erro))

    async def aguardar_conexao(self, segundos: float) -> bool:
        if self.ws is not None:
            return True
        if segundos <= 0:
            return False
        try:
            await asyncio.wait_for(self._evento().wait(), segundos)
        except asyncio.TimeoutError:
            pass
        return self.ws is not None

    async def pedir(self, cmd: str, args: dict | None = None, timeout: float | None = None,
                    espera_conexao: float | None = None) -> dict:
        espera = ESPERA_CONEXAO if espera_conexao is None else espera_conexao
        if not await self.aguardar_conexao(espera):
            raise AsepriteDesconectado(
                f"o Aseprite não está conectado (esperei {espera:.0f} s): abra o Aseprite com a extensão Horys "
                "(menu Horys › Conexão e painel) e confira o status")
        timeout = prazo(cmd) if timeout is None else timeout
        i = next(self._ids)
        f = asyncio.get_running_loop().create_future()
        self._espera[i] = f
        try:
            await self.ws.send(json.dumps({"t": "req", "id": i, "cmd": cmd, "args": args or {}}))
            return await asyncio.wait_for(f, timeout)
        except ConnectionClosed:
            raise AsepriteDesconectado(f"o Aseprite desconectou durante '{cmd}'") from None
        except asyncio.TimeoutError:
            raise ErroAseprite(
                f"o Aseprite não respondeu '{cmd}' em {timeout:.0f} s. Veja se há uma janela ou alerta aberto no "
                "Aseprite esperando um clique (ex.: 'formato não suporta camadas', 'Security' pedindo permissão para "
                "a extensão: Allow / 'Give full trust'). O comando pode terminar depois que a janela fechar; "
                "confira com horys_status antes de repetir") from None
        finally:
            self._espera.pop(i, None)
            if not f.done():
                f.cancel()
