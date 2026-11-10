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

EXT_IMAGEM = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}


def retrato_pasta(pasta: Path) -> dict[str, tuple[float, int]]:
    """{nome: (mtime, tamanho)} das imagens que já estão na pasta."""
    out = {}
    if pasta.is_dir():
        for p in pasta.iterdir():
            if p.is_file() and p.suffix.lower() in EXT_IMAGEM:
                st = p.stat()
                out[p.name] = (st.st_mtime, st.st_size)
    return out


def novas_imagens(pasta: Path, antes: dict[str, tuple[float, int]]) -> list[Path]:
    """Imagens que não estavam em 'antes' ou foram regravadas depois, da mais recente para a mais antiga."""
    agora = retrato_pasta(pasta)
    novas = [n for n, v in agora.items() if antes.get(n) != v]
    return sorted((pasta / n for n in novas), key=lambda p: agora[p.name][0], reverse=True)


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

    async def vigiar_entrada(self, i: str, pasta: Path, ao_chegar=None, intervalo: float = 1.0,
                             limite_s: float = 6 * 3600):
        """Resolve a espera 'i' quando uma imagem nova (ou regravada) aparece em 'pasta' e para de crescer.
        Para sozinha se a espera for resolvida por outro caminho (painel) ou passar de 'limite_s'."""
        antes = retrato_pasta(pasta)
        tamanhos: dict[str, int] = {}
        t0 = time.time()
        while time.time() - t0 < limite_s:
            it = self.itens.get(i)
            if it is None or it["estado"] != "pendente":
                return
            await asyncio.sleep(intervalo)
            for p in novas_imagens(pasta, antes):
                try:
                    tam = p.stat().st_size
                except OSError:
                    continue
                if tam > 0 and tamanhos.get(p.name) == tam:      # parou de crescer: o gerador terminou de gravar
                    self.resolver(i, {"imagem": str(p), "origem": "pasta"})
                    if ao_chegar:
                        await ao_chegar(i)
                    return
                tamanhos[p.name] = tam

    def _registrar(self, d: dict):
        try:
            with open(self._log, "a", encoding="utf-8") as f:
                f.write(json.dumps({"t": time.time(), **d}, ensure_ascii=False, default=str) + "\n")
        except OSError:
            pass
