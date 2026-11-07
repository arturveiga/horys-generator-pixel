"""Ferramentas de treino: repassam para a CLI `python -m horys_pixel.treino` (kohya-ss/sd-scripts)."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from .registro import BOOL, STR, ErroFerramenta, ferramenta, texto

SRC = Path(__file__).resolve().parents[2]
COMANDOS = ["gpu", "perfil", "instalar", "preparar", "configurar", "treinar", "avaliar", "notas", "promover", "gerar"]


async def rodar_cli(argumentos: list[str], timeout: float = 600) -> tuple[int, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    proc = await asyncio.create_subprocess_exec(sys.executable, "-m", "horys_pixel.treino", *argumentos,
                                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
                                                env=env)
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return 124, "tempo esgotado"
    return proc.returncode, out.decode("utf-8", "replace")


@ferramenta("horys_treino_status", "Treino do estilo: GPU detectada, perfil (SD 1.5 / SDXL) e se o kohya está "
            "instalado. Só lê; não baixa nem treina.", {"estilo": STR})
async def treino_status(ctx, a):
    _, gpu = await rodar_cli(["gpu"], 60)
    _, perfil = await rodar_cli(["perfil"], 60)
    return [texto(gpu.strip() + "\n\n" + perfil.strip())]


@ferramenta("horys_treino", f"""Roda um passo do treino do estilo (CLI python -m horys_pixel.treino): 'comando' em
{', '.join(COMANDOS)} e 'args' (lista de argumentos da CLI, ex. ["--estilo", "horys-pixel-liso"]). Tudo que baixa,
treina ou gera imagem só acontece com 'executar': true — PEÇA O SIM DO USUÁRIO antes (horys_perguntar): instalar
baixa de 3 a 5 GB e treinar ocupa a GPU por quase uma hora.""",
            {"comando": STR, "args": {"type": "array", "items": STR}, "executar": BOOL}, ["comando"])
async def treino(ctx, a):
    cmd = a["comando"]
    if cmd not in COMANDOS:
        raise ErroFerramenta(f"comando inválido: {cmd} (use {', '.join(COMANDOS)})")
    argumentos = [cmd] + [str(x) for x in a.get("args") or []]
    if any(x.startswith("--") and "--executar".startswith(x.split("=", 1)[0]) for x in argumentos[1:]):
        raise ErroFerramenta("use o campo 'executar', não --executar em args")
    if a.get("executar") and cmd in ("instalar", "treinar", "avaliar", "gerar"):
        argumentos.append("--executar")
    timeout = 6 * 3600 if a.get("executar") else 600
    codigo, saida = await rodar_cli(argumentos, timeout)
    return [texto(f"(código {codigo})\n" + saida[-6000:])]
