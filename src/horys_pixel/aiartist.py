"""Peças portadas do aseprite-ai-artist: guarda do loop de correção e movimento de célula (tween e oscilação).

Portado do aseprite-ai-artist (pebbly, MIT, v0.8.3): a guarda vem da skill `studio` (rodada de correção que mexe
em mais de ~¼ dos pixels opacos da camada é redesenho e é desfeita; no máximo 3 rodadas) e o movimento vem de
`cel` op 'tween'/'oscillate' da extensão Lua. Reimplementado em Python sobre arrays numpy.

Copyright (c) pebbly (aseprite-ai-artist), licença MIT: o aviso de copyright e a permissão valem para as partes
derivadas deste arquivo.

A ponte do horys não move célula (não há cel.position nem LinkCels nela): o movimento aqui é calculado como
deslocamento de pixels da camada inteira e escrito quadro a quadro. Pixel que sai da tela se perde nos quadros
deslocados (o quadro de origem não muda).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

LIMITE_REDESENHO = 0.25
MAX_RODADAS = 3


# ---------------------------------------------------------------- guarda do loop de correção

def pixels_mudados(antes: np.ndarray, depois: np.ndarray) -> np.ndarray:
    """Máscara dos pixels que mudaram. Dois pixels transparentes contam como iguais, qualquer que seja o RGB."""
    if antes.shape != depois.shape:
        raise ValueError(f"tamanhos diferentes: {antes.shape} e {depois.shape}")
    op_a, op_d = antes[..., 3] > 0, depois[..., 3] > 0
    dif = (antes != depois).any(-1)
    return dif & (op_a | op_d)


@dataclass
class Rodada:
    numero: int
    mudados: int
    opacos: int
    fracao: float
    aceita: bool
    motivo: str


@dataclass
class GuardaCorrecao:
    """Guarda de uma camada num quadro. 'foto' é o último estado aceito; cada conferência é uma rodada.

    Uma rodada que muda mais que 'limite' dos pixels opacos da foto (ou da correção, se a foto está vazia) é
    redesenho: é recusada e a foto continua valendo (quem chama restaura). Passadas 'max_rodadas' rodadas aceitas,
    toda correção nova é recusada: pare e pergunte ao Artur."""
    foto: np.ndarray
    limite: float = LIMITE_REDESENHO
    max_rodadas: int = MAX_RODADAS
    rodadas: list[Rodada] = field(default_factory=list)

    def __post_init__(self):
        self.foto = np.array(self.foto, np.uint8, copy=True)

    @property
    def aceitas(self) -> int:
        return sum(r.aceita for r in self.rodadas)

    @property
    def esgotada(self) -> bool:
        return self.aceitas >= self.max_rodadas

    def conferir(self, depois: np.ndarray) -> Rodada:
        mud = pixels_mudados(self.foto, depois)
        n = int(mud.sum())
        opacos = int((self.foto[..., 3] > 0).sum()) or int((depois[..., 3] > 0).sum())
        fracao = n / max(opacos, 1)
        numero = self.aceitas + 1
        if n == 0:
            r = Rodada(numero, 0, opacos, 0.0, False, "nada mudou")
        elif self.esgotada:
            r = Rodada(numero, n, opacos, fracao, False,
                       f"as {self.max_rodadas} rodadas já foram usadas: pergunte antes de seguir")
        elif fracao > self.limite:
            r = Rodada(numero, n, opacos, fracao, False,
                       f"mudou {fracao:.0%} dos pixels opacos (> {self.limite:.0%}): é redesenho, não correção. "
                       f"Faça a correção menor, só onde o achado aponta")
        else:
            r = Rodada(numero, n, opacos, fracao, True, "correção aceita")
            self.foto = np.array(depois, np.uint8, copy=True)
        self.rodadas.append(r)
        return r


def aplicar_com_guarda(guarda: GuardaCorrecao, corrigir: Callable[[np.ndarray], np.ndarray]
                       ) -> tuple[np.ndarray, Rodada]:
    """Aplica 'corrigir' na foto atual; devolve (camada que vale depois da rodada, rodada). Se a rodada é recusada,
    a camada devolvida é a foto (a correção é desfeita)."""
    depois = np.asarray(corrigir(guarda.foto.copy()), np.uint8)
    r = guarda.conferir(depois)
    return (depois.copy() if r.aceita else guarda.foto.copy()), r


# ---------------------------------------------------------------- movimento de célula

def _suavizar(t: float, curva: str) -> float:
    if curva == "linear":
        return t
    if curva in ("ease_in", "entrar"):
        return t * t
    if curva in ("ease_out", "sair"):
        return 1 - (1 - t) ** 2
    if curva in ("ease_in_out", "entrar_sair"):
        return 2 * t * t if t < 0.5 else 1 - ((-2 * t + 2) ** 2) / 2
    if curva == "smoothstep":
        return t * t * (3 - 2 * t)
    raise ValueError(f"curva desconhecida: {curva!r} (linear, ease_in, ease_out, ease_in_out, smoothstep)")


def _arred(v: float) -> int:
    return int(math.floor(v + 0.5))


def deslocamentos_tween(n_quadros: int, dx: int, dy: int, curva: str = "linear") -> list[tuple[int, int]]:
    """Deslocamento de cada quadro de 0 (origem, (0,0)) a n_quadros-1 (exatamente (dx,dy))."""
    if n_quadros < 2:
        raise ValueError("tween precisa de ao menos 2 quadros (ate > de)")
    vao = n_quadros - 1
    out = []
    for i in range(n_quadros):
        if i == 0:
            out.append((0, 0))
        elif i == vao:
            out.append((int(dx), int(dy)))
        else:
            t = _suavizar(i / vao, curva)
            out.append((_arred(dx * t), _arred(dy * t)))
    return out


def deslocamentos_oscilar(n_quadros: int, amp_x: float = 0, amp_y: float = 0, periodo: int | None = None,
                          fase: float = 0.0) -> list[tuple[int, int]]:
    """Seno por quadro: amp·sen(2π(i/periodo + fase)). Período padrão = n_quadros (o ciclo fecha no loop)."""
    if n_quadros < 2:
        raise ValueError("oscilar precisa de ao menos 2 quadros (ate > de)")
    p = int(periodo or n_quadros)
    if p < 2:
        raise ValueError("o período precisa ser >= 2")
    out = []
    for i in range(n_quadros):
        s = math.sin(2 * math.pi * (i / p + fase))
        out.append((_arred(amp_x * s), _arred(amp_y * s)))
    return out


def deslocar(rgba: np.ndarray, dx: int, dy: int) -> np.ndarray:
    """Camada deslocada por (dx, dy) no mesmo tamanho; o que sai da tela se perde, o que entra é transparente."""
    h, w = rgba.shape[:2]
    out = np.zeros_like(rgba)
    xs0, xs1 = max(0, -dx), min(w, w - dx)
    ys0, ys1 = max(0, -dy), min(h, h - dy)
    if xs1 > xs0 and ys1 > ys0:
        out[ys0 + dy:ys1 + dy, xs0 + dx:xs1 + dx] = rgba[ys0:ys1, xs0:xs1]
    return out
