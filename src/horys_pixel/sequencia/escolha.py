"""2.4 · Escolha de quadros (vídeo): mede a abertura dos pés e a silhueta por quadro e escolhe os N quadros do plano.
Extras só ANTES ou DEPOIS das chaves, nunca entre elas (lição do Dead Cells)."""
from __future__ import annotations

import numpy as np

from .registro import caixa


def pistas(quadros: list[np.ndarray]) -> dict:
    """Série por quadro: pé (y mais baixo), centro y, abertura (largura da faixa dos pés), largura e área."""
    pe, cy, abertura, larg, area = [], [], [], [], []
    for q in quadros:
        op = q[..., 3] >= 128
        b = caixa(q)
        if not b:
            pe.append(0); cy.append(0.0); abertura.append(0); larg.append(0); area.append(0)
            continue
        x0, y0, x1, y1 = b
        faixa = max(1, round((y1 - y0 + 1) * 0.10))
        cols = np.nonzero(op[y1 - faixa + 1:y1 + 1].any(0))[0]
        pe.append(y1)
        cy.append(float(np.nonzero(op)[0].mean()))
        abertura.append(int(cols.max() - cols.min() + 1) if len(cols) else 0)
        larg.append(x1 - x0 + 1)
        area.append(int(op.sum()))
    return {"pe": pe, "cy": cy, "abertura": abertura, "largura": larg, "area": area}


def _picos(serie, maximo: bool, dist_min: int) -> list[int]:
    s = np.asarray(serie, float)
    s = s if maximo else -s
    idx = [i for i in range(1, len(s) - 1) if s[i] >= s[i - 1] and s[i] > s[i + 1]]
    idx.sort(key=lambda i: -s[i])
    ok: list[int] = []
    for i in idx:
        if all(abs(i - j) >= dist_min for j in ok):
            ok.append(i)
    return sorted(ok)


def escolher_andar(quadros: list[np.ndarray], n: int = 8) -> list[int]:
    """Ciclo de andar: contatos = abertura máxima dos pés; passagens = abertura mínima entre dois contatos.
    Devolve até n índices em ordem. Contatos e passagens são sempre mantidos; os extras (se n > chaves) vêm só
    colados antes ou depois de uma chave, nunca no meio de um intervalo entre chaves."""
    p = pistas(quadros)
    ab, N = p["abertura"], len(quadros)
    if N <= n:
        return list(range(N))
    contatos = _picos(ab, True, max(1, N // max(2, n)))
    if len(contatos) < 2:
        return sorted(set(np.linspace(0, N - 1, n).round().astype(int).tolist()))
    chaves = set(contatos)
    for a, b in zip(contatos, contatos[1:]):
        if b - a > 1:
            chaves.add(min(range(a + 1, b), key=lambda i: ab[i]))
    chaves = sorted(chaves)
    if len(chaves) >= n:
        passo = len(chaves) / n
        return [chaves[int(i * passo)] for i in range(n)]
    escolhidos = list(chaves)
    for d in (1, -1, 2, -2):
        for k in chaves:
            j = k + d
            if len(escolhidos) >= n:
                break
            if 0 <= j < N and j not in escolhidos:
                escolhidos.append(j)
    return sorted(escolhidos)[:n]


def escolher_golpe(quadros: list[np.ndarray], n: int = 5) -> list[int]:
    """Golpe: antecipação (menor largura antes do impacto), impacto (maior largura) e recuperação (menor largura
    depois). Os extras entram só antes da antecipação e depois do impacto, nunca entre antecipação e impacto."""
    N = len(quadros)
    if N <= n:
        return list(range(N))
    larg = pistas(quadros)["largura"]
    imp = int(np.argmax(larg))
    ant = int(np.argmin(larg[:imp])) if imp > 0 else 0
    rec = int(np.argmin(larg[imp:])) + imp
    escolhidos = sorted({ant, imp, rec})
    candidatos = [i for i in range(N) if i not in escolhidos and (i < ant or i > imp)]
    candidatos.sort(key=lambda i: (ant - i) if i < ant else (i - imp))
    for i in candidatos:
        if len(escolhidos) >= n:
            break
        escolhidos.append(i)
    return sorted(escolhidos)
