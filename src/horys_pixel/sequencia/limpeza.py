"""2.8 · Limpeza da sequência: órfãos sem boil (kiln.limpar_sequencia) e a busca gulosa do M10 (1 px por vez, só
aceita se os degraus irregulares da silhueta caírem), aplicadas a todos os quadros com as mesmas regras."""
from __future__ import annotations

import numpy as np

from .. import kiln
from ..motor import comum as C


def degraus(op: np.ndarray) -> int:
    return len(C.degraus_irregulares(op))


def regularizar_borda(quadro: np.ndarray, max_passos: int = 60) -> np.ndarray:
    """Busca gulosa local: tenta ligar/desligar 1 pixel da borda da silhueta; só aceita se o M10 (degraus
    irregulares) cair. Pixel ligado herda a cor do vizinho opaco mais comum. Nunca cria forma: só regulariza."""
    q = quadro.copy()
    atual = degraus(q[..., 3] > 0)
    for _ in range(max_passos):
        op = q[..., 3] > 0
        pts = C.degraus_irregulares(op)
        if not pts:
            break
        melhor = None
        for x, y in pts:
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    xx, yy = x + dx, y + dy
                    if not (0 <= yy < q.shape[0] and 0 <= xx < q.shape[1]):
                        continue
                    novo = op.copy()
                    novo[yy, xx] = not op[yy, xx]
                    d = degraus(novo)
                    if d < atual and (melhor is None or d < melhor[0]):
                        melhor = (d, xx, yy, bool(novo[yy, xx]))
        if melhor is None:
            break
        d, xx, yy, liga = melhor
        if liga:
            viz = q[max(0, yy - 1):yy + 2, max(0, xx - 1):xx + 2].reshape(-1, 4)
            viz = viz[viz[:, 3] > 0]
            if not len(viz):
                break
            cores, cont = np.unique(viz, axis=0, return_counts=True)
            q[yy, xx] = cores[cont.argmax()]
        else:
            q[yy, xx] = (0, 0, 0, 0)
        atual = d
    return q


def limpar(quadros: list[np.ndarray], min_px: int = 3, proteger: set[tuple[int, int, int]] | None = None,
           regularizar: bool = True) -> list[np.ndarray]:
    """Órfãos sem boil e, se 'regularizar', a borda guloso quadro a quadro. Contorno e sombra fixa no pivô ficam
    para horys_contorno (as mesmas regras do portão), que roda depois em todos os quadros."""
    out = kiln.limpar_sequencia(quadros, min_px, proteger) if min_px > 1 else [q.copy() for q in quadros]
    if regularizar:
        out = [regularizar_borda(q) for q in out]
    return out
