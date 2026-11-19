"""Gabarito: o render parado do modelo 3D comparado com a arte parada aprovada, vista a vista.

Para cada vista (frente/sul, lado/leste, costas/norte do contrato):
- iou: silhuetas alinhadas pelo pé e pelo centro; 1 = idênticas;
- familia: dentro da interseção, fração dos pixels com a MESMA família de material (pele com pele, roupa com roupa;
  a tinta é uma família). Compara desenho, não sombreado;
- altura: altura do render / altura da arte (escala do modelo em metros contra a arte).
O lado é testado também espelhado (a arte pode olhar para o outro lado); fica o melhor e o relatório diz qual.
Passa quando toda vista tem iou >= iou_min, familia >= familia_min e altura dentro da tolerância.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

from . import cor as C
from . import paleta as P


def _recortar(rgba: np.ndarray) -> np.ndarray:
    op = rgba[..., 3] > 0
    if not op.any():
        raise ValueError("imagem vazia")
    ys, xs = np.nonzero(op)
    return rgba[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def alinhar(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Mesma tela, pé na mesma linha, centros horizontais juntos."""
    a, b = _recortar(a), _recortar(b)
    H = max(a.shape[0], b.shape[0])
    W = max(a.shape[1], b.shape[1]) + 2
    out = []
    for im in (a, b):
        t = np.zeros((H, W, 4), np.uint8)
        y0 = H - im.shape[0]
        x0 = (W - im.shape[1]) // 2
        t[y0:, x0:x0 + im.shape[1]] = im
        out.append(t)
    return out[0], out[1]


def comparar(arte: np.ndarray, render: np.ndarray, pal: dict) -> dict:
    a, r = alinhar(arte, render)
    ma, mr = a[..., 3] > 0, r[..., 3] > 0
    inter, uni = ma & mr, ma | mr
    iou = float(inter.sum() / max(1, uni.sum()))
    cache: dict = {}

    def fam(px):
        h = C.rgb_hex(px)
        if h not in cache:
            cache[h] = P.familia_mais_proxima(pal, h)
        return cache[h]

    # pixel que na arte é tinta (contorno e linha interna) não diz material: fica fora da conta de materiais
    # (decisão do Artur, 2026-11-17); a silhueta continua contando todos
    ys, xs = np.nonzero(inter)
    pares = [(fam(a[y, x, :3]), fam(r[y, x, :3])) for y, x in zip(ys, xs)]
    pares = [(fa, fr) for fa, fr in pares if fa != "_tinta"]
    familia = float(sum(fa == fr for fa, fr in pares) / max(1, len(pares)))
    ha = int(np.ptp(np.nonzero(ma.any(1))[0]) + 1)
    hr = int(np.ptp(np.nonzero(mr.any(1))[0]) + 1)
    return {"iou": round(iou, 4), "familia": round(familia, 4), "altura_arte": ha, "altura_render": hr,
            "altura_razao": round(hr / max(1, ha), 4)}


def comparar_vista(arte: np.ndarray, render: np.ndarray, pal: dict, testar_espelho: bool) -> dict:
    res = comparar(arte, render, pal)
    res["espelhado"] = False
    if testar_espelho:
        esp = comparar(arte[:, ::-1], render, pal)
        if esp["iou"] + esp["familia"] > res["iou"] + res["familia"]:
            res = {**esp, "espelhado": True}
    return res


def avaliar(vistas_arte: dict, renders: dict, pal: dict, limites: dict) -> dict:
    """vistas_arte/renders: {nome_da_vista: RGBA}. limites: jogo['portoes']['gabarito']."""
    out = {"vistas": {}, "falhas": []}
    for nome, arte in vistas_arte.items():
        if nome not in renders:
            out["falhas"].append(f"{nome}: sem render")
            continue
        r = comparar_vista(arte, renders[nome], pal, testar_espelho=(nome == "lado"))
        out["vistas"][nome] = r
        if r["iou"] < limites["iou_min"]:
            out["falhas"].append(f"{nome}: silhueta {r['iou']:.0%} igual (mínimo {limites['iou_min']:.0%}): ajuste a "
                                 "forma do modelo")
        if r["familia"] < limites["familia_min"]:
            out["falhas"].append(f"{nome}: materiais {r['familia']:.0%} no lugar certo (mínimo "
                                 f"{limites['familia_min']:.0%}): confira cores/peças do modelo")
        if abs(r["altura_razao"] - 1) > limites["altura_tol"]:
            out["falhas"].append(f"{nome}: o render tem {r['altura_render']} px e a arte {r['altura_arte']} px: mude o "
                                 "tamanho do modelo em metros (a escala do jogo não muda)")
    out["ok"] = not out["falhas"] and bool(out["vistas"])
    return out


def prancha(vistas_arte: dict, renders: dict, k: int = 6) -> Image.Image:
    """Por vista: arte | render | diferença (verde = os dois, vermelho = só a arte, azul = só o render)."""
    blocos = []
    for nome, arte in vistas_arte.items():
        if nome not in renders:
            continue
        a, r = alinhar(arte, renders[nome])
        ma, mr = a[..., 3] > 0, r[..., 3] > 0
        dif = np.zeros_like(a)
        dif[ma & mr] = (90, 200, 90, 255)
        dif[ma & ~mr] = (230, 70, 70, 255)
        dif[~ma & mr] = (70, 110, 240, 255)
        sep = np.zeros((a.shape[0], 2, 4), np.uint8)
        blocos.append(np.concatenate([a, sep, r, sep, dif], 1))
    if not blocos:
        return Image.new("RGBA", (8, 8))
    H = max(b.shape[0] for b in blocos)
    linha = np.concatenate([np.pad(b, ((H - b.shape[0], 0), (0, 4), (0, 0))) for b in blocos], 1)
    im = Image.fromarray(linha)
    bg = Image.new("RGBA", (im.width * k, im.height * k), (58, 58, 68, 255))
    bg.alpha_composite(im.resize(bg.size, Image.NEAREST))
    return bg
