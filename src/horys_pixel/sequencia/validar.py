"""Validação objetiva de uma sequência pronta (quadros RGBA no tamanho final). Mede o que o olho cobra numa animação
de câmera fixa: canvas, transparência, paleta, proporção, câmera, deriva, cintilação, quadros repetidos, loop e
identidade. Os números não substituem a revisão artística: uma sequência que passa aqui mas desliza continua
reprovada no revisor.

Cada checagem devolve {id, nome, ok, valor, limite, grave}. 'grave' = estrutural (reprova a sequência);
não grave = aviso (o revisor decide)."""
from __future__ import annotations

import numpy as np

from scipy import ndimage

from .anticintilacao import pisca_rgba
from .registro import caixa

LIMITES = {
    "altura_var": 0.06,       # variação da altura da figura / altura mediana
    "deriva_x_frac": 0.02,    # deriva do centro de massa / largura do canvas (mín. 2 px)
    "pes_var_px": 3,          # variação da linha dos pés (aviso: quique deliberado é permitido)
    "pisca": 0.02,            # fração de pixels que piscam A→B→A
    "loop_razao": 2.0,        # diferença último→primeiro / mediana das diferenças consecutivas
    "iou_min": 0.55,          # silhueta de cada quadro × quadro 0 (alinhada pelos pés)
    "cabeca_iou_min": 0.5,    # faixa de cima (25% da altura) × quadro 0
    "cor_presente_px": 6,     # cor com ≥ isso no quadro 0 precisa existir em todos (olho, runa)
    "pivo_px": 3,             # centro dos pés × pivô declarado
}


def _chk(id_, nome, ok, valor, limite, grave=True) -> dict:
    return {"id": id_, "nome": nome, "ok": bool(ok), "valor": valor, "limite": limite, "grave": grave}


def _hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(int(c) for c in rgb[:3])


def _sil(q):
    return q[..., 3] >= 128


def _iou(a, b) -> float:
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else 1.0


def _alinhar(sil, dx, dy):
    """Desloca a silhueta (sem embrulhar)."""
    out = np.zeros_like(sil)
    h, w = sil.shape
    ys, xs = slice(max(0, dy), min(h, h + dy)), slice(max(0, dx), min(w, w + dx))
    yo, xo = slice(max(0, -dy), min(h, h - dy)), slice(max(0, -dx), min(w, w - dx))
    out[ys, xs] = sil[yo, xo]
    return out


def _dif(a, b) -> float:
    """Fração dos pixels (da união das silhuetas) que mudam de cor ou de opacidade."""
    sa, sb = _sil(a), _sil(b)
    u = sa | sb
    if not u.any():
        return 0.0
    mud = (sa != sb) | (sa & sb & np.any(a[..., :3] != b[..., :3], -1))
    return float(mud[u].mean())


def pisca_isolado(quadros: list[np.ndarray], ciclo: bool = True, tam_max: int = 2) -> float:
    """Fração dos pixels opacos que piscam (A→B→A) SOLTOS: manchas 8-conexas de até 'tam_max' px. Movimento de
    verdade (borda de peça que sobe 1 px e desce) pisca em linhas e não conta; o boil (pixel solto trocando de cor)
    conta."""
    n = len(quadros)
    if n < 3:
        return 0.0
    total = piscou = 0
    for i in range(n):
        if not ciclo and (i == 0 or i == n - 1):
            continue
        a, b, c = quadros[i - 1], quadros[i], quadros[(i + 1) % n]
        op = (a[..., 3] == 255) & (b[..., 3] == 255) & (c[..., 3] == 255)
        m = op & np.all(a[..., :3] == c[..., :3], -1) & np.any(a[..., :3] != b[..., :3], -1)
        rot, k = ndimage.label(m, structure=np.ones((3, 3), int))
        if k:
            tam = np.bincount(rot.ravel())[1:]
            piscou += int(tam[tam <= tam_max].sum())
        total += int(op.sum())
    return piscou / max(total, 1)


