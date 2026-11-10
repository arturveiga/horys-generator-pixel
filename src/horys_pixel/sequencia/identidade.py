"""2.6 · Trava de identidade: peças declaradas na ficha (decalques: crânio, medalhão, olho, runa) recortadas da base
aprovada e coladas em cada quadro na posição achada por casamento de modelo (translação e espelho). Rotação só por
RotSprite, nunca vizinho direto: este módulo não gira peças. Generaliza o montar.py da r5 do golem."""
from __future__ import annotations

import numpy as np


def recortar(base: np.ndarray, rect: tuple[int, int, int, int]) -> np.ndarray:
    x, y, w, h = rect
    return base[y:y + h, x:x + w].copy()


def _erro(quadro: np.ndarray, peca: np.ndarray, x: int, y: int) -> float:
    """Erro médio (RGB, só pixels opacos da peça) ao pôr a peça em (x, y); quadro fora = erro máximo."""
    h, w = peca.shape[:2]
    if x < 0 or y < 0 or y + h > quadro.shape[0] or x + w > quadro.shape[1]:
        return 1e9
    m = peca[..., 3] >= 128
    if not m.any():
        return 1e9
    jan = quadro[y:y + h, x:x + w]
    d = np.abs(jan[..., :3].astype(int) - peca[..., :3].astype(int)).sum(-1)
    d = np.where(jan[..., 3] >= 128, d, 3 * 255)     # quadro transparente onde a peça é opaca: erro máximo
    return float(d[m].mean())


def achar(quadro: np.ndarray, peca: np.ndarray, centro: tuple[int, int], raio: int = 8,
          espelho: bool = True) -> dict:
    """Melhor posição (x, y do canto de cima à esquerda da peça) numa janela de ±raio em volta de 'centro'
    (canto original). Devolve {x, y, espelho, erro}."""
    melhor = {"x": centro[0], "y": centro[1], "espelho": False, "erro": 1e9}
    variantes = [(False, peca)] + ([(True, peca[:, ::-1])] if espelho else [])
    for esp, p in variantes:
        for dy in range(-raio, raio + 1):
            for dx in range(-raio, raio + 1):
                e = _erro(quadro, p, centro[0] + dx, centro[1] + dy)
                if e < melhor["erro"]:
                    melhor = {"x": centro[0] + dx, "y": centro[1] + dy, "espelho": esp, "erro": e}
    return melhor


def colar(quadro: np.ndarray, peca: np.ndarray, x: int, y: int, espelho: bool = False) -> np.ndarray:
    """Cola só os pixels opacos da peça (sem borda, sem retângulo)."""
    q = quadro.copy()
    p = peca[:, ::-1] if espelho else peca
    h, w = p.shape[:2]
    y0, x0 = max(0, y), max(0, x)
    y1, x1 = min(q.shape[0], y + h), min(q.shape[1], x + w)
    if y1 <= y0 or x1 <= x0:
        return q
    sub = p[y0 - y:y1 - y, x0 - x:x1 - x]
    m = sub[..., 3] >= 128
    q[y0:y1, x0:x1][m] = sub[m]
    return q


def travar(quadros: list[np.ndarray], base: np.ndarray, decalques: list[dict], erro_max: float = 60.0) -> tuple[
        list[np.ndarray], list[dict]]:
    """Para cada decalque {nome, rect [x,y,w,h] na base, busca (raio px), espelho (bool)} acha a peça em cada quadro
    e cola a versão da base por cima. Só cola se o erro de casamento ≤ erro_max (senão a peça não está no quadro e
    não se cola nada). Devolve (quadros, relatório por quadro e decalque)."""
    out, rel = [], []
    for i, q in enumerate(quadros):
        for d in decalques:
            x, y, w, h = d["rect"]
            peca = recortar(base, (x, y, w, h))
            r = achar(q, peca, (x, y), int(d.get("busca", 8)), bool(d.get("espelho", True)))
            colou = r["erro"] <= erro_max
            if colou:
                q = colar(q, peca, r["x"], r["y"], r["espelho"])
            rel.append({"quadro": i, "nome": d.get("nome", "?"), "x": r["x"], "y": r["y"], "espelho": r["espelho"],
                        "erro": round(r["erro"], 1), "colou": colou})
        out.append(q)
    return out, rel
