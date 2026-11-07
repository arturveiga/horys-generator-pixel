"""Detecção da GPU NVIDIA via ``nvidia-smi`` (sem torch, sem rede)."""

from __future__ import annotations

import subprocess
from typing import Callable

CONSULTA = [
    "nvidia-smi",
    "--query-gpu=name,memory.total,driver_version",
    "--format=csv,noheader,nounits",
]


def interpretar(saida: str) -> list[dict]:
    """Converte a saída CSV do nvidia-smi em ``[{"nome", "vram_mb", "driver"}]`` (uma por placa)."""
    gpus = []
    for linha in (saida or "").splitlines():
        linha = linha.strip()
        if not linha:
            continue
        partes = [p.strip() for p in linha.rsplit(",", 2)]  # o nome pode ter vírgula; os outros não
        if len(partes) != 3 or not partes[0]:
            continue
        nome, memoria, driver = partes
        try:
            vram = int(float(memoria))
        except ValueError:  # "[N/A]" e afins
            vram = None
        gpus.append({"nome": nome, "vram_mb": vram, "driver": driver or None})
    return gpus


def listar(rodar: Callable | None = None, timeout: float = 15) -> list[dict]:
    """Todas as GPUs NVIDIA visíveis; lista vazia se o nvidia-smi não existir ou falhar."""
    rodar = rodar or subprocess.run
    try:
        r = rodar(CONSULTA, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError, ValueError):
        return []
    if getattr(r, "returncode", 1) != 0:
        return []
    return interpretar(getattr(r, "stdout", "") or "")


def detectar(rodar: Callable | None = None) -> dict | None:
    """A GPU com mais VRAM (``{"nome", "vram_mb", "driver"}``) ou ``None`` se não houver NVIDIA."""
    gpus = [g for g in listar(rodar) if g.get("vram_mb")]
    if not gpus:
        return None
    return max(gpus, key=lambda g: g["vram_mb"])


def descrever(gpu: dict | None) -> str:
    if not gpu:
        return (
            "Nenhuma GPU NVIDIA encontrada (nvidia-smi ausente ou sem placa). "
            "Dá para usar a memória de gosto; para treinar, use uma GPU alugada e traga o LoRA."
        )
    return f"{gpu['nome']} — {gpu['vram_mb']} MB de VRAM, driver {gpu.get('driver') or '?'}"
