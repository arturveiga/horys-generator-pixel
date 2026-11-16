"""Operações de paleta: rampa com giro de matiz e análise (quase iguais por ΔE, rampas achadas, contraste).

Portado do aseprite-ai-artist (pebbly, MIT, v0.8.3: `buildRamp`/`hueShiftShade` de src/lib/color.ts e
`palette` op 'analyze' de src/tools/palette.ts), reimplementado em Python. A análise ganhou a detecção de rampas
(reusa o agrupamento por matiz/croma OKLCH de analise_estilo) e o aviso de rampa sem giro de matiz.

Copyright (c) pebbly (aseprite-ai-artist), licença MIT: o aviso de copyright e a permissão valem para as partes
derivadas deste arquivo.
"""
from __future__ import annotations

import math
from collections import Counter

import numpy as np

from . import pixels
from .analise_estilo import NEUTRO_C, _agrupar_rampas, _dh, _lch
from .analise_estilo import _lab as _oklab

# para onde a sombra e a luz puxam a matiz: sombra para o azul, luz para o amarelo
MATIZ_SOMBRA = 240.0
MATIZ_LUZ = 60.0


# ---------------------------------------------------------------- HSL

def _rgb_hsl(r: int, g: int, b: int) -> tuple[float, float, float]:
    rn, gn, bn = r / 255, g / 255, b / 255
    mx, mn = max(rn, gn, bn), min(rn, gn, bn)
    l = (mx + mn) / 2
    d = mx - mn
    if d == 0:
        return 0.0, 0.0, l
    s = d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)
    if mx == rn:
        h = ((gn - bn) / d + (6 if gn < bn else 0)) * 60
    elif mx == gn:
        h = ((bn - rn) / d + 2) * 60
    else:
        h = ((rn - gn) / d + 4) * 60
    return h, s, l


def _hsl_rgb(h: float, s: float, l: float) -> tuple[int, int, int]:
    if s == 0:
        v = round(l * 255)
        return v, v, v
    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q
    hk = (h % 360) / 360

    def canal(t: float) -> float:
        t = t + 1 if t < 0 else t - 1 if t > 1 else t
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p

    return round(canal(hk + 1 / 3) * 255), round(canal(hk) * 255), round(canal(hk - 1 / 3) * 255)


def girar_matiz_para(h: float, alvo: float, graus: float) -> float:
    """Gira 'h' na direção de 'alvo' pelo arco mais curto, no máximo 'graus'."""
    delta = ((alvo - h) % 360 + 540) % 360 - 180
    passo = math.copysign(min(abs(delta), graus), delta) if delta else 0.0
    return (h + passo) % 360


def sombrear(hx: str, quanto: float, giro: float = 25.0) -> str:
    """Sombra/luz de artista, não de brilho: quanto < 0 escurece girando para o azul e tirando um pouco de
    saturação; quanto > 0 clareia girando para o amarelo e saturando. ~0,15 por degrau de rampa."""
    r, g, b, a = pixels.hex_rgba(hx)
    h, s, l = _rgb_hsl(r, g, b)
    h2 = girar_matiz_para(h, MATIZ_SOMBRA if quanto < 0 else MATIZ_LUZ, giro * abs(quanto))
    l2 = min(1.0, max(0.0, l + quanto * 0.5))
    s2 = min(1.0, max(0.0, s + (0.06 if quanto > 0 else -0.04) * abs(quanto) * 2))
    return pixels.rgba_hex((*_hsl_rgb(h2, s2, l2), a))


def rampa(base: str, passos: int = 5, abertura: float = 0.55, giro: float = 25.0) -> list[str]:
    """Rampa de 'passos' cores do escuro ao claro com a base no meio (sombra e luz iguais)."""
    if passos < 2:
        raise ValueError("uma rampa precisa de ao menos 2 passos")
    if not 0 < abertura <= 1:
        raise ValueError("abertura vai de 0 (exclusivo) a 1")
    pixels.hex_rgba(base)  # valida
    return [sombrear(base, ((i / (passos - 1)) * 2 - 1) * abertura, giro) for i in range(passos)]


# ---------------------------------------------------------------- contraste

