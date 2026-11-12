"""Recuperador de grade alternativo: o Sprite Fusion Pixel Snapper (CLI local do Hugo Duprez,
github.com/Hugo-Dz/spritefusion-pixel-snapper). Opcional: o horys não depende dele. Acha o executável em
HORYS_SNAPPER ou no PATH; sem ele, disponivel() é False e recuperar() explica como instalar. Serve para comparar
com o converter (motor/conceito.py) no portão: mesma imagem, duas grades nativas, o portão decide."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

NOMES = ("spritefusion-pixel-snapper", "spritefusion-pixel-snapper.exe")


class ErroSnapper(RuntimeError):
    pass


def achar_exe() -> str | None:
    env = os.environ.get("HORYS_SNAPPER")
    if env and Path(env).is_file():
        return env
    for nome in NOMES:
        achado = shutil.which(nome)
        if achado:
            return achado
    return None


def disponivel() -> bool:
    return achar_exe() is not None


def versao(exe: str | None = None) -> str:
    exe = exe or achar_exe()
    if not exe:
        raise ErroSnapper("Pixel Snapper não encontrado")
    r = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=30)
    v = (r.stdout or "").strip()
    if r.returncode != 0 or not v.startswith("spritefusion-pixel-snapper"):
        raise ErroSnapper(f"{exe} não parece o Pixel Snapper: {v or (r.stderr or '').strip()[:200]}")
    return v


def pixel_detectado(stdout: str) -> float | None:
    m = re.search(r"Pixel size:\s*([0-9.]+)\s*px", stdout or "")
    return float(m.group(1)) if m else None


def recuperar(imagem, saida, cores: int = 16, tamanho_pixel: float | None = None,
              paleta_hex: list[str] | None = None, exe: str | None = None) -> dict:
    """Roda o snapper: imagem ampliada → PNG nativo (1 px por pixel de arte) em 'saida'.
    Devolve {saida, largura, altura, tamanho_pixel (o detectado, se o CLI disser), versao, rgba}."""
    exe = exe or achar_exe()
    if not exe:
        raise ErroSnapper("Pixel Snapper não encontrado. Compile github.com/Hugo-Dz/spritefusion-pixel-snapper "
                          "(cargo build --release) e ponha o executável no PATH ou em HORYS_SNAPPER.")
    v = versao(exe)
    saida = Path(saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    cmd = [exe, str(imagem), str(saida), str(int(cores))]
    if tamanho_pixel:
        cmd += ["--pixel-size", str(tamanho_pixel)]
    if paleta_hex:
        cmd += ["--palette", ",".join(h.lstrip("#") for h in paleta_hex)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise ErroSnapper("snapper falhou: " + (r.stderr or "").strip()[:500])
    if not saida.is_file():
        raise ErroSnapper("snapper não gravou a imagem nativa")
    rgba = np.array(Image.open(saida).convert("RGBA"), dtype=np.uint8)
    return {"saida": str(saida), "largura": rgba.shape[1], "altura": rgba.shape[0],
            "tamanho_pixel": pixel_detectado(r.stdout), "versao": v, "rgba": rgba}
