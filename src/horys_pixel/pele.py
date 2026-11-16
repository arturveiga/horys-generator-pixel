"""Base + Pele: vestir um corpo-base com a imagem do Codex e levar a roupa para cada quadro da animação.

Ideia (perfeicao.md, seção 6, P3): o movimento é resolvido UMA vez num corpo-base animado. Cada personagem novo é só
a "pele" (roupa, cabelo, arma) por cima da base.

1. vestir: a base (folha 1x com as vistas lado a lado e margem transparente) é ampliada sobre cor-chave e vai ao
   Codex com "A ÚNICA MUDANÇA: vista esta figura como <ficha>". A imagem devolvida é relida NA GRADE DA BASE
   (tamanho de célula e posição procurados até a maioria das células da base sair igual) e só as células que
   mudaram viram a camada de pele. O resto é a base, pixel por pixel. Ideia do agent-sprite-forge (pixel looks,
   MIT), reimplementada aqui.
2. propagar: cada pixel da pele pertence à parte da base que está embaixo dele (ou à mais próxima). Em cada quadro,
   a parte da base se desloca; a pele daquela parte vai junto. Partes que se deformam demais (IoU baixo depois do
   deslocamento) são avisadas: ali o agente ou o Artur limpam à mão.

Só lógica pura (numpy). Não cria forma: copia, encaixa e avisa.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage

# ------------------------------------------------------------------ cor


def _oklab(rgb) -> np.ndarray:
    c = np.asarray(rgb, dtype=np.float64) / 255.0
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = lin[..., 0], lin[..., 1], lin[..., 2]
    l = np.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
    m = np.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
    s = np.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
    return np.stack([0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
                     1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
                     0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s], -1)


def hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.strip().lstrip("#")
    if len(h) != 6:
        raise ValueError(f"cor '{h}' inválida: use #rrggbb")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# ------------------------------------------------------------------ leitura na grade da base


@dataclass
class Grade:
    celula: float      # px da imagem por pixel da base
    x0: float          # canto esquerdo da célula (0,0) na imagem
    y0: float
    acerto: float      # fração das células da base que saíram iguais (opacas) ou vazias (transparentes)


def _amostrar(img: np.ndarray, celula: float, x0: float, y0: float, w: int, h: int) -> np.ndarray:
    """Cor do centro de cada célula (img já suavizada 3x3). Fora da imagem = -1."""
    xs = np.floor(x0 + (np.arange(w) + 0.5) * celula).astype(int)
    ys = np.floor(y0 + (np.arange(h) + 0.5) * celula).astype(int)
    out = np.full((h, w, 3), -1.0)
    okx = (xs >= 0) & (xs < img.shape[1])
    oky = (ys >= 0) & (ys < img.shape[0])
    sub = img[np.ix_(ys[oky], xs[okx])]
    out[np.ix_(np.nonzero(oky)[0], np.nonzero(okx)[0])] = sub
    return out


def _e_chave(rgb: np.ndarray, chave: tuple[int, int, int], tol: float) -> np.ndarray:
    d = np.abs(rgb - np.asarray(chave, float)).sum(-1)
    return (d <= tol) | (rgb[..., 0] < 0)


def achar_grade(imagem: np.ndarray, base: np.ndarray, chave: tuple[int, int, int], *, tol_lab: float = 0.07,
                tol_chave: float = 90.0, folga: float = 0.08) -> Grade:
    """Procura tamanho de célula e posição que fazem a imagem reproduzir a base.

    Estimativa pelo retângulo da figura (tudo que não é chave) contra o retângulo opaco da base; depois busca fina:
    célula em ±folga (passo 1%), posição em passos de 1 px dentro de uma célula. Pontuação = fração das células
    opacas da base com cor igual (OKLab < tol_lab) somada à fração das transparentes que caem na chave, com peso
    pela quantidade de cada uma.
    """
    rgb = ndimage.uniform_filter(imagem[..., :3].astype(np.float64), size=(3, 3, 1))
    h, w = base.shape[:2]
    opaca = base[..., 3] > 127
    if not opaca.any():
        raise ValueError("a base está vazia (nenhum pixel opaco)")
    lab_base = _oklab(base[..., :3])
    fig = ~_e_chave(imagem[..., :3].astype(float), chave, tol_chave)
    if not fig.any():
        raise ValueError("a imagem não tem figura: tudo é cor-chave (confira a chave)")
    fy, fx = np.nonzero(fig)
    by, bx = np.nonzero(opaca)
    # A roupa pode crescer além da base (chapéu, capa): o retângulo da figura engana. Estimativas: altura, largura
    # e o bloco medido pela periodicidade das bordas (a imagem é pixel art ampliada).
    ests = [(fy.max() - fy.min() + 1) / (by.max() - by.min() + 1), (fx.max() - fx.min() + 1) / (bx.max() - bx.min() + 1)]
    try:  # bloco pela periodicidade das bordas: quando é coerente, manda (a roupa não muda o tamanho do pixel)
        from .motor.conceito import grade_nativa
        (coer, sx, _), _ = grade_nativa(imagem[..., :3])
        if coer > 0.5:
            ests = [float(sx)]
            folga = min(folga, 0.015)
        else:
            ests.append(float(sx))
    except Exception:
        pass
    n_op, n_tr = opaca.sum(), (~opaca).sum()

    def nota(cel, x0, y0):
        # a roupa cobre parte da base e cresce fora dela: o que decide é a base opaca reaparecer igual; o vazio
        # da base que continua vazio só desempata (peso 0,1)
        a = _amostrar(rgb, cel, x0, y0, w, h)
        vazio = _e_chave(a, chave, tol_chave)
        d = np.linalg.norm(_oklab(np.clip(a, 0, 255)) - lab_base, axis=-1)
        return ((opaca & ~vazio & (d < tol_lab)).sum() + 0.1 * (~opaca & vazio).sum()) / (n_op + 0.1 * n_tr)

    # âncoras: pés (a roupa raramente desce abaixo deles) e centro horizontal; busca ±2 células em passo grosso,
    # depois fino em volta do melhor
    # em empate (célula um pouco maior ou menor lê as mesmas cores), fica a mais perto da estimativa
    cels = sorted({round(float(e * f), 2) for e in ests for f in np.arange(1 - folga, 1 + folga + 1e-9, 0.0025)},
                  key=lambda c: min(abs(c - e) for e in ests))
    melhor = Grade(float(ests[0]), 0.0, 0.0, -1.0)
    for cel in cels:
        ox0 = (fx.min() + fx.max() + 1) / 2 - (bx.min() + bx.max() + 1) / 2 * cel
        oy0 = fy.max() + 1 - (by.max() + 1) * cel
        passo = max(1.0, cel / 3)
        for dy in np.arange(-2 * cel, 2 * cel + 1e-9, passo):
            for dx in np.arange(-2 * cel, 2 * cel + 1e-9, passo):
                ac = nota(cel, ox0 + dx, oy0 + dy)
                if ac > melhor.acerto:
                    melhor = Grade(float(cel), float(ox0 + dx), float(oy0 + dy), float(ac))
    passo = max(1.0, melhor.celula / 3)
    base_g = melhor
    for cel in sorted(base_g.celula * np.arange(0.985, 1.0151, 0.0025), key=lambda c: abs(c - base_g.celula)):
        for dy in np.arange(-passo, passo + 1e-9, 1.0):
            for dx in np.arange(-passo, passo + 1e-9, 1.0):
                ac = nota(cel, base_g.x0 + dx, base_g.y0 + dy)
                if ac > melhor.acerto:
                    melhor = Grade(float(cel), float(base_g.x0 + dx), float(base_g.y0 + dy), float(ac))
    return melhor


# ------------------------------------------------------------------ paleta da pele


def _kmeans_lab(cores: np.ndarray, k: int, iters: int = 20) -> np.ndarray:
    """k-médias determinístico em OKLab; início pelas cores mais frequentes. cores: (n,3) uint8 -> centros (k,3)."""
    uni, cont = np.unique(cores.reshape(-1, 3), axis=0, return_counts=True)
    if len(uni) <= k:
        return uni.astype(np.float64)
    lab = _oklab(uni)
    # início determinístico "mais distante": a cor mais frequente, depois a que mais se afasta das escolhidas
    # (pesada pela raiz da frequência). Pegar só as k mais frequentes juntava dois quase-iguais e perdia a sombra.
    esc = [int(cont.argmax())]
    dmin = np.linalg.norm(lab - lab[esc[0]], axis=-1)
    while len(esc) < k:
        i = int((dmin * np.sqrt(cont)).argmax())
        esc.append(i)
        dmin = np.minimum(dmin, np.linalg.norm(lab - lab[i], axis=-1))
    centros = lab[esc].copy()
    for _ in range(iters):
        lbl = np.linalg.norm(lab[:, None] - centros[None], axis=-1).argmin(1)
        novo = np.array([np.average(lab[lbl == i], 0, weights=cont[lbl == i]) if (lbl == i).any() else centros[i]
                         for i in range(k)])
        if np.allclose(novo, centros):
            break
        centros = novo
    # devolve a cor real (sRGB) mais frequente de cada grupo, nunca uma média inventada
    lbl = np.linalg.norm(lab[:, None] - centros[None], axis=-1).argmin(1)
    reps = [uni[lbl == i][cont[lbl == i].argmax()] for i in range(k) if (lbl == i).any()]
    return np.array(reps, np.float64)


def _encaixar(cores: np.ndarray, paleta: np.ndarray) -> np.ndarray:
    d = np.linalg.norm(_oklab(cores)[:, None] - _oklab(paleta)[None], axis=-1)
    return paleta[d.argmin(1)]


# ------------------------------------------------------------------ vestir


@dataclass
class Vestido:
    pele: np.ndarray            # RGBA, só as células que mudaram (resto transparente)
    lido: np.ndarray            # RGBA, a imagem inteira relida na grade da base (base + pele + remoções)
    mudou: np.ndarray           # bool, células que mudaram
    grade: Grade
    mantido: float              # fração das células opacas da base que ficaram iguais
    removidos: int              # células opacas da base que a imagem apagou (a pele não expressa isso)
    isolados_tirados: int       # células soltas de pele removidas como ruído
    cores_pele: list = field(default_factory=list)
    avisos: list = field(default_factory=list)


def vestir(base: np.ndarray, imagem: np.ndarray, chave: str = "#ff00ff", *, paleta: list[str] | None = None,
           max_cores: int = 12, tol_lab: float = 0.07, tol_chave: float = 90.0, manter_isolados: bool = False,
           grade: Grade | None = None) -> Vestido:
    """Relê `imagem` (RGB/RGBA grande, do Codex) na grade de `base` (RGBA 1x) e separa a pele.

    paleta: cores permitidas para a pele (#rrggbb); sem ela, a pele é reduzida a no máximo `max_cores` cores reais
    da própria imagem (k-médias em OKLab que devolve a cor mais frequente de cada grupo).
    """
    if base.ndim != 3 or base.shape[2] != 4:
        raise ValueError("a base precisa ser RGBA")
    ch = hex_rgb(chave)
    g = grade or achar_grade(imagem, base, ch, tol_lab=tol_lab, tol_chave=tol_chave)
    h, w = base.shape[:2]
    rgb = ndimage.uniform_filter(imagem[..., :3].astype(np.float64), size=(3, 3, 1))
    a = _amostrar(rgb, g.celula, g.x0, g.y0, w, h)
    vazio = _e_chave(a, ch, tol_chave)
    cor = np.clip(np.rint(a), 0, 255)
    opaca = base[..., 3] > 127
    d = np.linalg.norm(_oklab(cor) - _oklab(base[..., :3]), axis=-1)
    igual = opaca & ~vazio & (d < tol_lab)
    mudou = ~vazio & ~igual
    removidos = int((opaca & vazio).sum())
    avisos = []

    tirados = 0
    if not manter_isolados and mudou.any():
        lbl, n = ndimage.label(mudou)  # 4-vizinhança
        tam = np.bincount(lbl.ravel())
        solto = (tam[lbl] == 1) & mudou
        tirados = int(solto.sum())
        mudou &= ~solto

    pele = np.zeros((h, w, 4), np.uint8)
    cores_pele: list[str] = []
    if mudou.any():
        novas = cor[mudou]
        if paleta:
            pal = np.array([hex_rgb(p) for p in paleta], np.float64)
        else:
            pal = _kmeans_lab(novas.astype(np.uint8), max_cores)
        enc = _encaixar(novas, pal)
        pele[mudou, :3] = enc.astype(np.uint8)
        pele[mudou, 3] = 255
        cores_pele = sorted({"#%02x%02x%02x" % tuple(int(v) for v in c) for c in enc})

    lido = base.copy()
    lido[opaca & vazio] = 0
    lido[mudou] = pele[mudou]

    mantido = float(igual.sum() / max(1, opaca.sum()))
    if g.acerto < 0.6:
        avisos.append(f"a grade achada reproduz só {g.acerto:.0%} da base: o Codex redesenhou ou mudou a escala. "
                      "Gere de novo (não conserte à mão).")
    if removidos > 0.05 * opaca.sum():
        avisos.append(f"{removidos} células da base sumiram na imagem: a pele não apaga a base. Confira a vista.")
    if mantido < 0.5:
        avisos.append(f"só {mantido:.0%} da base ficou igual: a roupa cobre quase tudo ou a imagem não é a base vestida.")
    return Vestido(pele, lido, mudou, g, mantido, removidos, tirados, cores_pele, avisos)


# ------------------------------------------------------------------ propagar


def atribuir_partes(pele: np.ndarray, partes0: np.ndarray) -> np.ndarray:
    """Rótulo de parte de cada pixel da pele: o da base embaixo dele, senão o da parte mais próxima."""
    rot = partes0.astype(int).copy()
    if (rot > 0).any():
        _, (iy, ix) = ndimage.distance_transform_edt(rot == 0, return_indices=True)
        rot = rot[iy, ix]
    rot[pele[..., 3] == 0] = 0
    return rot


def _melhor_desloc(m0: np.ndarray, m1: np.ndarray, raio: int) -> tuple[int, int, float]:
    """Deslocamento inteiro (dx, dy) que leva m0 a m1 com maior IoU, dentro de ±raio."""
    melhor = (0, 0, -1.0)
    if not m0.any() or not m1.any():
        return 0, 0, 0.0
    for dy in range(-raio, raio + 1):
        for dx in range(-raio, raio + 1):
            s = _deslocar(m0, dx, dy)
            inter = (s & m1).sum()
            uni = (s | m1).sum()
            iou = inter / uni if uni else 0.0
            if iou > melhor[2] or (iou == melhor[2] and abs(dx) + abs(dy) < abs(melhor[0]) + abs(melhor[1])):
                melhor = (dx, dy, float(iou))
    return melhor


def _deslocar(a: np.ndarray, dx: int, dy: int) -> np.ndarray:
    out = np.zeros_like(a)
    h, w = a.shape[:2]
    ys0, ys1 = max(0, dy), min(h, h + dy)
    xs0, xs1 = max(0, dx), min(w, w + dx)
    out[ys0:ys1, xs0:xs1] = a[ys0 - dy:ys1 - dy, xs0 - dx:xs1 - dx]
    return out


@dataclass
class Propagado:
    pele: np.ndarray                 # RGBA da pele no quadro alvo
    por_parte: dict                  # parte -> {"dx","dy","iou","pixels"}
    avisos: list


def propagar(pele: np.ndarray, partes0: np.ndarray, partes_n: np.ndarray, *, ordem: list[int] | None = None,
             raio: int = 6, iou_min: float = 0.7) -> Propagado:
    """Leva a pele do quadro de referência (partes0) para outro quadro (partes_n).

    partes0/partes_n: mapas inteiros (0 = vazio, k = parte k) da base no quadro de referência e no alvo.
    ordem: ordem de pintura das partes (a última fica por cima); padrão = ordem crescente do rótulo.
    """
    if pele.shape[:2] != partes0.shape or partes0.shape != partes_n.shape:
        raise ValueError("pele e mapas de partes precisam ter o mesmo tamanho")
    rot = atribuir_partes(pele, partes0)
    ids = [int(i) for i in np.unique(partes0) if i > 0]
    ordem = ordem or ids
    out = np.zeros_like(pele)
    info, avisos = {}, []
    for k in ordem:
        if k not in ids:
            continue
        dx, dy, iou = _melhor_desloc(partes0 == k, partes_n == k, raio)
        sel = rot == k
        n = int(sel.sum())
        info[k] = {"dx": dx, "dy": dy, "iou": round(iou, 3), "pixels": n}
        if n == 0:
            continue
        camada = np.where(sel[..., None], pele, 0).astype(pele.dtype)
        camada = _deslocar(camada, dx, dy)
        m = camada[..., 3] > 0
        out[m] = camada[m]
        if iou < iou_min:
            avisos.append(f"parte {k}: a base muda de forma neste quadro (IoU {iou:.2f} após deslocar {dx},{dy}); "
                          "a pele dela precisa de limpeza à mão.")
    return Propagado(out, info, avisos)


def compor(base: np.ndarray, pele: np.ndarray) -> np.ndarray:
    """Pele por cima da base (alfa binário)."""
    out = base.copy()
    m = pele[..., 3] > 0
    out[m] = pele[m]
    return out


# ------------------------------------------------------------------ ler o master (imagem do Codex -> folha 1x)


@dataclass
class Master:
    folha: np.ndarray        # RGBA 1x: vistas lado a lado, mesma linha de chão, margem transparente
    vistas: list             # [RGBA 1x recortado de cada vista], da esquerda para a direita
    bloco: float             # px da imagem por pixel do sprite
    cores: list              # #rrggbb usadas
    alturas: list            # altura (px) de cada vista
    avisos: list


def cortes_proprios(rgb: np.ndarray, bloco: float, fase: float, eixo: int, folga: float = 0.35) -> np.ndarray:
    """Linhas de corte da grade da PRÓPRIA imagem num eixo (eixo=1: colunas, 0: linhas).

    O gpt-image não desenha blocos uniformes (15–30 px na mesma imagem). Parte da grade rígida (bloco, fase) e move
    cada corte para o pico de borda de cor mais próximo, dentro de ±folga·bloco. Sem pico forte, fica o corte
    rígido. Ideia do pixel_look do agent-sprite-forge (MIT), reimplementada."""
    d = np.abs(np.diff(rgb.astype(np.int32), axis=eixo)).sum(-1)
    perfil = d.sum(axis=1 - eixo).astype(np.float64)        # força da borda entre i e i+1 → corte em i+1
    n = rgb.shape[eixo]
    rig = np.arange(fase, n + bloco, bloco)
    raio = max(1, int(round(folga * bloco)))
    limiar = np.median(perfil) * 2 + 1
    cortes = []
    for c in rig:
        ci = int(round(c))
        a, b = max(1, ci - raio), min(n - 1, ci + raio)
        if a >= b:
            cortes.append(min(max(ci, 0), n))
            continue
        j = a + int(np.argmax(perfil[a - 1:b - 1]))
        cortes.append(j if perfil[j - 1] > limiar else ci)
    cortes = sorted(set(min(max(c, 0), n) for c in cortes))
    if cortes[0] > 0:
        cortes.insert(0, 0) if cortes[0] > bloco * 0.5 else None
    return np.array(cortes)


def ler_grade_propria(rgb: np.ndarray, *, paleta: list[str] | None, chave: str = "#ff00ff", n_cores: int = 16,
                      miolo: float = 0.6, altura: int | None = None) -> tuple[np.ndarray, float, float]:
    """Pixel art ampliada (Codex) → RGBA 1x pela grade própria + voto da maioria por célula.

    Cada pixel da imagem é encaixado na paleta (a da ficha, ou n_cores cores reais) OU na chave; a célula recebe a
    cor mais votada no miolo dela (miolo·tamanho, sem a borda onde a chave e a cor se misturam). Chave ganhando =
    transparente. Devolve (rgba, bloco, coerência).
    altura: altura (px 1x) da figura mais alta, quando já se sabe (pose/vista lida na grade do master): o bloco
    vem de altura_da_figura / altura e a fase do Sobel. Necessário quando o Codex mistura meio-bloco no detalhe."""
    from .motor.conceito import _sobel_eixos, fase_sobel, grade_nativa
    if altura:
        fig = np.abs(rgb.astype(np.int32) - np.array(hex_rgb(chave))).sum(-1) > 90
        lbl, _ = ndimage.label(fig)
        alt = max((sl[0].stop - sl[0].start for sl in ndimage.find_objects(lbl) if sl is not None), default=0)
        b = alt / float(altura)
        sx, sy = _sobel_eixos(rgb)
        gx, gy = (1.0, b, fase_sobel(sx, b)), (1.0, b, fase_sobel(sy, b))
    else:
        gx, gy = grade_nativa(rgb)
    cx = cortes_proprios(rgb, gx[1], gx[2], 1)
    cy = cortes_proprios(rgb, gy[1], gy[2], 0)
    ch = np.array(hex_rgb(chave), np.float64)
    if paleta:
        pal = np.array([hex_rgb(p) for p in paleta], np.float64)
    else:
        amostra = rgb[::3, ::3].reshape(-1, 3)
        amostra = amostra[np.abs(amostra.astype(float) - ch).sum(-1) > 90]
        pal = _kmeans_lab(amostra.astype(np.uint8), n_cores)
    todas = np.vstack([pal, ch[None]])
    lab_t = _oklab(todas)
    idx = np.empty(rgb.shape[:2], np.int16)
    for y0 in range(0, rgb.shape[0], 128):
        L = _oklab(rgb[y0:y0 + 128].astype(np.float64))
        idx[y0:y0 + 128] = np.linalg.norm(L[..., None, :] - lab_t, axis=-1).argmin(-1)
    k_chave = len(pal)
    H, W = len(cy) - 1, len(cx) - 1
    out = np.zeros((H, W, 4), np.uint8)
    for i in range(H):
        a, b = cy[i], cy[i + 1]
        m = (b - a) * (1 - miolo) / 2
        ya, yb = int(a + m), max(int(a + m) + 1, int(round(b - m)))
        for j in range(W):
            c, e = cx[j], cx[j + 1]
            m2 = (e - c) * (1 - miolo) / 2
            xa, xb = int(c + m2), max(int(c + m2) + 1, int(round(e - m2)))
            v = np.bincount(idx[ya:yb, xa:xb].ravel(), minlength=k_chave + 1)
            k = int(v.argmax())
            if k != k_chave:
                out[i, j, :3] = pal[k]
                out[i, j, 3] = 255
    return out, float((gx[1] + gy[1]) / 2), float(gx[0])


def ler_master(imagem: np.ndarray, chave: str = "#ff00ff", *, n_cores: int = 4, tol_chave: float = 90.0,
               margem: int = 4, vao: int = 4, min_px: int = 20, paleta: list[str] | None = None,
               metodo: str = "propria") -> Master:
    """Lê uma imagem de pixel art ampliada (Codex) na grade nativa dela e devolve o sprite 1x.

    Bloco e fase pela periodicidade das bordas (motor.conceito.grade_nativa). Cor de cada célula = mediana do miolo
    5x5; a cor-chave vira transparente; as cores são reduzidas a `n_cores` cores reais da imagem (k-médias OKLab
    que devolve a cor mais frequente de cada grupo, nunca uma média). Pixel solto (sem vizinho opaco) sai.
    Cada figura (componente) vira uma vista; a folha põe todas na mesma linha de chão, com `margem` em volta
    (espaço para chapéu e capa na hora de vestir) e `vao` entre elas.
    """
    from .motor.conceito import amostrar_nativo, grade_nativa
    rgb = imagem[..., :3]
    avisos = []
    if metodo == "propria":
        out, bloco, coer = ler_grade_propria(rgb, paleta=paleta, chave=chave, n_cores=n_cores)
        gx = (coer, bloco, 0.0)
        pal = np.array(sorted({tuple(int(v) for v in c) for c in out[out[..., 3] > 0][:, :3]}), np.float64)
    else:
        gx, gy = grade_nativa(rgb)
        peq = amostrar_nativo(rgb.astype(np.float64), gx, gy)
        ch = hex_rgb(chave)
        vazio = _e_chave(peq, ch, tol_chave)
        cor = np.clip(np.rint(peq), 0, 255).astype(np.uint8)
        opaca = ~vazio
        pal = (np.array([hex_rgb(p) for p in paleta], np.float64) if paleta else _kmeans_lab(cor[opaca], n_cores))
        out = np.zeros(cor.shape[:2] + (4,), np.uint8)
        out[opaca, :3] = _encaixar(cor[opaca].astype(np.float64), pal).astype(np.uint8)
        out[opaca, 3] = 255
    if gx[0] < 0.5 and metodo != "propria":
        avisos.append(f"grade pouco coerente ({gx[0]:.2f}): a imagem talvez não seja pixel art de bloco uniforme")
    viz = ndimage.convolve((out[..., 3] > 0).astype(int), np.ones((3, 3), int), mode="constant") - 1
    solto = (out[..., 3] > 0) & (viz <= 0)
    out[solto] = 0

    lbl, n = ndimage.label(out[..., 3] > 0, structure=np.ones((3, 3), int))
    objs = [(sl, i + 1) for i, sl in enumerate(ndimage.find_objects(lbl)) if sl is not None]
    objs = [(sl, k) for sl, k in objs if (lbl[sl] == k).sum() >= min_px]
    objs.sort(key=lambda t: t[0][1].start)
    vistas = []
    for sl, k in objs:
        v = np.where((lbl[sl] == k)[..., None], out[sl], 0).astype(np.uint8)
        vistas.append(v)
    if not vistas:
        raise ValueError("nenhuma figura encontrada (confira a cor-chave)")
    alturas = [v.shape[0] for v in vistas]
    if max(alturas) - min(alturas) > 1:
        avisos.append(f"vistas com alturas diferentes {alturas}: a folha alinha pelos pés, confira")
    H = max(alturas) + 2 * margem
    W = sum(v.shape[1] for v in vistas) + vao * (len(vistas) - 1) + 2 * margem
    folha = np.zeros((H, W, 4), np.uint8)
    x = margem
    for v in vistas:
        y = H - margem - v.shape[0]
        m = v[..., 3] > 0
        folha[y:y + v.shape[0], x:x + v.shape[1]][m] = v[m]
        x += v.shape[1] + vao
    cores = sorted({"#%02x%02x%02x" % tuple(int(c) for c in p) for p in pal})
    return Master(folha, vistas, float(gx[1]), cores, alturas, avisos)


# ------------------------------------------------------------------ ler pose/vista do Codex na grade do master


def tirar_franja(rgba: np.ndarray, *, passadas: int = 2) -> np.ndarray:
    """Tira o halo claro (ciano/branco) que o Codex às vezes põe por fora do contorno: pixel claro e saturado
    encostado no vazio vira vazio. Limpeza mecânica; o contorno escuro de dentro fica."""
    out = rgba.copy()
    cruz = ndimage.generate_binary_structure(2, 1)
    lab = _oklab(out[..., :3])
    for _ in range(passadas):
        op = out[..., 3] > 0
        borda = op & ndimage.binary_dilation(~op, cruz)
        claro = (lab[..., 0] > 0.75) & (np.hypot(lab[..., 1], lab[..., 2]) > 0.08)
        tirar = borda & claro
        if not tirar.any():
            break
        out[tirar] = 0
    return out


@dataclass
class PoseLida:
    quadro: np.ndarray      # RGBA 1x, recortado, cabeça travada
    bruto: np.ndarray       # RGBA 1x lido, antes de travar a cabeça
    bloco: float
    cabeca_iou: float
    avisos: list


def ler_pose(imagem: np.ndarray, master: np.ndarray, *, paleta: list[str], chave: str = "#ff00ff",
             cabeca: int | None = None, busca: int = 6) -> PoseLida:
    """Pose (ou vista) do Codex → quadro 1x na grade do master, sem halo, com a cabeça TRAVADA.

    master: a vista aprovada (RGBA 1x recortada). O bloco vem da altura do master (o Codex mistura meio-bloco no
    detalhe). cabeca: linhas do topo do master que formam cabeça+chifre/cabelo; essas linhas do master são coladas
    por cima da pose no lugar de melhor encaixe da silhueta (a cabeça redesenhada pela pose é apagada antes). O rosto
    não "ferve" entre quadros (perfeicao.md F6)."""
    out, bloco, _ = ler_grade_propria(imagem[..., :3], paleta=paleta, chave=chave, altura=master.shape[0])
    op = out[..., 3] > 0
    lbl, n = ndimage.label(op, np.ones((3, 3), int))
    if n == 0:
        raise ValueError("nenhuma figura na pose (confira a cor-chave)")
    out[lbl != np.bincount(lbl.ravel())[1:].argmax() + 1] = 0
    out = tirar_franja(out)
    ys, xs = np.nonzero(out[..., 3])
    pose = out[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    avisos = []
    H = pose.shape[0]
    if abs(H - master.shape[0]) > 1:
        avisos.append(f"altura {H} ≠ master {master.shape[0]}: o Codex mudou a escala; gere de novo")
    if not cabeca:
        return PoseLida(pose, pose, bloco, 0.0, avisos)
    cab = master[:cabeca]
    sil = cab[..., 3] > 0
    melhor = (-1.0, 0, 0)
    for dy in range(-3, 4):
        y0 = dy + (H - master.shape[0])
        for dx in range(-busca, pose.shape[1] - cab.shape[1] + busca + 1):
            reg = np.zeros_like(sil)
            ys0, ys1 = max(0, y0), min(H, y0 + cabeca)
            xs0, xs1 = max(0, dx), min(pose.shape[1], dx + cab.shape[1])
            if ys1 <= ys0 or xs1 <= xs0:
                continue
            reg[ys0 - y0:ys1 - y0, xs0 - dx:xs1 - dx] = pose[ys0:ys1, xs0:xs1, 3] > 0
            iou = (reg & sil).sum() / max(1, (reg | sil).sum())
            if iou > melhor[0]:
                melhor = (float(iou), dx, y0)
    iou, dx, y0 = melhor
    if iou < 0.5:
        avisos.append(f"cabeça da pose encaixa mal na do master (IoU {iou:.2f}): a pose virou o corpo; descarte")
    sx, top = -min(0, dx), -min(0, y0)
    W = max(pose.shape[1] + sx, sx + dx + cab.shape[1])
    q = np.zeros((H + top, W, 4), np.uint8)
    q[top:top + H, sx:sx + pose.shape[1]] = pose
    q[:top + y0 + cabeca] = 0
    reg = q[top + y0:top + y0 + cabeca, sx + dx:sx + dx + cab.shape[1]]
    reg[sil] = cab[sil]
    ys, xs = np.nonzero(q[..., 3])
    return PoseLida(q[ys.min():ys.max() + 1, xs.min():xs.max() + 1], pose, bloco, iou, avisos)
