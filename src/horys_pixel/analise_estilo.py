"""Leitura de imagens para "criar meu estilo" (docs/estilos.md, passo 2 e 3).

analisar_imagens(caminhos) -> dict
    Para um lote de PNG/JPG (pixel art de verdade ou imagens comuns): detecta o tamanho do pixel (escala) pela
    coerência das bordas de cor (equivalente ao MDC dos run-lengths, mas tolerante a ruído de JPG) e reduz para a
    grade real; tira o fundo liso; conta cores; propõe uma paleta em RAMPAS (agrupa por matiz em OKLCH, ordena por L,
    2–4 tons por rampa, no máximo ~32 cores); acha a cor de contorno provável (a mais escura e frequente na borda da
    silhueta) e se há contorno; mede tamanho médio de cluster, tons por material, proporção altura/largura dos
    sprites, dithering e antialiasing, luz e temperatura.

criar_pacote(nome, caminhos, destino=None, autor="", licenca_imagens="") -> Path
    Roda a análise e grava um pacote de estilo em ~/.horys-pixel/estilos/<nome>/ (estilo.json, paleta.json/.gpl/.hex,
    analise.json, estilo.md rascunho com os 15 itens do guia de estilo, referencias/ + origem.json).
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math
import re
import shutil
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

from . import estilos as E
from .motor import comum as C

CRUZ = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], bool)
MAX_CORES = 32
NEUTRO_C = 0.035          # croma OKLCH abaixo disso: rampa neutra (cinza)
LIMIAR_BORDA = 40         # soma |ΔRGBA| que conta como "mudou de cor" ao procurar a grade
NOMES_MATIZ = [(35, "vermelho"), (70, "laranja"), (115, "amarelo"), (165, "verde"), (215, "ciano"),
               (285, "azul"), (320, "roxo"), (360, "rosa")]


# ====================================================================== cor

def _hex(c) -> str:
    return "#%02x%02x%02x" % tuple(int(v) for v in c[:3])


def _lab(rgb) -> np.ndarray:
    L, a, b = C.oklab(np.asarray(rgb, dtype=np.float64))
    return np.stack([L, a, b], -1)


def _lch(lab) -> tuple[float, float, float]:
    L, a, b = (float(v) for v in lab)
    return L, math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360


def _nome_matiz(h: float, c: float) -> str:
    if c < NEUTRO_C:
        return "neutro"
    for lim, nome in NOMES_MATIZ:
        if h < lim:
            return nome
    return "vermelho"


def _dh(h1: float, h2: float) -> float:
    d = abs(h1 - h2) % 360
    return min(d, 360 - d)


# ====================================================================== escala e grade

def _escala_eixo(im: np.ndarray, eixo: int) -> tuple[int, int, float]:
    """(tamanho do pixel, fase, coerência) num eixo: o maior bloco s em que quase toda a ENERGIA das bordas de cor
    cai na mesma posição módulo s. Numa imagem limpa é o MDC dos run-lengths; pesar pela força da borda deixa o
    ruído fraco de JPG e de redimensionamento de fora."""
    d = np.abs(np.diff(im.astype(np.int32), axis=eixo)).sum(-1)
    forca = np.clip(d - LIMIAR_BORDA, 0, None).astype(float)
    perfil = forca.sum(axis=1 - eixo)          # energia por posição de borda ao longo do eixo
    pos = np.arange(1, len(perfil) + 1)
    total = perfil.sum()
    if total <= 0 or (forca > 0).sum() < 12:
        return 1, 0, 1.0
    melhor = (1, 0, 1.0)
    for s in range(2, 33):
        if s * 3 > len(perfil):
            break
        cont = np.bincount(pos % s, weights=perfil, minlength=s)
        coer = cont.max() / total
        if coer >= 0.75:
            melhor = (s, int(cont.argmax()), float(coer))
    return melhor


def _reduzir(im: np.ndarray, sx: int, fx: int, sy: int, fy: int) -> np.ndarray:
    """Um pixel por célula da grade (inclui células parciais nas bordas): a mediana do miolo da célula (sem a margem
    de 1 px, onde o JPG borra), que numa imagem limpa é a própria cor da célula."""
    H, W = im.shape[:2]
    top, left = (sy - fy) % sy, (sx - fx) % sx            # alinha a grade em 0
    bottom, right = (-(H + top)) % sy, (-(W + left)) % sx
    p = np.pad(im, ((top, bottom), (left, right), (0, 0)), mode="edge")
    ny, nx = p.shape[0] // sy, p.shape[1] // sx
    blocos = p.reshape(ny, sy, nx, sx, 4)
    my, mx = (1 if sy >= 3 else 0), (1 if sx >= 3 else 0)
    miolo = blocos[:, my:sy - my, :, mx:sx - mx, :]
    return np.median(miolo, axis=(1, 3)).round().astype(np.uint8)


def _tirar_fundo(im: np.ndarray) -> tuple[np.ndarray, bool]:
    """Imagem toda opaca: se a borda da imagem for quase toda de uma cor, essa cor (ligada à borda) vira transparente."""
    if (im[..., 3] < 255).any():
        return im, False
    borda = np.concatenate([im[0], im[-1], im[:, 0], im[:, -1]])[:, :3]
    lab_b = _lab(borda)
    ref = np.median(lab_b, 0)
    perto_b = np.linalg.norm(lab_b - ref, axis=-1) < 0.04
    if perto_b.mean() < 0.6:
        return im, False
    perto = np.linalg.norm(_lab(im[..., :3]) - ref, axis=-1) < 0.04
    lab, _ = ndimage.label(perto)
    ids = set(np.unique(np.r_[lab[0], lab[-1], lab[:, 0], lab[:, -1]])) - {0}
    fundo = np.isin(lab, list(ids))
    if fundo.mean() > 0.97:
        return im, False
    out = im.copy()
    out[fundo, 3] = 0
    return out, True


def _ler(caminho) -> np.ndarray:
    im = np.array(Image.open(caminho).convert("RGBA"))
    im[im[..., 3] == 0] = 0   # o RGB escondido sob alfa 0 não conta como borda de cor
    return im


def _preparar(caminho) -> dict:
    bruta = _ler(caminho)
    H, W = bruta.shape[:2]
    a = bruta[..., 3]
    m_semi = (a > 0) & (a < 255)
    semi = float(m_semi.sum() / max((a > 0).sum(), 1))
    # antialiasing de alfa: semitransparente encostado no opaco e com alfa variado (a sombra no chão tem alfa único)
    aa_alfa = 0.0
    if m_semi.any():
        moda = np.bincount(a[m_semi]).argmax()
        junto = ndimage.binary_dilation(a == 255, structure=CRUZ)
        aa_alfa = float((m_semi & junto & (a != moda)).sum() / max((a > 0).sum(), 1))
    sx, fx, cx = _escala_eixo(bruta, 1)
    sy, fy, cy = _escala_eixo(bruta, 0)
    # pixels quadrados: as duas escalas têm que concordar; se não, vale o MDC (o menor bloco comum)
    if sx != sy:
        g = math.gcd(sx, sy)
        sx = sy = g
        fx, fy = fx % g, fy % g
    im = _reduzir(bruta, sx, fx, sy, fy) if sx > 1 else bruta.copy()
    unicas = len(np.unique(im[..., :3][im[..., 3] > 0].reshape(-1, 3), axis=0))
    pixel_art = sx > 1 or unicas <= 256
    if not pixel_art and max(im.shape[:2]) > 256:  # imagem comum grande: reduz para a análise de cor e forma
        f = 256 / max(im.shape[:2])
        im = np.array(Image.fromarray(im).resize((max(1, round(im.shape[1] * f)), max(1, round(im.shape[0] * f))),
                                                 Image.BOX))
    im[..., 3] = np.where(im[..., 3] >= 128, 255, 0)
    im, fundo = _tirar_fundo(im)
    return {"arquivo": str(Path(caminho).resolve()), "tamanho": [W, H], "escala": int(sx),
            "fase": [int(fx), int(fy)], "coerencia_grade": [round(cx, 3), round(cy, 3)],
            "tamanho_real": [int(im.shape[1]), int(im.shape[0])], "pixel_art": bool(pixel_art),
            "fundo_removido": bool(fundo), "semitransparente_pct": round(semi * 100, 2),
            "aa_alfa_pct": round(aa_alfa * 100, 2), "_im": im}


# ====================================================================== paleta

def _kmeans(lab: np.ndarray, peso: np.ndarray, k: int, iters: int = 25) -> np.ndarray:
    """k-means ponderado em OKLab, inicialização determinística (a mais frequente e depois a mais distante)."""
    ordem = np.argsort(-peso, kind="stable")
    cent = [lab[ordem[0]]]
    dmin = np.linalg.norm(lab - cent[0], axis=-1)
    while len(cent) < k:
        i = int(np.argmax(dmin * np.sqrt(peso)))
        cent.append(lab[i])
        dmin = np.minimum(dmin, np.linalg.norm(lab - lab[i], axis=-1))
    cent = np.array(cent)
    for _ in range(iters):
        idx = np.linalg.norm(lab[:, None] - cent[None], axis=-1).argmin(1)
        novo = np.array([np.average(lab[idx == j], axis=0, weights=peso[idx == j]) if (idx == j).any() else cent[j]
                         for j in range(k)])
        if np.allclose(novo, cent):
            break
        cent = novo
    return cent


def _cores_do_lote(imgs: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    todas = Counter()
    for im in imgs:
        op = im[..., 3] == 255
        cores, cont = np.unique(im[..., :3][op].reshape(-1, 3), axis=0, return_counts=True)
        for c, n in zip(map(tuple, cores.tolist()), cont.tolist()):
            todas[c] += n
    if not todas:
        return np.zeros((0, 3), int), np.zeros(0)
    cores = np.array(list(todas.keys()), int)
    peso = np.array(list(todas.values()), float)
    return cores, peso


def _fundir_parecidas(cores: np.ndarray, peso: np.ndarray, limiar: float = 0.05):
    """Ruído (JPG, redimensionamento): funde cada cor na mais frequente que esteja a menos de `limiar` em OKLab."""
    ordem = np.argsort(-peso, kind="stable")
    lab = _lab(cores)
    reps, rep_lab, rep_peso = [], [], []
    for i in ordem:
        if rep_lab:
            d = np.linalg.norm(np.array(rep_lab) - lab[i], axis=-1)
            j = int(d.argmin())
            if d[j] < limiar:
                rep_peso[j] += peso[i]
                continue
        reps.append(cores[i])
        rep_lab.append(lab[i])
        rep_peso.append(peso[i])
    return np.array(reps), np.array(rep_peso, float)


def _paleta_base(cores: np.ndarray, peso: np.ndarray) -> np.ndarray:
    """Até MAX_CORES cores: as próprias cores se couberem; senão funde as quase iguais (ruído) e, se ainda passar,
    k-means em OKLab (cor final = a cor real do lote mais próxima do centro, para não inventar tom)."""
    if len(cores) <= MAX_CORES:
        return cores
    cores, peso = _fundir_parecidas(cores, peso)
    # descarta a poeira (cores com menos de 0,05% dos pixels), comum em JPG e em imagem reduzida
    forte = peso >= peso.sum() * 0.0005
    if forte.sum() >= 2:
        cores, peso = cores[forte], peso[forte]
    if len(cores) <= MAX_CORES:
        return cores
    lab = _lab(cores)
    cent = _kmeans(lab, peso, MAX_CORES)
    idx = np.linalg.norm(lab[:, None] - cent[None], axis=-1).argmin(1)
    saida = []
    for j in range(len(cent)):
        m = idx == j
        if not m.any():
            continue
        cand = np.nonzero(m)[0]
        perto = cand[np.linalg.norm(lab[cand] - cent[j], axis=-1).argmin()]
        saida.append(cores[perto])
    return np.unique(np.array(saida), axis=0)


def _mapear(im: np.ndarray, pal: np.ndarray) -> np.ndarray:
    """Índice da cor da paleta (OKLab mais próxima) em cada pixel; -1 no transparente."""
    idx = np.full(im.shape[:2], -1, int)
    op = im[..., 3] == 255
    if op.any() and len(pal):
        cores, inv = np.unique(im[..., :3][op].reshape(-1, 3), axis=0, return_inverse=True)
        d = np.linalg.norm(_lab(cores)[:, None] - _lab(pal)[None], axis=-1)
        idx[op] = d.argmin(1)[inv.ravel()]
    return idx


def _anel_borda(op: np.ndarray) -> np.ndarray:
    return op & ~ndimage.binary_erosion(op, structure=CRUZ, border_value=0)


def _agrupar_rampas(labs: list, ids: list) -> list[list[int]]:
    """Agrupamento aglomerativo (ligação completa) por matiz e croma, com rampas de no máximo 4 tons e sem dois tons
    de L quase igual na mesma rampa (dois tons iguais em L são materiais diferentes, não degraus da mesma rampa)."""
    lch = {i: _lch(labs[i]) for i in ids}

    def dist(i, j):
        Li, Ci, hi = lch[i]
        Lj, Cj, hj = lch[j]
        if abs(Li - Lj) < 0.04:
            return 99.0
        neutro_i, neutro_j = Ci < NEUTRO_C, Cj < NEUTRO_C
        if neutro_i != neutro_j:
            return 99.0
        dh = 0.0 if neutro_i else _dh(hi, hj) * min(1.0, min(Ci, Cj) / 0.06)
        return math.hypot(dh / 40.0, (Ci - Cj) / 0.10) + abs(Li - Lj) * 0.5

    grupos = [[i] for i in ids]

    def dg(a, b):
        return max(dist(i, j) for i in a for j in b)

    while True:
        melhor = None
        for x in range(len(grupos)):
            for y in range(x + 1, len(grupos)):
                if len(grupos[x]) + len(grupos[y]) > 4:
                    continue
                d = dg(grupos[x], grupos[y])
                if d <= 1.0 and (melhor is None or d < melhor[0]):
                    melhor = (d, x, y)
        if not melhor:
            break
        _, x, y = melhor
        grupos[x] += grupos[y]
        del grupos[y]
    # tom solto: entra na rampa mais parecida que ainda tenha espaço (mais tolerante)
    soltos = [g for g in grupos if len(g) == 1]
    for g in soltos:
        alvo = min((h for h in grupos if h is not g and len(h) < 4), key=lambda h: dg(g, h), default=None)
        if alvo is not None and dg(g, alvo) <= 1.6:
            alvo += g
            grupos.remove(g)
    return [sorted(g, key=lambda i: lch[i][0]) for g in grupos]


# ====================================================================== medidas por imagem

def _clusters(idx: np.ndarray) -> list[int]:
    tam = []
    for c in np.unique(idx[idx >= 0]):
        lab, n = ndimage.label(idx == c, structure=CRUZ)
        if n:
            tam += np.bincount(lab.ravel())[1:].tolist()
    return tam


def _sprites(op: np.ndarray) -> list[dict]:
    lab, n = ndimage.label(op, structure=np.ones((3, 3), bool))
    if not n:
        return []
    areas = np.bincount(lab.ravel())[1:]
    minimo = max(16, 0.01 * areas.max())
    saida = []
    for k, sl in enumerate(ndimage.find_objects(lab)):
        if areas[k] < minimo:
            continue
        h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        saida.append({"x": int(sl[1].start), "y": int(sl[0].start), "largura": int(w), "altura": int(h),
                      "area": int(areas[k]), "altura_largura": round(h / max(w, 1), 3)})
    return saida


def _quase_iguais(im: np.ndarray) -> float:
    """Fração dos pares vizinhos opacos de cores diferentes que são QUASE iguais (ΔE OKLab < 0,04): antialiasing,
    gradiente ou ruído de compressão."""
    op = im[..., 3] == 255
    lab = _lab(im[..., :3])
    dif = quase = 0
    for a, b, m in ((lab[:, 1:], lab[:, :-1], op[:, 1:] & op[:, :-1]), (lab[1:], lab[:-1], op[1:] & op[:-1])):
        d = np.linalg.norm(a - b, axis=-1)[m]
        dif += int((d > 1e-6).sum())
        quase += int(((d > 1e-6) & (d < 0.04)).sum())
    return quase / max(dif, 1)


def _dither(idx: np.ndarray) -> float:
    """Fração dos pixels opacos em padrão de xadrez (os 4 vizinhos iguais entre si e diferentes do centro, as
    diagonais iguais ao centro)."""
    if min(idx.shape) < 3:
        return 0.0
    c = idx[1:-1, 1:-1]
    u, d, l, r = idx[:-2, 1:-1], idx[2:, 1:-1], idx[1:-1, :-2], idx[1:-1, 2:]
    dg = [idx[:-2, :-2], idx[:-2, 2:], idx[2:, :-2], idx[2:, 2:]]
    xadrez = (c >= 0) & (u >= 0) & (u == d) & (u == l) & (u == r) & (u != c)
    for x in dg:
        xadrez &= x == c
    return float(xadrez.sum() / max((idx >= 0).sum(), 1))


def _luz(im: np.ndarray, contorno_rgb) -> dict | None:
    """Correlação de L com x e com y DENTRO de cada sprite (média ponderada pela área): y negativo = luz de cima,
    x positivo = luz da direita."""
    op = im[..., 3] == 255
    lab_s, n = ndimage.label(op, structure=np.ones((3, 3), bool))
    preench = op.copy()
    if contorno_rgb is not None:
        preench &= ~np.all(im[..., :3] == np.array(contorno_rgb), axis=-1)
    L_all = _lab(im[..., :3])[..., 0]
    acc, peso = np.zeros(2), 0.0
    for k in range(1, n + 1):
        m = preench & (lab_s == k)
        ys, xs = np.nonzero(m)
        if len(xs) < 20:
            continue
        L = L_all[m]
        if np.std(L) < 1e-6 or np.std(xs) < 1e-6 or np.std(ys) < 1e-6:
            continue
        acc += len(xs) * np.array([np.corrcoef(xs, L)[0, 1], np.corrcoef(ys, L)[0, 1]])
        peso += len(xs)
    if not peso:
        return None
    return {"x": float(acc[0] / peso), "y": float(acc[1] / peso)}


# ====================================================================== análise do lote

def analisar_imagens(caminhos) -> dict:
    """Mede um lote de imagens e propõe paleta em rampas e respostas do guia de estilo. Ver o docstring do módulo."""
    if isinstance(caminhos, (str, Path)):
        caminhos = [caminhos]
    caminhos = [Path(c) for c in caminhos]
    if not caminhos:
        raise ValueError("analisar_imagens: nenhuma imagem")
    preps = [_preparar(c) for c in caminhos]
    imgs = [p.pop("_im") for p in preps]
    cores, peso = _cores_do_lote(imgs)
    if not len(cores):
        raise ValueError("analisar_imagens: as imagens não têm pixel opaco depois de tirar o fundo")
    pal = _paleta_base(cores, peso)
    idxs = [_mapear(im, pal) for im in imgs]
    uso = np.zeros(len(pal))
    anel = np.zeros(len(pal))
    for idx in idxs:
        uso += np.bincount(idx[idx >= 0], minlength=len(pal))
        a = idx[_anel_borda(idx >= 0)]
        anel += np.bincount(a[a >= 0], minlength=len(pal))
    labs = _lab(pal)
    Ls = labs[:, 0]
    # ---- contorno: entre as cores frequentes na borda da silhueta (>= 8% do anel), a mais escura
    frac_anel = anel / max(anel.sum(), 1)
    cand = [i for i in range(len(pal)) if frac_anel[i] >= 0.08] or [int(np.argmax(frac_anel))]
    i_cont = min(cand, key=lambda i: Ls[i])
    escura = Ls[i_cont] <= np.percentile(Ls, 35) or Ls[i_cont] < 0.35
    tem_contorno = bool(frac_anel[i_cont] >= 0.5 and escura)
    parcial = bool(not tem_contorno and frac_anel[i_cont] >= 0.25 and escura)
    # ---- brilho: a cor mais clara, se for clara e rara (ponto de luz); senão a mais clara mesmo (a confirmar)
    i_bri = int(np.argmax(Ls))
    _, Cb, _ = _lch(labs[i_bri])
    brilho_confirmado = bool(Ls[i_bri] >= 0.88 and uso[i_bri] / uso.sum() <= 0.06 and i_bri != i_cont)
    especiais = {i_cont} if (tem_contorno or parcial) else set()
    if brilho_confirmado:
        especiais.add(i_bri)
    ids = [i for i in range(len(pal)) if i not in especiais and uso[i] > 0]
    grupos = _agrupar_rampas(list(labs), ids)
    # ---- nomes e ordem (rampas mais usadas primeiro)
    grupos.sort(key=lambda g: -uso[g].sum())
    rampas, nome_de, contagem = {}, {}, Counter()
    for g in grupos:
        meio = g[len(g) // 2]
        L, Cc, h = _lch(labs[meio])
        base = _nome_matiz(h, Cc)
        contagem[base] += 1
        nome = base if contagem[base] == 1 else f"{base} {contagem[base]}"
        rampas[nome] = [_hex(pal[i]) for i in g]
        for i in g:
            nome_de[i] = nome
    cor_contorno = _hex(pal[i_cont]) if especiais & {i_cont} else None
    cor_brilho = _hex(pal[i_bri])
    paleta = {"nome": "", "versao": "0.1", "contorno": cor_contorno or _hex(pal[int(np.argmin(Ls))]),
              "brilho": cor_brilho,
              "nota": "Proposta pela análise das imagens (analise_estilo.py). Rampas na ordem sombra -> base -> luz.",
              "rampas": {}}
    paleta["rampas"]["contorno"] = [paleta["contorno"]]
    paleta["rampas"]["brilho"] = [paleta["brilho"]]
    paleta["rampas"].update({k: v for k, v in rampas.items()})
    escuros = [g[0] for g in grupos if len(g) >= 2]
    if escuros:  # contorno "suave" do grade.py: o tom mais escuro das rampas
        paleta["contorno_suave"] = _hex(pal[min(escuros, key=lambda i: Ls[i])])
    # ---- medidas por imagem
    por_imagem, clusters_todos, tons, razoes, alturas, larguras, luzes = [], [], [], [], [], [], []
    quase, dith, n_cores_img = [], [], []
    for p, im, idx in zip(preps, imgs, idxs):
        op = idx >= 0
        tam = _clusters(idx)
        clusters_todos.append(float(np.mean(tam)) if tam else 0.0)
        usados = Counter()
        cnt = np.bincount(idx[op], minlength=len(pal)) if op.any() else np.zeros(len(pal))
        for i, n in enumerate(cnt):
            if n >= 3 and i in nome_de:
                usados[nome_de[i]] += 1
        t = float(np.mean(list(usados.values()))) if usados else 0.0
        if usados:
            tons.append(t)
        sp = _sprites(op)
        for s in sp:
            razoes.append(s["altura_largura"])
            alturas.append(s["altura"])
            larguras.append(s["largura"])
        lz = _luz(im, pal[i_cont] if cor_contorno else None)
        if lz:
            luzes.append(lz)
        q = _quase_iguais(im)
        dt = _dither(idx)
        quase.append(q)
        dith.append(dt)
        n_cores = int(len(np.unique(im[..., :3][im[..., 3] == 255].reshape(-1, 3), axis=0)))
        n_cores_img.append(n_cores)
        a = idx[_anel_borda(op)]
        frac_c = float((a == i_cont).mean()) if a.size else 0.0
        por_imagem.append({**p, "cores": n_cores, "cluster_medio": round(clusters_todos[-1], 1),
                           "tons_por_material": round(t, 2), "rampas_usadas": sorted(usados),
                           "contorno_fracao_borda": round(frac_c, 3), "sprites": sp,
                           "vizinhos_quase_iguais_pct": round(q * 100, 1), "dither_pct": round(dt * 100, 2),
                           "luz": {k: round(v, 3) for k, v in lz.items()} if lz else None})
    escalas = Counter(p["escala"] for p in preps)
    lx = float(np.mean([l["x"] for l in luzes])) if luzes else None
    ly = float(np.mean([l["y"] for l in luzes])) if luzes else None
    q_med = float(np.mean(quase))
    semi_med = float(np.mean([p["semitransparente_pct"] for p in preps]))
    aa_alfa_med = float(np.mean([p["aa_alfa_pct"] for p in preps]))
    d_med = float(np.mean(dith))
    # ---- saturação, temperatura e hue shift
    pesos = uso / max(uso.sum(), 1)
    cromas = np.array([_lch(l)[1] for l in labs])
    matizes = np.array([_lch(l)[2] for l in labs])
    quente = float(sum(pesos[i] for i in range(len(pal)) if cromas[i] >= NEUTRO_C
                       and (matizes[i] < 115 or matizes[i] >= 330)))
    fria = float(sum(pesos[i] for i in range(len(pal)) if cromas[i] >= NEUTRO_C and 115 <= matizes[i] < 330))
    shifts = []
    for g in grupos:
        if len(g) >= 2 and all(cromas[i] >= NEUTRO_C for i in g):
            # positivo = a luz anda para o amarelo (≈ 100°) e a sombra para o azul/roxo: hue shift "clássico"
            shifts.append(_dh(matizes[g[0]], 100) - _dh(matizes[g[-1]], 100))
    analise = {
        "versao": 1,
        "data": _dt.date.today().isoformat(),
        "imagens": por_imagem,
        "escala": {"mais_comum": escalas.most_common(1)[0][0], "por_imagem": dict(escalas)},
        "cores": {"no_lote": int(len(cores)), "na_paleta": int(len(pal)),
                  "media_por_imagem": round(float(np.mean(n_cores_img)), 1)},
        "paleta": paleta,
        "contorno": {"cor": cor_contorno, "candidata": _hex(pal[i_cont]), "fracao_borda": round(float(frac_anel[i_cont]), 3),
                     "tem_contorno": tem_contorno, "parcial": parcial},
        "brilho": {"cor": cor_brilho, "confirmado": brilho_confirmado},
        "rampas": {"quantas": len(rampas), "tons": {k: len(v) for k, v in rampas.items()}},
        "cluster_medio": round(float(np.mean(clusters_todos)), 1),
        "tons_por_material": round(float(np.mean(tons)), 2) if tons else 0.0,
        "sprites": {"quantos": len(razoes),
                    "altura_largura_mediana": round(float(np.median(razoes)), 3) if razoes else None,
                    "altura_mediana": float(np.median(alturas)) if alturas else None,
                    "largura_mediana": float(np.median(larguras)) if larguras else None},
        "antialiasing": {"vizinhos_quase_iguais_pct": round(q_med * 100, 1),
                         "semitransparente_pct": round(semi_med, 2),
                         "aa_alfa_pct": round(aa_alfa_med, 2), "tem": bool(q_med > 0.15 or aa_alfa_med > 1.0)},
        "dithering": {"pct": round(d_med * 100, 2), "tem": bool(d_med > 0.01)},
        "luz": {"x": round(lx, 3), "y": round(ly, 3), "leitura": _ler_luz(lx, ly)} if luzes else None,
        "temperatura": {"quente_pct": round(quente * 100, 1), "fria_pct": round(fria * 100, 1),
                        "croma_medio": round(float((cromas * pesos).sum()), 3),
                        "hue_shift_medio_graus": round(float(np.mean(shifts)), 1) if shifts else None},
        "pixel_art": all(p["pixel_art"] for p in preps),
    }
    return analise


def _ler_luz(lx, ly) -> str:
    partes = []
    if ly is not None and ly <= -0.25:
        partes.append("de cima")
    elif ly is not None and ly >= 0.25:
        partes.append("de baixo")
    if lx is not None and lx >= 0.25:
        partes.append("da direita (frente)")
    elif lx is not None and lx <= -0.25:
        partes.append("da esquerda")
    return "luz " + " e ".join(partes) if partes else "luz frontal ou difusa (sem direção clara)"


# ====================================================================== pacote

def _slug(nome: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", nome.strip().lower()).strip("-")
    if not s:
        raise ValueError(f"nome de estilo inválido: {nome!r}")
    return s


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _rascunho_md(nome: str, a: dict, autor: str) -> str:
    ct, pal, sp = a["contorno"], a["paleta"], a["sprites"]
    conf = "**a confirmar**"
    if ct["tem_contorno"]:
        contorno = f"sim: cor única `{ct['cor']}` em {ct['fracao_borda']:.0%} da borda da silhueta"
    elif ct["parcial"]:
        contorno = (f"parcial: `{ct['cor']}` em {ct['fracao_borda']:.0%} da borda (contorno seletivo ou colorido?) — "
                    f"{conf}")
    else:
        contorno = f"não medido como contorno único (a cor mais escura da borda cobre {ct['fracao_borda']:.0%}) — {conf}"
    n_ramp = a["rampas"]["quantas"]
    n_cores = sum(len(v) for v in pal["rampas"].values())
    tons = a["tons_por_material"]
    cl = a["cluster_medio"]
    pintura = ("chapado em blocos (clusters grandes)" if cl >= 40 else
               "blocos médios" if cl >= 15 else "detalhado / texturizado (clusters pequenos)")
    t = a["temperatura"]
    hs = t["hue_shift_medio_graus"]
    temp = (f"croma médio {t['croma_medio']:.3f} ({'saturado' if t['croma_medio'] > 0.12 else 'moderado' if t['croma_medio'] > 0.06 else 'apagado'}); "
            f"{t['quente_pct']:.0f}% quente, {t['fria_pct']:.0f}% frio"
            + (f"; hue shift médio {hs:+.0f}° ({'luz quente, sombra fria' if hs > 5 else 'pouco ou nenhum hue shift'})"
               if hs is not None else ""))
    aa, dt = a["antialiasing"], a["dithering"]
    textura = ("flat: sem dithering e sem antialiasing" if not aa["tem"] and not dt["tem"] else
               ", ".join(x for x in ["com dithering" if dt["tem"] else "", "com antialiasing/gradiente" if aa["tem"] else ""] if x))
    textura += f" (xadrez {dt['pct']:.2f}%, vizinhos quase iguais {aa['vizinhos_quase_iguais_pct']:.0f}%)"
    prop = (f"sprites com altura mediana {sp['altura_mediana']:.0f} px e largura {sp['largura_mediana']:.0f} px "
            f"(altura/largura {sp['altura_largura_mediana']:.2f}); altura em cabeças {conf}"
            if sp["quantos"] else f"nenhum sprite recortado — {conf}")
    fundo = sum(1 for i in a["imagens"] if i["fundo_removido"])
    luz = (f"{a['luz']['leitura']} (estimada pela correlação do valor com x/y em cada sprite; material escuro engana)"
           if a["luz"] else "não medida")
    nomes = ", ".join(Path(i["arquivo"]).name for i in a["imagens"][:8]) + (" …" if len(a["imagens"]) > 8 else "")
    linhas = [
        f"# Estilo \"{nome}\" — rascunho v0.1",
        "",
        f"> Rascunho gerado por `analise_estilo.criar_pacote` em {a['data']}" + (f" para {autor}" if autor else "") + ".",
        "> Cada item foi preenchido pelo que a análise das imagens mediu; o que ela não decide está marcado "
        "**a confirmar**. Confirme ou ajuste item por item (docs/estilos.md, passo 2).",
        "",
        "## Escala e grade",
        f"- Tamanho do pixel nas imagens: {a['escala']['mais_comum']}× ("
        + ", ".join(f"{k}× em {v} imagem(ns)" for k, v in a["escala"]["por_imagem"].items()) + ").",
        f"- {'Pixel art de verdade' if a['pixel_art'] else 'Há imagens que não são pixel art nativa'}"
        f" ({len(a['imagens'])} imagem(ns)).",
        f"- Luz: {luz}.",
        "",
        "## Guia de estilo (os 15 itens)",
        "| # | Item | Proposta |",
        "|---|---|---|",
        f"| 1 | Contorno | {contorno} |",
        f"| 2 | Paleta | {n_cores} cores em {n_ramp} rampas + contorno + brilho (`paleta.json`); "
        f"{a['cores']['media_por_imagem']:.0f} cores por imagem em média |",
        f"| 3 | Tons por material | {tons:.1f} em média por rampa usada |",
        f"| 4 | Estilo de pintura | {pintura}; cluster médio {cl:.0f} px (estimado) |",
        f"| 5 | Vista | {conf} (top-down, lateral, 3/4) |",
        f"| 6 | Tema | {conf} |",
        f"| 7 | Saturação e temperatura | {temp} |",
        f"| 8 | Fundo | {fundo} de {len(a['imagens'])} imagem(ns) tinham fundo liso (tirado na análise); regra do fundo {conf} |",
        f"| 9 | Textura | {textura} |",
        f"| 10 | Coerência | {conf} (vale a régua e o revisor, depois de escolhidos) |",
        f"| 11 | Referências | as imagens do lote em `referencias/` ({nomes}); jogos que inspiram {conf} |",
        f"| 12 | Quadros de animação | {conf} (imagem parada não diz) |",
        f"| 13 | Estilo de animação | {conf} |",
        f"| 14 | Proporções | {prop} |",
        f"| 15 | Densidade de assets | {conf} |",
        "",
        "## Rampas propostas (sombra → base → luz)",
    ]
    for k, v in pal["rampas"].items():
        linhas.append(f"- **{k}**: " + " ".join(f"`{c}`" for c in v))
    linhas += ["", "## Próximos passos",
               "1. Confirmar os itens acima e a paleta (`paleta.json`).",
               "2. Escolher a régua (sprites que medem a qualidade) e calibrar as metas.",
               "3. Fazer um personagem simples de teste pelo fluxo inteiro.", ""]
    return "\n".join(linhas)


def criar_pacote(nome: str, caminhos, destino=None, autor: str = "", licenca_imagens: str = "") -> Path:
    """Analisa as imagens e grava um pacote de estilo (ver docstring do módulo). Devolve a pasta do pacote."""
    slug = _slug(nome)
    if isinstance(caminhos, (str, Path)):
        caminhos = [caminhos]
    caminhos = [Path(c) for c in caminhos]
    a = analisar_imagens(caminhos)
    pasta = Path(destino) if destino else E.home() / "estilos" / slug
    pasta.mkdir(parents=True, exist_ok=True)
    # referências: cópia das imagens + origem declarada
    refs = pasta / "referencias"
    refs.mkdir(exist_ok=True)
    origem = {"licenca": licenca_imagens or "não declarada", "autor": autor, "data": a["data"], "arquivos": []}
    usados = set()
    for c in caminhos:
        dst = c.name
        k = 2
        while dst in usados:
            dst = f"{c.stem}_{k}{c.suffix}"
            k += 1
        usados.add(dst)
        shutil.copy2(c, refs / dst)
        origem["arquivos"].append({"arquivo": dst, "origem": str(c.resolve()), "sha256": _sha256(c)})
    with open(refs / "origem.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(origem, f, ensure_ascii=False, indent=1)
    # paleta
    pal = a["paleta"]
    pal["nome"] = nome
    with open(pasta / "paleta.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(pal, f, ensure_ascii=False, indent=1)
    E.exportar_paleta(pal, pasta / "paleta", nome)
    with open(pasta / "analise.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(a, f, ensure_ascii=False, indent=1)
    with open(pasta / "estilo.md", "w", encoding="utf-8", newline="\n") as f:
        f.write(_rascunho_md(nome, a, autor))
    neutros = [v for k, v in pal["rampas"].items() if k.startswith("neutro")]
    estilo = {
        "nome": slug, "versao": "0.1", "autor": autor, "licenca": "a definir",
        "descricao": f"Estilo criado a partir de {len(caminhos)} imagem(ns) (rascunho; confirmar no estilo.md).",
        "kb": None, "paleta": "paleta.json", "regua": None,
        "chao": {"claro": "#78a05e", "escuro": neutros[0][0] if neutros else "#5a5870"},
        "contorno_regua": pal["contorno"], "brilho_regua": [pal["brilho"]], "metas": None,
        "leitura": ["estilo.md"], "motor_padrao": "claude", "referencia_padrao": "pedir",
        "trigger": re.sub(r"[^a-z0-9]", "", slug) + "px",
        "referencias": {"pasta": "referencias", "licenca": licenca_imagens or "não declarada",
                        "treino_permitido": None},
        "analise": "analise.json",
    }
    with open(pasta / "estilo.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(estilo, f, ensure_ascii=False, indent=1)
    return pasta
