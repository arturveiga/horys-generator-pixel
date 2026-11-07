"""Coisas que esperam alguém: perguntas, aprovações e tarefas (revisões, motores).

Cada item tem um id. Quem cria devolve o id na hora; `aguardar` espera em fatias curtas,
para nenhum cliente MCP estourar o tempo limite de uma chamada.
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from pathlib import Path

from .. import config


class Pendencias:
    def __init__(self):
        self.itens: dict[str, dict] = {}
        self._eventos: dict[str, asyncio.Event] = {}
        self.ouvintes = []           # funções chamadas quando algo é resolvido: f(item)
        self._log = config.pasta("logs") / "conversa.jsonl"

    def criar(self, tipo: str, dados: dict, prefixo: str | None = None) -> str:
        i = f"{prefixo or tipo}-{uuid.uuid4().hex[:8]}"
        self.itens[i] = {"id": i, "tipo": tipo, "dados": dados, "criado": time.time(), "estado": "pendente",
                         "resposta": None}
        self._eventos[i] = asyncio.Event()
        self._registrar({"evento": "criado", "id": i, "tipo": tipo, "dados": dados})
        return i

    def resolver(self, i: str, resposta, estado: str = "respondido") -> bool:
        it = self.itens.get(i)
        if it is None:
            return False
        it["resposta"] = resposta
        it["estado"] = estado
        it["resolvido"] = time.time()
        ev = self._eventos.get(i)
        if ev:
            ev.set()
        self._registrar({"evento": estado, "id": i, "resposta": resposta})
        for f in list(self.ouvintes):
            try:
                f(it)
            except Exception:
                pass
        return True

    def obter(self, i: str) -> dict | None:
        return self.itens.get(i)

    async def aguardar(self, i: str, timeout: float = 45.0) -> dict:
        it = self.itens.get(i)
        if it is None:
            return {"id": i, "estado": "desconhecido"}
        if it["estado"] == "pendente":
            try:
                await asyncio.wait_for(self._eventos[i].wait(), timeout)
            except asyncio.TimeoutError:
                pass
        return {k: v for k, v in it.items() if k != "dados"} | {"tipo": it["tipo"]}

    def pendentes(self, tipo: str | None = None) -> list[dict]:
        return [it for it in self.itens.values() if it["estado"] == "pendente" and (tipo is None or it["tipo"] == tipo)]

    def _registrar(self, d: dict):
        try:
            with open(self._log, "a", encoding="utf-8") as f:
                f.write(json.dumps({"t": time.time(), **d}, ensure_ascii=False, default=str) + "\n")
        except OSError:
            pass
