"""2.3 · Registro: alinha escala e posição de todos os quadros pela linha dos pés, pela altura de referência e pelo
pivô. Corrige deriva de câmera (vídeo) e escalas diferentes entre células (grade)."""
from __future__ import annotations

import numpy as np
from PIL import Image


def caixa(q: np.ndarray, limiar: int = 128):
    """(x0, y0, x1, y1) inclusivo da figura opaca, ou None."""
    ys, xs = np.nonzero(q[..., 3] >= limiar)
    if not len(ys):
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def pivo_dos_pes(q: np.ndarray, frac: float = 0.04, limiar: int = 128) -> tuple[float, int]:
    """(x do centro da faixa de baixo, y da linha dos pés). A faixa de baixo é ~4% da altura: o centro é o meio do
    vão entre os pés, não a ponta de um pé."""
    x0, y0, x1, y1 = caixa(q, limiar)
    faixa = max(1, round((y1 - y0 + 1) * frac))
    op = q[y1 - faixa + 1:y1 + 1, :, 3] >= limiar
    xs = np.nonzero(op.any(0))[0]
    return (float(xs.min() + xs.max()) / 2.0, y1)


def ancora(q: np.ndarray, limiar: int = 128) -> tuple[float, int]:
    """(x do centro de massa da figura, y da linha dos pés). Para registrar SEQUÊNCIAS: no andar só o pé da frente
    cai na faixa de baixo, e o pivo_dos_pes pularia de um pé para o outro; o centro de massa fica no corpo."""
    op = q[..., 3] >= limiar
    ys, xs = np.nonzero(op)
    return (float(xs.mean()), int(ys.max()))


def _escalar(q: np.ndarray, s: float) -> np.ndarray:
    if abs(s - 1.0) < 1e-3:
        return q
    h, w = q.shape[:2]
    nw, nh = max(1, round(w * s)), max(1, round(h * s))
    a = q[..., 3:4].astype(np.float32) / 255.0   # pré-multiplicado: a cor do fundo não vaza para a borda
    pm = np.concatenate([q[..., :3].astype(np.float32) * a, q[..., 3:4].astype(np.float32)], -1)
    canais = [np.array(Image.fromarray(pm[..., c]).resize((nw, nh), Image.LANCZOS)) for c in range(4)]
    pm2 = np.stack(canais, -1)
    al = np.clip(pm2[..., 3:4], 1e-3, 255)
    rgb = np.clip(pm2[..., :3] / (al / 255.0), 0, 255)
    return np.concatenate([rgb, pm2[..., 3:4]], -1).round().clip(0, 255).astype(np.uint8)


def registrar(quadros: list[np.ndarray], altura_ref: float, tamanho: tuple[int, int], pivo: tuple[float, int],
              escala: str = "por_quadro") -> list[np.ndarray]:
    """Devolve quadros do mesmo 'tamanho' (w, h) com a figura na altura 'altura_ref', o centro dos pés em pivo[0] e
    a linha dos pés em pivo[1].
    escala = 'por_quadro' (cada quadro ganha a sua escala: célula de grade ou zoom de câmera) ou 'comum' (uma escala
    só, a da altura mediana: golpe e salto, em que a altura muda de verdade)."""
    W, H = tamanho
    caixas = [caixa(q) for q in quadros]
    alturas = [(b[3] - b[1] + 1) if b else 0 for b in caixas]
    validas = [a for a in alturas if a]
    if not validas:
        raise ValueError("nenhum quadro com figura")
    mediana = float(np.median(validas))
    out = []
    for q, b, alt in zip(quadros, caixas, alturas):
        canvas = np.zeros((H, W, 4), np.uint8)
        if not b:
            out.append(canvas)
            continue
        s = altura_ref / (alt if escala == "por_quadro" else mediana)
        qs = _escalar(q, s)
        px, py = ancora(qs)
        dx, dy = round(pivo[0] - px), round(pivo[1] - py)
        y0, x0 = max(0, dy), max(0, dx)
        y1, x1 = min(H, dy + qs.shape[0]), min(W, dx + qs.shape[1])
        if y1 > y0 and x1 > x0:
            canvas[y0:y1, x0:x1] = qs[y0 - dy:y1 - dy, x0 - dx:x1 - dx]
        out.append(canvas)
    return out


def deriva(quadros: list[np.ndarray]) -> dict:
    """Quanto os quadros divergem em linha dos pés, centro do corpo (centro de massa) e altura (px)."""
    pes, xs, alts = [], [], []
    for q in quadros:
        b = caixa(q)
        if not b:
            continue
        x, y = ancora(q)
        pes.append(y)
        xs.append(x)
        alts.append(b[3] - b[1] + 1)
    return {"pes": float(max(pes) - min(pes)), "x": float(max(xs) - min(xs)), "altura": float(max(alts) - min(alts))}
