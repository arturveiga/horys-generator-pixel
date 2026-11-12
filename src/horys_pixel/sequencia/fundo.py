"""2.2 · Tirar o fundo por célula (inundação a partir dos cantos, a mesma do conceito.py), mais a franja: a
redução/o snap escurece o fundo encostado no contorno e a tolerância estreita deixa um anel de pixels "quase fundo"
em volta da figura. A franja tira só esses, a até 2 px do fundo e perto da cor dele; nunca a cor no corpo inteiro."""
from __future__ import annotations

import numpy as np
from scipy import ndimage

from ..motor import conceito
from .entradas import distancia_fundo

CHROMA_MIN = 0.12  # croma OKLab do fundo abaixo disso = fundo neutro/escuro, sem franja (verde puro ≈ 0.29)


def tirar_franja(rgb: np.ndarray, fig: np.ndarray, cor_fundo: str = "auto", tolerancia: float = 0.08,
                 alcance: int = 2, fator: float = 2.5) -> np.ndarray:
    """Máscara da figura sem a franja: pixels da figura colados no fundo (até 'alcance' camadas) cuja distância à
    cor do fundo é menor que tolerancia × fator. Só age com fundo de chroma saturado (verde, magenta, azul): com
    fundo escuro ou neutro a "franja" seria o contorno escuro do personagem (medido numa prancha real do Codex com
    fundo roxo-escuro, que perdia o contorno inteiro)."""
    dist, ref = distancia_fundo(rgb, cor_fundo, com_ref=True)
    if float(np.hypot(ref[1], ref[2])) < CHROMA_MIN:
        return fig
    perto = dist < tolerancia * fator
    fig = fig.copy()
    for _ in range(alcance):
        anel = ndimage.binary_dilation(~fig, structure=np.ones((3, 3))) & fig
        tirar = anel & perto
        if not tirar.any():
            break
        fig &= ~tirar
    return fig


def tirar_buracos(rgb: np.ndarray, fig: np.ndarray, cor_fundo: str = "auto", tolerancia: float = 0.08,
                  area_min: int = 16) -> np.ndarray:
    """Fundo preso dentro da figura (entre braço e corpo): a inundação dos cantos não chega lá. Só com fundo de
    chroma saturado, onde a cor do fundo não existe no personagem; com fundo escuro, isso comeria as sombras."""
    dist, ref = distancia_fundo(rgb, cor_fundo, com_ref=True)
    if float(np.hypot(ref[1], ref[2])) < CHROMA_MIN:
        return fig
    lab, n = ndimage.label(fig & (dist < tolerancia))
    if not n:
        return fig
    tam = np.bincount(lab.ravel())
    tam[0] = 0
    return fig & ~(tam[lab] >= area_min)


def tirar_fundo(quadros: list[np.ndarray], fundo: str = "auto", tolerancia: float = 0.08,
                franja: bool = True) -> list[np.ndarray]:
    """Quadro já com transparência fica como está; os opacos perdem o fundo liso (cor 'auto' = mediana dos cantos)
    e, com franja=True, o anel de pixels quase-fundo colado no contorno."""
    out = []
    for q in quadros:
        q = q.copy()
        if (q[..., 3] < 255).any():
            out.append(q)
            continue
        fig = conceito.tirar_fundo(q[..., :3], fundo, tolerancia)
        if franja:
            fig = tirar_buracos(q[..., :3], fig, fundo, tolerancia)
            fig = tirar_franja(q[..., :3], fig, fundo, tolerancia)
        q[..., 3] = np.where(fig, 255, 0).astype(np.uint8)
        q[~fig, :3] = 0
        out.append(q)
    return out
