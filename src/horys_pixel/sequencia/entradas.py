"""2.1 · Entradas do motor de sequência: pasta de PNGs, grade (PNG + linhas × colunas), vídeo (ffmpeg) ou atlas do
Kiln. Todas viram a mesma coisa: lista de quadros RGBA uint8."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image


class ErroEntrada(ValueError):
    pass


def _rgba(im: Image.Image) -> np.ndarray:
    return np.array(im.convert("RGBA"), dtype=np.uint8)


def de_pasta(pasta) -> list[np.ndarray]:
    arqs = sorted(p for p in Path(pasta).iterdir() if p.suffix.lower() in (".png", ".webp", ".jpg", ".jpeg"))
    if not arqs:
        raise ErroEntrada(f"nenhuma imagem em {pasta}")
    return [_rgba(Image.open(p)) for p in arqs]


def fatiar_grade(imagem: np.ndarray, linhas: int, colunas: int) -> list[np.ndarray]:
    """Fatia em células iguais, da esquerda para a direita e de cima para baixo."""
    if linhas < 1 or colunas < 1:
        raise ErroEntrada("grade é [linhas, colunas], ambos >= 1")
    h, w = imagem.shape[:2]
    ch, cw = h // linhas, w // colunas
    if ch < 1 or cw < 1:
        raise ErroEntrada("grade maior que a imagem")
    return [imagem[r * ch:(r + 1) * ch, c * cw:(c + 1) * cw].copy() for r in range(linhas) for c in range(colunas)]


def de_grade(png, linhas: int, colunas: int) -> list[np.ndarray]:
    return fatiar_grade(_rgba(Image.open(png)), int(linhas), int(colunas))


def de_video(video, fps: float | None = None) -> list[np.ndarray]:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise ErroEntrada("vídeo exige o ffmpeg no PATH (instale o ffmpeg ou entregue uma pasta de PNGs/uma grade)")
    with tempfile.TemporaryDirectory() as tmp:
        cmd = [exe, "-y", "-loglevel", "error", "-i", str(video)]
        if fps:
            cmd += ["-vf", f"fps={fps}"]
        cmd += [str(Path(tmp) / "%05d.png")]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise ErroEntrada("ffmpeg falhou: " + (r.stderr or "")[-400:])
        return de_pasta(tmp)


def de_atlas(json_path) -> list[np.ndarray]:
    from .. import kiln
    return [q.copy() for q in kiln.ler_atlas(json_path).quadros]


def carregar(fonte, linhas: int | None = None, colunas: int | None = None, fps: float | None = None) -> list[np.ndarray]:
    """Decide pela forma da fonte: diretório → pasta; .json → atlas do Kiln; vídeo → ffmpeg; PNG com grade → fatias;
    PNG sozinho → um quadro."""
    p = Path(fonte)
    if not p.exists():
        raise ErroEntrada(f"fonte não encontrada: {p}")
    if p.is_dir():
        return de_pasta(p)
    suf = p.suffix.lower()
    if suf == ".json":
        return de_atlas(p)
    if suf in (".mp4", ".mov", ".webm", ".mkv", ".avi", ".gif"):
        return de_video(p, fps)
    if linhas and colunas:
        return de_grade(p, linhas, colunas)
    return [_rgba(Image.open(p))]
