"""Cor: hex, OKLab, k-médias determinístico e encaixe na paleta. Só numpy."""
from __future__ import annotations

import numpy as np


def hex_rgb(h: str) -> tuple[int, int, int]:
    h = str(h).strip().lstrip("#")
    if len(h) == 8:
        h = h[:6]
    if len(h) != 6:
        raise ValueError(f"cor '{h}' inválida: use #rrggbb")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_hex(c) -> str:
    return "#%02x%02x%02x" % tuple(int(v) for v in list(c)[:3])


def oklab(rgb) -> np.ndarray:
    """sRGB 0..255 (qualquer forma (..., 3)) -> OKLab (..., 3)."""
    c = np.asarray(rgb, dtype=np.float64) / 255.0
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = lin[..., 0], lin[..., 1], lin[..., 2]
    l = np.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
    m = np.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
    s = np.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
    return np.stack([0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
                     1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
                     0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s], -1)


def delta(a: str, b: str) -> float:
    """Distância OKLab entre duas cores hex (~0,02 é a menor diferença visível)."""
    return float(np.linalg.norm(oklab(hex_rgb(a)) - oklab(hex_rgb(b))))


def _lin(v: float) -> float:
    v /= 255
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def luminancia(hx: str) -> float:
    r, g, b = hex_rgb(hx)
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def razao_contraste(a: str, b: str) -> float:
    la, lb = luminancia(a), luminancia(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def kmeans(cores: np.ndarray, k: int, iters: int = 20) -> np.ndarray:
    """k-médias determinístico em OKLab. cores: (n,3) uint8 -> (<=k,3) cores REAIS (a mais frequente de cada grupo)."""
    uni, cont = np.unique(np.asarray(cores, np.uint8).reshape(-1, 3), axis=0, return_counts=True)
    if len(uni) <= k:
        return uni.astype(np.float64)
    lab = oklab(uni)
    esc = [int(cont.argmax())]
    dmin = np.linalg.norm(lab - lab[esc[0]], axis=-1)
    while len(esc) < k:
        i = int((dmin * np.sqrt(cont)).argmax())
        esc.append(i)
        dmin = np.minimum(dmin, np.linalg.norm(lab - lab[i], axis=-1))
    centros = lab[esc].copy()
    for _ in range(iters):
        lbl = np.linalg.norm(lab[:, None] - centros[None], axis=-1).argmin(1)
        novo = np.array([np.average(lab[lbl == i], 0, weights=cont[lbl == i]) if (lbl == i).any() else centros[i]
                         for i in range(k)])
        if np.allclose(novo, centros):
            break
        centros = novo
    lbl = np.linalg.norm(lab[:, None] - centros[None], axis=-1).argmin(1)
    reps = [uni[lbl == i][cont[lbl == i].argmax()] for i in range(k) if (lbl == i).any()]
    return np.array(reps, np.float64)


def encaixar(rgb: np.ndarray, pal: np.ndarray) -> np.ndarray:
    """Índice da cor da paleta mais próxima (OKLab) de cada pixel de rgb (..., 3)."""
    forma = rgb.shape[:-1]
    uni, inv = np.unique(np.asarray(rgb).reshape(-1, 3), axis=0, return_inverse=True)
    d = np.linalg.norm(oklab(uni)[:, None] - oklab(np.asarray(pal, np.float64))[None], axis=-1)
    return d.argmin(1)[np.asarray(inv).ravel()].reshape(forma)
