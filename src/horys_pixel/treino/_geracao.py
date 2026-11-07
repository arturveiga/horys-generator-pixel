"""Geração de imagens com o script do sd-scripts (gen_img.py), com ou sem LoRA.

Usa um arquivo de prompts (``--from_file``) com opções por linha do sd-scripts: ``--n`` (negativo),
``--d`` (seed), ``--w``/``--h`` (tamanho). Os arquivos saem com nome sequencial (``--sequential_file_name``),
então a ordem dos PNGs gerados é a ordem das linhas.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import kohya
from ._comum import ErroTreino, env_kohya, listar_pngs, rodar_com_log
from .perfis import Perfil

NEGATIVO = (
    "blurry, smooth shading, gradient, antialiasing, 3d render, photo, realistic, jpeg artifacts, "
    "noise, text, watermark, signature, frame, cropped"
)
PASSOS = 28
ESCALA = 7.0
SAMPLER = "euler_a"


def limpar_prompt(texto: str) -> str:
    """Tira quebras de linha e ``--`` (que o sd-scripts leria como opção) do texto do prompt."""
    texto = re.sub(r"\s+", " ", texto.replace("--", "-")).strip()
    if not texto:
        raise ErroTreino("prompt vazio")
    return texto


def linha_prompt(prompt: str, seed: int, resolucao: int, negativo: str = NEGATIVO) -> str:
    return f"{limpar_prompt(prompt)} --n {limpar_prompt(negativo)} --d {int(seed)} --w {resolucao} --h {resolucao}"


def escrever_prompts(arquivo: Path, linhas: list[str]) -> Path:
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return arquivo


def comando(
    perfil: Perfil,
    modelo_base: Path | str,
    arquivo_prompts: Path | str,
    pasta_saida: Path | str,
    lora: Path | str | None = None,
    peso_lora: float = 1.0,
    python: Path | str | None = None,
) -> list[str]:
    script = kohya.script_geracao(perfil.familia)
    cmd = [str(python or kohya.python_kohya()), str(script)]
    if perfil.sdxl and script.name == "gen_img.py":
        cmd.append("--sdxl")
    cmd += [
        "--ckpt", str(modelo_base),
        "--outdir", str(pasta_saida),
        "--from_file", str(arquivo_prompts),
        "--images_per_prompt", "1",
        "--sequential_file_name",
        "--sampler", SAMPLER,
        "--steps", str(PASSOS),
        "--scale", str(ESCALA),
        "--W", str(perfil.resolucao),
        "--H", str(perfil.resolucao),
        "--batch_size", "1",
        "--sdpa",
        "--fp16",
    ]
    if perfil.sdxl:
        cmd.append("--no_half_vae")  # o VAE do SDXL em fp16 tende a dar imagem preta
    if lora:
        cmd += ["--network_module", "networks.lora", "--network_weights", str(lora), "--network_mul", str(peso_lora)]
    return cmd


def rodar(cmd: list[str], pasta_saida: Path, log: Path, esperadas: int, eco: bool = True) -> list[Path]:
    """Roda a geração e devolve os PNGs novos em ``pasta_saida`` (em ordem)."""
    pasta_saida.mkdir(parents=True, exist_ok=True)
    antes = set(listar_pngs(pasta_saida))
    cwd = kohya.pasta_repo() if kohya.pasta_repo().is_dir() else None
    codigo = rodar_com_log(cmd, log, cwd=cwd, env=env_kohya(), eco=eco)
    novas = [p for p in listar_pngs(pasta_saida) if p not in antes]
    if codigo != 0:
        raise ErroTreino(f"a geração falhou (código {codigo}). Veja o log: {log}")
    if len(novas) != esperadas:
        raise ErroTreino(f"esperava {esperadas} imagens e saíram {len(novas)} em {pasta_saida}. Veja o log: {log}")
    return novas
