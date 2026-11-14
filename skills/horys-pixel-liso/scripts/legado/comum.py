"""Funções comuns da skill horys-pixel-liso: config, cor (OKLab), paleta, folhas, grades ampliadas e
detecção de degraus irregulares (adaptada de pixelart-review/scripts/pixel_review.py)."""
import hashlib
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

AQUI = os.path.dirname(os.path.abspath(__file__))

# console do Windows: saída sempre em UTF-8 (acentos) e processos filhos também
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# ---------------------------------------------------------------- config

def config():
    with open(os.path.join(AQUI, "config.json"), encoding="utf-8") as f:
        c = json.load(f)
    c["kb"] = os.path.normpath(c["kb"])
    c["regua"] = os.path.normpath(c["regua"])
    c["trabalho"] = os.path.normpath(c["trabalho"])
    return c


# ---------------------------------------------------------------- cor

def hex2rgb(h):
    h = h.strip().lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb2hex(c):
    return "#%02x%02x%02x" % tuple(int(v) for v in c[:3])


def oklab(rgb):
    """rgb: array (...,3) uint8 -> (L, a, b) float arrays."""
    c = np.asarray(rgb, dtype=np.float64) / 255.0
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = lin[..., 0], lin[..., 1], lin[..., 2]
    l = np.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
    m = np.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
    s = np.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
    L = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s
    A = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
    B = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
    return L, A, B


def carregar_paleta(cfg):
    with open(os.path.join(cfg["kb"], cfg["paleta_json"]), encoding="utf-8") as f:
        p = json.load(f)
    cores, indice = set(), {}
    for nome, lista in p["rampas"].items():
        for i, h in enumerate(lista):
            c = hex2rgb(h)
            cores.add(c)
            indice.setdefault(c, (nome, i))
    return {"contorno": hex2rgb(p["contorno"]), "brilho": [hex2rgb(p["brilho"])], "cores": cores,
            "indice": indice, "rampas": {k: [hex2rgb(h) for h in v] for k, v in p["rampas"].items()}}


# ---------------------------------------------------------------- folhas

def sha256(caminho):
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 16), b""):
            h.update(bloco)
    return h.hexdigest()


def carregar_folha(caminho, quadro_w=0, quadro_h=0):
    """Divide a folha em quadros (horizontal). quadro_w = 0: a imagem inteira é um quadro."""
    im = np.array(Image.open(caminho).convert("RGBA"))
    H, W = im.shape[:2]
    if not quadro_w:
        return [im]
    qh = quadro_h or H
    quadros = []
    for y in range(0, H - qh + 1, qh):
        for x in range(0, W - quadro_w + 1, quadro_w):
            quadros.append(im[y:y + qh, x:x + quadro_w])
    return quadros


def bbox_uniao(quadros, margem=3, incluir_semi=True):
    x0 = y0 = 10 ** 9
    x1 = y1 = -1
    for f in quadros:
        m = f[..., 3] > 0 if incluir_semi else f[..., 3] == 255
        ys, xs = np.nonzero(m)
        if len(xs):
            x0, y0 = min(x0, xs.min()), min(y0, ys.min())
            x1, y1 = max(x1, xs.max()), max(y1, ys.max())
    if x1 < 0:
        h, w = quadros[0].shape[:2]
        return 0, 0, w, h
    h, w = quadros[0].shape[:2]
    return max(0, x0 - margem), max(0, y0 - margem), min(w, x1 + 1 + margem), min(h, y1 + 1 + margem)


def categoria_estado(nome):
    n = nome.lower()
    tabela = [
        ("idle", ("idle", "parado", "respira")), ("andar", ("andar", "walk")), ("correr", ("correr", "run")),
        ("ataque", ("ataque", "attack", "golpe", "slash")), ("tiro", ("tiro", "shoot", "arco", "arremesso")),
        ("trabalhar", ("trabalhar", "interact", "martelar", "picareta", "machado", "work")),
        ("magia", ("magia", "cura", "heal", "cast", "conjurar")), ("dano", ("dano", "hurt", "hit")),
        ("morte", ("morte", "death", "morrer")), ("ambiente", ("ambiente", "balanco", "loop")),
    ]
    for cat, chaves in tabela:
        if any(k in n for k in chaves):
            return cat
    return "idle"


# ---------------------------------------------------------------- desenho de pranchas

def fonte(tam=12):
    for nome in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(nome, tam)
        except OSError:
            pass
    return ImageFont.load_default()


def compor_sobre(f, fundo_rgb):
    """Quadro RGBA sobre fundo sólido -> RGB."""
    base = Image.new("RGBA", (f.shape[1], f.shape[0]), tuple(fundo_rgb) + (255,))
    base.alpha_composite(Image.fromarray(f))
    return base.convert("RGB")


def escala_para_caber(w, h, colunas, linhas, limite, maximo=8, minimo=1):
    for e in range(maximo, minimo - 1, -1):
        if w * e * colunas + 6 * colunas <= limite and (h * e + 22) * linhas <= limite:
            return e
    return minimo


