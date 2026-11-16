"""Passo 0 do pipeline Blender: a PALETA da arte, antes de tudo (pedido do Artur, 14/11).

Boas práticas do horys (skill horys-base-e-pele): no máximo 20 cores, 2–3 tons por material com giro de matiz (a
sombra puxa para o azul, a luz para o amarelo), uma tinta de contorno escura, emissivos chapados. A paleta vira
paleta.json, que o render usa como rampa toon de cada família; o Artur aprova o arquivo (travas) antes do render
final.

- propor(): as cores principais do conceito (k-médias em OKLab sem o fundo), para dar nome às famílias.
- montar(): famílias {nome, base, tons, tipo} -> rampas com giro de matiz (paleta_ops.rampa) + tinta + checagens.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

from .. import paleta_ops as PO
from ..pele import _kmeans_lab, hex_rgb

MAX_CORES = 20


def _hex(c) -> str:
    return "#%02x%02x%02x" % tuple(int(v) for v in c[:3])


def propor(conceito: np.ndarray, n: int = 6, fundo: str = "auto") -> list[dict]:
    """Cores-base do conceito: k-médias em OKLab (devolve cores reais da imagem), sem o fundo (cor dos cantos)."""
    rgb = conceito[..., :3].astype(np.int32)
    if conceito.shape[-1] == 4:
        op = conceito[..., 3] > 127
    else:
        op = np.ones(rgb.shape[:2], bool)
    if fundo == "auto":
        cantos = np.concatenate([rgb[:4, :4].reshape(-1, 3), rgb[:4, -4:].reshape(-1, 3),
                                 rgb[-4:, :4].reshape(-1, 3), rgb[-4:, -4:].reshape(-1, 3)])
        f = np.median(cantos, 0)
    else:
        f = np.array(hex_rgb(fundo))
    op &= np.abs(rgb - f).sum(-1) > 45
    amostra = rgb[op][:: max(1, int(op.sum()) // 60000)].astype(np.uint8)
    cent = _kmeans_lab(amostra, n)
    d =np.linalg.norm(amostra[:, None, :].astype(float) - cent[None].astype(float), axis=-1).argmin(1)
    frac = np.bincount(d, minlength=len(cent)) / max(1, len(d))
    saida = [{"base": _hex(c), "fracao": round(float(fr), 3)} for c, fr in zip(cent, frac)]
    return sorted(saida, key=lambda x: -x["fracao"])


def rampa_material(base: str, tons: int = 3, abertura: float = 0.30, giro: float = 25.0) -> list[str]:
    """A base fica SEMPRE na rampa (é a cor do conceito). 3 tons: sombra, base, luz; 2 tons: sombra, base (a luz
    toon de 2 tons fica estourada); 4+: rampa simétrica do paleta_ops. Sombra para o azul, luz para o amarelo."""
    base = base.lower()
    if tons <= 1:
        return [base]
    if tons == 2:
        return [PO.sombrear(base, -abertura, giro), base]
    if tons == 3:
        return [PO.sombrear(base, -abertura, giro), base, PO.sombrear(base, abertura * 0.8, giro)]
    return PO.rampa(base, tons, abertura * 1.6, giro)


def montar(familias: list[dict], tinta: str | None = None, max_cores: int = MAX_CORES) -> dict:
    """familias: [{"nome", "base": "#hex", "tons": 3, "tipo": "toon"|"emissivo", "abertura": 0.55, "giro": 25,
    "rampa": [...] (opcional: rampa pronta, ganha da base), "limiares": [...]}]."""
    fams, avisos = {}, []
    for f in familias:
        nome = f["nome"]
        tipo = f.get("tipo", "toon")
        if f.get("rampa"):
            rampa = [h.lower() for h in f["rampa"]]
        elif tipo == "emissivo":
            tons = int(f.get("tons", 1))
            rampa = [f["base"].lower()] if tons == 1 else PO.rampa(f["base"], tons, float(f.get("abertura", 0.35)),
                                                                   float(f.get("giro", 15)))
        else:
            tons = int(f.get("tons", 3))
            if tons > 3:
                avisos.append(f"{nome}: {tons} tons (a regra é 2–3 por material)")
            rampa = rampa_material(f["base"], tons, float(f.get("abertura", 0.30)), float(f.get("giro", 25)))
        lum = [PO.luminancia(h) for h in rampa]
        if any(b < a for a, b in zip(lum, lum[1:])):
            avisos.append(f"{nome}: a rampa não vai do escuro ao claro ({rampa})")
        fams[nome] = {"rampa": rampa, "tipo": tipo}
        if f.get("limiares"):
            fams[nome]["limiares"] = list(f["limiares"])
    todas = [h for f in fams.values() for h in f["rampa"]]
    if not tinta:
        escura = min(todas, key=PO.luminancia)
        tinta = PO.sombrear(escura, -0.45)
    tinta = tinta.lower()
    cores = sorted(set(todas + [tinta]))
    if len(cores) > max_cores:
        avisos.append(f"{len(cores)} cores (máximo {max_cores}): junte famílias ou divida o tom mais escuro")
    for i, a in enumerate(cores):
        for b in cores[i + 1:]:
            if PO.delta_e(a, b) < 3.0:
                avisos.append(f"{a} e {b} quase iguais (ΔE {PO.delta_e(a, b):.1f})")
    outras = [h for h in todas if h != tinta]
    if outras and PO.razao_contraste(tinta, min(outras, key=PO.luminancia)) < 1.15:
        avisos.append("a tinta do contorno quase some contra o tom mais escuro")
    return {"familias": fams, "tinta": tinta, "cores": cores, "avisos": avisos}


def amostra(pal: dict, k: int = 28) -> Image.Image:
    """Prancha da paleta: uma linha por família (rampa do escuro ao claro) + a tinta."""
    linhas = list(pal["familias"].items()) + [("tinta", {"rampa": [pal["tinta"]]})]
    w = max(len(f["rampa"]) for _, f in linhas) * k + 130
    im = Image.new("RGB", (w, len(linhas) * (k + 6) + 6), (40, 44, 56))
    d = ImageDraw.Draw(im)
    for i, (nome, f) in enumerate(linhas):
        y = 6 + i * (k + 6)
        d.text((6, y + k // 3), nome[:18], fill=(230, 230, 230))
        for j, h in enumerate(f["rampa"]):
            d.rectangle([124 + j * k, y, 124 + (j + 1) * k - 2, y + k], fill=hex_rgb(h))
    return im
