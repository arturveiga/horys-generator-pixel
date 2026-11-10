"""2.7 · Anti-cintilação: um pixel só muda de cor entre quadros se a FORMA mudou ali (máscara de movimento por
diferença de silhueta); se a forma não mudou, ele herda a cor do quadro anterior. Mais a métrica: % de pixels que
piscam (mudam e voltam em 2 quadros), com meta calibrada no Tiny."""
from __future__ import annotations

import numpy as np
from scipy import ndimage


def mascara_movimento(sil_a: np.ndarray, sil_b: np.ndarray, dilatar: int = 1) -> np.ndarray:
    """Onde a silhueta mudou entre dois quadros (XOR), engrossada em 'dilatar' px."""
    dif = sil_a != sil_b
    if dilatar > 0 and dif.any():
        dif = ndimage.binary_dilation(dif, iterations=dilatar)
    return dif


def aplicar(idx_quadros: list[np.ndarray], dilatar: int = 1, proteger: list[np.ndarray] | None = None,
            ciclo: bool = False) -> list[np.ndarray]:
    """idx_quadros: mapas de índice (-1 = vazio), mesmo tamanho. Onde a silhueta não mudou perto, o pixel herda o
    quadro anterior (já tratado). 'proteger' = máscaras por quadro onde a cor PODE mudar sem a forma mudar (brilho
    pulsando, olho piscando)."""
    out = [idx_quadros[0].copy()]
    for i in range(1, len(idx_quadros)):
        atual = idx_quadros[i].copy()
        ant = out[-1]
        mov = mascara_movimento(ant >= 0, atual >= 0, dilatar)
        herdar = (~mov) & (ant >= 0) & (atual >= 0)
        if proteger is not None and proteger[i] is not None:
            herdar &= ~proteger[i]
        atual[herdar] = ant[herdar]
        out.append(atual)
    return out


def pisca(idx_quadros: list[np.ndarray], ciclo: bool = True) -> float:
    """Fração dos pixels opacos que mudam de cor num quadro e VOLTAM no seguinte (A→B→A) — a cintilação. Não exige
    isolamento (o boil do portão só conta pixel solto). 0 = nenhum pisca."""
    n = len(idx_quadros)
    if n < 3:
        return 0.0
    total = piscou = 0
    for i in range(n):
        a, b, c = idx_quadros[i - 1], idx_quadros[i], idx_quadros[(i + 1) % n]
        if not ciclo and (i == 0 or i == n - 1):
            continue
        op = (a >= 0) & (b >= 0) & (c >= 0)
        piscou += int((op & (a == c) & (a != b)).sum())
        total += int(op.sum())
    return piscou / max(total, 1)


def pisca_rgba(quadros: list[np.ndarray], ciclo: bool = True) -> float:
    """O mesmo, sobre quadros RGBA (para o medir.py): cor exata."""
    idx = []
    for q in quadros:
        k = (q[..., 0].astype(np.int32) << 16) | (q[..., 1].astype(np.int32) << 8) | q[..., 2].astype(np.int32)
        idx.append(np.where(q[..., 3] == 255, k, -1))
    return pisca(idx, ciclo)
