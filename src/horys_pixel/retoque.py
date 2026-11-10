"""4.3 · Gosto automático: o que o usuário mudou no retoque (antes × depois), resumido por categoria (rosto, brilho,
contorno, cor, forma). Módulo puro; a ferramenta horys_gosto_do_retoque grava o resumo na memória de gosto."""
from __future__ import annotations

import re

import numpy as np

from .motor import comum as C

CATEGORIAS = ("rosto", "brilho", "contorno", "cor", "forma")


def _L(rgb: np.ndarray) -> np.ndarray:
    return C.oklab(rgb.reshape(-1, 3))[0].reshape(rgb.shape[:2])


def categorizar(antes: np.ndarray, depois: np.ndarray, cor_contorno: str | None = None) -> dict:
    """Conta os pixels mudados por categoria (um pixel entra na primeira que casar):
    forma = a silhueta mudou; contorno = virou/deixou de ser a cor de contorno; brilho = ficou mais claro (ΔL > 0,08);
    rosto = mudou na faixa de cima (35%) da figura e perto do centro; cor = o resto."""
    if antes.shape != depois.shape:
        return {"erro": "tamanhos diferentes", "total": 0}
    mud = np.any(antes != depois, axis=-1)
    total = int(mud.sum())
    res = {c: 0 for c in CATEGORIAS}
    res["total"] = total
    if not total:
        return res
    op = (antes[..., 3] > 0) | (depois[..., 3] > 0)
    ys, xs = np.nonzero(op)
    y0, y1 = ys.min(), ys.max()
    cx = (xs.min() + xs.max()) / 2
    larg = max(1, xs.max() - xs.min() + 1)
    livre = mud.copy()
    forma = livre & ((antes[..., 3] > 0) != (depois[..., 3] > 0))
    res["forma"] = int(forma.sum())
    livre &= ~forma
    if cor_contorno:
        oc = np.array(C.hex2rgb(cor_contorno), np.uint8)
        e_a = np.all(antes[..., :3] == oc, -1)
        e_d = np.all(depois[..., :3] == oc, -1)
        cont = livre & (e_a != e_d)
        res["contorno"] = int(cont.sum())
        livre &= ~cont
    dL = _L(depois[..., :3]) - _L(antes[..., :3])
    # rosto antes de brilho: um olho clareado em cima ainda é rosto
    yy, xx = np.mgrid[0:op.shape[0], 0:op.shape[1]]
    rosto = livre & (yy <= y0 + 0.35 * (y1 - y0 + 1)) & (np.abs(xx - cx) <= 0.35 * larg)
    res["rosto"] = int(rosto.sum())
    livre &= ~rosto
    br = livre & (dL > 0.08)
    res["brilho"] = int(br.sum())
    livre &= ~br
    res["cor"] = int(livre.sum())
    return res


def resumo(por_quadro: list[dict]) -> dict:
    """Soma as categorias de vários quadros/camadas."""
    s = {c: 0 for c in CATEGORIAS}
    s["total"] = 0
    for d in por_quadro:
        for c in (*CATEGORIAS, "total"):
            s[c] += int(d.get(c, 0))
    return s


def texto_do_resumo(s: dict) -> str:
    if not s["total"]:
        return "o usuário não mudou nada"
    partes = [f"{c} {s[c]} px ({s[c] / s['total']:.0%})" for c in CATEGORIAS if s[c]]
    return f"retoque de {s['total']} px: " + ", ".join(partes)


def defeitos_do_resumo(s: dict, minimo_frac: float = 0.15) -> list[str]:
    """Categorias que o usuário mais mexeu viram 'defeitos' para o gosto (o que o gerador deixou a desejar)."""
    nomes = {"rosto": "rosto refeito à mão", "brilho": "brilho/luz refeitos", "contorno": "contorno refeito",
             "cor": "cor trocada", "forma": "silhueta alterada"}
    if not s["total"]:
        return []
    return [nomes[c] for c in CATEGORIAS if s[c] / s["total"] >= minimo_frac]


COORD = re.compile(r"\(?\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*(\d+)\s*,\s*(\d+))?\s*\)?")


def coordenadas(onde: str) -> tuple[list[list[int]], list[list[int]]]:
    """Acha 'x,y' (ponto) e 'x,y,w,h' (retângulo) no texto 'onde' do revisor."""
    pontos, retangulos = [], []
    for m in COORD.finditer(onde or ""):
        if m.group(3) is not None:
            retangulos.append([int(m.group(i)) for i in (1, 2, 3, 4)])
        else:
            pontos.append([int(m.group(1)), int(m.group(2))])
    return pontos, retangulos
