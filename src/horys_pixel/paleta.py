"""Paleta do asset: famílias de material com rampa de 2–3 tons (sombra puxa para o azul, luz para o amarelo) + uma
tinta de contorno. É a única fonte de cor: a arte parada, o render e o pós usam só estas cores.

paleta.json = {"familias": {nome: {"rampa": [hex escuro -> claro], "tipo": "toon"|"emissivo"}}, "tinta": hex,
               "cores": [todas], "avisos": [...]}
A rampa toon de 2 tons, de rampa_material, é [sombra, base]: o 2º tom seria uma luz estourada.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from . import cor as C

MATIZ_SOMBRA = 240.0
MATIZ_LUZ = 60.0


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


def _girar(h: float, alvo: float, graus: float) -> float:
    d = ((alvo - h) % 360 + 540) % 360 - 180
    return (h + (math.copysign(min(abs(d), graus), d) if d else 0.0)) % 360


def sombrear(hx: str, quanto: float, giro: float = 25.0) -> str:
    """quanto < 0 escurece girando para o azul; quanto > 0 clareia girando para o amarelo."""
    r, g, b = C.hex_rgb(hx)
    h, s, l = _rgb_hsl(r, g, b)
    h2 = _girar(h, MATIZ_SOMBRA if quanto < 0 else MATIZ_LUZ, giro * abs(quanto))
    l2 = min(1.0, max(0.0, l + quanto * 0.5))
    s2 = min(1.0, max(0.0, s + (0.06 if quanto > 0 else -0.04) * abs(quanto) * 2))
    return C.rgb_hex(_hsl_rgb(h2, s2, l2))


def rampa(base: str, passos: int = 5, abertura: float = 0.55, giro: float = 25.0) -> list[str]:
    if passos < 2:
        raise ValueError("uma rampa precisa de ao menos 2 passos")
    return [sombrear(base, ((i / (passos - 1)) * 2 - 1) * abertura, giro) for i in range(passos)]


def rampa_material(base: str, tons: int = 3, abertura: float = 0.30, giro: float = 25.0) -> list[str]:
    """A base fica sempre na rampa. 3 tons: sombra, base, luz; 2: sombra, base; 4+: simétrica."""
    base = base.lower()
    if tons <= 1:
        return [base]
    if tons == 2:
        return [sombrear(base, -abertura, giro), base]
    if tons == 3:
        return [sombrear(base, -abertura, giro), base, sombrear(base, abertura * 0.8, giro)]
    return rampa(base, tons, abertura * 1.6, giro)


def propor(imagem: np.ndarray, n: int = 6, chave: str | None = None) -> list[dict]:
    """Cores-base de uma imagem RGBA/RGB (k-médias OKLab, cores reais), sem o fundo/chave e sem a tinta mais escura."""
    rgb = imagem[..., :3].astype(np.int32)
    op = imagem[..., 3] > 127 if imagem.shape[-1] == 4 else np.ones(rgb.shape[:2], bool)
    if chave:
        f = np.array(C.hex_rgb(chave))
    else:
        cantos = np.concatenate([rgb[:4, :4].reshape(-1, 3), rgb[:4, -4:].reshape(-1, 3),
                                 rgb[-4:, :4].reshape(-1, 3), rgb[-4:, -4:].reshape(-1, 3)])
        f = np.median(cantos, 0)
    if imagem.shape[-1] != 4 or op.all():
        op &= np.abs(rgb - f).sum(-1) > 45
    amostra = rgb[op][:: max(1, int(op.sum()) // 60000)].astype(np.uint8)
    if not len(amostra):
        raise ValueError("a imagem não tem figura para tirar a paleta")
    cent = C.kmeans(amostra, n + 1)
    lum = [C.luminancia(C.rgb_hex(c)) for c in cent]
    cent = [c for c, L in zip(cent, lum) if L > min(lum)] or list(cent)   # a mais escura é a tinta
    d = np.linalg.norm(amostra[:, None, :].astype(float) - np.array(cent)[None].astype(float), axis=-1).argmin(1)
    frac = np.bincount(d, minlength=len(cent)) / max(1, len(d))
    out = [{"nome": f"cor{i + 1}", "base": C.rgb_hex(c), "tons": 3, "fracao": round(float(fr), 3)}
           for i, (c, fr) in enumerate(zip(cent, frac))]
    return sorted(out, key=lambda x: -x["fracao"])


def montar(familias: list[dict], tinta: str | None = None, max_cores: int = 20) -> dict:
    """familias: [{"nome", "base", "tons": 3, "tipo": "toon"|"emissivo", "abertura", "giro", "rampa"(opcional)}]."""
    fams, avisos = {}, []
    for f in familias:
        nome, tipo = f["nome"], f.get("tipo", "toon")
        if f.get("rampa"):
            r = [h.lower() for h in f["rampa"]]
        elif tipo == "emissivo":
            tons = int(f.get("tons", 1))
            r = [f["base"].lower()] if tons == 1 else rampa(f["base"], tons, float(f.get("abertura", 0.35)), 15)
        else:
            tons = int(f.get("tons", 3))
            if tons > 3:
                avisos.append(f"{nome}: {tons} tons (a regra é 2–3 por material)")
            r = rampa_material(f["base"], tons, float(f.get("abertura", 0.30)), float(f.get("giro", 25)))
        lum = [C.luminancia(h) for h in r]
        if any(b < a for a, b in zip(lum, lum[1:])):
            avisos.append(f"{nome}: a rampa não vai do escuro ao claro ({r})")
        fams[nome] = {"rampa": r, "tipo": tipo}
        if f.get("limiares"):
            fams[nome]["limiares"] = list(f["limiares"])
    todas = [h for f in fams.values() for h in f["rampa"]]
    if not todas:
        raise ValueError("paleta sem famílias")
    if not tinta:
        tinta = sombrear(min(todas, key=C.luminancia), -0.45)
    tinta = tinta.lower()
    cores = sorted(set(todas + [tinta]))
    if len(cores) > max_cores:
        avisos.append(f"{len(cores)} cores (máximo {max_cores})")
    for i, a in enumerate(cores):
        for b in cores[i + 1:]:
            if C.delta(a, b) < 0.03:
                avisos.append(f"{a} e {b} quase iguais")
    outras = [h for h in todas if h != tinta]
    if outras and C.razao_contraste(tinta, min(outras, key=C.luminancia)) < 1.15:
        avisos.append("a tinta do contorno quase some contra o tom mais escuro")
    return {"familias": fams, "tinta": tinta, "cores": cores, "avisos": avisos}


def familia_de_cor(pal: dict) -> dict:
    """hex -> nome da família ('_tinta' para a tinta)."""
    m = {h: n for n, f in pal["familias"].items() for h in f["rampa"]}
    m[pal["tinta"]] = "_tinta"
    return m


def familia_mais_proxima(pal: dict, hx: str) -> str:
    fam = familia_de_cor(pal)
    if hx in fam:
        return fam[hx]
    return fam[min(fam, key=lambda h: C.delta(h, hx))]


def ler(caminho: str | Path) -> dict:
    p = json.loads(Path(caminho).read_text(encoding="utf-8"))
    for k in ("familias", "tinta", "cores"):
        if k not in p:
            raise ValueError(f"{caminho}: paleta sem '{k}'")
    return p


def salvar(pal: dict, pasta: str | Path) -> tuple[Path, Path]:
    pasta = Path(pasta)
    js = pasta / "paleta.json"
    js.write_text(json.dumps(pal, ensure_ascii=False, indent=1), encoding="utf-8")
    png = pasta / "paleta.png"
    amostra(pal).save(png)
    return js, png


def amostra(pal: dict, k: int = 28) -> Image.Image:
    linhas = list(pal["familias"].items()) + [("tinta", {"rampa": [pal["tinta"]]})]
    w = max(len(f["rampa"]) for _, f in linhas) * k + 130
    im = Image.new("RGB", (w, len(linhas) * (k + 6) + 6), (40, 44, 56))
    d = ImageDraw.Draw(im)
    for i, (nome, f) in enumerate(linhas):
        y = 6 + i * (k + 6)
        d.text((6, y + k // 3), nome[:18], fill=(230, 230, 230))
        for j, h in enumerate(f["rampa"]):
            d.rectangle([124 + j * k, y, 124 + (j + 1) * k - 2, y + k], fill=C.hex_rgb(h))
    return im
