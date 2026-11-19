"""Pós-render, em Python (sem Blender). Os quadros saem do Blender já nas cores da paleta (emissão, filtro 0).

Por ação × direção:
1. alfa binário e cada pixel encaixado na paleta aprovada (OKLab): nenhuma cor nova;
2. pixel solto: tom isolado no meio de outro tom vira o vizinho (emissivos são protegidos);
3. anticintilação: onde a silhueta não mudou, o pixel herda a cor do quadro anterior;
4. contorno de 1 px com a tinta (fora | dentro | nenhum, do contrato do jogo);
5. medidas para os portões: altura, linha do pé, cintilação antes/depois, mudança por quadro;
6. folha (PNG + JSON hash do Aseprite + GIF), prancha de conferência e .aseprite com tags (se houver Aseprite).
Os mapas de partes (_partes) medem o detalhe mínimo: peça com menos de 2 px de espessura vira aviso.
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

from . import anticintilacao as A
from . import cor as C
from . import folha

CRUZ = ndimage.generate_binary_structure(2, 1)


def duracoes(n: int, fps: int) -> list[int]:
    """ms por quadro em múltiplos de 10 que somam o tempo certo (12 fps -> 80, 90, 80, ...)."""
    out, acc = [], 0
    for i in range(n):
        alvo = int(round((i + 1) * 1000 / fps / 10.0)) * 10
        out.append(alvo - acc)
        acc = alvo
    return out


def limpar_soltos(idx: np.ndarray, familia: list[str], protegidos: set[int], tinta: int = -2) -> tuple[np.ndarray, int]:
    """Pixel sem vizinho (8) da mesma cor, cercado de figura, vira a cor vizinha mais comum quando ela domina: >= 5
    vizinhos se for da mesma família, >= 6 se for de outra família ou se o pixel for emissivo."""
    h, w = idx.shape
    out = idx.copy()
    n = 0
    for _ in range(2):
        p = np.pad(out, 1, constant_values=-1)
        viz = np.stack([p[dy:dy + h, dx:dx + w] for dy in range(3) for dx in range(3) if (dy, dx) != (1, 1)], -1)
        mud = 0
        for y, x in zip(*np.nonzero(out >= 0)):
            c = int(out[y, x])
            if c == tinta:
                continue
            v = viz[y, x]
            if (v < 0).any() or (v == c).any():
                continue
            v = v[v != tinta]
            if len(v) < 5:
                continue
            vals, cont = np.unique(v, return_counts=True)
            k, q = int(vals[cont.argmax()]), int(cont.max())
            precisa = 5 if (familia[k] == familia[c] and c not in protegidos) else 6
            if q >= precisa:
                out[y, x] = k
                mud += 1
        n += mud
        if not mud:
            break
    return out, n


def contorno(idx: np.ndarray, tinta: int, modo: str = "fora") -> np.ndarray:
    if modo == "nenhum":
        return idx
    op = idx >= 0
    out = idx.copy()
    if modo == "fora":
        borda = ndimage.binary_dilation(op, CRUZ) & ~op
    elif modo == "dentro":
        borda = op & ndimage.binary_dilation(~op, CRUZ)
    else:
        raise ValueError("contorno: fora | dentro | nenhum")
    out[borda] = tinta
    return out


def para_rgba(idx: np.ndarray, pal: np.ndarray) -> np.ndarray:
    out = np.zeros(idx.shape + (4,), np.uint8)
    m = idx >= 0
    out[m, :3] = pal[idx[m]]
    out[m, 3] = 255
    return out


def mudanca(idxs: list[np.ndarray], ciclo: bool = True) -> list[float]:
    """Fração dos pixels (união das duas silhuetas) que mudam entre quadros vizinhos."""
    out = []
    pares = list(zip(idxs, idxs[1:])) + ([(idxs[-1], idxs[0])] if ciclo and len(idxs) > 2 else [])
    for a, b in pares:
        uni = (a >= 0) | (b >= 0)
        out.append(float(((a != b) & uni).sum() / max(1, uni.sum())))
    return out


def emenda(mud: list[float]) -> dict | None:
    """Emenda do ciclo (ideia do loop_check.py do blender-skills, MIT), medida no pixel: compara a mudança
    último->primeiro (último item de 'mudanca' com ciclo) com a mediana dos passos internos.
    pop = a emenda pula muito mais que um passo; trava = a emenda quase não muda (último quadro repete o 1º)."""
    if len(mud) < 4:
        return None
    passo = float(np.median(mud[:-1]))
    return {"emenda": round(mud[-1], 4), "passo": round(passo, 4),
            "razao": round(mud[-1] / passo, 2) if passo > 0 else None}


def detalhe_fino(mapa: np.ndarray, cores_partes: dict, minimo: int = 2) -> list[str]:
    """Partes (mapa de cor chapada) que não comportam um bloco minimo×minimo em lugar nenhum."""
    finas = []
    rgb = mapa[..., :3].astype(int)
    op = mapa[..., 3] >= 128
    for nome, hx in cores_partes.items():
        m = op & (np.abs(rgb - np.array(C.hex_rgb(hx))).sum(-1) <= 40)
        if m.any() and not ndimage.binary_erosion(m, np.ones((minimo, minimo), bool)).any():
            finas.append(nome)
    return finas


def _quadros(pasta: Path, d: str) -> list[Path]:
    return sorted(pasta.glob(f"{d}_*.png"))


def processar(saida: str | Path, paleta: dict, jogo: dict, cores_partes: dict | None = None,
              aseprite: bool = True) -> dict:
    saida = Path(saida)
    mani = json.loads((saida / "_render" / "manifesto.json").read_text(encoding="utf-8"))
    cores = list(paleta["cores"])
    fam_de = {h: n for n, f in paleta["familias"].items() for h in f["rampa"]}
    fam_de[paleta["tinta"]] = "_tinta"
    familia = [fam_de.get(h, "_") for h in cores]
    protegidos = {i for i, h in enumerate(cores)
                  if paleta["familias"].get(fam_de.get(h, ""), {}).get("tipo") == "emissivo"}
    pal = np.array([C.hex_rgb(h) for h in cores], np.uint8)
    tinta = cores.index(paleta["tinta"])
    modo = jogo.get("contorno", "fora")
    rel = {"acoes": {}, "estados": {}, "cores": len(cores), "avisos": list(mani.get("avisos") or []),
           "camera": mani.get("camera"), "juntas": mani.get("juntas", {}), "detalhe_fino": {}}
    todas, tags = [], []
    for nome_a, a in mani["acoes"].items():
        rel["acoes"][nome_a] = a
        ms = duracoes(a["quadros"], a["fps"])
        ciclo = a["tipo"] not in ("morte", "parado")
        for d in mani["direcoes"]:
            arqs = _quadros(saida / "_render" / nome_a, d)
            if not arqs:
                continue
            idxs, soltos = [], 0
            for arq in arqs:
                im = np.asarray(Image.open(arq).convert("RGBA"))
                op = im[..., 3] >= 128
                idx = np.full(op.shape, -1, int)
                if op.any():
                    idx[op] = C.encaixar(im[..., :3][op][None], pal)[0]
                idx, k = limpar_soltos(idx, familia, protegidos, tinta)
                soltos += k
                idxs.append(idx)
            pisca_antes = A.pisca(idxs, ciclo=ciclo)
            prot = [np.isin(i, list(protegidos)) for i in idxs] if protegidos else None
            idxs = A.aplicar(idxs, dilatar=1, proteger=prot)
            idxs = [contorno(i, tinta, modo) for i in idxs]
            quadros = [para_rgba(i, pal) for i in idxs]
            est = f"{nome_a}_{d}"
            ms_d = ms[:len(quadros)] if len(quadros) <= len(ms) else [int(1000 / a["fps"])] * len(quadros)
            folha.salvar(quadros, saida, est, ms_d, est, None, ciclo)
            linhas = [np.nonzero((i >= 0).any(1))[0] for i in idxs]
            pes = [int(l.max()) for l in linhas if len(l)]
            alturas = [int(l.max() - l.min() + 1) for l in linhas if len(l)]
            mud = mudanca(idxs, ciclo)
            rel["estados"][est] = {
                "acao": nome_a, "tipo": a["tipo"], "direcao": d, "quadros": len(quadros), "ms": ms_d,
                "soltos_limpos": soltos, "pisca_antes": round(pisca_antes, 4),
                "pisca": round(A.pisca(idxs, ciclo=ciclo), 4),
                "mudanca_media": round(float(np.mean(mud)), 4) if mud else 0.0,
                "emenda": emenda(mud) if ciclo else None,
                "pe_linha": [min(pes), max(pes)] if pes else None,
                "altura_px": [min(alturas), max(alturas)] if alturas else None}
            tags.append((est, len(todas) + 1, len(todas) + len(quadros)))
            todas += [(q, m) for q, m in zip(quadros, ms_d)]
            # detalhe mínimo pelo mapa de partes do 1º quadro
            if cores_partes:
                pp = _quadros(saida / "_partes" / nome_a, d)
                if pp:
                    finas = detalhe_fino(np.asarray(Image.open(pp[0]).convert("RGBA")), cores_partes,
                                         int(jogo["portoes"].get("detalhe_min_px", 2)))
                    if finas:
                        rel["detalhe_fino"][est] = finas
    rel["prancha"] = str(prancha(saida, rel))
    rel["aseprite"] = exportar_aseprite(saida, todas, tags, cores) if aseprite else None
    (saida / "pos.json").write_text(json.dumps(rel, ensure_ascii=False, indent=1), encoding="utf-8")
    return rel


def prancha(saida: Path, rel: dict, k: int = 3) -> Path:
    """Uma linha por ação × direção, quadros lado a lado, ampliada k×, fundo verde de conferência."""
    linhas = []
    for est in rel["estados"]:
        png = saida / f"{est}.png"
        if png.exists():
            linhas.append(np.asarray(Image.open(png).convert("RGBA")))
    dst = saida / "prancha.png"
    if not linhas:
        return dst
    W = max(l.shape[1] for l in linhas)
    f = np.concatenate([np.pad(l, ((0, 2), (0, W - l.shape[1]), (0, 0))) for l in linhas], 0)
    im = Image.fromarray(f)
    bg = Image.new("RGBA", (im.width * k, im.height * k), (104, 160, 87, 255))
    bg.alpha_composite(im.resize(bg.size, Image.NEAREST))
    bg.save(dst)
    return dst


def achar_aseprite() -> str | None:
    cands = [os.environ.get("ASEPRITE"), str(Path.home() / "Documents" / "aseprite" / "aseprite.exe"),
             r"C:\Program Files\Aseprite\Aseprite.exe",
             r"C:\Program Files (x86)\Steam\steamapps\common\Aseprite\Aseprite.exe",
             "/Applications/Aseprite.app/Contents/MacOS/aseprite", "/usr/bin/aseprite"]
    cands += glob.glob(r"C:\Program Files\Aseprite*\Aseprite.exe")
    return next((c for c in cands if c and Path(c).exists()), None)


def exportar_aseprite(saida: Path, quadros: list, tags: list, paleta: list[str]) -> str | None:
    """.aseprite com uma tag por ação_direção (precisa do Aseprite instalado; sem ele, só pula)."""
    exe = achar_aseprite()
    if not exe or not quadros:
        return None
    pasta = saida / "_aseprite"
    pasta.mkdir(exist_ok=True)
    spec_q = []
    for i, (q, ms) in enumerate(quadros):
        png = pasta / f"q{i:04d}.png"
        Image.fromarray(q).save(png)
        spec_q.append({"ms": int(ms), "cels": {"personagem": str(png).replace("\\", "/")}})
    destino = saida / "personagem.aseprite"
    if destino.exists():
        destino.unlink()
    h, w = quadros[0][0].shape[:2]
    spec = {"largura": int(w), "altura": int(h), "paleta": paleta, "camadas": [{"nome": "personagem"}],
            "quadros": spec_q, "tags": [{"nome": n, "de": a, "ate": b} for n, a, b in tags],
            "saida": str(destino).replace("\\", "/")}
    sp = pasta / "spec.json"
    sp.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    lua = Path(__file__).with_name("aseprite.lua")
    subprocess.run([exe, "-b", "--script-param", f"spec={sp}", "--script", str(lua)], capture_output=True,
                   text=True, encoding="utf-8", errors="replace", timeout=600)
    return str(destino) if destino.exists() else None
