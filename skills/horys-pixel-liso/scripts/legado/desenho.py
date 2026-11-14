"""Biblioteca de desenho do Motor A (horys-pixel-liso): máscaras por primitivas, crescentes de luz e sombra,
contorno 2/1 e limpeza. Tudo em numpy, sem reamostrar (nada de antialiasing)."""
import numpy as np
from scipy import ndimage

CRUZ = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], bool)
QUADRADO = np.ones((3, 3), bool)


def vazio(W, H):
    return np.zeros((H, W), bool)


def elipse(W, H, cx, cy, rx, ry, inclinacao=0.0):
    """Elipse cheia com centro (cx, cy) e raios rx, ry; inclinacao em graus (gira a elipse)."""
    yy, xx = np.mgrid[0:H, 0:W]
    x, y = xx + 0.5 - cx, yy + 0.5 - cy
    if inclinacao:
        t = np.radians(inclinacao)
        x, y = x * np.cos(t) + y * np.sin(t), -x * np.sin(t) + y * np.cos(t)
    return (x / max(rx, 0.5)) ** 2 + (y / max(ry, 0.5)) ** 2 <= 1.0


def blob(W, H, elipses):
    m = vazio(W, H)
    for e in elipses:
        m |= elipse(W, H, *e)
    return m


def deslocar(m, dx, dy):
    out = np.zeros_like(m)
    H, W = m.shape
    ys, xs = np.nonzero(m)
    ys2, xs2 = ys + int(dy), xs + int(dx)
    ok = (ys2 >= 0) & (ys2 < H) & (xs2 >= 0) & (xs2 < W)
    out[ys2[ok], xs2[ok]] = True
    return out


def suavizar(m):
    """Tira pontas de 1 px e buracos pequenos: a borda fica com degraus regulares."""
    m = ndimage.binary_opening(m, structure=CRUZ)
    m = ndimage.binary_closing(m, structure=CRUZ)
    return ndimage.binary_fill_holes(m)


def crescentes(m, luz_dx=1, luz_dy=-1, k_sombra=4, k_luz=3):
    """Divide a máscara em sombra (crescente grande, lado oposto à luz), luz (crescente pequena, lado da luz) e base.
    luz_dx/luz_dy: direção de onde vem a luz (x+ = frente, y- = cima)."""
    sombra = m & ~deslocar(m, luz_dx * k_sombra, luz_dy * k_sombra)
    luz = m & ~deslocar(m, -luz_dx * k_luz, -luz_dy * k_luz) & ~sombra
    # crescentes limpas: sem fiapos de 1 px
    sombra = ndimage.binary_opening(sombra, structure=CRUZ) & m
    luz = ndimage.binary_opening(luz, structure=CRUZ) & m & ~sombra
    base = m & ~sombra & ~luz
    return sombra, base, luz


def contorno_externo(uniao, espessura=2):
    d = uniao.copy()
    for i in range(espessura):
        d = ndimage.binary_dilation(d, structure=CRUZ if i % 2 == 0 else QUADRADO)
    return d & ~uniao


def linha_interna(de_cima, de_baixo):
    """Linha de 1 px na borda da parte de cima onde ela está sobre a parte de baixo."""
    borda = de_cima & ~ndimage.binary_erosion(de_cima, structure=CRUZ)
    return borda & ndimage.binary_dilation(de_baixo & ~de_cima, structure=CRUZ)


def limpar_orfaos(img, protegidos=None):
    """Pixel opaco sem vizinho (4) da mesma cor vira a cor mais comum entre os vizinhos."""
    H, W = img.shape[:2]
    out = img.copy()
    op = img[..., 3] == 255
    for y, x in zip(*np.nonzero(op)):
        if protegidos is not None and protegidos[y, x]:
            continue
        c = img[y, x]
        viz = [img[yy, xx] for yy, xx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1))
               if 0 <= yy < H and 0 <= xx < W and img[yy, xx, 3] == 255]
        if viz and not any(np.array_equal(v, c) for v in viz):
            vals, cont = np.unique(np.array(viz), axis=0, return_counts=True)
            out[y, x] = vals[np.argmax(cont)]
    return out


def pintar(img, mascara, rgb, alfa=255):
    img[mascara, 0], img[mascara, 1], img[mascara, 2] = rgb
    img[mascara, 3] = alfa