def grade_quadros(quadros, bbox, fundo_rgb, limite=1500, escala=None, colunas=None, grade=8,
                  rotulos=None, marcas=None, titulo=None, minimo_lado=200):
    """Monta quadros recortados em bbox, ampliados (nearest) numa grade, com linhas a cada `grade` px do
    quadro e coordenadas na borda. marcas: lista por quadro de (x, y, cor) em coordenadas do quadro."""
    x0, y0, x1, y1 = bbox
    w, h = x1 - x0, y1 - y0
    n = len(quadros)
    if colunas is None:
        # escolhe o número de colunas que dá a MAIOR escala; empate -> menos linhas
        melhor = None
        for c in range(n, 0, -1):
            li = -(-n // c)
            e_c = escala or escala_para_caber(w, h, c, li, limite)
            chave = (e_c, -li)
            if melhor is None or chave > melhor[0]:
                melhor = (chave, c)
        colunas = melhor[1]
    linhas = -(-n // colunas)
    e = escala or escala_para_caber(w, h, colunas, linhas, limite)
    if e < 4:
        grade = 0  # em escala baixa a grade só polui
    # garante o lado mínimo (visão erra em imagem pequena)
    while (w * e * colunas < minimo_lado and h * e * linhas < minimo_lado) and e < 16:
        e += 1
    topo = 22 if (rotulos or titulo) else 4
    margem_esq = 26
    cw, ch = w * e, h * e
    W = margem_esq + colunas * (cw + 6)
    H = (20 if titulo else 0) + linhas * (ch + topo)
    img = Image.new("RGB", (W, H), (40, 40, 46))
    d = ImageDraw.Draw(img)
    ft = fonte(11)
    if titulo:
        d.text((4, 3), titulo, fill=(240, 240, 240), font=fonte(13))
    oy0 = 20 if titulo else 0
    for i, f in enumerate(quadros):
        col, lin = i % colunas, i // colunas
        ox = margem_esq + col * (cw + 6)
        oy = oy0 + lin * (ch + topo) + topo
        cel = compor_sobre(f[y0:y1, x0:x1], fundo_rgb).resize((cw, ch), Image.NEAREST)
        img.paste(cel, (ox, oy))
        if grade:
            for gx in range((x0 // grade + 1) * grade, x1, grade):
                X = ox + (gx - x0) * e
                d.line([(X, oy), (X, oy + ch - 1)], fill=(20, 20, 26), width=1)
            for gy in range((y0 // grade + 1) * grade, y1, grade):
                Y = oy + (gy - y0) * e
                d.line([(ox, Y), (ox + cw - 1, Y)], fill=(20, 20, 26), width=1)
            if col == 0:
                for gy in range((y0 // (grade * 2) + 1) * grade * 2, y1, grade * 2):
                    d.text((2, oy + (gy - y0) * e - 6), str(gy), fill=(200, 200, 200), font=ft)
            if lin == 0 and i < colunas:
                for gx in range((x0 // (grade * 2) + 1) * grade * 2, x1, grade * 2):
                    d.text((ox + (gx - x0) * e - 6, oy + ch + 1 if linhas == 1 and not rotulos else oy - 12),
                           str(gx), fill=(200, 200, 200), font=ft)
        if rotulos:
            d.text((ox + 2, oy - topo + 2 if not grade else oy - topo + 1), rotulos[i], fill=(255, 220, 120), font=ft)
        if marcas and i < len(marcas):
            for (mx, my, cor) in marcas[i]:
                if x0 <= mx < x1 and y0 <= my < y1:
                    X, Y = ox + (mx - x0) * e, oy + (my - y0) * e
                    d.rectangle([X - 1, Y - 1, X + e, Y + e], outline=cor, width=2)
    return img


# ---------------------------------------------------------------- degraus (adaptado de pixelart-review)

def _perfil_degraus(idx, vals):
    grupos = []
    for i, v in zip(idx, vals):
        if grupos and grupos[-1][2] == v and i == grupos[-1][0] + grupos[-1][1]:
            grupos[-1][1] += 1
        else:
            grupos.append([i, 1, v])
    problemas = []
    for j in range(1, len(grupos) - 1):
        a, b, c = grupos[j - 1], grupos[j], grupos[j + 1]
        if a[2] == c[2] and b[2] != a[2] and b[1] <= 1 and abs(b[2] - a[2]) == 1:
            problemas.append((b[0], b[2], "dente"))
    trechos, atual, sinal = [], [], 0
    for j in range(len(grupos) - 1):
        dx = grupos[j + 1][2] - grupos[j][2]
        if dx == 0:
            continue
        sg = 1 if dx > 0 else -1
        if atual and sg != sinal:
            trechos.append(atual)
            atual = []
        sinal = sg
        atual.append((grupos[j][0], grupos[j][2], grupos[j][1] / abs(dx)))
    if atual:
        trechos.append(atual)
    for t in trechos:
        for k in range(1, len(t) - 1):
            s0, s1, s2 = t[k - 1][2], t[k][2], t[k + 1][2]
            if ((s1 > s0 and s1 > s2) or (s1 < s0 and s1 < s2)) and abs(s0 - s2) <= 0.5 * max(s0, s2):
                problemas.append((t[k][0], t[k][1], "degrau"))
    return problemas


def degraus_irregulares(mascara):
    """Pontos (x, y) de dentes e degraus irregulares na borda externa da silhueta."""
    pts = []
    linhas = [y for y in range(mascara.shape[0]) if mascara[y].any()]
    if linhas:
        xl = [int(np.nonzero(mascara[y])[0].min()) for y in linhas]
        xr = [int(np.nonzero(mascara[y])[0].max()) for y in linhas]
        for (y, x, _k) in _perfil_degraus(linhas, xl) + _perfil_degraus(linhas, xr):
            pts.append((x, y))
    cols = [x for x in range(mascara.shape[1]) if mascara[:, x].any()]
    if cols:
        yt = [int(np.nonzero(mascara[:, x])[0].min()) for x in cols]
        for (x, y, _k) in _perfil_degraus(cols, yt):
            pts.append((x, y))
    return sorted(set(pts))
