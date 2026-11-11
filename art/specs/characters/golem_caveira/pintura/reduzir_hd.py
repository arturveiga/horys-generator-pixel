"""Reduz a arte HD (montado.png) para o tamanho do sprite do SpriteKiln, na paleta do golem.

Moda por bloco na paleta (sem borrar), achatada por cos(38°) como a câmera top-down vê uma frente,
contorno externo de 1 px no tom mais escuro. Saída: pintura/hd_reduzido.png e a comparação lado a lado.
"""
import math, numpy as np, yaml
from PIL import Image

LARG = 120                      # largura do personagem na base do SpriteKiln (bbox de base_s.png)
HD = r"..\..\..\..\..\hd\golem-caveira\montado.png"
pal = yaml.safe_load(open(r"..\..\..\palettes\golem.yaml", encoding="utf-8"))["ramps"]
cores = [tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) for r in pal.values() for h in r]

im = Image.open(HD).convert("RGB"); a = np.array(im).astype(int)
fundo = (a[..., 0] > 170) & (a[..., 2] > 170) & (a[..., 1] < 120)
ys, xs = np.where(~fundo); x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
a = a[y0:y1, x0:x1]; fundo = fundo[y0:y1, x0:x1]
w = LARG; h = round((y1 - y0) * LARG / (x1 - x0) * math.cos(math.radians(38)))
P = np.array(cores)
dist = ((a[..., None, :] - P[None, None]) ** 2).sum(-1); idx = dist.argmin(-1)
out = np.zeros((h, w, 4), np.uint8)
sx, sy = a.shape[1] / w, a.shape[0] / h
for y in range(h):
    for x in range(w):
        bx = slice(int(x * sx), max(int(x * sx) + 1, int((x + 1) * sx)))
        by = slice(int(y * sy), max(int(y * sy) + 1, int((y + 1) * sy)))
        f = fundo[by, bx]
        if f.mean() > 0.5: continue
        v = np.bincount(idx[by, bx][~f], minlength=len(P))
        out[y, x, :3] = P[v.argmax()]; out[y, x, 3] = 255
# contorno externo de 1 px na cor mais escura da paleta
esc = P[P.sum(1).argmin()]
op = out[..., 3] > 0; borda = op & ~(np.roll(op, 1, 0) & np.roll(op, -1, 0) & np.roll(op, 1, 1) & np.roll(op, -1, 1))
out[borda, :3] = esc
Image.fromarray(out).save("hd_reduzido.png")
base = Image.open("base_s.png").convert("RGBA")
z = 4; c = Image.new("RGBA", (base.width * z * 2 + 20, base.height * z), (40, 40, 52, 255))
c.alpha_composite(base.resize((base.width * z, base.height * z), Image.NEAREST), (0, 0))
r = Image.fromarray(out).resize((w * z, h * z), Image.NEAREST)
c.alpha_composite(r, (base.width * z + 20 + (base.width * z - w * z) // 2, (base.height - h) * z - 28 * z))
c.save("comparar.png"); print("hd reduzido:", w, "x", h)
