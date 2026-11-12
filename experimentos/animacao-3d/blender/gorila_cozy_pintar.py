"""Pintura por cima do render (frente): o render é guia; capacete e manoplas são redesenhados com o desenho da v03.

    python -I gorila_cozy_pintar.py <pasta anim> [direcao=s]
Lê <pasta>/final/<acao>_<dir>.png (folha, quadros de 72 px) e grava <pasta>/pintado/<acao>_<dir>.png + _6x.gif.
"""
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage as nd

H = lambda h: np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], np.uint8)
K, D, M, L = H("#2a1f2d"), H("#4c1c48"), H("#70346c"), H("#96588c")
S0, S1, S2 = H("#a06c88"), H("#c89ca0"), H("#f0ccb8")
G, E = H("#78f400"), H("#fff6d8")
PEDRA = [S0, S1, S2]


def eh(o, cores):
    r = np.zeros(o.shape[:2], bool)
    for c in cores:
        r |= np.all(o[..., :3] == c, -1) & (o[..., 3] > 0)
    return r


def caveira(o, y0, y1, x0, x1):
    """Capacete da v03 ajustado à caixa: topo claro, órbitas com olho verde e brilho, nariz, dentes e presas."""
    w, h = x1 - x0, y1 - y0
    P = {}
    for y in range(y0, y1):
        for x in range(x0, x1):
            P[(x, y)] = S1
    for x in range(x0, x1):
        P[(x, y0)] = S2
        P[(x, y0 + 1)] = S2 if x < x0 + w * 0.6 else S1
    for y in range(y0, y1):
        P[(x0, y)] = S2
        P[(x1 - 1, y)] = S0
    cx = x0 + w // 2
    ey = y0 + int(h * 0.38)
    for x in range(x0 + 1, x1 - 1):
        P[(x, ey - 2)] = S0
    for s in (-1, 1):
        ex = cx + 1 if s > 0 else cx - 5
        for dx in range(4):
            for dy in range(3):
                P[(ex + dx, ey - 1 + dy)] = K
        for dx in (1, 2):
            P[(ex + dx, ey)] = G
            P[(ex + dx, ey + 1)] = G
        P[(ex + 1, ey)] = E
    ny = ey + 3
    P[(cx - 1, ny)] = K
    P[(cx, ny)] = K
    ty = ny + 2
    for x in range(cx - 4, cx + 4):
        P[(x, ty - 1)] = K
        P[(x, ty)] = S2 if (x - cx) % 2 == 0 else K
        P[(x, ty + 1)] = S2 if (x - cx) % 2 == 0 else K
        P[(x, ty + 2)] = K
    P[(cx - 5, ty + 2)] = S2
    P[(cx + 4, ty + 2)] = S2
    for (x, y), c in P.items():
        if 0 <= y < o.shape[0] and 0 <= x < o.shape[1]:
            o[y, x, :3] = c
            o[y, x, 3] = 255


def manopla(o, mask):
    ys, xs = np.where(mask)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    for y, x in zip(ys, xs):
        c = S1
        if y == y0 or y == y0 + 1:
            c = S2
        if x == x1 - 1 or y == y1 - 1:
            c = S0
        o[y, x, :3] = c
    w = x1 - x0
    for k in (1, 2, 3):
        x = x0 + round(k * w / 4)
        for y in (y1 - 2, y1 - 3):
            if mask[y, x]:
                o[y, x, :3] = S0
    # faixa do punho (borda da manopla com o pelo)
    for x in range(x0, x1):
        if mask[y0, x]:
            o[y0, x, :3] = S0


REF = {}


def pintar(f):
    o = f.copy()
    pedra = eh(o, PEDRA + [G, E]) | eh(o, [K]) & False
    lab, n = nd.label(eh(o, PEDRA))
    if n == 0:
        return o
    comps = []
    for i in range(1, n + 1):
        ys, xs = np.where(lab == i)
        if len(ys) >= 6:
            comps.append((ys.min(), i, ys, xs))
    ry, rx = np.where(eh(o, [G, E]))
    if len(ry):
        cy, cxx = ry.mean(), rx.mean()
        cab = min(comps, key=lambda c: np.hypot(c[2].mean() - cy, c[3].mean() - cxx))
    else:
        cab = min(comps)
    comps = [c for c in comps if c[1] != cab[1]]
    if len(ry):
        ecy, ecx = int(round(ry.mean())), int(round(rx.mean()))
    else:
        ecy, ecx = int(cab[2].mean()), int(cab[3].mean())
    if "box" not in REF:
        ys, xs = cab[2], cab[3]
        REF["box"] = (ys.min() - ecy, ecx - xs.min(), xs.max() + 1 - xs.min(), max(ys.max() + 1, ry.max() + 4) - ys.min())
    dy, dx, bw, bh = REF["box"]
    y0, x0 = ecy + dy, ecx - dx
    y1, x1 = y0 + bh, x0 + bw
    caveira(o, y0, y1, x0, x1)
    for _, i, ys, xs in comps:
        if True:
            manopla(o, lab == i)
    return o


def main():
    base = sys.argv[1]
    d = sys.argv[2] if len(sys.argv) > 2 else "s"
    out = os.path.join(base, "pintado")
    os.makedirs(out, exist_ok=True)
    for acao in ("idle", "andar", "ataque"):
        folha = np.array(Image.open(os.path.join(base, "final", f"{acao}_{d}.png")).convert("RGBA"))
        h, W = folha.shape[:2]
        qs = [pintar(folha[:, i:i + 72]) for i in range(0, W, 72)]
        res = np.concatenate(qs, 1)
        Image.fromarray(res).save(os.path.join(out, f"{acao}_{d}.png"))
        g = []
        for q in qs:
            bg = Image.new("RGBA", (72, h), (79, 168, 71, 255))
            bg.alpha_composite(Image.fromarray(q))
            g.append(bg.resize((72 * 6, h * 6), 0).convert("P", palette=Image.ADAPTIVE))
        g[0].save(os.path.join(out, f"{acao}_{d}_6x.gif"), save_all=True, append_images=g[1:], duration=125, loop=0)


main()
