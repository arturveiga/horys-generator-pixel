"""Teste rápido ao vivo (perfeicao.md §11 item 8): conectar, criar, desenhar, ler, salvar.

Uso: `horys teste-vivo` com o Aseprite aberto. Fala com o horysd pelo mesmo caminho das ferramentas MCP e imprime
OK/FALHA por passo, com o tempo de cada um. Deixa aberta no Aseprite uma aba 'horys-teste-vivo' (8×8) e grava
~/.horys-pixel/temp/teste-vivo.aseprite.
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Awaitable, Callable

from . import config

PALETA = {"k": "#18122c", "r": "#b13e53"}
LINHAS = ["kr", "rk"]

Chamar = Callable[..., Awaitable[dict]]


def _texto(r: dict) -> str:
    return "\n".join(c.get("text", "") for c in r.get("conteudo") or [] if c.get("type") == "text")


async def rodar(chamar: Chamar, arquivo: Path | None = None, espera_conexao: float = 12.0,
                imprimir: Callable[[str], None] = print) -> bool:
    """`chamar(ferramenta, **args)` devolve {'conteudo': [...], 'erro': bool}. Devolve True se tudo passou."""
    arquivo = Path(arquivo or (config.pasta("temp") / "teste-vivo.aseprite"))
    resultados: list[tuple[str, bool, str, float]] = []

    async def passo(nome: str, fn) -> bool:
        t0 = time.monotonic()
        try:
            ok, info = await fn()
        except Exception as e:  # o teste nunca derruba: registra a falha e segue para o relatório
            ok, info = False, f"{type(e).__name__}: {e}"
        dt = time.monotonic() - t0
        resultados.append((nome, ok, info, dt))
        imprimir(f"{'OK   ' if ok else 'FALHA'} {nome:<9} {dt:5.1f} s  {info.splitlines()[0] if info else ''}")
        if not ok and info and len(info.splitlines()) > 1:
            imprimir("      " + "\n      ".join(info.splitlines()[1:]))
        return ok

    async def conectar():
        fim = time.monotonic() + espera_conexao
        while True:
            r = await chamar("horys_status")
            t = _texto(r)
            if not r.get("erro") and "NÃO conectado" not in t:
                return True, "horysd e Aseprite conectados"
            if time.monotonic() >= fim:
                return False, t or "sem resposta do horys_status"
            await asyncio.sleep(1.0)

    async def criar():
        r = await chamar("horys_sprite_novo", largura=8, altura=8, nome="horys-teste-vivo")
        t = _texto(r)
        return (not r.get("erro") and "8×8" in t), t

    async def desenhar():
        r = await chamar("horys_pixel_map", paleta=PALETA, linhas=LINHAS, x=1, y=1, camada="desenho")
        t = _texto(r)
        return (not r.get("erro") and "4 pixels" in t), t

    async def ler():
        r = await chamar("horys_ler_pixels", camada="desenho", paleta=PALETA)
        t = _texto(r)
        ok = not r.get("erro") and ".kr" in t and ".rk" in t
        return ok, ("pixels lidos batem com o desenho" if ok else t)

    async def salvar():
        r = await chamar("horys_salvar", arquivo=str(arquivo), sobrescrever=True)
        t = _texto(r)
        if r.get("erro"):
            return False, t
        if not arquivo.is_file():
            return False, f"o horys_salvar respondeu, mas {arquivo} não existe ({t})"
        return True, f"{arquivo} ({arquivo.stat().st_size} bytes)"

    if await passo("conectar", conectar):
        for nome, fn in (("criar", criar), ("desenhar", desenhar), ("ler", ler), ("salvar", salvar)):
            if not await passo(nome, fn):
                break
    total = sum(r[3] for r in resultados)
    ok = len(resultados) == 5 and all(r[1] for r in resultados)
    imprimir(f"{'TUDO OK' if ok else 'FALHOU'}: {sum(r[1] for r in resultados)}/5 passos em {total:.1f} s")
    return ok


def main() -> int:
    from .mcp_ponte import Daemon

    async def ir():
        d = Daemon()
        try:
            async def chamar(nome, **args):
                return await d.enviar({"t": "chamar", "ferramenta": nome, "args": args}, timeout=240)
            return await rodar(chamar)
        finally:
            await d.fechar()
    try:
        return 0 if asyncio.run(ir()) else 1
    except Exception as e:
        print(f"FALHA horysd    fora do ar ou recusou: {e}")
        return 2