def validar(quadros: list[np.ndarray], paleta_hex: list[str] | None = None, pivo: tuple[float, float] | None = None,
            loop: bool = True, limites: dict | None = None) -> dict:
    """Roda todas as checagens. Devolve {aprovado, graves, avisos, checagens: [...], metricas: {...}}."""
    L = {**LIMITES, **(limites or {})}
    ch: list[dict] = []
    n = len(quadros)
    if n == 0:
        return {"aprovado": False, "graves": 1, "avisos": 0,
                "checagens": [_chk("V00", "há quadros", False, 0, ">= 1")], "metricas": {}}

    # V01 canvas
    formas = {q.shape for q in quadros}
    ch.append(_chk("V01", "mesmo canvas em todos", len(formas) == 1 and all(q.ndim == 3 and q.shape[2] == 4
                                                                            for q in quadros),
                   sorted(f"{s[1]}x{s[0]}" for s in formas), "1 tamanho RGBA"))
    if len(formas) != 1:
        return {"aprovado": False, "graves": 1, "avisos": 0, "checagens": ch, "metricas": {}}
    H, W = quadros[0].shape[:2]

    # V02 alpha binário
    parciais = int(sum(((q[..., 3] > 0) & (q[..., 3] < 255)).sum() for q in quadros))
    ch.append(_chk("V02", "alpha só 0 ou 255 (sem antialias)", parciais == 0, parciais, 0))

    # V03 paleta
    usadas = set()
    for q in quadros:
        op = q[..., 3] > 0
        usadas |= {_hex(c) for c in np.unique(q[op][:, :3], axis=0)}
    if paleta_hex is not None:
        pal = {h.lower() for h in paleta_hex}
        fora = sorted(usadas - pal)
        ch.append(_chk("V03", "cores dentro da paleta", not fora, fora[:12], f"{len(pal)} cores"))
    ch.append(_chk("V03b", "total de cores da sequência", len(usadas) <= 16, len(usadas), "<= 16", grave=False))

    caixas = [caixa(q) for q in quadros]
    vazios = [i for i, b in enumerate(caixas) if b is None]
    ch.append(_chk("V04", "nenhum quadro vazio", not vazios, vazios, "[]"))
    if vazios:
        return {"aprovado": False, "graves": sum(1 for c in ch if c["grave"] and not c["ok"]), "avisos": 0,
                "checagens": ch, "metricas": {}}

    alturas = np.array([b[3] - b[1] + 1 for b in caixas], float)
    larguras = np.array([b[2] - b[0] + 1 for b in caixas], float)
    pes = np.array([b[3] for b in caixas], float)
    cx = np.array([np.nonzero(_sil(q))[1].mean() for q in quadros])

    # V05 proporção (a cabeça não cresce, o corpo não encolhe)
    var_alt = float((alturas.max() - alturas.min()) / np.median(alturas))
    ch.append(_chk("V05", "altura estável (proporção)", var_alt <= L["altura_var"], round(var_alt, 4),
                   L["altura_var"]))
    var_larg = float((larguras.max() - larguras.min()) / np.median(larguras))
    ch.append(_chk("V05b", "largura estável", var_larg <= 0.25, round(var_larg, 4), 0.25, grave=False))

    # V06 deriva horizontal sem intenção
    lim_x = max(2.0, L["deriva_x_frac"] * W)
    der_x = float(cx.max() - cx.min())
    ch.append(_chk("V06", "sem deriva horizontal", der_x <= lim_x, round(der_x, 2), round(lim_x, 2)))

    # V07 linha dos pés (aviso: quique e pé no ar são deliberados)
    var_pes = float(pes.max() - pes.min())
    ch.append(_chk("V07", "linha dos pés estável", var_pes <= L["pes_var_px"], var_pes, L["pes_var_px"],
                   grave=False))

    # V08 pivô declarado (só x: em 3/4 a origem no chão fica acima da ponta do pé da frente)
    if pivo is not None:
        erro = abs(float(np.median(cx)) - pivo[0])
        ch.append(_chk("V08", "câmera/pivô na posição declarada (x)", erro <= L["pivo_px"], round(erro, 2),
                       L["pivo_px"]))

    # V09 cintilação: pixel solto que pisca (grave); A→B→A total (inclui movimento real) só informa
    p = pisca_isolado(quadros, ciclo=loop)
    ch.append(_chk("V09", "sem cintilação (pixel solto piscando)", p <= L["pisca"], round(p, 4), L["pisca"]))
    p_total = pisca_rgba(quadros, ciclo=loop)

    # V10 quadros repetidos (animação disfarçada)
    difs = [_dif(quadros[i], quadros[i + 1]) for i in range(n - 1)]
    iguais = [i for i, d in enumerate(difs) if d == 0.0]
    unicos = len({q.tobytes() for q in quadros})
    ch.append(_chk("V10", "quadros vizinhos diferentes", not iguais, iguais, "[]"))
    ch.append(_chk("V10b", "quadros únicos", n < 2 or unicos > n // 2, unicos, f"> {n // 2}"))

    # V11 loop: último → primeiro parecido com um passo normal
    if loop and n >= 3:
        fecho = _dif(quadros[-1], quadros[0])
        med = float(np.median(difs)) if difs else 0.0
        razao = fecho / med if med > 0 else (0.0 if fecho == 0 else float("inf"))
        ok = med > 0 and razao <= L["loop_razao"] and fecho > 0
        ch.append(_chk("V11", "loop fecha (último → primeiro)", ok, round(razao, 3), L["loop_razao"]))

    # V12 identidade: silhueta e cabeça parecidas com o quadro 0 (alinhadas pelo pé e centro)
    s0 = _sil(quadros[0])
    b0 = caixas[0]
    topo0 = int(b0[1] + 0.25 * (b0[3] - b0[1] + 1))
    ious, cabeca = [], []
    for q, b, x in zip(quadros, caixas, cx):
        dx, dy = round(cx[0] - x), round(pes[0] - b[3])
        s = _alinhar(_sil(q), dx, dy)
        ious.append(_iou(s0, s))
        # cabeça: alinhada pelo topo e pelo centro da própria faixa (o quique do corpo não é mudança de forma)
        h = topo0 - b0[1]
        fa, fb = s0[b0[1]:topo0], _sil(q)[b[1]:b[1] + h]
        if fb.shape == fa.shape and fa.any() and fb.any():
            d = round(np.nonzero(fa)[1].mean() - np.nonzero(fb)[1].mean())
            cabeca.append(_iou(fa, _alinhar(fb, d, 0)))
        else:
            cabeca.append(0.0)
    ch.append(_chk("V12", "silhueta reconhecível (IoU × quadro 0)", min(ious) >= L["iou_min"], round(min(ious), 3),
                   L["iou_min"]))
    ch.append(_chk("V12b", "cabeça reconhecível (IoU do topo)", min(cabeca) >= L["cabeca_iou_min"],
                   round(min(cabeca), 3), L["cabeca_iou_min"]))

    # V13 elementos não somem: cada cor marcante do quadro 0 aparece em todos (olho aceso, runa)
    def contagem(q):
        op = q[..., 3] > 0
        cores, cont = np.unique(q[op][:, :3], axis=0, return_counts=True)
        return {_hex(c): int(k) for c, k in zip(cores, cont)}
    c0 = {h: k for h, k in contagem(quadros[0]).items() if k >= L["cor_presente_px"]}
    sumiu = sorted({h for q in quadros[1:] for h in c0 if h not in contagem(q)})
    ch.append(_chk("V13", "nenhum elemento some (cores do quadro 0 em todos)", not sumiu, sumiu, "[]"))

    graves = sum(1 for c in ch if c["grave"] and not c["ok"])
    avisos = sum(1 for c in ch if not c["grave"] and not c["ok"])
    return {"aprovado": graves == 0, "graves": graves, "avisos": avisos, "checagens": ch,
            "metricas": {"quadros": n, "canvas": [W, H], "altura": [int(alturas.min()), int(alturas.max())],
                         "deriva_x": round(der_x, 2), "pes_var": var_pes, "pisca": round(p, 4),
                         "pisca_total": round(p_total, 4), "cores": len(usadas),
                         "iou_min": round(min(ious), 3)}}


def resumo(rel: dict) -> str:
    """Uma linha por checagem que falhou, mais o veredito."""
    linhas = [("REPROVA" if c["grave"] else "aviso") + f" {c['id']} {c['nome']}: {c['valor']} (limite {c['limite']})"
              for c in rel["checagens"] if not c["ok"]]
    cab = ("APROVADA" if rel["aprovado"] else "REPROVADA") + f" · {rel['graves']} graves · {rel['avisos']} avisos"
    return "\n".join([cab] + linhas)
