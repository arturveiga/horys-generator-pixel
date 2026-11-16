"""Boas práticas de pixel art como código (docs/boas-praticas.md; regras em boas_praticas.json).

Mede, num quadro ou numa sequência RGBA no tamanho final, cada regra BP que tem métrica automática. As regras de
olho ficam para o revisor (motor/revisor_prompt.md cita os mesmos ids). Não há régua externa: os limites vêm do
envelope do Artur (perfeicao.md §5) e das fontes citadas no JSON.

API (sem Aseprite, só numpy/PIL):
  checar_quadro(rgba, contexto)            -> [resultado]   um por regra automática de quadro
  checar_animacao(quadros, contexto)       -> [resultado]   regras de sequência (pés, cintilação, loop...)
  checar_direcoes(vistas, contexto)        -> [resultado]   {'s': rgba, 'n': rgba, 'e': rgba}
  overlay(rgba, resultados, escala=8)      -> PIL.Image     marca os pixels de cada regra que falhou
  overlay_sequencia(quadros, por_quadro, anim, escala=6) -> PIL.Image
  checar_caminho(caminho, contexto, saida) -> dict          PNG | pasta de quadros | folha PNG+JSON; grava
                                                            <x>_praticas.json e <x>_praticas.png
resultado = {id, titulo, severidade, passa (True/False/None = não se aplica ou só informa), medida, limite,
             onde: [[x, y], ...] no quadro ou [[x, y, quadro], ...] na sequência, nota?}

contexto (tudo opcional):
  protegidas: [hex]   cores que podem ser 1 px (olho, brilho, emissivo); fora de ruído/detalhe/pedaço solto
  contorno: hex       cor do contorno (sem ela: a escura mais comum na borda)
  paleta: [hex]       paleta aprovada (BP13)
  chao: hex           chão do jogo para o contraste (padrão #68a057)
  perfil: '16'|'32'|'64'  (padrão: pela altura da figura)
  altura_alvo: int    (BP50)
  acao: idle|andar|correr|ataque|dano|morte   loop: bool   duracoes: [ms]
  render3d: bool      render 3D (Blender): BP40/BP41 só informam (o bob do corpo mexe tudo)
  limites: {"BP12": 24, ...}  troca o limite de uma regra
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

from . import paleta_ops
from .motor import comum as C
from .motor import medir as M
from .sequencia import validar as V
from .sequencia.registro import caixa

ARQ_REGRAS = Path(__file__).with_name("boas_praticas.json")
CHAO_PADRAO = "#68a057"
ESCURO_L = 0.56           # mesmo corte do anel1_escuro do portão (medir.py)
ACOES_PES = {None, "idle", "andar", "correr", "walk", "run"}
ACOES_ANDAR = {"andar", "correr", "walk", "run"}
LOOP_PADRAO = {"idle", "andar", "correr", "walk", "run", "ambiente"}
COR_GRAVE, COR_LEVE = (255, 40, 40, 255), (255, 210, 0, 255)
MAX_ONDE = 400


@lru_cache(maxsize=1)
def regras() -> dict[str, dict]:
    d = json.loads(ARQ_REGRAS.read_text(encoding="utf-8"))
    return {r["id"]: r for r in d["regras"]}


def automaticas() -> list[str]:
    return [i for i, r in regras().items() if r.get("metrica")]


# ---------------------------------------------------------------- contexto e utilidades

def _rgb(h) -> tuple[int, int, int]:
    return tuple(C.hex2rgb(h)) if isinstance(h, str) else tuple(int(v) for v in h[:3])


def _ctx(contexto: dict | None) -> dict:
    c = dict(contexto or {})
    c["_prot"] = [_rgb(h) for h in c.get("protegidas") or []]
    c["_paleta"] = {_rgb(h) for h in c["paleta"]} if c.get("paleta") else None
    c["_chao"] = _rgb(c.get("chao") or CHAO_PADRAO)
    c["_lim"] = c.get("limites") or {}
    return c


def _limite(rid: str, c: dict, perfil: str | None = None):
    lim = c["_lim"].get(rid, regras()[rid]["limite"])
    if isinstance(lim, dict) and perfil in lim:
        return lim[perfil]
    return lim


def _res(rid: str, passa, medida, limite, onde=None, nota: str | None = None) -> dict:
    r = regras()[rid]
    out = {"id": rid, "titulo": r["titulo"], "severidade": r["severidade"],
           "passa": None if passa is None else bool(passa), "medida": medida, "limite": limite,
           "onde": [list(map(int, p)) for p in (onde or [])][:MAX_ONDE]}
    if nota:
        out["nota"] = nota
    return out


def _pts(mask: np.ndarray) -> list[tuple[int, int]]:
    ys, xs = np.nonzero(mask)
    return list(zip(xs.tolist(), ys.tolist()))


def _desl(m: np.ndarray, dy: int, dx: int) -> np.ndarray:
    """m deslocada: out[y, x] = m[y + dy, x + dx] (fora = False)."""
    h, w = m.shape
    out = np.zeros_like(m)
    ys, yd = slice(max(0, dy), min(h, h + dy)), slice(max(0, -dy), min(h, h - dy))
    xs, xd = slice(max(0, dx), min(w, w + dx)), slice(max(0, -dx), min(w, w - dx))
    out[yd, xd] = m[ys, xs]
    return out


def _cor_mask(rgb: np.ndarray, op: np.ndarray, cores) -> np.ndarray:
    m = np.zeros(op.shape, bool)
    for c in cores:
        m |= op & np.all(rgb == np.array(c), axis=-1)
    return m


def _cor_contorno(rgb, L, r1, c) -> tuple | None:
    if c.get("contorno"):
        return _rgb(c["contorno"])
    esc = r1 & (L < ESCURO_L)
    base = esc if esc.any() else r1
    if not base.any():
        return None
    cores, n = np.unique(rgb[base].reshape(-1, 3), axis=0, return_counts=True)
    return tuple(int(v) for v in cores[int(np.argmax(n))])


def _cotovelos(O: np.ndarray) -> np.ndarray:
    """Contorno com 'L' num degrau (pixel duplo fora da quina; lógica do pixelart-review/find_doubles): vizinho na
    horizontal e na vertical, diagonal vazia e um dos braços com só 1 px."""
    out = np.zeros_like(O)
    for hdx in (-1, 1):
        for vdy in (-1, 1):
            h1, v1 = _desl(O, 0, hdx), _desl(O, vdy, 0)
            diag = _desl(O, vdy, hdx)
            h2, v2 = _desl(O, 0, 2 * hdx), _desl(O, 2 * vdy, 0)
            out |= O & h1 & v1 & ~diag & (~h2 | ~v2)
    return out


def _sem_bloco2(m: np.ndarray) -> np.ndarray:
    """Pixels de m que não fazem parte de nenhum bloco 2×2 todo em m."""
    ini = m & _desl(m, 0, 1) & _desl(m, 1, 0) & _desl(m, 1, 1)
    coberto = ini | _desl(ini, 0, -1) | _desl(ini, -1, 0) | _desl(ini, -1, -1)
    return m & ~coberto


# ---------------------------------------------------------------- quadro

def checar_quadro(rgba: np.ndarray, contexto: dict | None = None) -> list[dict]:
    """Mede todas as regras automáticas de quadro (BP03–BP26, BP29, BP50) num RGBA no tamanho final."""
    c = _ctx(contexto)
    f = np.asarray(rgba, np.uint8)
    rgb, a = f[..., :3], f[..., 3]
    op = a == 255
    vis = a > 0
    out: list[dict] = []
    if not op.any():
        return [_res("BP04", False, "vazio", 0, nota="quadro sem pixel opaco")]
    L = C.oklab(rgb)[0]
    area = int(op.sum())
    ys, xs = np.nonzero(op)
    altura = int(ys.max() - ys.min() + 1)
    perfil = str(c.get("perfil") or C.perfil_por_altura(altura))
    pf = M.PERFIS.get(perfil, {})
    r1, r2 = M.aneis(op, 2)
    prot = _cor_mask(rgb, op, c["_prot"])
    oc = _cor_contorno(rgb, L, r1, c)
    e_oc = _cor_mask(rgb, op, [oc]) if oc else np.zeros_like(op)

    # BP03 forma de primitivas
    lim = _limite("BP03", c, perfil)
    rmin = pf.get("reta_min", M.RETA_MIN)
    fr, reto = M.retas_silhueta(op, rmin) if rmin else (0.0, np.zeros_like(op))
    out.append(_res("BP03", fr <= lim, round(fr, 3), lim, _pts(reto), nota=f"perfil {perfil}"))

    # BP04 na borda do quadro
    moldura = np.zeros_like(op)
    moldura[0, :] = moldura[-1, :] = moldura[:, 0] = moldura[:, -1] = True
    nb = vis & moldura
    out.append(_res("BP04", int(nb.sum()) <= _limite("BP04", c), int(nb.sum()), _limite("BP04", c), _pts(nb)))

    # BP05 pedaços soltos (fora o maior; cores protegidas não contam)
    lab, n = ndimage.label(op & ~prot, structure=np.ones((3, 3), bool))
    soltos_m = np.zeros_like(op)
    if n > 1:
        tam = np.bincount(lab.ravel())
        tam[0] = 0
        maior = int(np.argmax(tam))
        for k in range(1, n + 1):
            if k != maior and tam[k] >= 3:
                soltos_m |= lab == k
    npz = int(ndimage.label(soltos_m, structure=np.ones((3, 3), bool))[1])
    out.append(_res("BP05", npz <= _limite("BP05", c), npz, _limite("BP05", c), _pts(soltos_m)))

    # BP07 contorno fechado / BP08 duplo / BP09 cotovelo / BP10 preto puro
    escuro_r1 = r1 & (e_oc | (L < ESCURO_L))
    fech = float(escuro_r1.sum() / max(r1.sum(), 1))
    lim = _limite("BP07", c)
    out.append(_res("BP07", fech >= lim, round(fech, 3), lim, _pts(r1 & ~escuro_r1),
                    nota=f"contorno {C.rgb2hex(oc) if oc else 'nenhum'}"))
    dup_m = r2 & e_oc
    dup = float(dup_m.sum() / max(r2.sum(), 1))
    lim = _limite("BP08", c)
    out.append(_res("BP08", dup <= lim, round(dup, 3), lim, _pts(dup_m)))
    cot = _cotovelos(e_oc)
    lim = max(2, round(_limite("BP09", c) * max(int(e_oc.sum()), 1)))
    out.append(_res("BP09", int(cot.sum()) <= lim, int(cot.sum()), lim, _pts(cot)))
    preto = op & np.all(rgb == 0, axis=-1)
    out.append(_res("BP10", int(preto.sum()) <= _limite("BP10", c), int(preto.sum()), _limite("BP10", c),
                    _pts(preto)))

    # BP12 cores / BP13 paleta / BP15 alfa
    cores = np.unique(rgb[vis].reshape(-1, 3), axis=0)
    lim = _limite("BP12", c)
    out.append(_res("BP12", len(cores) <= lim, int(len(cores)), lim))
    if c["_paleta"] is not None:
        dentro = _cor_mask(rgb, vis, c["_paleta"])
        fora = vis & ~dentro
        out.append(_res("BP13", int(fora.sum()) <= _limite("BP13", c), int(fora.sum()), _limite("BP13", c),
                        _pts(fora)))
    else:
        out.append(_res("BP13", None, None, _limite("BP13", c), nota="sem paleta no contexto"))
    semi = (a > 0) & (a < 255)
    out.append(_res("BP15", int(semi.sum()) <= _limite("BP15", c), int(semi.sum()), _limite("BP15", c), _pts(semi)))

    # BP14 / BP16 / BP17 / BP21 pela análise de paleta (paleta_ops.analisar); muitas cores = não mede
    if 1 < len(cores) <= 64:
        an = paleta_ops.analisar(imagem=f)
        q = an["quase_iguais"]
        onde = []
        for p in q:
            onde += _pts(_cor_mask(rgb, vis, [_rgb(p["b"])]))
        out.append(_res("BP14", len(q) <= _limite("BP14", c), len(q), _limite("BP14", c), onde,
                        nota=", ".join(f"{p['a']}~{p['b']}" for p in q[:6]) or None))
        maxr = max((len(r["cores"]) for r in an["rampas"]), default=1)
        out.append(_res("BP16", maxr <= _limite("BP16", c), maxr, _limite("BP16", c)))
        planas = [r for r in an["rampas"] if not r["neutra"] and r["giro_matiz"] < 5]
        out.append(_res("BP17", len(planas) <= _limite("BP17", c), len(planas), _limite("BP17", c)))
        fx = round(an["contraste"]["L_max"] - an["contraste"]["L_min"], 3)
        out.append(_res("BP21", fx >= _limite("BP21", c), fx, _limite("BP21", c)))
    else:
        for rid in ("BP14", "BP16", "BP17", "BP21"):
            out.append(_res(rid, None, None, _limite(rid, c), nota=f"{len(cores)} cores: reduza antes de medir"))

    # BP19 luz de cima-esquerda
    preench = op & ~e_oc & ~prot
    lim = _limite("BP19", c)
    pys, pxs = np.nonzero(preench)
    if len(pxs) > 20 and np.std(L[preench]) > 1e-6 and np.std(pxs) > 0 and np.std(pys) > 0:
        lx = float(np.corrcoef(pxs, L[preench])[0, 1])
        ly = float(np.corrcoef(pys, L[preench])[0, 1])
        out.append(_res("BP19", ly < lim["y_max"] and lx <= lim["x_max"], {"x": round(lx, 3), "y": round(ly, 3)},
                        lim))
    else:
        out.append(_res("BP19", None, None, lim, nota="preenchimento pequeno ou chapado"))

    # BP20 contraste com o chão (borda externa)
    Lc = float(C.oklab(np.array([c["_chao"]], np.uint8))[0][0])
    baixo = r1 & (np.abs(L - Lc) < 0.12)
    fc = float(1 - baixo.sum() / max(r1.sum(), 1))
    lim = _limite("BP20", c)
    out.append(_res("BP20", fc >= lim, round(fc, 3), lim, _pts(baixo), nota=f"chão {C.rgb2hex(c['_chao'])}"))

    # BP24 pixel solto / BP25 ruído / BP26 detalhe < 2×2
    viz = _desl(op, 0, 1) | _desl(op, 0, -1) | _desl(op, 1, 0) | _desl(op, -1, 0)
    solto = op & ~viz
    out.append(_res("BP24", int(solto.sum()) <= _limite("BP24", c), int(solto.sum()), _limite("BP24", c),
                    _pts(solto)))
    ruido, _iso8 = C.isolados8(f, excluir=prot | e_oc)
    ruido &= ~solto
    lim = max(2, round(_limite("BP25", c) * area))
    out.append(_res("BP25", int(ruido.sum()) <= lim, int(ruido.sum()), lim, _pts(ruido)))
    miolo = op & ~r1 & ~e_oc & ~prot & ~ruido & ~solto
    fino = np.zeros_like(op)
    for cor in np.unique(rgb[miolo].reshape(-1, 3), axis=0):
        m = miolo & np.all(rgb == cor, axis=-1)
        lab, n = ndimage.label(m)
        if not n:
            continue
        tam = np.bincount(lab.ravel())
        sem = _sem_bloco2(m)
        for k in np.nonzero((tam <= 4) & (np.arange(len(tam)) > 0))[0]:
            comp = lab == k
            if not (comp & ~sem).any():
                fino |= comp
    nfino = int(ndimage.label(fino)[1])
    lim = max(3, round(_limite("BP26", c) * area))
    out.append(_res("BP26", nfino <= lim, nfino, lim, _pts(fino)))

    # BP29 degraus irregulares
    pts = C.degraus_irregulares(op)
    lim = _limite("BP29", c, perfil)
    out.append(_res("BP29", len(pts) <= lim, len(pts), lim, pts))

    # BP50 altura no envelope
    if c.get("altura_alvo"):
        d = abs(altura - int(c["altura_alvo"]))
        out.append(_res("BP50", d <= _limite("BP50", c), altura, f"{c['altura_alvo']} ± {_limite('BP50', c)}"))
    else:
        out.append(_res("BP50", None, altura, _limite("BP50", c), nota="sem altura_alvo no contexto"))
    return out


# ---------------------------------------------------------------- animação

def _pisca_onde(quadros, ciclo=True, tam_max=2) -> list[tuple[int, int, int]]:
    """Posições do pisca solto (mesma regra de sequencia.validar.pisca_isolado)."""
    n, out = len(quadros), []
    for i in range(n):
        if not ciclo and (i == 0 or i == n - 1):
            continue
        a, b, c = quadros[i - 1], quadros[i], quadros[(i + 1) % n]
        op = (a[..., 3] == 255) & (b[..., 3] == 255) & (c[..., 3] == 255)
        m = op & np.all(a[..., :3] == c[..., :3], -1) & np.any(a[..., :3] != b[..., :3], -1)
        rot, k = ndimage.label(m, structure=np.ones((3, 3), int))
        if k:
            tam = np.bincount(rot.ravel())
            ys, xs = np.nonzero(m & (tam[rot] <= tam_max))
            out += [(int(x), int(y), i) for x, y in zip(xs, ys)]
    return out


def checar_animacao(quadros: list[np.ndarray], contexto: dict | None = None) -> list[dict]:
    """Regras de sequência (BP12 na sequência, BP31–BP41). Reusa sequencia.validar; onde = [x, y, quadro]."""
    c = _ctx(contexto)
    qs = [np.asarray(q, np.uint8) for q in quadros]
    acao = (c.get("acao") or None)
    acao = acao.lower() if isinstance(acao, str) else None
    loop = bool(c["loop"]) if "loop" in c else (acao in LOOP_PADRAO)
    r3d = bool(c.get("render3d"))
    out: list[dict] = []
    if len(qs) < 2:
        return [_res("BP31", None, len(qs), ">= 2 quadros", nota="um quadro só: use checar_quadro")]
    rel = V.validar(qs, sorted(C.rgb2hex(p) for p in c["_paleta"]) if c["_paleta"] else None, loop=loop,
                    limites={"altura_var": _limite("BP33", c), "pisca": _limite("BP35", c),
                             "loop_razao": _limite("BP37", c)})
    ch = {k["id"]: k for k in rel["checagens"]}

    def ok(*ids):
        presentes = [ch[i] for i in ids if i in ch]
        return (all(k["ok"] for k in presentes) if presentes else None), presentes

    p, ks = ok("V01", "V02")
    out.append(_res("BP31", p, {k["id"]: k["valor"] for k in ks}, 0))
    if "V04" in ch and not ch["V04"]["ok"] or "V01" in ch and not ch["V01"]["ok"]:
        return out

    # BP12 na sequência
    usadas = set()
    for q in qs:
        usadas |= {tuple(int(v) for v in x) for x in np.unique(q[q[..., 3] > 0][:, :3], axis=0)}
    out.append(_res("BP12", len(usadas) <= _limite("BP12", c), len(usadas), _limite("BP12", c),
                    nota="sequência inteira"))

    # BP32 linha dos pés
    caixas = [caixa(q) for q in qs]
    pes = np.array([b[3] for b in caixas])
    var = int(pes.max() - pes.min())
    med = int(np.median(pes))
    onde = []
    for i, (q, b) in enumerate(zip(qs, caixas)):
        if b[3] != med:
            onde += [(x, b[3], i) for x in np.nonzero(q[b[3], :, 3] >= 128)[0].tolist()]
    if acao in ACOES_PES:
        out.append(_res("BP32", var <= _limite("BP32", c), var, _limite("BP32", c), onde))
    else:
        out.append(_res("BP32", None, var, _limite("BP32", c), onde, nota=f"ação '{acao}': pé pode sair do chão"))

    for rid, vid in (("BP33", "V05"), ("BP34", "V06"), ("BP36", "V10"), ("BP39", "V13")):
        k = ch.get(vid)
        out.append(_res(rid, k["ok"] if k else None, k["valor"] if k else None,
                        k["limite"] if k else _limite(rid, c)))
    k = ch.get("V09")
    out.append(_res("BP35", k["ok"], k["valor"], k["limite"], _pisca_onde(qs, ciclo=loop)))
    k = ch.get("V11")
    out.append(_res("BP37", k["ok"] if k else None, k["valor"] if k else None, _limite("BP37", c),
                    nota=None if k else "sem loop (ação não cíclica ou < 3 quadros)"))
    p, ks = ok("V12", "V12b")
    out.append(_res("BP38", p, {"silhueta": ch["V12"]["valor"], "cabeca": ch["V12b"]["valor"]},
                    _limite("BP38", c)))

    # BP40 mudança por quadro no andar (diretriz; render 3D só informa)
    lo, hi = _limite("BP40", c)
    difs = [round(V._dif(qs[i], qs[(i + 1) % len(qs)]), 3) for i in range(len(qs) - (0 if loop else 1))]
    if acao in ACOES_ANDAR:
        fora = [i for i, d in enumerate(difs) if not lo <= d <= hi]
        out.append(_res("BP40", None if r3d else not fora, difs, [lo, hi],
                        nota="render 3D: só informa (o bob mexe o corpo todo)" if r3d else
                        (f"pares fora: {fora}" if fora else None)))
    else:
        out.append(_res("BP40", None, difs, [lo, hi], nota="só vale para andar/correr"))

    # BP41 quadros e tempo no envelope
    env = _limite("BP41", c)
    n = len(qs)
    problemas = []
    if acao in env:
        a0, a1 = env[acao]
        if not a0 <= n <= a1:
            problemas.append(f"{n} quadros (envelope {a0}–{a1})")
    dur = c.get("duracoes") or []
    ms0, ms1 = env["ms"]
    fora_ms = [d for d in dur if not ms0 <= d <= ms1]
    if fora_ms:
        problemas.append(f"durações fora de {ms0}–{ms1} ms: {fora_ms[:6]}")
    aplica = acao in env or bool(dur)
    out.append(_res("BP41", None if (r3d or not aplica) else not problemas,
                    {"quadros": n, "acao": acao, "ms": dur[:12]}, env if aplica else None,
                    nota="; ".join(problemas) or ("render 3D: só informa" if r3d else
                                                  (None if aplica else "sem ação nem durações no contexto"))))
    return out


# ---------------------------------------------------------------- direções

FRENTE, LADO = ("s", "frente", "sul"), ("e", "w", "l", "o", "lado", "leste", "oeste")


def checar_direcoes(vistas: dict, contexto: dict | None = None) -> list[dict]:
    """BP45–BP47 entre vistas do mesmo estado ({'s': rgba, 'n': rgba, 'e': rgba}; mesmo canvas)."""
    c = _ctx(contexto)
    vs = {k.lower(): np.asarray(v, np.uint8) for k, v in vistas.items()}
    if len(vs) < 2:
        return [_res("BP45", None, len(vs), ">= 2 vistas")]
    ref = next((k for k in FRENTE if k in vs), next(iter(vs)))
    cx = {k: caixa(v) for k, v in vs.items()}
    alt = {k: b[3] - b[1] + 1 for k, b in cx.items() if b}
    pe = {k: b[3] for k, b in cx.items() if b}
    d = max(max(alt.values()) - min(alt.values()), max(pe.values()) - min(pe.values()))
    out = [_res("BP45", d <= _limite("BP45", c), {"altura": alt, "pe": pe}, _limite("BP45", c))]

    def cores(v):
        return {tuple(int(x) for x in p) for p in np.unique(v[v[..., 3] > 0][:, :3], axis=0)}
    c0 = cores(vs[ref])
    novas = {k: len(cores(v) - c0) for k, v in vs.items() if k != ref}
    out.append(_res("BP46", max(novas.values()) <= _limite("BP46", c), novas, _limite("BP46", c),
                    nota=f"referência '{ref}'"))
    lado = next((k for k in LADO if k in vs), None)
    if lado and ref in FRENTE:
        r = round(float((vs[lado][..., 3] == 255).sum() / max((vs[ref][..., 3] == 255).sum(), 1)), 3)
        lo, hi = _limite("BP47", c)
        out.append(_res("BP47", lo <= r <= hi, r, [lo, hi]))
    else:
        out.append(_res("BP47", None, None, _limite("BP47", c), nota="falta a vista de frente (s) ou de lado (e/w)"))
    return out


# ---------------------------------------------------------------- overlay e resumo

def falhas(resultados: list[dict]) -> list[dict]:
    return [r for r in resultados if r["passa"] is False]


def resumo(resultados: list[dict]) -> str:
    f = falhas(resultados)
    g = sum(1 for r in f if r["severidade"] == "grave")
    cab = f"{'REPROVA' if g else 'PASSA'} · {g} graves · {len(f) - g} leves · {len(resultados)} regras medidas"
    return "\n".join([cab] + [f"{r['severidade']} {r['id']} {r['titulo']}: {r['medida']} (limite {r['limite']})"
                              for r in sorted(f, key=lambda r: r["severidade"] != "grave")])


def _resumo_seq(anim: list[dict], por_quadro: list[list[dict]]) -> str:
    """Resumo de uma folha: falhas de sequência + falhas de quadro agrupadas por regra (quadros e pior medida)."""
    agg: dict[str, list] = {}
    for i, rs in enumerate(por_quadro):
        for r in falhas(rs):
            a = agg.setdefault(r["id"], [r, [], []])
            a[1].append(i)
            a[2].append(r["medida"])
    fa = falhas(anim)
    g = sum(1 for r in fa if r["severidade"] == "grave") + sum(1 for r, _, _ in agg.values()
                                                              if r["severidade"] == "grave")
    linhas = [f"{'REPROVA' if g else 'PASSA'} · {len(por_quadro)} quadros · {g} regras graves falhando"]
    linhas += [f"{r['severidade']} {r['id']} {r['titulo']}: {r['medida']} (limite {r['limite']})" for r in fa]
    for r, qs, med in sorted(agg.values(), key=lambda a: a[0]["severidade"] != "grave"):
        pior = max(med, key=lambda m: m if isinstance(m, (int, float)) else 0)
        linhas.append(f"{r['severidade']} {r['id']} {r['titulo']}: quadros {qs[:10]}, pior {pior} "
                      f"(limite {r['limite']})")
    return "\n".join(linhas)


def _legenda(img: Image.Image, linhas: list[tuple[str, tuple]]) -> Image.Image:
    if not linhas:
        return img
    fonte = C.fonte(12)
    alt = 16 * len(linhas) + 6
    out = Image.new("RGBA", (max(img.width, 360), img.height + alt), (24, 24, 32, 255))
    out.alpha_composite(img, (0, 0))
    d = ImageDraw.Draw(out)
    for i, (t, cor) in enumerate(linhas):
        d.text((6, img.height + 3 + 16 * i), t, fill=cor, font=fonte)
    return out


def _base(rgba: np.ndarray, escala: int, chao) -> Image.Image:
    im = Image.fromarray(np.asarray(rgba, np.uint8), "RGBA")
    big = im.resize((im.width * escala, im.height * escala), Image.NEAREST)
    bg = Image.new("RGBA", big.size, (*_rgb(chao or CHAO_PADRAO), 255))
    bg.alpha_composite(big)
    return bg


def _marcar(d: ImageDraw.ImageDraw, pts, escala, cor, ox=0, oy=0):
    w = max(1, escala // 4)
    for p in pts:
        x, y = p[0], p[1]
        d.rectangle([ox + x * escala, oy + y * escala, ox + (x + 1) * escala - 1, oy + (y + 1) * escala - 1],
                    outline=cor, width=w)


def overlay(rgba: np.ndarray, resultados: list[dict], escala: int = 8, chao: str | None = None) -> Image.Image:
    """Quadro ampliado (vizinho mais próximo) sobre o chão, com cada pixel de regra que falhou marcado (vermelho =
    grave, amarelo = leve) e a legenda das falhas embaixo."""
    img = _base(rgba, escala, chao)
    d = ImageDraw.Draw(img)
    f = sorted(falhas(resultados), key=lambda r: r["severidade"] == "grave")   # grave por cima
    for r in f:
        _marcar(d, r["onde"], escala, COR_GRAVE if r["severidade"] == "grave" else COR_LEVE)
    return _legenda(img, [(f"{r['id']} {r['titulo'][:48]}: {r['medida']} (lim {r['limite']})",
                           COR_GRAVE if r["severidade"] == "grave" else COR_LEVE) for r in f[::-1]])


def overlay_sequencia(quadros: list[np.ndarray], por_quadro: list[list[dict]], anim: list[dict],
                      escala: int = 6, chao: str | None = None) -> Image.Image:
    """Quadros lado a lado, cada um com as marcas das próprias falhas e das falhas de sequência daquele quadro."""
    H, W = quadros[0].shape[:2]
    gap = 4
    img = Image.new("RGBA", (len(quadros) * (W * escala + gap), H * escala), (24, 24, 32, 255))
    d = ImageDraw.Draw(img)
    fa = falhas(anim)
    for i, q in enumerate(quadros):
        ox = i * (W * escala + gap)
        img.alpha_composite(_base(q, escala, chao), (ox, 0))
        for r in sorted(falhas(por_quadro[i]) if i < len(por_quadro) else [],
                        key=lambda r: r["severidade"] == "grave"):
            _marcar(d, r["onde"], escala, COR_GRAVE if r["severidade"] == "grave" else COR_LEVE, ox)
        for r in fa:
            _marcar(d, [p for p in r["onde"] if len(p) > 2 and p[2] == i], escala,
                    COR_GRAVE if r["severidade"] == "grave" else COR_LEVE, ox)
    linhas = {}
    for i, rs in enumerate(por_quadro):
        for r in falhas(rs):
            linhas.setdefault(r["id"], [r, []])[1].append(i)
    leg = [(f"{r['id']} {r['titulo'][:44]} (quadros {qs[:8]})", COR_GRAVE if r["severidade"] == "grave"
            else COR_LEVE) for r, qs in linhas.values()]
    leg += [(f"{r['id']} {r['titulo'][:44]}: {r['medida']} (lim {r['limite']})",
             COR_GRAVE if r["severidade"] == "grave" else COR_LEVE) for r in fa]
    return _legenda(img, leg)


# ---------------------------------------------------------------- arquivos

def carregar(caminho) -> tuple[list[np.ndarray], list[int], list[tuple[str, int, int]]]:
    """PNG solto (1 quadro) | pasta de PNGs (quadros em ordem de nome) | folha PNG+JSON do Aseprite/SpriteKiln
    (o .json, ou o .png com um .json de mesmo nome ao lado). Devolve (quadros, durações ms, tags)."""
    p = Path(caminho)
    if not p.exists():
        raise ValueError(f"não encontrado: {p}")
    if p.is_dir():
        from .sequencia.entradas import de_pasta
        qs = de_pasta(p)
        return qs, [], [("quadros", 0, len(qs) - 1)]
    js = p if p.suffix.lower() == ".json" else p.with_suffix(".json")
    if js.is_file():
        from . import kiln
        at = kiln.ler_atlas(js)
        return [q.copy() for q in at.quadros], list(at.duracoes_ms), list(at.tags)
    q = np.array(Image.open(p).convert("RGBA"))
    return [q], [], [("quadro", 0, 0)]


def _acao_da_tag(nome: str) -> str | None:
    base = nome.lower().rpartition("_")[0] or nome.lower()
    for k, v in (("idle", "idle"), ("walk", "andar"), ("andar", "andar"), ("run", "correr"), ("corr", "correr"),
                 ("attack", "ataque"), ("ataq", "ataque"), ("hit", "dano"), ("dano", "dano"), ("hurt", "dano"),
                 ("death", "morte"), ("die", "morte"), ("morte", "morte")):
        if base.startswith(k):
            return v
    return None


def checar_caminho(caminho, contexto: dict | None = None, saida=None, escala: int | None = None) -> dict:
    """Checa um PNG, uma pasta de quadros ou uma folha PNG+JSON e grava <x>_praticas.json e <x>_praticas.png
    (em 'saida', ou ao lado da entrada). Uma tag por sequência na folha (a ação vem do nome da tag se o contexto
    não disser). Devolve {entrada, json, png, aprovado, graves, leves, quadros, sequencias, resumo}."""
    p = Path(caminho)
    qs, dur, tags = carregar(p)
    ctx = dict(contexto or {})
    por_quadro = [checar_quadro(q, ctx) for q in qs]
    seqs = []
    if len(qs) > 1:
        for nome, de, ate in tags:
            sub = qs[de:ate + 1]
            if len(sub) < 2:
                continue
            c2 = dict(ctx)
            c2.setdefault("acao", _acao_da_tag(nome))
            if dur and "duracoes" not in ctx:
                c2["duracoes"] = dur[de:ate + 1]
            r = checar_animacao(sub, c2)
            for x in r:   # índice do quadro na folha inteira
                x["onde"] = [[o[0], o[1], o[2] + de] if len(o) > 2 else o for o in x["onde"]]
            seqs.append({"tag": nome, "de": de, "ate": ate, "acao": c2.get("acao"), "resultados": r})
    todas = [r for rs in por_quadro for r in rs] + [r for s in seqs for r in s["resultados"]]
    f = falhas(todas)
    graves = sorted({r["id"] for r in f if r["severidade"] == "grave"})
    leves = sorted({r["id"] for r in f if r["severidade"] == "leve"} - set(graves))
    base = p.stem if p.is_file() else p.name
    pasta = Path(saida) if saida else (p.parent if p.is_file() else p)
    pasta.mkdir(parents=True, exist_ok=True)
    jp, pp = pasta / f"{base}_praticas.json", pasta / f"{base}_praticas.png"
    if len(qs) == 1:
        img = overlay(qs[0], por_quadro[0], escala or 8, ctx.get("chao"))
        txt = resumo(por_quadro[0])
    else:
        anim = [r for s in seqs for r in s["resultados"]]
        img = overlay_sequencia(qs, por_quadro, anim, escala or max(2, min(6, 1600 // max(1, len(qs) *
                                                                                          qs[0].shape[1]))),
                                ctx.get("chao"))
        txt = _resumo_seq(anim, por_quadro)
    img.save(pp)
    rel = {"entrada": str(p), "json": str(jp), "png": str(pp), "aprovado": not graves, "graves": graves,
           "leves": leves, "quadros": por_quadro, "sequencias": seqs, "resumo": txt,
           "regras_de_olho": [i for i, r in regras().items() if not r.get("metrica")]}
    jp.write_text(json.dumps(rel, ensure_ascii=False, indent=1), encoding="utf-8")
    return rel
