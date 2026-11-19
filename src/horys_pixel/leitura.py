"""Arte parada: imagem do gerador -> um sprite 1x por vista, lido na grade da PRÓPRIA imagem. Não cria forma.

Entrada (ver prompt.md): pixel art ampliada (cada pixel = um bloco de N px; o gerador varia o bloco alguns px), vistas
lado a lado na ordem frente, lado (olhando para a direita), costas, fundo chapado #FF00FF. Também aceita pixel art 1x
ou ampliada por um inteiro exato (arte feita à mão): essa é lida sem nenhuma alteração.

Passos da leitura de imagem gerada:
1. grade: tamanho do bloco e fase pelas bordas de cor; cada corte é puxado para a borda real mais próxima;
2. cor: cada pixel encaixado na paleta (a do asset, travada, ou n cores reais da imagem) ou na chave; cada célula
   recebe a cor mais votada no miolo dela;
3. detalhe preservado: mancha de cor contrastante, com área >= 35% de um bloco, que sumiu no voto (olho, botão,
   fivela) volta na célula que ela mais cobre;
4. ruído: célula isolada com quase a mesma cor do entorno vira o entorno; detalhe preservado e tinta ficam;
5. contorno: contorno duplo afinado para 1 px e falha no contorno fechada (opcional);
6. escala: a altura lida tem que ser a pedida (± 5%); senão ErroLeitura: gere a imagem de novo;
7. vistas separadas e alinhadas pelo pé numa folha.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

from . import cor as C

CHAVE = "#ff00ff"
NOMES_VISTAS = ["frente", "lado", "costas"]
CRUZ = ndimage.generate_binary_structure(2, 1)
QUADRADO = np.ones((3, 3), bool)


class ErroLeitura(ValueError):
    pass


@dataclass
class Leitura:
    vistas: dict                      # nome -> RGBA 1x recortado
    folha: np.ndarray                 # vistas lado a lado, alinhadas pelo pé
    bloco: float
    altura: int
    paleta: list
    relatorio: dict = field(default_factory=dict)


# ------------------------------------------------------------------ entrada


def carregar(caminho: str | Path, chave: str = CHAVE) -> np.ndarray:
    """RGB uint8; o que for transparente vira a cor-chave."""
    im = Image.open(caminho).convert("RGBA")
    bg = Image.new("RGBA", im.size, C.hex_rgb(chave) + (255,))
    bg.alpha_composite(im)
    return np.asarray(bg.convert("RGB")).copy()


def escala_exata(rgb: np.ndarray, maximo: int = 32) -> int:
    """k > 1 quando a imagem é pixel art ampliada por um inteiro exato (sem compressão nem antisserrilhado)."""
    h, w = rgb.shape[:2]
    g = math.gcd(h, w)
    for k in range(min(g, maximo), 1, -1):
        if g % k == 0:
            red = rgb[::k, ::k]
            if np.array_equal(np.repeat(np.repeat(red, k, 0), k, 1), rgb):
                return k
    return 1


# ------------------------------------------------------------------ grade da própria imagem


def _sobel_eixos(rgb: np.ndarray):
    c = rgb[..., :3].astype(np.float64) @ np.array([0.299, 0.587, 0.114])
    g = np.pad(c, 1, mode="reflect")
    gx = (g[:-2, 2:] + 2 * g[1:-1, 2:] + g[2:, 2:]) - (g[:-2, :-2] + 2 * g[1:-1, :-2] + g[2:, :-2])
    gy = (g[2:, :-2] + 2 * g[2:, 1:-1] + g[2:, 2:]) - (g[:-2, :-2] + 2 * g[:-2, 1:-1] + g[:-2, 2:])
    return np.abs(gx).sum(0), np.abs(gy).sum(1)


def _fase_sobel(grad: np.ndarray, passo: float) -> float:
    """Fase da grade rígida que mais cai em cima das bordas (média da raiz do gradiente nas linhas da grade)."""
    n = len(grad)
    raiz = np.sqrt(np.maximum(grad, 0))
    eixo = np.arange(n)
    melhor_f, melhor_s = 0.0, -np.inf
    for f in np.arange(0.0, passo, min(0.25, passo / 16)):
        pos = np.arange(f, n - 1, passo)
        pos = pos[pos > 0]
        if len(pos):
            s = float(np.interp(pos, eixo, raiz).mean())
            if s > melhor_s:
                melhor_s, melhor_f = s, float(f)
    return melhor_f


def grade_nativa(rgb: np.ndarray) -> tuple[float, float, float, float]:
    """Bloco (pixel quadrado) pela coerência de fase das bordas módulo o bloco; fases pelo Sobel.
    Devolve (bloco, fase_x, fase_y, coerência)."""
    res = []
    for eixo in (1, 0):
        d = np.abs(np.diff(rgb.astype(int), axis=eixo)).sum(-1) > 60
        pos = np.nonzero(d)[eixo] + 1
        if not len(pos):
            raise ErroLeitura("a imagem não tem bordas de cor: não é pixel art")
        melhor = (0.0, 1.0)
        for s in np.arange(4.0, 48.0, 0.02):
            r = abs(np.mean(np.exp(2j * np.pi * (pos % s) / s))) * (1 + 0.002 * s)
            if r > melhor[0]:
                melhor = (r, s)
        # submúltiplo: se todas as bordas caem em k·s, o bloco certo é o maior que mantém >= 90% da coerência
        for k in (4, 3, 2):
            sk = melhor[1] * k
            if sk >= 48.0:
                continue
            cand = max(((abs(np.mean(np.exp(2j * np.pi * (pos % s) / s))), s)
                        for s in np.arange(sk * 0.99, sk * 1.01, 0.01)), key=lambda t: t[0])
            if cand[0] >= 0.9 * melhor[0] / (1 + 0.002 * melhor[1]):
                melhor = (cand[0] * (1 + 0.002 * cand[1]), cand[1])
                break
        res.append(melhor)
    coer, bloco = max(res, key=lambda t: t[0])
    sx, sy = _sobel_eixos(rgb)
    return float(bloco), _fase_sobel(sx, bloco), _fase_sobel(sy, bloco), float(coer)


def cortes_exatos(s: np.ndarray, k: int, bloco: float, menor: float = 0.7, maior: float = 1.35,
                  peso_ritmo: float = 2.0, com_nota: bool = False):
    """k blocos num trecho de comprimento n = len(s)-1, com cortes nas pontas (0 e n, bordas da figura).
    Programação dinâmica: cada corte interno cai onde a borda de cor é forte; cada bloco mede entre menor·bloco e
    maior·bloco e custa por fugir do tamanho médio (onde não há borda, vale o ritmo). O gerador não desenha blocos
    uniformes e o erro de uma grade rígida acumula; aqui a sequência inteira é escolhida de uma vez."""
    n = len(s) - 1
    k = max(1, int(k))
    lo, hi = max(1, int(np.floor(menor * bloco))), max(2, int(np.ceil(maior * bloco)))
    lo, hi = min(lo, n // k), max(hi, -(-n // k))
    lo = max(1, lo)
    gaps = np.arange(lo, hi + 1)
    custo = peso_ritmo * ((gaps - n / k) / (n / k)) ** 2 * 4
    menos = -np.inf
    melhor = np.full(n + 1, menos)
    melhor[0] = 0.0
    de = np.zeros((k + 1, n + 1), np.int64)
    for kk in range(1, k + 1):
        cand = np.full((len(gaps), n + 1), menos)
        for gi, g in enumerate(gaps):
            cand[gi, g:] = melhor[:n + 1 - g] - custo[gi]
        arg = cand.argmax(0)
        novo = cand[arg, np.arange(n + 1)] + s
        de[kk] = np.arange(n + 1) - gaps[arg]
        melhor = novo
    if not np.isfinite(melhor[n]):
        out = [int(round(i * n / k)) for i in range(k + 1)]
        return (out, -np.inf) if com_nota else out
    out = [n]
    i = n
    for kk in range(k, 0, -1):
        i = int(de[kk, i])
        out.append(i)
    out = sorted(out)
    return (out, float(melhor[n])) if com_nota else out


def _trechos(proj: np.ndarray) -> list[tuple[int, int]]:
    return [(sl[0].start, sl[0].stop) for sl in ndimage.find_objects(ndimage.label(proj)[0])]


def cortes(rgb: np.ndarray, bloco: float, eixo: int, figura: np.ndarray, contagens: list[int] | None = None,
           juntar: float = 0.0) -> np.ndarray:
    """Cortes de um eixo (1: colunas, 0: linhas). Cada trecho com figura (projeção) recebe cortes_exatos com o número
    de blocos dado (contagens) ou o mais perto de comprimento/bloco; o fundo entre trechos fica com grade rígida.
    juntar: trechos separados por menos que isso (px) viram um só (a capa solta do corpo, o vão entre as pernas)."""
    d = np.abs(np.diff(rgb.astype(np.int32), axis=eixo)).sum(-1)
    perfil = d.sum(axis=1 - eixo).astype(np.float64)
    n = rgb.shape[eixo]
    s = np.zeros(n + 1)
    s[1:n] = np.sqrt(perfil)
    pos = s[s > 0]
    if len(pos):
        s = s / np.percentile(pos, 75)
    trechos = []
    for a, b in _trechos(figura.any(axis=1 - eixo)):
        if trechos and a - trechos[-1][1] <= juntar:
            trechos[-1] = (trechos[-1][0], b)
        else:
            trechos.append((a, b))
    out: list[int] = [0]
    passo = max(1.0, bloco)
    for t, (a, b) in enumerate(trechos):
        c = out[-1] + passo
        while c < a - 0.5 * passo:
            out.append(int(round(c)))
            c += passo
        if contagens and t < len(contagens):
            melhores = cortes_exatos(s[a:b + 1], contagens[t], bloco)
        else:
            # contagem livre: k-1, k ou k+1 blocos, o que casar melhor com as bordas (cada corte paga 1)
            k0 = max(1, int(round((b - a) / bloco)))
            notas = []
            for k in (k0 - 1, k0, k0 + 1):
                if k >= 1:
                    c, v = cortes_exatos(s[a:b + 1] - 1.0, k, bloco, com_nota=True)
                    notas.append((v, c))
            melhores = max(notas, key=lambda t: t[0])[1]
        out += [a + x for x in melhores]
    c = out[-1] + passo
    while c < n - 0.5 * passo:
        out.append(int(round(c)))
        c += passo
    out.append(n)
    return np.array(sorted(set(min(max(int(v), 0), n) for v in out)))


# ------------------------------------------------------------------ etapas


def _votar(idx_img: np.ndarray, cx: np.ndarray, cy: np.ndarray, k_chave: int, miolo: float = 0.6) -> np.ndarray:
    H, W = len(cy) - 1, len(cx) - 1
    out = np.full((H, W), -1, np.int32)
    for i in range(H):
        a, b = cy[i], cy[i + 1]
        m = (b - a) * (1 - miolo) / 2
        ya, yb = int(a + m), max(int(a + m) + 1, int(round(b - m)))
        for j in range(W):
            c, e = cx[j], cx[j + 1]
            m2 = (e - c) * (1 - miolo) / 2
            xa, xb = int(c + m2), max(int(c + m2) + 1, int(round(e - m2)))
            v = np.bincount(idx_img[ya:yb, xa:xb].ravel(), minlength=k_chave + 1)
            k = int(v.argmax())
            out[i, j] = -1 if k == k_chave else k
    return out


def _preservar(idx_img, cx, cy, out, k_chave, lab_pal, bloco, area_min=0.35, contraste=0.15, cobertura=0.25):
    """Mancha de cor (componente na imagem grande) que sumiu no voto volta na célula que ela mais cobre, se
    contrastar com a cor que ganhou ali. Devolve a máscara das células restauradas."""
    H, W = out.shape
    lin = np.clip(np.searchsorted(cy, np.arange(idx_img.shape[0]), side="right") - 1, 0, H - 1)
    col = np.clip(np.searchsorted(cx, np.arange(idx_img.shape[1]), side="right") - 1, 0, W - 1)
    area_cel = (np.diff(cy)[:, None] * np.diff(cx)[None, :]).astype(np.float64)
    prot = np.zeros((H, W), bool)
    minimo = area_min * bloco * bloco
    for c in range(k_chave):
        rot, n = ndimage.label(idx_img == c)
        if not n:
            continue
        tam = np.bincount(rot.ravel())
        for comp, sl in enumerate(ndimage.find_objects(rot), 1):
            if sl is None or tam[comp] < minimo:
                continue
            ys, xs = np.nonzero(rot[sl] == comp)
            cel = lin[ys + sl[0].start] * W + col[xs + sl[1].start]
            cont = np.bincount(cel, minlength=H * W)
            tocadas = np.nonzero(cont)[0]
            if (out.flat[tocadas] == c).any():
                continue
            melhor = int(tocadas[cont[tocadas].argmax()])
            if cont[melhor] < cobertura * area_cel.flat[melhor]:
                continue
            ganhou = int(out.flat[melhor])
            if ganhou >= 0 and np.linalg.norm(lab_pal[c] - lab_pal[ganhou]) < contraste:
                continue
            out.flat[melhor] = c
            prot.flat[melhor] = True
    return prot


def _limpar_ruido(idx: np.ndarray, lab_pal: np.ndarray, proteger: np.ndarray, tinta: int, limiar: float = 0.10) -> int:
    """Célula sem vizinho (4) da mesma cor, com quase a mesma cor do entorno (8, maioria >= 4), vira o entorno."""
    h, w = idx.shape
    n = 0
    for _ in range(2):
        p = np.pad(idx, 1, constant_values=-1)
        mud = 0
        for y, x in zip(*np.nonzero(idx >= 0)):
            c = int(idx[y, x])
            if c == tinta or proteger[y, x]:
                continue
            v4 = (p[y, x + 1], p[y + 2, x + 1], p[y + 1, x], p[y + 1, x + 2])
            if c in v4:
                continue
            v8 = p[y:y + 3, x:x + 3].ravel()
            v8 = np.delete(v8, 4)
            v8 = v8[(v8 >= 0) & (v8 != tinta)]
            if len(v8) < 4:
                continue
            vals, cont = np.unique(v8, return_counts=True)
            k = int(vals[cont.argmax()])
            if cont.max() >= 4 and np.linalg.norm(lab_pal[c] - lab_pal[k]) < limiar:
                idx[y, x] = k
                mud += 1
        n += mud
        if not mud:
            break
    return n


def _contorno(idx: np.ndarray, tinta: int, fechar: bool = True) -> tuple[int, int]:
    """Afina contorno duplo para 1 px e (fechar) fecha falhas na borda. Devolve (afinados, fechados)."""
    op = idx >= 0
    fora = ndimage.binary_dilation(~op, CRUZ) & op            # pixel da figura encostado no vazio
    borda_t = fora & (idx == tinta)
    dentro = (idx == tinta) & ~fora & ndimage.binary_dilation(borda_t, CRUZ)
    afinados = 0
    p = np.pad(idx, 1, constant_values=-1)
    for y, x in zip(*np.nonzero(dentro)):
        v = p[y:y + 3, x:x + 3].ravel()
        v = v[(v >= 0) & (v != tinta)]
        if len(v):
            vals, cont = np.unique(v, return_counts=True)
            idx[y, x] = int(vals[cont.argmax()])
            afinados += 1
    fechados = 0
    op = idx >= 0
    fora = ndimage.binary_dilation(~op, CRUZ) & op
    # só fecha falha quando a arte USA contorno (>= 60% da borda já é tinta); contorno seletivo fica como veio
    if fechar and fora.any() and (idx[fora] == tinta).mean() >= 0.6:
        pv = np.pad(op, 1, constant_values=False)
        fino = (~pv[1:-1, :-2] & ~pv[1:-1, 2:]) | (~pv[:-2, 1:-1] & ~pv[2:, 1:-1])
        abrir = fora & (idx != tinta) & ~fino
        idx[abrir] = tinta
        fechados = int(abrir.sum())
    return afinados, fechados


def _separar(rgba: np.ndarray) -> list[np.ndarray]:
    """Uma imagem por vista: componentes grandes, da esquerda para a direita; peças pequenas (arma solta, faísca) vão
    para a vista cuja faixa horizontal as contém (ou a mais perto)."""
    op = rgba[..., 3] > 0
    rot, n = ndimage.label(op, QUADRADO)
    if not n:
        raise ErroLeitura("nenhuma figura encontrada (confira a cor-chave do fundo)")
    tam = np.bincount(rot.ravel())
    tam[0] = 0
    objs = ndimage.find_objects(rot)
    grandes = [i for i in range(1, n + 1) if tam[i] >= 0.15 * tam.max()]
    grupos = {g: [g] for g in grandes}
    faixa = {g: (objs[g - 1][1].start, objs[g - 1][1].stop) for g in grandes}
    for i in range(1, n + 1):
        if i in grupos:
            continue
        cx = (objs[i - 1][1].start + objs[i - 1][1].stop) / 2
        g = min(grandes, key=lambda g: 0 if faixa[g][0] - 2 <= cx <= faixa[g][1] + 2
                else min(abs(cx - faixa[g][0]), abs(cx - faixa[g][1])))
        grupos[g].append(i)
    vistas = []
    for g in sorted(grandes, key=lambda g: faixa[g][0]):
        m = np.isin(rot, grupos[g])
        ys, xs = np.nonzero(m)
        sub = np.where(m[..., None], rgba, 0).astype(np.uint8)
        vistas.append(sub[ys.min():ys.max() + 1, xs.min():xs.max() + 1])
    return vistas


def montar_folha(vistas: list[np.ndarray], margem: int = 2, vao: int = 4) -> np.ndarray:
    H = max(v.shape[0] for v in vistas) + 2 * margem
    W = sum(v.shape[1] for v in vistas) + vao * (len(vistas) - 1) + 2 * margem
    folha = np.zeros((H, W, 4), np.uint8)
    x = margem
    for v in vistas:
        y = H - margem - v.shape[0]
        m = v[..., 3] > 0
        folha[y:y + v.shape[0], x:x + v.shape[1]][m] = v[m]
        x += v.shape[1] + vao
    return folha


# ------------------------------------------------------------------ leitura


def ler(rgb: np.ndarray, alvo: int, *, paleta: list[str] | None = None, tinta: str | None = None,
        chave: str = CHAVE, n_cores: int = 16, contorno: bool = True, tolerancia: float = 0.05) -> Leitura:
    """rgb: imagem RGB (fundo = chave). alvo: altura em px que a figura mais alta tem que ter."""
    if rgb.ndim != 3 or rgb.shape[2] < 3:
        raise ErroLeitura("imagem inválida")
    rgb = np.ascontiguousarray(rgb[..., :3]).astype(np.uint8)
    ch = np.array(C.hex_rgb(chave), np.float64)
    avisos: list[str] = []
    rel: dict = {"alvo": int(alvo)}
    k = escala_exata(rgb)
    exata = k > 1 or max(rgb.shape[:2]) <= 256
    if exata:
        nat = rgb[::k, ::k] if k > 1 else rgb
        vazio = np.abs(nat.astype(np.float64) - ch).sum(-1) <= 90
        fig = nat[~vazio]
        if not len(fig):
            raise ErroLeitura("nenhuma figura encontrada (confira a cor-chave do fundo)")
        if paleta:
            pal = np.array([C.hex_rgb(h) for h in paleta], np.float64)
        else:
            uni = np.unique(fig.reshape(-1, 3), axis=0)
            pal = uni.astype(np.float64) if len(uni) <= max(n_cores, 64) else C.kmeans(fig, n_cores)
        idx = np.full(nat.shape[:2], -1, np.int32)
        idx[~vazio] = C.encaixar(fig[None], pal)[0]
        rel.update({"modo": "exata", "escala": int(k), "bloco": float(k), "coerencia": 1.0})
        bloco = float(k)
    else:
        bloco_fft, _, _, coer = grade_nativa(rgb)
        figura = np.abs(rgb.astype(np.float64) - ch).sum(-1) > 90
        figura = ndimage.binary_opening(figura, QUADRADO)          # tira a franja de 1 px do antisserrilhado
        if not figura.any():
            raise ErroLeitura("nenhuma figura encontrada (confira a cor-chave do fundo)")
        linhas = np.nonzero(figura.any(1))[0]
        alt_img = int(linhas.max() - linhas.min() + 1)
        nativa = alt_img / bloco_fft
        tol_n = max(1.5, 0.045 * alvo)
        rel["altura_estimada"] = round(nativa, 1)
        if abs(nativa - alvo) > tol_n:
            raise ErroLeitura(f"a figura tem ~{nativa:.0f} px de altura na grade da imagem (bloco de "
                              f"{bloco_fft:.1f} px), e o pedido é {alvo} px. Gere a imagem de novo (ver prompt.md): "
                              f"peça a figura com exatamente {alvo} pixels de altura.")
        bloco = alt_img / float(alvo)                                # a altura pedida fixa o bloco
        cy = cortes(rgb, bloco, 0, figura, contagens=[alvo], juntar=10 ** 9)
        cx = cortes(rgb, bloco, 1, figura, juntar=0.5 * bloco)
        if paleta:
            pal = np.array([C.hex_rgb(h) for h in paleta], np.float64)
        else:
            amostra = rgb[figura][:: max(1, int(figura.sum()) // 200000)]
            pal = C.kmeans(amostra, n_cores)
        todas = np.vstack([pal, ch[None]])
        idx_img = C.encaixar(rgb, todas).astype(np.int32)
        kc = len(pal)
        idx = _votar(idx_img, cx, cy, kc)
        lab = C.oklab(pal)
        prot = _preservar(idx_img, cx, cy, idx, kc, lab, bloco)
        t = (int(np.argmin([C.luminancia(C.rgb_hex(c)) for c in pal])) if not tinta
             else int(C.encaixar(np.array([C.hex_rgb(tinta)], np.float64)[None], pal)[0][0]))
        ruido = _limpar_ruido(idx, lab, prot, t)
        afin, fech = _contorno(idx, t, fechar=contorno) if contorno else (0, 0)
        rel.update({"modo": "grade", "bloco": round(bloco, 2), "bloco_fft": round(bloco_fft, 2),
                    "coerencia": round(coer, 3),
                    "detalhes_preservados": int(prot.sum()), "ruido_limpo": ruido,
                    "contorno_afinado": afin, "contorno_fechado": fech})
        if coer < 0.05:
            avisos.append(f"grade fraca (coerência {coer:.2f}): a imagem talvez não seja pixel art")
    rgba = np.zeros(idx.shape + (4,), np.uint8)
    m = idx >= 0
    rgba[m, :3] = np.clip(np.rint(pal[idx[m]]), 0, 255).astype(np.uint8)
    rgba[m, 3] = 255
    vistas = _separar(rgba)
    alturas = [int(v.shape[0]) for v in vistas]
    altura = max(alturas)
    tol = max(1, int(round(tolerancia * alvo)))
    rel["altura"] = altura
    if abs(altura - alvo) > tol:
        sugerido = ""
        if not exata:
            sugerido = f" Hoje cada pixel tem ~{bloco:.1f} px; peça a figura com exatamente {alvo} pixels de altura."
        raise ErroLeitura(f"a figura tem {altura} px de altura na grade da imagem, e o pedido é {alvo} px "
                          f"(tolerância ±{tol}). Gere a imagem de novo (ver prompt.md).{sugerido}")
    if max(alturas) - min(alturas) > tol:
        avisos.append(f"vistas com alturas diferentes {alturas}: confira se é a mesma escala")
    if len(vistas) == 3:
        nomes = list(NOMES_VISTAS)
    elif len(vistas) == 1:
        nomes = ["frente"]
    else:
        nomes = [f"vista{i + 1}" for i in range(len(vistas))]
        avisos.append(f"{len(vistas)} vistas encontradas (o pedido é 3: frente, lado, costas)")
    usadas = sorted({tuple(int(c) for c in p) for v in vistas for p in v[v[..., 3] > 0][:, :3]})
    rel.update({"vistas": {n: [int(v.shape[1]), int(v.shape[0])] for n, v in zip(nomes, vistas)},
                "cores": [C.rgb_hex(c) for c in usadas], "avisos": avisos})
    return Leitura(dict(zip(nomes, vistas)), montar_folha(vistas), float(bloco), altura,
                   [C.rgb_hex(c) for c in usadas], rel)


def previa(rgba: np.ndarray, k: int = 8, fundo=(58, 58, 68, 255)) -> Image.Image:
    big = Image.fromarray(rgba).resize((rgba.shape[1] * k, rgba.shape[0] * k), Image.NEAREST)
    bg = Image.new("RGBA", big.size, fundo)
    bg.alpha_composite(big)
    return bg
