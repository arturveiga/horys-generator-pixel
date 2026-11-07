"""Camadas do Aseprite <-> grade de texto (.grade, o formato do portão de medidas).

O Aseprite é a tela; a .grade é o formato interno que o motor (grade.py/medir.py) mede. Exportar as PARTES para
.grade e deixar o grade.py recompor contorno e sombra garante o mesmo resultado do fluxo antigo.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .pixels import LETRAS, hex_rgba, rgba_hex

RESERVADAS = ("contorno", "sombra", "revisao", "referencia", "regua")


def pivo_quadro(Q: int) -> tuple[int, int]:
    """Onde o pé fica no quadro (igual ao grade.py): (Q//2, round(Q*127/192))."""
    return Q // 2, round(Q * 127 / 192)


def letras_da_paleta(paleta: dict | None) -> dict:
    """{letra: hex} estável para as cores do estilo (rampas, contorno, brilho)."""
    cores: list[str] = []
    if paleta:
        for rampa in (paleta.get("rampas") or {}).values():
            cores += [c.lower() for c in rampa]
        for k in ("contorno", "brilho"):
            v = paleta.get(k)
            if isinstance(v, str):
                cores.append(v.lower())
            elif isinstance(v, list):
                cores += [c.lower() for c in v]
    vistos, saida = set(), {}
    livres = iter(LETRAS)
    for c in cores:
        if c in vistos:
            continue
        vistos.add(c)
        saida[next(livres)] = c
    return saida


def cabecalho(ficha: dict, estado: str, pivo: tuple[int, int], ms: int, Q: int, cores: dict) -> list[str]:
    inv = {v: k for k, v in cores.items()}
    linhas = [f"nome {ficha.get('nome') or 'asset'}", f"estado {estado}", f"tipo {ficha.get('tipo') or 'personagem'}",
              f"quadro {Q}", f"pivo {pivo[0]} {pivo[1]}", f"ms {ms}", f"contorno {ficha.get('contorno') or 'auto'}",
              f"sombra {'sim' if ficha.get('sombra', True) else 'nao'}"]
    if ficha.get("cor_contorno"):
        linhas.append(f"cor_contorno {ficha['cor_contorno']}")
    for chave in ("sem_contorno", "sem_borda"):
        ls = [inv[c.lower()] for c in ficha.get(chave) or [] if c.lower() in inv]
        if ls:
            linhas.append(f"{chave} {' '.join(ls)}")
    if ficha.get("limite_cores"):
        linhas.append(f"limite_cores {int(ficha['limite_cores'])}")
    if ficha.get("ritmo"):
        linhas.append(f"ritmo {ficha['ritmo']}")
    if ficha.get("paleta_arquivo"):
        linhas.append(f"paleta {ficha['paleta_arquivo']}")
    linhas.append("cores")
    linhas += [f"  {k} {v}" for k, v in cores.items()]
    return linhas


def grade_de_camadas(ficha: dict, partes: list[str], quadros: list[dict], estado: str, ms: int, Q: int,
                     cores_base: dict | None = None) -> tuple[str, list[str]]:
    """quadros: [{nome_da_parte: rgba QxQ}] na ordem; partes: de baixo para cima. Devolve (texto, avisos)."""
    avisos = []
    cores = dict(cores_base or {})
    inv = {v: k for k, v in cores.items()}
    livres = [c for c in LETRAS if c not in cores]
    uniao = np.zeros((Q, Q), bool)
    for q in quadros:
        for p in partes:
            im = q.get(p)
            if im is not None:
                uniao |= im[..., 3] > 0
    if not uniao.any():
        raise ValueError("nada desenhado nas camadas de partes (" + ", ".join(partes) + ")")
    ys, xs = np.nonzero(uniao)
    x0, y0, x1, y1 = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
    px, py = pivo_quadro(Q)
    pivo = (px - x0, py - y0)
    semi = 0
    blocos = []
    for k, q in enumerate(quadros):
        for p in partes:
            im = q.get(p)
            linhas = []
            for y in range(y0, y1):
                s = []
                for x in range(x0, x1):
                    if im is None or im[y, x, 3] == 0:
                        s.append(".")
                        continue
                    if im[y, x, 3] != 255:
                        semi += 1
                    hx = rgba_hex((*im[y, x, :3], 255))
                    letra = inv.get(hx)
                    if letra is None:
                        if not livres:
                            raise ValueError(f"cores demais (mais de {len(LETRAS)}) nas partes")
                        letra = livres.pop(0)
                        inv[hx] = letra
                        cores[letra] = hx
                    s.append(letra)
                linhas.append("".join(s).rstrip(".") or ".")
            blocos.append(f"--- q{k} @{p}")
            blocos += linhas
    if semi:
        avisos.append(f"{semi} px semitransparentes nas partes viraram opacos (a arte do estilo é de alfa binário)")
    usadas = set("".join(b for b in blocos if not b.startswith("---"))) - {"."}
    cores = {k: v for k, v in cores.items() if k in usadas}
    texto = "\n".join(["# exportado do Aseprite pelo horys-pixel"] + cabecalho(ficha, estado, pivo, ms, Q, cores)
                      + blocos) + "\n"
    return texto, avisos


def ler_grade_simples(caminho: str | Path) -> tuple[list[str], dict, list[str], tuple[int, int] | None]:
    """Lê uma .grade de um quadro sem camadas (saída do conceito.py): (cabeçalho, cores, linhas, pivo)."""
    cab, cores, linhas, pivo = [], {}, [], None
    modo = "meta"
    for bruta in Path(caminho).read_text(encoding="utf-8").splitlines():
        l = bruta.rstrip()
        if l.startswith("---"):
            if modo == "grade":
                break
            modo = "grade"
            continue
        if modo == "grade":
            if l.strip():
                linhas.append(l)
            continue
        if not l.strip() or l.lstrip().startswith("#"):
            continue
        p = l.split()
        if p[0] == "cores":
            modo = "cores"
            continue
        if modo == "cores" and len(p) == 2 and p[1].startswith("#"):
            cores[p[0]] = p[1].lower()
            continue
        if p[0] == "pivo":
            pivo = (int(p[1]), int(p[2]))
        cab.append(l)
    return cab, cores, linhas, pivo


def rgba_de_letras(linhas: list[str], cores: dict, Q: int, pivo: tuple[int, int] | None,
                   origem: tuple[int, int] | None = None) -> np.ndarray:
    """Põe as letras no quadro QxQ: pelo pivô (como o grade.py) ou numa origem (x, y) explícita."""
    img = np.zeros((Q, Q, 4), np.uint8)
    if origem is not None:
        ox, oy = origem
    else:
        px, py = pivo_quadro(Q)
        gx, gy = pivo or (0, 0)
        ox, oy = px - gx, py - gy
    cache = {}
    for i, l in enumerate(linhas):
        for j, c in enumerate(l):
            if c == "." or c not in cores:
                continue
            y, x = oy + i, ox + j
            if 0 <= x < Q and 0 <= y < Q:
                cor = cache.get(c) or hex_rgba(cores[c])
                cache[c] = cor
                img[y, x] = cor
    return img


def legenda(ficha: dict, cores: dict, Q: int) -> str:
    """Arquivo de legenda para o conceito.py converter/limpar/afinar (cabeçalho + cores, sem quadros)."""
    return "\n".join(cabecalho(ficha, ficha.get("estado") or "idle", (0, 0), 100, Q, cores)) + "\n"


def grade_de_imagem(ficha: dict, rgba: np.ndarray, cores_base: dict, Q: int) -> tuple[str, tuple[int, int]]:
    """Uma camada (QxQ) como .grade de um quadro, recortada; devolve (texto, origem x0,y0) para voltar ao lugar."""
    m = rgba[..., 3] > 0
    if not m.any():
        raise ValueError("camada vazia")
    ys, xs = np.nonzero(m)
    x0, y0, x1, y1 = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
    cores = dict(cores_base)
    inv = {v: k for k, v in cores.items()}
    livres = [c for c in LETRAS if c not in cores]
    linhas = []
    for y in range(y0, y1):
        s = []
        for x in range(x0, x1):
            if not m[y, x]:
                s.append(".")
                continue
            hx = rgba_hex((*rgba[y, x, :3], 255))
            if hx not in inv:
                inv[hx] = livres.pop(0)
                cores[inv[hx]] = hx
            s.append(inv[hx])
        linhas.append("".join(s).rstrip(".") or ".")
    usadas = set("".join(linhas)) - {"."}
    manter = {c.lower() for c in (ficha.get("sem_contorno") or [])}
    if ficha.get("cor_contorno"):
        manter.add(ficha["cor_contorno"].lower())
    cores = {k: v for k, v in cores.items() if k in usadas or v in manter}
    px, py = pivo_quadro(Q)
    texto = "\n".join(cabecalho(ficha, "q", (px - x0, py - y0), 100, Q, cores) + ["--- q0"] + linhas) + "\n"
    return texto, (x0, y0)
