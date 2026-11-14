"""Exigências de entrada de todo asset: uma imagem de referência EM PIXEL ART e o ÂNGULO de câmera.

Pedido do Artur (2026-11-13): nenhum asset começa sem referência em pixel art e sem ângulo declarado
(top-down, 3/4 top-down, lateral, isométrico...). A referência pode ser pixel art nativa (1×) ou ampliada
(blocos k×k, como a que o Codex/ChatGPT gera); ilustração lisa, foto ou render não servem.
"""
from __future__ import annotations

import math
import unicodedata
from pathlib import Path

import numpy as np
from PIL import Image

ANGULOS = {
    "top-down": "vista de cima, câmera a 90° (só topo de cabeça e ombros)",
    "3/4 top-down": "top-down 3/4 (RPG/Zelda): vê o topo e a frente, ~45–60°",
    "lateral": "vista de lado, plataforma/side-scroller",
    "frontal": "de frente, câmera na altura do olho (retrato, carta, luta)",
    "3/4 frontal": "três quartos de frente, câmera na altura do olho",
    "isometrico": "isométrico 2:1 (diagonal, sem ponto de fuga)",
}
_ALIASES = {
    "top down": "top-down", "topdown": "top-down", "pixel top": "top-down", "top": "top-down",
    "cima": "top-down", "vista de cima": "top-down", "aerea": "top-down",
    "3 4": "3/4 top-down", "3 4 top down": "3/4 top-down", "tres quartos": "3/4 top-down", "rpg": "3/4 top-down",
    "3 4 topdown": "3/4 top-down", "top down 3 4": "3/4 top-down",
    "side": "lateral", "lado": "lateral", "perfil": "lateral", "side view": "lateral", "plataforma": "lateral",
    "front": "frontal", "frente": "frontal",
    "3 4 frontal": "3/4 frontal", "3 4 front": "3/4 frontal",
    "iso": "isometrico", "isometric": "isometrico", "isometrica": "isometrico",
}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return " ".join("".join(c if c.isalnum() else " " for c in s).split())


def normalizar_angulo(valor: str | None) -> str:
    """Nome canônico do ângulo; ValueError com as opções se faltar ou não for reconhecido."""
    opcoes = "; ".join(f"'{k}' ({v})" for k, v in ANGULOS.items())
    if not valor or not str(valor).strip():
        raise ValueError("falta o ÂNGULO de câmera (obrigatório). Pergunte ao usuário. Opções: " + opcoes)
    n = _norm(valor)
    for k in ANGULOS:
        if n == _norm(k):
            return k
    if n in _ALIASES:
        return _ALIASES[n]
    raise ValueError(f"ângulo '{valor}' não reconhecido. Opções: " + opcoes)


def _escala_exata(arr: np.ndarray, maximo: int = 32) -> int:
    h, w = arr.shape[:2]
    g = math.gcd(h, w)
    for k in range(min(g, maximo), 1, -1):
        if g % k == 0:
            red = arr[::k, ::k]
            if np.array_equal(np.repeat(np.repeat(red, k, 0), k, 1), arr):
                return k
    return 1


def checar_pixel_art(caminho: str | Path, max_cores: int = 64) -> dict:
    """Diz se a imagem é pixel art (nativa ou ampliada). Devolve
    {ok, motivo, escala, cores, erro, tamanho_nativo}."""
    p = Path(caminho)
    if not p.exists():
        return {"ok": False, "motivo": f"imagem não existe: {p}"}
    im = Image.open(p).convert("RGBA")
    arr = np.asarray(im)
    a = arr[..., 3]
    vis = a > 0
    if not vis.any():
        return {"ok": False, "motivo": "imagem vazia (toda transparente)"}
    semi = float(((a > 0) & (a < 250)).sum()) / float(vis.sum())
    # 1) blocos exatos (pixel art nativa ou ampliada sem compressão)
    k = _escala_exata(arr)
    red = arr[::k, ::k] if k > 1 else arr
    if k > 1 or max(arr.shape[:2]) <= 256:
        rv = red[red[..., 3] > 0][:, :3]
        cores = len(np.unique(rv.reshape(-1, 3), axis=0))
        ok = bool(cores <= max_cores and semi <= 0.05)
        return {"ok": ok, "escala": k, "cores": cores, "erro": 0.0, "semitransparente": round(semi, 3),
                "tamanho_nativo": [red.shape[1], red.shape[0]],
                "motivo": "pixel art" + (" ampliada" if k > 1 else " nativa") if ok else
                (f"{cores} cores (máx. {max_cores})" if cores > max_cores else
                 f"{semi:.0%} de pixels semitransparentes (antialias/borrado)")}
    # 2) pixel art ampliada com ruído (gerador/JPEG): acha a grade e mede o quanto os blocos são lisos
    from .motor.conceito import amostrar_nativo, grade_nativa
    rgb = arr[..., :3].copy()
    rgb[~vis] = 0
    try:
        gx, gy = grade_nativa(rgb)
    except Exception as e:  # pragma: no cover
        return {"ok": False, "motivo": f"não achei grade de pixels ({e})"}
    coer = min(gx[0], gy[0])
    bloco = gx[1]
    nat = amostrar_nativo(rgb, gx, gy)
    ys = np.clip((np.arange(rgb.shape[0]) - gy[2]) / gy[1], 0, nat.shape[0] - 1).astype(int)
    xs = np.clip((np.arange(rgb.shape[1]) - gx[2]) / gx[1], 0, nat.shape[1] - 1).astype(int)
    recon = nat[ys][:, xs]
    erro = float(np.abs(recon - rgb.astype(float))[vis].mean())
    q = (nat[..., :3] // 16).reshape(-1, 3)
    _, cont = np.unique(q, axis=0, return_counts=True)
    cont = np.sort(cont)[::-1]
    cores = int(np.searchsorted(np.cumsum(cont), 0.95 * cont.sum()) + 1)
    ok = bool(coer >= 0.35 and erro <= 14 and cores <= max_cores * 2)
    motivo = "pixel art ampliada (grade achada)" if ok else (
        f"não parece pixel art: grade fraca (coerência {coer:.2f}), erro dos blocos {erro:.1f}, "
        f"{cores} cores. Peça uma imagem EM PIXEL ART (blocos de pixel visíveis, paleta curta, sem degradê "
        f"nem antialias), no ângulo pedido.")
    return {"ok": ok, "escala": round(float(bloco), 2), "cores": cores, "erro": round(erro, 1),
            "coerencia": round(float(coer), 2), "semitransparente": round(semi, 3),
            "tamanho_nativo": [int(nat.shape[1]), int(nat.shape[0])], "motivo": motivo}
