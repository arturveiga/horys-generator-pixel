"""Converte uma imagem de IA em pixel art binaria na paleta Horys Liso."""
import argparse
import os
from collections import Counter, deque

import numpy as np
from PIL import Image

import comum as C
import desenho as D


def _amostra_runs(rotulos, eixo, limite):
    """Comprimentos de trechos numa versao grosseiramente quantizada da imagem."""
    dados = np.swapaxes(rotulos, 0, eixo)
    passo = max(1, dados.shape[0] // 96)
    contagem = Counter()
    for linha in dados[::passo]:
        mudancas = np.flatnonzero(np.any(linha[1:] != linha[:-1], axis=1)) + 1
        for n in np.diff(np.r_[0, mudancas, len(linha)]):
            if 1 <= n <= limite:
                contagem[int(n)] += 1
    return contagem


def detectar_escala(img):
    """Estima a grade pelo periodo comum dos trechos de cor em X e Y."""
    h, w = img.shape[:2]
    limite = max(1, min(64, h // 4, w // 4))
    # Cinco bits por canal toleram pequenas variacoes e antialiasing da IA.
    rotulos = np.empty_like(img)
    rotulos[..., :3] = img[..., :3] // 8
    rotulos[..., 3] = img[..., 3] // 64
    runs = _amostra_runs(rotulos, 0, limite) + _amostra_runs(rotulos, 1, limite)
    if not runs or limite < 2:
        return 1

    total = sum(runs.values())
    melhor_n, melhor = 1, 0.0
    for n in range(2, limite + 1):
        # Um trecho pode cobrir varias celulas; aceita erro de 1 px nas bordas suaves.
        apoio = sum(qtd for tam, qtd in runs.items()
                    if tam >= n and min(tam % n, (-tam) % n) <= 1)
        exatos = runs.get(n, 0) + runs.get(n - 1, 0) + runs.get(n + 1, 0)
        score = apoio / total + 0.35 * exatos / total
        if score > melhor + 0.015 or (score >= melhor - 0.015 and score > 0.28 and n > melhor_n):
            melhor_n, melhor = n, score
    # Sem evidencia repetida, a imagem ja esta em densidade 1x.
    return melhor_n if melhor >= 0.28 else 1


def _oklab_para_rgb(lab):
    """Inversa vetorizada de C.oklab, com recorte para sRGB."""
    L, a, b = np.moveaxis(np.asarray(lab, dtype=np.float64), -1, 0)
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    r = 4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    bl = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    linear = np.stack((r, g, bl), axis=-1)
    srgb = np.where(linear <= 0.0031308, 12.92 * linear,
                    1.055 * np.maximum(linear, 0) ** (1 / 2.4) - 0.055)
    return np.clip(np.rint(srgb * 255), 0, 255).astype(np.uint8)


def reduzir(img, escala):
    h, w = img.shape[:2]
    oh, ow = (h + escala - 1) // escala, (w + escala - 1) // escala
    out = np.zeros((oh, ow, 4), dtype=np.uint8)
    for y in range(oh):
        for x in range(ow):
            cel = img[y * escala:min((y + 1) * escala, h),
                      x * escala:min((x + 1) * escala, w)]
            opaca = cel[..., 3] >= 128
            if np.count_nonzero(opaca) * 2 < opaca.size:
                continue
            cores = cel[..., :3][opaca]
            unicas, cont = np.unique(cores, axis=0, return_counts=True)
            i = int(np.argmax(cont))
            if cont[i] / len(cores) > 0.40:
                cor = unicas[i]
            else:
                lab = np.stack(C.oklab(cores), axis=-1)
                cor = _oklab_para_rgb(np.median(lab, axis=0))
            out[y, x, :3] = cor
            out[y, x, 3] = 255
    return out


def recortar_opacos(img):
    ys, xs = np.nonzero(img[..., 3] == 255)
    if not len(xs):
        return img[:1, :1].copy()
    return img[ys.min():ys.max() + 1, xs.min():xs.max() + 1].copy()


def ajustar_altura(img, altura):
    figura = recortar_opacos(img)
    h, w = figura.shape[:2]
    if h == altura:
        return figura
    fator = altura / h
    nw = max(1, int(round(w * fator)))
    return np.array(Image.fromarray(figura).resize((nw, altura), Image.Resampling.NEAREST))


def quantizar(img, paleta):
    cores = np.array(sorted(paleta["cores"]), dtype=np.uint8)
    labs = np.stack(C.oklab(cores), axis=-1)
    op = img[..., 3] == 255
    valores = img[..., :3][op]
    if not len(valores):
        return img
    unicas, inversa = np.unique(valores, axis=0, return_inverse=True)
    ulab = np.stack(C.oklab(unicas), axis=-1)
    indices = np.argmin(np.sum((ulab[:, None, :] - labs[None, :, :]) ** 2, axis=2), axis=1)
    out = img.copy()
    out[..., :3][op] = cores[indices[inversa]]
    out[..., 3] = np.where(op, 255, 0).astype(np.uint8)
    out[..., :3][~op] = 0
    return out


def remover_componentes_pequenos(img, minimo=4):
    mascara = img[..., 3] == 255
    vistos = np.zeros_like(mascara)
    h, w = mascara.shape
    for y, x in zip(*np.nonzero(mascara)):
        if vistos[y, x]:
            continue
        fila, comp = deque([(int(y), int(x))]), []
        vistos[y, x] = True
        while fila:
            yy, xx = fila.popleft()
            comp.append((yy, xx))
            for ny, nx in ((yy - 1, xx), (yy + 1, xx), (yy, xx - 1), (yy, xx + 1)):
                if 0 <= ny < h and 0 <= nx < w and mascara[ny, nx] and not vistos[ny, nx]:
                    vistos[ny, nx] = True
                    fila.append((ny, nx))
        if len(comp) < minimo:
            yy, xx = zip(*comp)
            img[np.array(yy), np.array(xx)] = 0
    return img


def aplicar_contorno(img, rgb):
    mascara = img[..., 3] == 255
    borda = D.contorno_externo(mascara, 2)
    out = img.copy()
    D.pintar(out, borda, rgb)
    return out


def enquadrar(img, q):
    figura = recortar_opacos(img)
    h, w = figura.shape[:2]
    out = np.zeros((q, q, 4), dtype=np.uint8)
    pe = int(round(q * 127 / 192))
    x0, y0 = (q - w) // 2, pe - (h - 1)
    sx0, sy0 = max(0, -x0), max(0, -y0)
    sx1, sy1 = min(w, q - x0), min(h, q - y0)
    if sx1 > sx0 and sy1 > sy0:
        out[max(0, y0):max(0, y0) + sy1 - sy0,
            max(0, x0):max(0, x0) + sx1 - sx0] = figura[sy0:sy1, sx0:sx1]
    return out


def contar_cores(img):
    op = img[..., 3] >= 128
    return len(np.unique(img[..., :3][op], axis=0)) if np.any(op) else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("entrada")
    ap.add_argument("saida")
    ap.add_argument("--escala", type=int)
    ap.add_argument("--altura-alvo", type=int)
    ap.add_argument("--quadro", type=int, default=0)
    ap.add_argument("--contorno", action="store_true")
    args = ap.parse_args()
    if args.escala is not None and args.escala < 1:
        ap.error("--escala deve ser >= 1")
    if args.altura_alvo is not None and args.altura_alvo < 1:
        ap.error("--altura-alvo deve ser >= 1")
    if args.quadro < 0:
        ap.error("--quadro deve ser >= 0")

    original = np.array(Image.open(args.entrada).convert("RGBA"))
    cores_antes = contar_cores(original)
    escala = args.escala or detectar_escala(original)
    img = reduzir(original, escala)
    if args.altura_alvo:
        img = ajustar_altura(img, args.altura_alvo)
    paleta = C.carregar_paleta(C.config())
    img = quantizar(img, paleta)
    img = remover_componentes_pequenos(img)
    img = D.limpar_orfaos(img)
    if args.contorno:
        img = aplicar_contorno(img, paleta["contorno"])
    tamanho_figura = recortar_opacos(img).shape[:2]
    if args.quadro:
        img = enquadrar(img, args.quadro)

    os.makedirs(os.path.dirname(os.path.abspath(args.saida)), exist_ok=True)
    Image.fromarray(img, "RGBA").save(args.saida)
    print(f"Escala detectada: {escala}")
    print(f"Cores antes/depois: {cores_antes}/{contar_cores(img)}")
    print(f"Tamanho da figura: {tamanho_figura[1]}x{tamanho_figura[0]} px")


if __name__ == "__main__":
    main()
