"""2.2 · Tirar o fundo por célula (inundação a partir dos cantos, a mesma do conceito.py)."""
from __future__ import annotations

import numpy as np

from ..motor import conceito


def tirar_fundo(quadros: list[np.ndarray], fundo: str = "auto", tolerancia: float = 0.08) -> list[np.ndarray]:
    """Quadro já com transparência fica como está; os opacos perdem o fundo liso (cor 'auto' = mediana dos cantos)."""
    out = []
    for q in quadros:
        q = q.copy()
        if (q[..., 3] < 255).any():
            out.append(q)
            continue
        fig = conceito.tirar_fundo(q[..., :3], fundo, tolerancia)
        q[..., 3] = np.where(fig, 255, 0).astype(np.uint8)
        q[~fig, :3] = 0
        out.append(q)
    return out
