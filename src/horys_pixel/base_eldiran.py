"""Corpo-base Eldiran 32x32 (CC0) para o fluxo Base + Pele (perfeicao.md, seção 2.15 e P3).

Decisão do Artur (14/11): "usa a base do eldiran". A folha da Eldiran é só ESQUELETO (corpo nu animado), não régua
de estilo.

Layout da folha `RPGCharacterSprites32x32.png` (384x672, conferido olhando o PNG):
- células de 32x32, 12 colunas x 21 linhas, fundo magenta opaco (#ff00ff);
- cada linha é um personagem; a LINHA 0 é o corpo nu;
- colunas 0-3 = andar de frente (s), 4-7 = andar de costas (n), 8-11 = andar de lado olhando para a direita (e);
- o oeste é o leste espelhado.
- Na linha 0 as colunas 4-7 (costas) estão VAZIAS. As costas do corpo nu são derivadas da frente (mesma silhueta,
  como nas outras linhas da folha) apagando o rosto: o miolo da cabeça vira a cor de enchimento. É limpeza
  mecânica, marcada como 'derivado' no base.json; o Artur confere.

Não há ação parada na folha: idle = o quadro de descanso do andar (pernas juntas, coluna 1 de cada direção).

`extrair(saida)` grava quadros 1x, base.png (3 vistas de descanso lado a lado, o formato que `pele.vestir` espera),
base.json e o mapa de partes de cada quadro (contrato `mapa_partes.CORES`), checado com `mapa_partes.checar`.
`animar_pele(base_dir, pele_png, saida)` leva a pele vestida em base.png para todos os quadros.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

from . import mapa_partes as M
from . import pele as P

FOLHA_PADRAO = Path(r"D:\godot\referencias\eldiran-32\RPGCharacterSprites32x32.png")
SAIDA_PADRAO = Path("art-src/base32/eldiran")
CELULA = 32
MARGEM = 4                      # margem transparente em volta de cada célula (chapéu, capa, arma)
CHAVE = (255, 0, 255)
LINHA_BASE = 0
COLUNAS = {"s": [0, 1, 2, 3], "n": [4, 5, 6, 7], "e": [8, 9, 10, 11]}
DIRS = ["s", "n", "e"]
DESCANSO = 1                    # índice do quadro de pernas juntas no andar de 4
ACOES = {"idle": {"quadros": [DESCANSO], "ms": [500]},
         "andar": {"quadros": [0, 1, 2, 3], "ms": [150, 150, 150, 150]}}
LICENCA = {"licenca": "CC0", "autor": "Eldiran",
           "procedencia": "pack 32x32 da Eldiran em D:\\godot\\referencias\\eldiran-32 (sem arquivo de licença na "
                          "pasta; CC0 registrado nas notas do projeto, perfeicao.md seção 2.15)"}


# ------------------------------------------------------------------ fatiar


def _celula(folha: np.ndarray, linha: int, col: int) -> np.ndarray:
    c = folha[linha * CELULA:(linha + 1) * CELULA, col * CELULA:(col + 1) * CELULA].copy()
    chave = (c[..., :3] == np.array(CHAVE)).all(-1)
    c[chave] = 0
    c[c[..., 3] == 0] = 0
    return c


def _pad(q: np.ndarray, m: int = MARGEM) -> np.ndarray:
    return np.pad(q, ((m, m), (m, m), (0, 0)))


def costas_de_frente(frente: np.ndarray) -> np.ndarray:
    """Costas a partir da frente: o miolo da cabeça (entre o contorno da esquerda e o da direita, das linhas abaixo
    do topo até o pescoço) vira a cor de enchimento mais comum. Só apaga rosto; não muda silhueta."""
    q = frente.copy()
    m = q[..., 3] > 0
    if not m.any():
        return q
    ys, _ = np.nonzero(m)
    y0, y1 = ys.min(), ys.max() + 1
    H = y1 - y0
    larg = m[y0:y1].sum(1)
    a, b = int(0.25 * H), int(0.55 * H)
    pescoco = y0 + a + int(np.argmin(larg[a:b]))
    op = q[m][:, :3]
    cores, n = np.unique(op, axis=0, return_counts=True)
    escuro = cores.sum(1) < 120
    enche = cores[~escuro][np.argmax(n[~escuro])] if (~escuro).any() else cores[np.argmax(n)]
    for y in range(y0 + 1, pescoco):
        xs = np.nonzero(m[y])[0]
        if len(xs) < 3:
            continue
        q[y, xs[0] + 1:xs[-1], :3] = enche
        q[y, xs[0] + 1:xs[-1], 3] = 255
    return q


def _alinhar_pes(q: np.ndarray, chao: int) -> np.ndarray:
    ys = np.nonzero(q[..., 3] > 0)[0]
    if not len(ys):
        return q
    dy = chao - int(ys.max())
    return np.roll(q, dy, axis=0) if dy else q


# ------------------------------------------------------------------ mapa de partes


def _pernas_lado(q: np.ndarray, rot: np.ndarray) -> np.ndarray:
    """Vista de lado: separa a perna da frente e a de trás pelo contorno interno (componentes do enchimento abaixo
    da virilha). Esquerda da imagem = perna-esq, direita = perna-dir. Contorno vai para a perna mais próxima."""
    pid = M._id("perna-esq")
    zona = rot == pid
    if not zona.any():
        return rot
    escuro = q[..., :3].astype(int).sum(-1) < 120
    miolo = zona & ~escuro
    lbl, n = ndimage.label(miolo)
    if n < 2:
        return rot
    tam = ndimage.sum(miolo, lbl, range(1, n + 1))
    dois = np.argsort(tam)[::-1][:2] + 1
    if tam[dois[1] - 1] < 4:
        return rot
    cx = [np.nonzero(lbl == k)[1].mean() for k in dois]
    esq, dirr = (dois[0], dois[1]) if cx[0] < cx[1] else (dois[1], dois[0])
    sem = np.where((lbl == esq) | (lbl == dirr), 0, 1).astype(np.uint8)
    _, (iy, ix) = ndimage.distance_transform_edt(sem, return_indices=True)
    perto = lbl[iy, ix]
    out = rot.copy()
    out[zona & (perto == esq)] = pid
    out[zona & (perto == dirr)] = M._id("perna-dir")
    return out


def juntar_pedacos(rot: np.ndarray) -> np.ndarray:
    """Pedaço solto de uma parte (não o maior) passa para a parte vizinha com mais contato. Corrige o contorno da
    perna que o rascunho pinta como braço quando a perna abre além do quadril."""
    out = rot.copy()
    oito = np.ones((3, 3), int)
    cruz = ndimage.generate_binary_structure(2, 1)
    for k in [int(v) for v in np.unique(out) if v > 0]:
        lbl, n = ndimage.label(out == k, structure=oito)
        if n < 2:
            continue
        tam = ndimage.sum(np.ones_like(lbl), lbl, range(1, n + 1))
        maior = int(np.argmax(tam)) + 1
        for j in range(1, n + 1):
            if j == maior:
                continue
            peca = lbl == j
            viz = out[ndimage.binary_dilation(peca, cruz) & ~peca]
            viz = viz[(viz > 0) & (viz != k)]
            if len(viz):
                out[peca] = np.bincount(viz).argmax()
    return out


def mapa_quadro(q: np.ndarray, direcao: str, y_pernas: int | None = None) -> np.ndarray:
    """Mapa de partes de um quadro da base. Lado: 'y_pernas' (linha em que as pernas começam, tirada da frente)
    passa o tronco abaixo dela para as pernas, que são separadas em frente/trás pelo contorno interno."""
    lado = direcao in ("e", "w")
    rot = M.mapa_auto(q, lado=lado)
    if lado:
        if y_pernas is not None:
            fig = q[..., 3] > 0
            baixo = np.zeros_like(fig)
            baixo[y_pernas:] = True
            rot[baixo & fig & (rot == M._id("tronco"))] = M._id("perna-esq")
        rot = _pernas_lado(q, rot)
    return juntar_pedacos(rot)


# ------------------------------------------------------------------ extrair


def extrair(saida: str | Path = SAIDA_PADRAO, folha: str | Path = FOLHA_PADRAO) -> dict:
    """Fatia o corpo nu da folha Eldiran e grava quadros, base.png, base.json e os mapas de partes."""
    folha = Path(folha)
    if not folha.is_file():
        raise FileNotFoundError(f"folha Eldiran não encontrada: {folha}")
    arr = np.array(Image.open(folha).convert("RGBA"))
    if arr.shape[0] % CELULA or arr.shape[1] < 12 * CELULA:
        raise ValueError(f"folha {arr.shape[1]}x{arr.shape[0]} fora do layout 12 colunas de {CELULA}")
    saida = Path(saida)
    (saida / "quadros").mkdir(parents=True, exist_ok=True)
    (saida / "partes").mkdir(parents=True, exist_ok=True)

    andar = {}
    derivados = []
    for d in DIRS:
        qs = [_celula(arr, LINHA_BASE, c) for c in COLUNAS[d]]
        if d == "n" and not any(q[..., 3].any() for q in qs):
            qs = [costas_de_frente(_celula(arr, LINHA_BASE, c)) for c in COLUNAS["s"]]
            derivados.append("n: costas derivadas da frente (rosto apagado); a linha 0 da folha não tem costas")
        andar[d] = [_pad(q) for q in qs]
    lado_canvas = CELULA + 2 * MARGEM
    chao = lado_canvas - MARGEM - 1
    for d in DIRS:
        andar[d] = [_alinhar_pes(q, chao) for q in andar[d]]

    # onde as pernas começam: a linha mais alta das pernas no descanso de frente (a vista de lado não tem vão)
    rf = mapa_quadro(andar["s"][DESCANSO], "s")
    pern = np.isin(rf, [M._id("perna-esq"), M._id("perna-dir")])
    y_pernas = int(np.nonzero(pern)[0].min()) if pern.any() else None

    quadros, checagens, falhas = [], {}, []
    for acao, cfg in ACOES.items():
        for d in DIRS:
            for i, k in enumerate(cfg["quadros"]):
                q = andar[d][k]
                nome = f"{acao}_{d}_{i:02d}"
                Image.fromarray(q).save(saida / "quadros" / f"{nome}.png")
                rot = mapa_quadro(q, d, y_pernas)
                Image.fromarray(M.pintar(rot)).save(saida / "partes" / f"{nome}.png")
                ch = M.checar(q, rot)
                checagens[nome] = ch.como_dict()
                if not ch.ok:
                    falhas.append(f"{nome}: " + " | ".join(ch.problemas))
                quadros.append({"nome": nome, "acao": acao, "dir": d, "i": i, "fonte_coluna": COLUNAS[d][k],
                                "derivado": d == "n" and bool(derivados), "partes_ok": ch.ok})

    # base.png: as 3 vistas de descanso lado a lado, cada uma no seu canvas com margem
    vistas = []
    base = np.concatenate([andar[d][DESCANSO] for d in DIRS], axis=1)
    for j, d in enumerate(DIRS):
        vistas.append({"dir": d, "x": j * lado_canvas, "y": 0, "w": lado_canvas, "h": lado_canvas,
                       "quadro": f"idle_{d}_00"})
    Image.fromarray(base).save(saida / "base.png")
    Image.fromarray(base).resize((base.shape[1] * 8, base.shape[0] * 8), Image.NEAREST).save(saida / "base_8x.png")

    info = {
        **LICENCA,
        "folha": str(folha), "linha": LINHA_BASE, "celula": CELULA, "margem": MARGEM,
        "canvas": [lado_canvas, lado_canvas], "origem": [lado_canvas // 2, chao + 1],
        "layout": {"colunas": COLUNAS, "descanso": DESCANSO, "espelho": {"w": "e"},
                   "nota": "colunas 0-3 frente, 4-7 costas, 8-11 lado olhando para a direita; linha 0 = corpo nu"},
        "acoes": {a: {"ms": c["ms"], "n": len(c["quadros"]), "quadros_fonte": c["quadros"]} for a, c in ACOES.items()},
        "direcoes": DIRS + ["w"], "vistas": vistas, "quadros": quadros,
        "derivados": derivados, "partes_falhas": falhas,
        "partes_nota": "lado: braço não separado do tronco (desenhado por cima dele); pernas separadas pelo "
                       "contorno interno",
    }
    (saida / "base.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    (saida / "partes" / "checagem.json").write_text(json.dumps(checagens, ensure_ascii=False, indent=2),
                                                    encoding="utf-8")
    return info


# ------------------------------------------------------------------ animar a pele


def _ler(p: Path) -> np.ndarray:
    return np.array(Image.open(p).convert("RGBA"))


def animar_pele(base_dir: str | Path, pele_png: str | Path, saida: str | Path, *, raio: int = 6) -> dict:
    """Leva a pele (feita por horys_vestir sobre base.png) a cada quadro de cada ação/direção e grava as folhas.

    A pele é cortada por vista (offsets do base.json), propagada do mapa de partes da vista de descanso para o de
    cada quadro (pele.propagar), composta sobre o quadro da base e gravada por <acao>_<dir> (PNG+JSON+GIF). O oeste
    é o leste espelhado. Avisos = partes que mudam de forma (limpar à mão)."""
    from .sequencia import spritesheet

    base_dir, saida = Path(base_dir), Path(saida)
    info = json.loads((base_dir / "base.json").read_text(encoding="utf-8"))
    pele = _ler(Path(pele_png))
    base = _ler(base_dir / "base.png")
    if pele.shape != base.shape:
        raise ValueError(f"pele {pele.shape[1]}x{pele.shape[0]} e base.png {base.shape[1]}x{base.shape[0]} de "
                         "tamanhos diferentes (a pele precisa ser feita sobre base.png)")
    ordem = [M._id(n) for n in M.ORDEM_PADRAO]
    saida.mkdir(parents=True, exist_ok=True)
    folhas, avisos, relatorio = {}, [], {}
    for v in info["vistas"]:
        d = v["dir"]
        pv = pele[v["y"]:v["y"] + v["h"], v["x"]:v["x"] + v["w"]]
        p0 = M.rotulos(_ler(base_dir / "partes" / f"{v['quadro']}.png"))
        for acao, cfg in info["acoes"].items():
            comps = []
            for i in range(cfg["n"]):
                nome = f"{acao}_{d}_{i:02d}"
                pn = M.rotulos(_ler(base_dir / "partes" / f"{nome}.png"))
                r = P.propagar(pv, p0, pn, ordem=ordem, raio=raio)
                comps.append(P.compor(_ler(base_dir / "quadros" / f"{nome}.png"), r.pele))
                relatorio[nome] = {M.NOMES[k - 1]: x for k, x in r.por_parte.items()}
                avisos += [f"{nome}: " + _nomear(a) for a in r.avisos]
            folhas[f"{acao}_{d}"] = spritesheet.salvar(comps, saida, f"{acao}_{d}", cfg["ms"], acao)
            if d == "e":
                folhas[f"{acao}_w"] = spritesheet.salvar([c[:, ::-1].copy() for c in comps], saida, f"{acao}_w",
                                                         cfg["ms"], acao)
    res = {"folhas": folhas, "avisos": avisos, "partes": relatorio, "pele": str(pele_png), "base": str(base_dir)}
    (saida / "animar.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    return res


def _nomear(aviso: str) -> str:
    """'parte 3: ...' -> 'braco-esq: ...' (propagar fala em rótulo inteiro)."""
    if aviso.startswith("parte "):
        k, resto = aviso[6:].split(":", 1)
        if k.strip().isdigit() and 0 < int(k) <= len(M.NOMES):
            return M.NOMES[int(k) - 1] + ":" + resto
    return aviso