def _lin(c: float) -> float:
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminancia(hx: str) -> float:
    r, g, b, _ = pixels.hex_rgba(hx)
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def razao_contraste(a: str, b: str) -> float:
    la, lb = luminancia(a), luminancia(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def delta_e(a: str, b: str) -> float:
    """ΔE76 em CIELAB (a mesma conta da trava de paleta e do ai-artist)."""
    return float(np.linalg.norm(pixels._lab(a) - pixels._lab(b)))


# ---------------------------------------------------------------- análise

def _hex6(hx: str) -> str:
    return pixels.rgba_hex((*pixels.hex_rgba(hx)[:3], 255))


def cores_da_imagem(rgba: np.ndarray) -> Counter:
    """Contagem das cores opacas (alfa > 0) de uma imagem RGBA, em hex #rrggbb."""
    op = rgba[..., 3] > 0
    px = rgba[op][:, :3]
    if not len(px):
        return Counter()
    cores, n = np.unique(px, axis=0, return_counts=True)
    return Counter({pixels.rgba_hex((*c, 255)): int(k) for c, k in zip(cores, n)})


def detectar_rampas(cores: list[str]) -> list[dict]:
    """Rampas (2 a 4 tons da mesma matiz/croma, do escuro ao claro) e o giro de matiz de cada uma."""
    if len(cores) < 2:
        return []
    rgb = np.array([pixels.hex_rgba(c)[:3] for c in cores], np.float64)
    labs = list(_oklab(rgb))
    grupos = _agrupar_rampas(labs, list(range(len(cores))))
    out = []
    for g in grupos:
        if len(g) < 2:
            continue
        lch = [_lch(labs[i]) for i in g]
        neutra = all(c < NEUTRO_C for _, c, _ in lch)
        giro = 0.0 if neutra else _dh(lch[0][2], lch[-1][2])
        out.append({"cores": [cores[i] for i in g], "neutra": neutra, "giro_matiz": round(giro, 1),
                    "degraus_L": [round(lch[k + 1][0] - lch[k][0], 3) for k in range(len(g) - 1)]})
    return out


def analisar(cores: list[str] | None = None, imagem: np.ndarray | None = None, limiar_de: float = 3.0,
             max_pares: int = 32) -> dict:
    """Relatório da paleta. Sem 'cores', a paleta são as cores da imagem. Com imagem, conta o uso, as cores
    fora da paleta e as entradas sem uso; o par de menor contraste olha só as cores usadas."""
    uso = cores_da_imagem(imagem) if imagem is not None else Counter()
    if cores:
        pal = list(dict.fromkeys(_hex6(c) for c in cores if pixels.hex_rgba(c)[3] > 0))
    else:
        pal = [c for c, _ in uso.most_common()]
    if not pal:
        raise ValueError("nenhuma cor para analisar (passe 'cores' ou uma imagem com pixels)")

    quase = []
    for i in range(len(pal)):
        for j in range(i + 1, len(pal)):
            d = delta_e(pal[i], pal[j])
            if d < limiar_de:
                quase.append({"a": pal[i], "b": pal[j], "delta_e": round(d, 2)})

    usadas = [c for c in pal if uso.get(c, 0) > 0] if uso else list(pal)
    usadas = sorted(usadas, key=lambda c: -uso.get(c, 0))[:max_pares]
    menor = None
    for i in range(len(usadas)):
        for j in range(i + 1, len(usadas)):
            r = razao_contraste(usadas[i], usadas[j])
            if menor is None or r < menor["razao"]:
                menor = {"a": usadas[i], "b": usadas[j], "razao": round(r, 2)}
    lum = sorted(pal, key=luminancia)
    L = [float(_oklab(np.array(pixels.hex_rgba(c)[:3], np.float64))[0]) for c in lum]

    rampas = detectar_rampas(pal)
    fora = [{"cor": c, "pixels": n} for c, n in uso.most_common() if c not in set(pal)] if cores else []
    sem_uso = [c for c in pal if uso and uso.get(c, 0) == 0]

    avisos = []
    if quase:
        avisos.append(f"{len(quase)} par(es) quase iguais (ΔE < {limiar_de:g}): junte para a rampa ler melhor")
    planas = [r for r in rampas if not r["neutra"] and r["giro_matiz"] < 5]
    if planas:
        avisos.append(f"{len(planas)} rampa(s) sem giro de matiz (só muda o brilho): cara de pixel art de máquina")
    if fora:
        avisos.append(f"{len(fora)} cor(es) da arte fora da paleta")
    if len(pal) > 64:
        avisos.append(f"{len(pal)} cores é muito para pixel art; a maioria dos sprites lê melhor com menos de 32")
    if menor and menor["razao"] < 1.1 and len(usadas) > 1:
        avisos.append(f"par usado quase sem contraste: {menor['a']} e {menor['b']} ({menor['razao']}:1)")

    return {
        "n": len(pal),
        "quase_iguais": quase,
        "rampas": rampas,
        "contraste": {"mais_escura": lum[0], "mais_clara": lum[-1],
                      "razao_extremos": round(razao_contraste(lum[0], lum[-1]), 2),
                      "L_min": round(L[0], 3), "L_max": round(L[-1], 3), "menor_par": menor},
        "uso": [{"cor": c, "pixels": uso.get(c, 0)} for c in pal] if uso else [],
        "fora_da_paleta": fora,
        "sem_uso": sem_uso,
        "avisos": avisos,
        "veredito": "limpa" if not avisos else "; ".join(avisos),
    }
