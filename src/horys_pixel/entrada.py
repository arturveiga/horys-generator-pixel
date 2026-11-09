"""Portão de entrada (tarefa 1.4): mede a imagem gerada ANTES da conversão para pixel art.

Puro (numpy, Pillow, scipy; sem Aseprite). `checar()` devolve
    {"aprovado": bool, "falhas": [{"item": <nº do item do prompt de tradução>, "texto": correção}], "medidas": {...}}
e, com `gravar=True`, escreve ao lado da imagem o `entrada_checagem.txt` (primeira linha
"PORTÃO DE ENTRADA: APROVADO|REPROVADO") e a prévia no tamanho final (vizinho mais próximo, figura na altura alvo).

Os itens citados são os do "Modelo do prompt de tradução" (padroes/README.md do cofre):
  1 formato e escala · 7 cores · 9 estilo chapado · 10 enquadramento, fundo, chão e sombra.

Checagens (o checklist "Portão de entrada"):
  - fundo liso: os quatro cantos concordam (ΔE OKLab) e a cor do fundo não aparece dentro da figura;
  - figura inteira, com margem >= margem_min em cada lado (em grade: dentro de cada célula);
  - linha dos pés (última linha opaca), sem sombra no chão nem chão desenhado;
  - escala: altura da figura >= escala_min × altura alvo;
  - grade: uma figura por célula, alturas iguais (±3%) e chão comum;
  - chapado: número de grupos de cor (OKLab), fração em áreas lisas (textura, ruído) e degradê dentro das áreas.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

from .motor import comum as C

# tolerâncias (ΔE em OKLab, onde ~0.02 é a menor diferença visível)
TOL_CANTOS = 0.03        # cantos do fundo: diferença máxima entre eles
TOL_FUNDO = 0.08         # pixel "da cor do fundo" (mesma do conceito.py --tolerancia)
FRACAO_COR_FUNDO = 0.002  # fração máxima da figura com a cor do fundo
TOL_ALTURAS = 0.03       # grade: alturas iguais ±3%
CORES_MAX = 48           # grupos de cor OKLab que cobrem 95% da figura
PASSO_GRUPO = 0.04       # raio do agrupamento de cores
AREA_DEGRAU = 0.015      # degrau entre vizinhos abaixo do qual o pixel continua a mesma área lisa
LISAS_MIN = 0.35         # fração mínima da figura em áreas lisas (calibrado: macaco original 0.28, chapados >= 0.42)
DEGRADE_MAX = 0.15       # fração máxima das áreas lisas com degradê por dentro (macaco 0.31, chapados <= 0.08)


def _lab(rgb: np.ndarray) -> np.ndarray:
    return np.stack(C.oklab(rgb.reshape(-1, 3).astype(np.float64)), -1).reshape(*rgb.shape[:2], 3)


def _hex(lab_rgb) -> str:
    return C.rgb2hex(np.clip(np.round(lab_rgb), 0, 255))


def _ler(caminho) -> tuple[np.ndarray, np.ndarray | None]:
    im = Image.open(caminho)
    if im.mode in ("RGBA", "LA", "PA") or (im.mode == "P" and "transparency" in im.info):
        a = np.asarray(im.convert("RGBA"))
        alfa = a[..., 3]
        if (alfa < 250).mean() > 0.01:  # fundo transparente de verdade
            return a[..., :3].copy(), alfa
        return a[..., :3].copy(), None
    return np.asarray(im.convert("RGB")).copy(), None


# ------------------------------------------------------------------ fundo

def _cantos(lab: np.ndarray, rgb: np.ndarray):
    h, w = lab.shape[:2]
    k = max(4, min(h, w) // 64)
    fatias = [(slice(0, k), slice(0, k)), (slice(0, k), slice(w - k, w)),
              (slice(h - k, h), slice(0, k)), (slice(h - k, h), slice(w - k, w))]
    meds = np.array([np.median(lab[f].reshape(-1, 3), 0) for f in fatias])
    rgbs = np.array([np.median(rgb[f].reshape(-1, 3), 0) for f in fatias])
    dmax = max(float(np.linalg.norm(meds[i] - meds[j])) for i in range(4) for j in range(i + 1, 4))
    ruido = max(float(np.linalg.norm(lab[f] - meds[i], axis=-1).mean()) for i, f in enumerate(fatias))
    return meds, rgbs, dmax, ruido


def _modelo_fundo(meds: np.ndarray, h: int, w: int) -> np.ndarray:
    """Fundo esperado: interpolação bilinear das cores dos 4 cantos (liso = constante; degradê linear = coberto),
    para que um fundo em degradê não vire 'figura cortada' por engano."""
    ty = np.linspace(0, 1, h)[:, None, None]
    tx = np.linspace(0, 1, w)[None, :, None]
    tl, tr, bl, br = meds
    return (1 - ty) * ((1 - tx) * tl + tx * tr) + ty * ((1 - tx) * bl + tx * br)


def _degrau(lab: np.ndarray) -> np.ndarray:
    """Maior ΔE entre o pixel e o vizinho da direita ou de baixo."""
    gx = np.zeros(lab.shape[:2])
    gy = np.zeros(lab.shape[:2])
    gx[:, :-1] = np.linalg.norm(lab[:, 1:] - lab[:, :-1], axis=-1)
    gy[:-1] = np.linalg.norm(lab[1:] - lab[:-1], axis=-1)
    return np.maximum(gx, gy)


def _ligado_a_borda(m: np.ndarray) -> np.ndarray:
    rot, _ = ndimage.label(m)
    borda = np.unique(np.r_[rot[0], rot[-1], rot[:, 0], rot[:, -1]])
    return np.isin(rot, borda[borda > 0]), rot


def _mascaras(lab, alfa, meds, tol, liso=True):
    """Devolve (figura, fundo, dist ao fundo). Fundo liso = região da cor do fundo ligada à borda + buracos grandes.
    Fundo em degradê/vinheta: região SUAVE (sem degrau) ligada à borda, que para no contorno da figura."""
    h, w = lab.shape[:2]
    if alfa is not None:
        fundo = alfa < 128
        return ~fundo, fundo, np.where(fundo, 0.0, 1.0)
    dist = np.linalg.norm(lab - _modelo_fundo(meds, h, w), axis=-1)
    if liso:
        perto = dist < tol
        fundo, rot = _ligado_a_borda(perto)
        # buracos fechados da cor EXATA do fundo (entre braço e corpo) também são fundo, se forem grandes; uma área
        # fechada só parecida com o fundo fica na figura e cai na checagem "cor do fundo na figura"
        exato = (dist < tol / 2) & ~fundo
        rot, _ = ndimage.label(exato)
        tam = np.bincount(rot.ravel())
        tam[0] = 0
        buraco = exato & (tam[rot] >= max(64, h * w * 0.0002))
        fundo |= buraco
    else:
        fundo, _ = _ligado_a_borda(_degrau(lab) < 0.012)
        fundo = ndimage.binary_opening(fundo, iterations=2)
    fig = ~fundo
    rot2, n = ndimage.label(fig)
    if n > 1:  # tira pó solto; mantém peças separadas que fazem parte da arte (pedras flutuando etc.)
        t2 = np.bincount(rot2.ravel())
        t2[0] = 0
        fig = t2[rot2] >= max(30, t2.max() * 0.002)
    return fig, ~fig, dist


# ------------------------------------------------------------------ figura

def _bbox(m: np.ndarray):
    ys, xs = np.nonzero(m)
    if not len(ys):
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def _margens(bb, x0, y0, w, h):
    bx0, by0, bx1, by1 = bb
    return {"esq": (bx0 - x0) / w, "dir": (x0 + w - 1 - bx1) / w,
            "topo": (by0 - y0) / h, "base": (y0 + h - 1 - by1) / h}


def _sombra(lab, alfa, fig, fig_total, fundo_lab, bb, fig_area):
    """Sombra no chão: mancha larga e baixa perto dos pés, na cor do fundo escurecida (ou semitransparente),
    que encosta no fundo. O contorno escuro do estilo não conta (quase sem croma na direção do fundo)."""
    bx0, by0, bx1, by1 = bb
    hf = by1 - by0 + 1
    wf = bx1 - bx0 + 1
    y_ini = max(0, by1 - int(0.15 * hf))
    faixa = np.zeros_like(fig)
    faixa[y_ini:by1 + 1, max(0, bx0 - wf // 4):bx1 + wf // 4 + 1] = True
    if alfa is not None:
        cand = (alfa > 10) & (alfa < 200) & faixa
    else:
        Lb, ab = fundo_lab[0], fundo_lab[1:]
        croma_b = float(np.linalg.norm(ab))
        if croma_b < 0.02:  # fundo cinza: sombra = mais escuro e sem croma
            cand = (lab[..., 0] < Lb - 0.04) & (np.linalg.norm(lab[..., 1:], axis=-1) < 0.03)
        else:
            u = ab / croma_b
            proj = lab[..., 1] * u[0] + lab[..., 2] * u[1]
            perp = np.abs(lab[..., 1] * -u[1] + lab[..., 2] * u[0])
            cand = ((proj > 0.25 * croma_b) & (perp < 0.6 * np.maximum(proj, 1e-6))
                    & (lab[..., 0] < Lb - 0.03) & (lab[..., 0] > Lb - 0.45))
        cand &= fig & faixa
        # sombra suave que a máscara pôs no fundo: mais escura que o fundo da mesma linha, longe da figura
        y_fim = min(lab.shape[0], by1 + int(0.06 * hf) + 1)
        L = lab[..., 0]
        faixa2 = np.zeros_like(fig)
        faixa2[y_ini:y_fim, max(0, bx0 - wf // 4):bx1 + wf // 4 + 1] = True
        Lf = np.where(fig_total[y_ini:y_fim], np.nan, L[y_ini:y_fim])
        with np.errstate(all="ignore"):
            ref = np.nanmedian(Lf, 1)[:, None]
        ref = np.nan_to_num(ref, nan=-1.0)
        escuro = np.zeros_like(fig)
        escuro[y_ini:y_fim] = L[y_ini:y_fim] < ref - 0.04
        cand |= faixa2 & ~fig_total & escuro
    if not cand.any():
        return {"pixels": 0, "largura": 0, "fracao_largura": 0.0}
    vizinho_fundo = ndimage.binary_dilation(~fig_total, iterations=2)
    rot, n = ndimage.label(cand)
    melhor = {"pixels": 0, "largura": 0, "fracao_largura": 0.0}
    for i, sl in enumerate(ndimage.find_objects(rot), 1):
        comp = rot[sl] == i
        area = int(comp.sum())
        if area < max(20, 0.001 * fig_area) or not (vizinho_fundo[sl] & comp).any():
            continue
        larg = sl[1].stop - sl[1].start
        alt = sl[0].stop - sl[0].start
        if larg < 1.5 * alt:  # sombra no chão é achatada
            continue
        if area > melhor["pixels"]:
            melhor = {"pixels": area, "largura": int(larg), "fracao_largura": round(larg / wf, 3),
                      "bbox": [int(sl[1].start), int(sl[0].start), int(sl[1].stop - 1), int(sl[0].stop - 1)]}
    return melhor


def _grupos(cores: np.ndarray, pesos: np.ndarray, raio: float) -> int:
    """Agrupa cores OKLab (guloso, do mais frequente) e devolve quantos grupos cobrem 95% do peso."""
    cent: list = []
    pes: list = []
    for i in np.argsort(-pesos):
        c = cores[i]
        if cent:
            d = np.linalg.norm(np.asarray(cent) - c, axis=1)
            k = int(d.argmin())
            if d[k] < raio:
                pes[k] += pesos[i]
                continue
        cent.append(c)
        pes.append(pesos[i])
    p = np.sort(np.asarray(pes))[::-1]
    return int(np.searchsorted(np.cumsum(p), 0.95 * p.sum()) + 1)


def _chapado(lab, fig):
    """Mede se a figura é ilustração chapada (cel shading):
    - grupos_cor: grupos de cor OKLab (raio PASSO_GRUPO) que cobrem 95% da figura;
    - areas_lisas: fração da figura em áreas lisas (sem degrau entre vizinhos) de pelo menos 100 px. Textura fina,
      ruído e pixel falso quebram as áreas e derrubam esta fração;
    - degrade: das áreas lisas, a fração cuja cor varia por dentro (ΔE > 0.04 do meio da área): degradê/desfoque;
    - bordas_suaves: entre os pixels que mudam de cor, a fração que muda pouco (borda mole), só como medida."""
    inter = ndimage.binary_erosion(fig, iterations=2)
    n = int(inter.sum())
    if n < 200:
        return {"grupos_cor": 0, "areas_lisas": 1.0, "degrade": 0.0, "bordas_suaves": 0.0}
    q = np.round(lab[inter] / 0.01).astype(np.int64)
    u, cnt = np.unique(q, axis=0, return_counts=True)
    sel = cnt >= 5
    grupos = _grupos(u[sel] * 0.01, cnt[sel].astype(float), PASSO_GRUPO) if sel.any() else 0
    d1 = _degrau(lab)
    rot, _ = ndimage.label(inter & (d1 < AREA_DEGRAU))
    tam = np.bincount(rot.ravel())
    tam[0] = 0
    lisas = 0
    com_degrade = 0
    for i, sl in enumerate(ndimage.find_objects(rot), 1):
        if sl is None or tam[i] < 100:
            continue
        px = lab[sl][rot[sl] == i]
        espalha = np.percentile(np.linalg.norm(px - np.median(px, 0), axis=-1), 90)
        lisas += int(tam[i])
        if espalha > 0.04:
            com_degrade += int(tam[i])
    g = d1[inter]
    borda = g >= 0.004
    suave = borda & (g < 0.03)
    return {"grupos_cor": grupos, "areas_lisas": round(lisas / n, 3),
            "degrade": round(com_degrade / max(1, lisas), 3),
            "bordas_suaves": round(float(suave.sum() / max(1, borda.sum())), 3)}


# ------------------------------------------------------------------ checagem

def checar(imagem_path, altura_alvo: int, grade=None, margem_min: float = 0.01, escala_min: float = 3.0,
           gravar: bool = True, tol_fundo: float = TOL_FUNDO, tol_cantos: float = TOL_CANTOS,
           cores_max: int = CORES_MAX, lisas_min: float = LISAS_MIN, degrade_max: float = DEGRADE_MAX) -> dict:
    """Portão de entrada. `grade` = (linhas, colunas) para uma folha de poses, ou None para figura única."""
    caminho = Path(imagem_path)
    rgb, alfa = _ler(caminho)
    h, w = rgb.shape[:2]
    lab = _lab(rgb)
    falhas: list[dict] = []
    med: dict = {"imagem": str(caminho), "tamanho": [w, h], "altura_alvo": int(altura_alvo)}

    def falha(item, txt):
        falhas.append({"item": item, "texto": txt})

    # 1. fundo liso
    meds, rgbs, dmax, ruido = _cantos(lab, rgb)
    fundo_lab = np.median(meds, 0)
    fundo_hex = _hex(np.median(rgbs, 0))
    med["fundo"] = {"transparente": alfa is not None, "cor": None if alfa is not None else fundo_hex,
                    "cantos": [_hex(c) for c in rgbs], "delta_cantos": round(dmax, 4), "ruido": round(ruido, 4)}
    if alfa is None:
        if dmax > tol_cantos:
            falha(10, f"Fundo não é liso: os cantos diferem (ΔE {dmax:.3f} > {tol_cantos}; "
                      f"{', '.join(med['fundo']['cantos'])}). Peça fundo liso de uma cor só ({fundo_hex} ou "
                      "#3DBE5B), sem degradê, vinheta, textura ou luz.")
        elif ruido > tol_cantos:
            falha(10, f"Fundo com ruído ou textura (ΔE médio {ruido:.3f} nos cantos). Peça fundo liso de uma "
                      "cor só, sem textura.")

    liso = alfa is not None or (dmax <= tol_cantos and ruido <= tol_cantos)
    fig, fundo_m, dist = _mascaras(lab, alfa, meds, tol_fundo, liso)
    bb = _bbox(fig)
    if bb is None:
        falha(2, "Nenhuma figura encontrada (a imagem é só fundo).")
        return _fim(caminho, falhas, med, gravar, rgb, alfa, None, altura_alvo)

    # cor do fundo dentro da figura (fora da faixa de borda/antisserrilhado); com fundo em degradê não dá para medir
    if alfa is None and liso:
        miolo = ndimage.binary_erosion(fig, iterations=3)
        n_miolo = int(miolo.sum())
        perto = miolo & (dist < tol_fundo * 1.5)
        frac_cf = float(perto.sum() / max(1, n_miolo))
        med["fundo"]["cor_na_figura"] = round(frac_cf, 4)
        if frac_cf > FRACAO_COR_FUNDO:
            alt = "#FF00FF" if fundo_hex.lower() != "#ff00ff" else "#3DBE5B"
            falha(10, f"A cor do fundo ({fundo_hex}) aparece dentro da figura ({frac_cf:.1%} da figura). Troque o "
                      f"fundo por uma cor que não está no asset (ex.: {alt}) ou tire essa cor do asset.")

    # 2-5. figura(s)
    if grade:
        linhas, colunas = int(grade[0]), int(grade[1])
        ch, cw = h / linhas, w / colunas
        celulas = []
        for r in range(linhas):
            for c in range(colunas):
                y0, y1 = int(round(r * ch)), int(round((r + 1) * ch))
                x0, x1 = int(round(c * cw)), int(round((c + 1) * cw))
                celulas.append((r, c, x0, y0, x1 - x0, y1 - y0))
    else:
        celulas = [(0, 0, 0, 0, w, h)]

    aprox = "" if liso else " (Medida aproximada: com o fundo em degradê a figura não se separa bem do fundo.)"
    alturas, pes_rel, regs = [], [], []
    altura_ref = None
    for (r, c, x0, y0, cw_, ch_) in celulas:
        sub = np.zeros_like(fig)
        sub[y0:y0 + ch_, x0:x0 + cw_] = fig[y0:y0 + ch_, x0:x0 + cw_]
        nome = f"célula ({r + 1},{c + 1})" if grade else "figura"
        reg = {"linha": r + 1, "coluna": c + 1} if grade else {}
        cbb = _bbox(sub)
        if cbb is None:
            reg["vazia"] = True
            regs.append(reg)
            falha(1, f"{nome} está vazia: a grade pedida tem {len(celulas)} poses, uma por célula.")
            continue
        # quantas figuras: peças grandes separadas (o pó e pedras pequenas não contam)
        rot, n = ndimage.label(sub)
        tam = np.bincount(rot.ravel())[1:]
        grandes = int((tam >= 0.3 * tam.max()).sum())
        mg = _margens(cbb, x0, y0, cw_, ch_)
        hf = cbb[3] - cbb[1] + 1
        reg.update({"bbox": list(cbb), "altura": hf, "largura": cbb[2] - cbb[0] + 1, "pes_y": cbb[3],
                    "margens": {k: round(v, 4) for k, v in mg.items()}, "pecas_grandes": grandes})
        if grade and grandes > 1:
            falha(1, f"{nome} tem {grandes} figuras grandes separadas; deve ter uma pose só por célula.")
        cortes = [k for k, v in mg.items() if v <= 0]
        if grade:  # na grade, encostar na borda da célula também pode ser invasão da vizinha
            invade = [lado for lado, cond in (("esq", cbb[0] == x0 and x0 > 0), ("dir", cbb[2] == x0 + cw_ - 1
                      and x0 + cw_ < w), ("topo", cbb[1] == y0 and y0 > 0), ("base", cbb[3] == y0 + ch_ - 1
                      and y0 + ch_ < h)) if cond]
            cortes = sorted(set(cortes) | set(invade))
        lados = {"esq": "esquerda", "dir": "direita", "topo": "topo", "base": "base"}
        if cortes:
            falha(10, f"{nome} cortada ou encostada na borda ({', '.join(lados[k] for k in cortes)}). Peça a figura "
                      f"inteira, com margem de pelo menos {margem_min:.0%} em volta." + aprox)
        else:
            curtas = {k: v for k, v in mg.items() if v < margem_min}
            if curtas:
                txt = ", ".join(f"{lados[k]} {v:.1%}" for k, v in curtas.items())
                falha(10, f"{nome} com margem curta ({txt}; mínimo {margem_min:.0%}). Peça a figura menor no "
                          "quadro, centrada, com margem em volta (punhos, armas e cauda dentro)." + aprox)
        # chão desenhado: a base da figura ocupa quase toda a largura
        base_larg = int(sub[cbb[3]].sum())
        if base_larg >= 0.9 * cw_:
            falha(10, f"{nome}: há um chão desenhado (a última linha ocupa {base_larg / cw_:.0%} da largura). "
                      "Peça sem chão, sem sombra no chão e sem moldura.")
        sb = _sombra(lab, alfa, sub, fig, fundo_lab, cbb, int(sub.sum()))
        reg["sombra"] = sb
        if sb["pixels"]:
            falha(10, f"{nome}: sombra no chão em volta dos pés ({sb['largura']} px de largura, "
                      f"{sb['fracao_largura']:.0%} da figura). Peça sem sombra no chão: pés direto sobre o fundo liso.")
        alturas.append(hf)
        pes_rel.append((cbb[3] - y0) / ch_)
        regs.append(reg)

    if grade:
        med["grade"] = {"linhas": int(grade[0]), "colunas": int(grade[1]), "celulas": regs}
    else:
        med["figura"] = regs[0]
        med["pes_y"] = regs[0].get("pes_y")

    if alturas:
        altura_ref = float(np.median(alturas))
        hmin = min(alturas)
        razao = hmin / altura_alvo
        med["escala"] = {"altura_figura": int(hmin), "altura_alvo": int(altura_alvo), "razao": round(razao, 2),
                         "minimo": escala_min}
        if razao < escala_min:
            falha(1, f"Figura pequena demais: {hmin} px de altura para alvo de {altura_alvo} px ({razao:.1f}×; "
                     f"mínimo {escala_min:g}×, ideal 4×). Gere maior: imagem maior ou figura ocupando ~75% da altura.")
        if grade and len(alturas) > 1:
            desv = [abs(a - altura_ref) / altura_ref for a in alturas]
            med["grade"]["alturas"] = alturas
            med["grade"]["desvio_altura_max"] = round(max(desv), 4)
            if max(desv) > TOL_ALTURAS:
                falha(10, f"As poses têm alturas diferentes ({min(alturas)}–{max(alturas)} px, desvio "
                          f"{max(desv):.1%} > {TOL_ALTURAS:.0%}). Peça todas as poses na MESMA escala e no mesmo "
                          "enquadramento.")
            # chão comum: pés no mesmo y relativo à célula (tolerância: 1% da célula ou 3 px)
            tol_chao = max(0.01, 3.0 / (h / int(grade[0])))
            pes = np.array(pes_rel)
            med["grade"]["pes_relativos"] = [round(float(p), 4) for p in pes]
            if pes.max() - pes.min() > tol_chao:
                falha(10, f"As poses não estão no mesmo chão (a linha dos pés varia "
                          f"{(pes.max() - pes.min()):.1%} da altura da célula; máximo {tol_chao:.1%}). Peça os pés "
                          "de todas as poses na mesma linha horizontal.")

    # 6. chapado
    ch_ = _chapado(lab, fig)
    med["chapado"] = ch_
    if ch_["grupos_cor"] > cores_max:
        falha(9, f"Cores demais: {ch_['grupos_cor']} grupos de cor cobrem 95% da figura (máximo {cores_max}). "
                 "Peça ilustração chapada só com as cores da paleta (item 7), áreas lisas, sem degradê nem textura.")
    if ch_["degrade"] > degrade_max:
        falha(9, f"Tem degradê: {ch_['degrade']:.0%} das áreas lisas mudam de cor por dentro (máximo "
                 f"{degrade_max:.0%}). Peça cel shading: cada área de uma cor só, bordas nítidas, sem degradê, "
                 "desfoque, brilho especular, névoa ou luz de borda.")
    if ch_["areas_lisas"] < lisas_min:
        falha(9, f"Não está chapado: só {ch_['areas_lisas']:.0%} da figura está em áreas lisas (mínimo "
                 f"{lisas_min:.0%}). Peça ilustração chapada em alta resolução, sem textura fina, ruído ou pixel "
                 "falso; áreas grandes e lisas.")

    return _fim(caminho, falhas, med, gravar, rgb, alfa, altura_ref, altura_alvo)


def _fim(caminho: Path, falhas, med, gravar, rgb, alfa, altura_ref, altura_alvo) -> dict:
    aprovado = not falhas
    res = {"aprovado": aprovado, "falhas": falhas, "medidas": med}
    if gravar:
        pasta = caminho.parent
        if altura_ref:
            fator = altura_alvo / altura_ref
            nw, nh = max(1, round(rgb.shape[1] * fator)), max(1, round(rgb.shape[0] * fator))
            src = Image.fromarray(np.dstack([rgb, alfa]) if alfa is not None else rgb)
            previa = pasta / f"{caminho.stem}_previa_{int(altura_alvo)}px.png"
            src.resize((nw, nh), Image.NEAREST).save(previa)
            med["previa"] = str(previa)
        txt = pasta / "entrada_checagem.txt"
        txt.write_text(relatorio(res), encoding="utf-8")
        med["checagem"] = str(txt)
    return res


def relatorio(res: dict) -> str:
    m = res["medidas"]
    linhas = [f"PORTÃO DE ENTRADA: {'APROVADO' if res['aprovado'] else 'REPROVADO'}",
              f"imagem: {m.get('imagem')}  ({m['tamanho'][0]}×{m['tamanho'][1]}), altura alvo {m.get('altura_alvo')} px"]
    if res["falhas"]:
        linhas.append("")
        linhas.append("Correções (citar o item do prompt de tradução):")
        linhas += [f"- item {f['item']}: {f['texto']}" for f in res["falhas"]]
    f = m.get("fundo", {})
    linhas += ["", "Medidas:",
               f"- fundo: {'transparente' if f.get('transparente') else f.get('cor')}; ΔE entre cantos "
               f"{f.get('delta_cantos')}; cor do fundo na figura {f.get('cor_na_figura', '-')}"]
    fig = m.get("figura")
    if fig and "bbox" in fig:
        mg = fig["margens"]
        linhas.append(f"- figura: bbox {fig['bbox']}, altura {fig['altura']} px, pés em y={fig['pes_y']}; margens "
                      f"esq {mg['esq']:.1%} dir {mg['dir']:.1%} topo {mg['topo']:.1%} base {mg['base']:.1%}; "
                      f"sombra {fig['sombra']['pixels']} px")
    g = m.get("grade")
    if g:
        linhas.append(f"- grade {g['linhas']}×{g['colunas']}: alturas {g.get('alturas')}, desvio "
                      f"{g.get('desvio_altura_max')}, pés relativos {g.get('pes_relativos')}")
    e = m.get("escala")
    if e:
        linhas.append(f"- escala: {e['altura_figura']} px / {e['altura_alvo']} px = {e['razao']}× (mínimo {e['minimo']}×)")
    c = m.get("chapado")
    if c:
        linhas.append(f"- chapado: {c['grupos_cor']} grupos de cor (95%), áreas lisas {c['areas_lisas']:.0%}, degradê "
                      f"{c['degrade']:.0%}, bordas suaves {c['bordas_suaves']:.0%}")
    if m.get("previa"):
        linhas.append(f"- prévia no tamanho final (teste de olho, item 6): {m['previa']}")
    return "\n".join(linhas) + "\n"
