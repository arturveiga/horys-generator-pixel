"""Mapa de partes de uma vista (cor por parte), checagem de forma fechada e animação por tabela de deslocamento.

perfeicao.md, seção 13, itens C2 e C9/C11. O mapa de partes é um PNG do mesmo tamanho da vista em que cada cor
opaca é uma parte. As cores seguem o contrato de `art-src/motion-rigs/README.md` (o mesmo dos rigs de movimento e
do guia de pose do SpriteKiln), então um mapa feito aqui, um render de proxy e um rig GIF falam a mesma língua.

- `mapa_auto`: primeiro rascunho do mapa de uma vista humanoide (cabeça, tronco, braços, pernas) por perfil de
  largura e vãos. É só rascunho: o agente ou o Artur corrigem no Aseprite e a `checar` diz se ficou fechado.
- `checar`: cobertura (todo pixel da figura tem parte, nenhuma parte fora da figura), uma peça só por parte, sem
  buraco e as junções do contrato encostadas.
- `animar`: a vista vira quadros deslocando partes por uma tabela (dx, dy por parte por quadro). Regras do
  sprite-forge (MIT): o que não mexe fica idêntico; nunca abrir emenda (o vão deixado por uma parte que saiu é
  preenchido com a parte vizinha que estava encostada, nunca com cor inventada); o cabelo/chifre segue a cabeça com
  1 quadro de atraso quando pedido.

Só lógica pura (numpy). Não cria forma.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage

# contrato de cores (art-src/motion-rigs/README.md)
CORES = {
    "cabeca": (0, 255, 255),          # ciano
    "tronco": (255, 140, 0),          # laranja
    "braco-esq": (0, 200, 0),         # verde (braço do lado esquerdo da IMAGEM)
    "braco-dir": (160, 0, 255),       # roxo
    "perna-esq": (255, 230, 0),       # amarelo
    "perna-dir": (255, 0, 0),         # vermelho
    "arma": (255, 0, 160),            # rosa
    "enfeite": (255, 255, 255),       # branco: chifre, cabelo, capa (segue a cabeça com atraso opcional)
}
NOMES = list(CORES)
# ordem de pintura de baixo para cima (o último fica por cima)
ORDEM_PADRAO = ["perna-esq", "perna-dir", "braco-esq", "tronco", "braco-dir", "cabeca", "enfeite", "arma"]
JUNCOES = [("cabeca", "tronco"), ("braco-esq", "tronco"), ("braco-dir", "tronco"), ("perna-esq", "tronco"),
           ("perna-dir", "tronco"), ("enfeite", "cabeca")]


def rotulos(mapa_rgba: np.ndarray, tol: int = 40) -> np.ndarray:
    """PNG de partes -> rótulos inteiros (0 = vazio, i+1 = NOMES[i]). Cor fora do contrato = -1."""
    op = mapa_rgba[..., 3] > 0
    rgb = mapa_rgba[..., :3].astype(int)
    out = np.where(op, -1, 0)
    for i, n in enumerate(NOMES, 1):
        d = np.abs(rgb - np.array(CORES[n])).sum(-1)
        out[op & (d <= tol)] = i
    return out


def pintar(rot: np.ndarray) -> np.ndarray:
    out = np.zeros(rot.shape + (4,), np.uint8)
    for i, n in enumerate(NOMES, 1):
        m = rot == i
        out[m, :3] = CORES[n]
        out[m, 3] = 255
    out[rot == -1] = (128, 128, 128, 255)
    return out


def _id(nome: str) -> int:
    return NOMES.index(nome) + 1


# ------------------------------------------------------------------ rascunho automático


def _runs(linha: np.ndarray) -> list[tuple[int, int]]:
    d = np.diff(np.concatenate([[0], linha.astype(int), [0]]))
    return list(zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]))


def mapa_auto(vista: np.ndarray, *, lado: bool = False, cabeca_frac: float | None = None,
              enfeite_topo: int = 0) -> np.ndarray:
    """Rascunho do mapa de partes de uma vista humanoide (RGBA 1x, figura recortada ou não).

    cabeça: do topo até o pescoço (menor largura entre 25% e 55% da altura; sem pescoço visível, `cabeca_frac`
    ou 42%). pernas: abaixo da virilha (linha mais baixa em que o miolo da figura fica vazio entre duas pernas);
    vista de lado (`lado`) sem vão = uma perna só ('perna-esq'). braços: na faixa do tronco, as tiras separadas da
    tira central, ou o que passa da largura do quadril. enfeite_topo: linhas do topo que são chifre/cabelo/antena.
    """
    m = vista[..., 3] > 0
    rot = np.zeros(m.shape, int)
    if not m.any():
        return rot
    ys, xs = np.nonzero(m)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    H = y1 - y0
    larg = m[y0:y1].sum(1)

    # pescoço
    a, b = y0 + int(0.25 * H), y0 + int(0.55 * H)
    if cabeca_frac is not None:
        pescoco = y0 + int(round(cabeca_frac * H))
    else:
        faixa = larg[a - y0:b - y0]
        k = int(np.argmin(faixa)) if len(faixa) else 0
        # só vale como pescoço se for bem mais estreito que a cabeça acima
        if len(faixa) and faixa[k] < 0.8 * larg[:a - y0 + k].max():
            pescoco = a + k
        else:
            pescoco = y0 + int(round(0.42 * H))

    # virilha: de baixo para cima, enquanto a linha tem vão no miolo entre duas tiras
    cx = (x0 + x1) / 2
    virilha = y1
    for y in range(y1 - 1, pescoco, -1):
        runs = [(s, e) for s, e in _runs(m[y]) if e - s >= 1]
        esq = any(e <= cx + 0.5 for s, e in runs)
        dirr = any(s >= cx - 0.5 for s, e in runs)
        tem_vao = len(runs) >= 2 and esq and dirr and not any(s < cx - 0.5 < e and s < cx + 0.5 < e for s, e in runs)
        if tem_vao:
            virilha = y
        elif virilha < y1 and y < virilha - 0:
            break
    if virilha >= y1 - 1:      # sem vão entre as pernas: pernas = 30% de baixo
        virilha = y0 + int(round(0.70 * H))

    rot[y0:pescoco][m[y0:pescoco]] = _id("cabeca")
    if enfeite_topo > 0:
        rot[y0:y0 + enfeite_topo][m[y0:y0 + enfeite_topo]] = _id("enfeite")

    # quadril: tiras na altura da virilha
    linha_q = m[max(virilha - 1, pescoco)]
    rq = _runs(linha_q)
    qx0 = min((s for s, e in rq), default=x0)
    qx1 = max((e for s, e in rq), default=x1)

    for y in range(pescoco, virilha):
        for s, e in _runs(m[y]):
            seg = np.arange(s, e)
            if e <= qx0 or s >= qx1:                 # tira solta fora do quadril = braço inteiro
                rot[y, s:e] = _id("braco-esq") if (s + e) / 2 < cx else _id("braco-dir")
                continue
            for x in seg:
                if x < qx0 - 0:
                    rot[y, x] = _id("braco-esq")
                elif x >= qx1:
                    rot[y, x] = _id("braco-dir")
                else:
                    rot[y, x] = _id("tronco")
    for y in range(virilha, y1):
        for s, e in _runs(m[y]):
            if lado:
                rot[y, s:e] = _id("perna-esq")
                continue
            for x in range(s, e):
                if x < qx0 or x >= qx1:              # mão que desce ao lado da perna
                    rot[y, x] = _id("braco-esq") if x < cx else _id("braco-dir")
                else:
                    rot[y, x] = _id("perna-esq") if x + 0.5 < cx else _id("perna-dir")
    rot[~m] = 0
    return rot


def mapa_regioes(vista: np.ndarray, regioes: list[dict], base: np.ndarray | None = None) -> np.ndarray:
    """Mapa por retângulos, aplicados em ordem (o seguinte sobrescreve), só onde há figura.

    regioes: [{"parte": "braco-esq", "rect": [x0, y0, x1, y1]}] com x1/y1 exclusivos. `base`: mapa de partida
    (ex.: o rascunho de mapa_auto) para corrigir só um trecho."""
    m = vista[..., 3] > 0
    rot = np.zeros(m.shape, int) if base is None else base.copy()
    for r in regioes:
        if r["parte"] not in CORES:
            raise ValueError(f"parte '{r['parte']}' fora do contrato ({', '.join(NOMES)})")
        x0, y0, x1, y1 = (int(v) for v in r["rect"])
        sel = np.zeros_like(m)
        sel[max(0, y0):y1, max(0, x0):x1] = True
        rot[sel & m] = _id(r["parte"])
    rot[~m] = 0
    return rot


# ------------------------------------------------------------------ checagem


@dataclass
class Checagem:
    ok: bool
    problemas: list = field(default_factory=list)
    partes: dict = field(default_factory=dict)       # nome -> {"pixels", "pecas", "buracos"}

    def como_dict(self) -> dict:
        return {"ok": self.ok, "problemas": self.problemas, "partes": self.partes}


def checar(vista: np.ndarray, rot: np.ndarray, *, juncoes=JUNCOES, pecas_max: dict | None = None,
           buraco_max: int = 2) -> Checagem:
    """Forma fechada por parte: cobertura exata, 1 peça por parte, sem buraco (> buraco_max px), junções encostadas."""
    if vista.shape[:2] != rot.shape:
        return Checagem(False, [f"mapa {rot.shape[::-1]} e vista {vista.shape[1::-1]} de tamanhos diferentes"])
    pecas_max = {"enfeite": 4, "arma": 2, **(pecas_max or {})}
    fig = vista[..., 3] > 0
    probs = []
    sem = fig & (rot == 0)
    if sem.any():
        probs.append(f"{int(sem.sum())} px da figura sem parte (ex.: {_ex(sem)})")
    fora = ~fig & (rot != 0)
    if fora.any():
        probs.append(f"{int(fora.sum())} px de parte fora da figura (ex.: {_ex(fora)})")
    estranho = rot == -1
    if estranho.any():
        probs.append(f"{int(estranho.sum())} px com cor fora do contrato (ex.: {_ex(estranho)})")
    info = {}
    oito = np.ones((3, 3), int)
    for i, n in enumerate(NOMES, 1):
        p = rot == i
        if not p.any():
            continue
        _, k = ndimage.label(p, structure=oito)
        cheio = ndimage.binary_fill_holes(p)
        buracos = int((cheio & ~p & ~fig).sum())
        info[n] = {"pixels": int(p.sum()), "pecas": int(k), "buracos": buracos}
        if k > pecas_max.get(n, 1):
            probs.append(f"{n}: {k} pedaços soltos (máx {pecas_max.get(n, 1)}); junte ou mude de parte")
        if buracos > buraco_max:
            probs.append(f"{n}: buraco transparente de {buracos} px dentro da parte")
    cruz = ndimage.generate_binary_structure(2, 1)
    for a, b in juncoes:
        if a in info and b in info:
            if not (ndimage.binary_dilation(rot == _id(a), cruz) & (rot == _id(b))).any():
                probs.append(f"junção {a}-{b}: as partes não se encostam (emenda aberta)")
    return Checagem(not probs, probs, info)


def _ex(m: np.ndarray, n: int = 3) -> str:
    ys, xs = np.nonzero(m)
    return ", ".join(f"({x},{y})" for x, y in list(zip(xs, ys))[:n])


# ------------------------------------------------------------------ animar por tabela


def _desloc(a: np.ndarray, dx: int, dy: int) -> np.ndarray:
    out = np.zeros_like(a)
    h, w = a.shape[:2]
    out[max(0, dy):min(h, h + dy), max(0, dx):min(w, w + dx)] = \
        a[max(0, -dy):min(h, h - dy), max(0, -dx):min(w, w - dx)]
    return out


# tabelas padrão: {parte: [(dx, dy) por quadro]}. Pequenas de propósito (1 px a 32–48 px de altura).
TABELAS = {
    # idle de 4: respira (tronco+cabeça descem 1 px nos quadros 1-2), braços acompanham, enfeite 1 quadro atrasado
    "idle": {"n": 4, "ms": [220, 160, 220, 160], "partes": {
        "cabeca": [(0, 0), (0, 1), (0, 1), (0, 0)],
        "tronco": [(0, 0), (0, 1), (0, 1), (0, 0)],
        "braco-esq": [(0, 0), (0, 1), (0, 1), (0, 0)],
        "braco-dir": [(0, 0), (0, 1), (0, 1), (0, 0)],
        "arma": [(0, 0), (0, 1), (0, 1), (0, 0)],
        "enfeite": "atraso:cabeca"}},
    # andar de 4 visto de frente/costas: contato, passagem (sobe), contato oposto, passagem
    # andar de 4 visto de frente/costas: contato, passagem (a bota da perna que passa sobe 3 px e o corpo sobe
    # 1 px), contato oposto, passagem oposta; o punho oposto à perna que sobe balança 1-2 px. Amplitude revista
    # em 14/11 (robô v01: com 1 px "lê como tremor no lugar, não como passo").
    "andar-frente": {"n": 4, "ms": [140, 140, 140, 140], "partes": {
        "perna-esq": [(0, 0), (0, -3), (0, 0), (0, -1)],
        "perna-dir": [(0, 0), (0, -1), (0, 0), (0, -3)],
        "tronco": [(0, 1), (0, -1), (0, 1), (0, -1)],
        "cabeca": [(0, 1), (0, -1), (0, 1), (0, -1)],
        "braco-esq": [(0, 1), (0, -1), (0, 1), (0, -3)],
        "braco-dir": [(0, 1), (0, -3), (0, 1), (0, -1)],
        "arma": [(0, 1), (0, -3), (0, 1), (0, -1)],
        "enfeite": "atraso:cabeca"}},
    # andar de 4 de lado (olhando para a direita): pernas e braços em oposição, 1-2 px
    "andar-lado": {"n": 4, "ms": [140, 140, 140, 140], "partes": {
        "perna-esq": [(-2, 0), (0, -1), (2, 0), (0, 0)],
        "perna-dir": [(2, 0), (0, 0), (-2, 0), (0, -1)],
        "tronco": [(0, 0), (0, -1), (0, 0), (0, -1)],
        "cabeca": [(0, 0), (0, -1), (0, 0), (0, -1)],
        "braco-esq": [(1, 0), (0, -1), (-1, 0), (0, -1)],
        "braco-dir": [(-1, 0), (0, -1), (1, 0), (0, -1)],
        "arma": [(-1, 0), (0, -1), (1, 0), (0, -1)],
        "enfeite": "atraso:cabeca"}},
}


_PARES = {frozenset((_id(a), _id(b))) for a, b in JUNCOES}


def _tapar_emendas(q: np.ndarray, dono: np.ndarray, fig0: np.ndarray, i: int, avisos: list) -> np.ndarray:
    """Fecha só a emenda: vão de 1 px de espessura, dentro da figura do quadro 0, encostado em duas partes de uma
    junção. O pixel vazio recebe a cor do pixel opaco mais próximo (estica a parte, não inventa cor). Vão deixado
    por uma parte que andou (encosta numa parte só) é fundo de verdade e fica vazio."""
    vao = fig0 & (q[..., 3] == 0)
    if not vao.any():
        return q
    h, w = dono.shape
    pad = np.pad(dono, 1)
    viz = [pad[0:h, 1:w + 1], pad[2:h + 2, 1:w + 1], pad[1:h + 1, 0:w], pad[1:h + 1, 2:w + 2]]  # cima, baixo, esq, dir
    qpad = np.pad(q, ((1, 1), (1, 1), (0, 0)))
    qviz = [qpad[0:h, 1:w + 1], qpad[2:h + 2, 1:w + 1], qpad[1:h + 1, 0:w], qpad[1:h + 1, 2:w + 2]]
    out = q.copy()
    tapados = np.zeros(dono.shape, bool)
    for y, x in zip(*np.nonzero(vao)):
        ds = [int(v[y, x]) for v in viz]
        # par oposto (cima/baixo ou esq/dir) de uma junção: a emenda abriu entre as duas partes
        for a_, b_ in ((0, 1), (2, 3)):
            if ds[a_] and ds[b_] and ds[a_] != ds[b_] and frozenset((ds[a_], ds[b_])) in _PARES:
                out[y, x] = qviz[a_][y, x]           # estica a parte de cima / da esquerda
                tapados[y, x] = True
                break
    resto = vao & ~tapados
    if resto.any():
        cruz = ndimage.generate_binary_structure(2, 1)
        lbl, nv = ndimage.label(resto, cruz)
        for j in range(1, nv + 1):
            v = lbl == j
            borda = ndimage.binary_dilation(v, cruz) & ~v
            donos = {int(d) for d in np.unique(dono[borda]) if d > 0}
            if len(donos) >= 2 and ndimage.binary_erosion(v, cruz).any():
                avisos.append(f"q{i}: vão de {int(v.sum())} px entre partes perto de {_ex(v, 1)}: conferir à mão")
    return out


@dataclass
class Animado:
    quadros: list
    ms: list
    avisos: list


def animar(vista: np.ndarray, rot: np.ndarray, tabela: dict | str, *, ordem: list[str] | None = None,
           tapar: bool = True, folga: bool = True) -> Animado:
    """Quadros a partir de uma vista e do mapa dela, deslocando partes pela tabela.

    tapar: o vão que uma parte deixa ao sair (pixel que era figura no quadro 0, ficou vazio e encosta numa parte
    que ficou) é preenchido com a cor do vizinho dessa parte. Isso só fecha a emenda de 1 px; vão maior vira aviso
    (ali o agente limpa à mão, com leitura de volta).
    """
    t = TABELAS[tabela] if isinstance(tabela, str) else tabela
    n = int(t["n"])
    partes_t = dict(t["partes"])
    ordem = ordem or ORDEM_PADRAO
    # resolve "atraso:<parte>"
    for p, v in list(partes_t.items()):
        if isinstance(v, str) and v.startswith("atraso:"):
            ref = partes_t.get(v.split(":", 1)[1], [(0, 0)] * n)
            partes_t[p] = [ref[(i - 1) % n] for i in range(n)]
    quadros, avisos = [], []
    # folga: o canvas cresce o necessário para nenhuma parte sair da borda (antes a perna era cortada)
    desl = [abs(int(c)) for v in partes_t.values() for d in v for c in d]
    f = max(desl, default=0)
    if f and folga:
        vista = np.pad(vista, ((f, f), (f, f), (0, 0)))
        rot = np.pad(rot, f)
    fig0 = vista[..., 3] > 0
    for i in range(n):
        q = np.zeros_like(vista)
        dono = np.zeros(rot.shape, int)
        for nome in ordem:
            k = _id(nome)
            sel = rot == k
            if not sel.any():
                continue
            dx, dy = (partes_t.get(nome) or [(0, 0)] * n)[i]
            camada = _desloc(np.where(sel[..., None], vista, 0).astype(vista.dtype), int(dx), int(dy))
            mm = camada[..., 3] > 0
            q[mm] = camada[mm]
            dono[mm] = k
        if tapar:
            q = _tapar_emendas(q, dono, fig0, i, avisos)
        quadros.append(q)
    return Animado(quadros, list(t.get("ms") or [150] * n), avisos)
