"""2.5 · Quantização conjunta: UM mapeamento material → cor da subpaleta para todos os quadros (agrupamento OKLab
sobre a união dos quadros, depois a subpaleta do estilo) e redução por moda até a altura alvo. Uma região parada
recebe a mesma cor em todos os quadros, porque o mapa não depende do quadro."""
from __future__ import annotations

import numpy as np

from ..motor import comum as C


def _lab(rgb: np.ndarray) -> np.ndarray:
    L, A, B = C.oklab(rgb.reshape(-1, 3))
    return np.stack([L, A, B], -1)


def hex_para_rgb(paleta_hex: list[str]) -> np.ndarray:
    return np.array([C.hex2rgb(h) for h in paleta_hex], dtype=np.uint8)


def agrupar(quadros: list[np.ndarray], raio: float = 0.04, amostra: int = 400_000) -> tuple[np.ndarray, np.ndarray]:
    """Agrupamento guloso (líder) em OKLab sobre a UNIÃO dos pixels opacos. Devolve (centros Lab, pesos)."""
    pix = np.concatenate([q[q[..., 3] >= 128][:, :3] for q in quadros]) if quadros else np.zeros((0, 3), np.uint8)
    if not len(pix):
        return np.zeros((0, 3)), np.zeros(0)
    if len(pix) > amostra:
        pix = pix[np.random.default_rng(0).choice(len(pix), amostra, replace=False)]
    cores, cont = np.unique((pix // 4) * 4 + 2, axis=0, return_counts=True)   # buckets de 4 níveis
    lab = _lab(cores)
    ordem = np.argsort(-cont)
    centros: list[np.ndarray] = []
    pesos: list[float] = []
    acum: list[np.ndarray] = []
    for i in ordem:
        v = lab[i]
        if centros:
            d = np.linalg.norm(np.array(centros) - v, axis=1)
            j = int(d.argmin())
            if d[j] < raio:
                pesos[j] += cont[i]
                acum[j] += v * cont[i]
                centros[j] = acum[j] / pesos[j]
                continue
        centros.append(v.copy())
        pesos.append(float(cont[i]))
        acum.append(v * cont[i])
    return np.array(centros), np.array(pesos)


def mapa_para_paleta(centros: np.ndarray, paleta_rgb: np.ndarray) -> np.ndarray:
    """Para cada centro, o índice da cor mais próxima da subpaleta (OKLab)."""
    pal = _lab(paleta_rgb)
    return np.linalg.norm(centros[:, None, :] - pal[None], axis=-1).argmin(1)


def quantizar(quadros: list[np.ndarray], paleta_hex: list[str], raio: float = 0.04) -> list[np.ndarray]:
    """Índices da paleta por pixel (-1 = transparente), com o MESMO mapa para todos os quadros."""
    pal_rgb = hex_para_rgb(paleta_hex)
    centros, _ = agrupar(quadros, raio)
    para_pal = mapa_para_paleta(centros, pal_rgb) if len(centros) else np.zeros(0, int)
    out = []
    for q in quadros:
        h, w = q.shape[:2]
        idx = np.full((h, w), -1, np.int16)
        op = q[..., 3] >= 128
        if op.any():
            lab = _lab(q[op][:, :3])
            esc = np.empty(len(lab), np.int16)
            for a in range(0, len(lab), 200_000):
                d = np.linalg.norm(lab[a:a + 200_000, None, :] - centros[None], axis=-1)
                esc[a:a + 200_000] = para_pal[d.argmin(1)]
            idx[op] = esc
        out.append(idx)
    return out


def reduzir_moda(idx: np.ndarray, saida: tuple[int, int], minimo: float = 0.5) -> np.ndarray:
    """Reduz o mapa de índices para (W, H) escolhendo, em cada bloco, o índice mais frequente. Bloco com menos de
    'minimo' de pixels opacos fica transparente (-1)."""
    W, H = saida
    ey, ex = idx.shape[0] / H, idx.shape[1] / W
    n = int(idx.max()) + 1 if (idx >= 0).any() else 1
    out = np.full((H, W), -1, np.int16)
    for y in range(H):
        a0 = int(y * ey); a1 = max(int((y + 1) * ey), a0 + 1)
        for x in range(W):
            b0 = int(x * ex); b1 = max(int((x + 1) * ex), b0 + 1)
            blk = idx[a0:a1, b0:b1].ravel()
            op = blk >= 0
            if op.mean() < minimo:
                continue
            out[y, x] = np.bincount(blk[op], minlength=n).argmax()
    return out


def para_rgba(idx: np.ndarray, paleta_hex: list[str]) -> np.ndarray:
    pal = hex_para_rgb(paleta_hex)
    out = np.zeros((*idx.shape, 4), np.uint8)
    op = idx >= 0
    out[op, :3] = pal[idx[op]]
    out[op, 3] = 255
    return out
