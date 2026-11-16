"""Pós-render do pipeline Blender (B3/B7), em Python, sem o Blender.

Os quadros do Blender já saem com as cores da paleta (emissão, filtro 0). Aqui:
1. alfa binário e cada pixel encaixado na paleta aprovada (OKLab) — nenhuma cor nova;
2. pixel solto: um tom isolado no meio de outro tom da MESMA família vira o tom vizinho (regra do 2×2; emissivos
   ficam: brilho de 1 px é intencional);
3. contorno de 1 px com a tinta (por fora da silhueta, ou por dentro, ou nenhum);
4. recolor opcional (B7): mapa cor antiga -> cor nova;
5. folha + JSON + GIF por ação × direção, prancha de conferência e um .aseprite com uma tag por ação_direção.
Os mapas de partes (_partes) só são encaixados nas cores do contrato (mapa_partes.CORES).
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

from .. import config
from ..pele import _oklab, hex_rgb
from ..sequencia import spritesheet
from ..sequencia.anticintilacao import pisca


def duracoes(n: int, fps: int) -> list[int]:
    """ms por quadro em múltiplos de 10 que somam o tempo certo (12 fps -> 80, 90, 80, ...)."""
    out, acc = [], 0
    for i in range(n):
        alvo = int(round((i + 1) * 1000 / fps / 10.0)) * 10
        out.append(alvo - acc)
        acc = alvo
    return out


def _encaixar(rgb: np.ndarray, pal: np.ndarray) -> np.ndarray:
    """Índice da cor da paleta mais próxima (OKLab) de cada pixel; usa as cores únicas para ser rápido."""
    uni, inv = np.unique(rgb.reshape(-1, 3), axis=0, return_inverse=True)
    d = np.linalg.norm(_oklab(uni.astype(np.float64))[:, None] - _oklab(pal.astype(np.float64))[None], axis=-1)
    return d.argmin(1)[inv.ravel()].reshape(rgb.shape[:2])


def limpar_soltos(idx: np.ndarray, familia: list[str], protegidos: set[int], tinta: int = -2) -> tuple[np.ndarray, int]:
    """Regra do 2×2: pixel sem vizinho (8) da mesma cor, cercado de figura, vira a cor vizinha mais comum quando
    ela domina: >= 5 vizinhos se for da mesma família (só um tom), >= 6 se for de outra família ou se o pixel for
    emissivo (brilho de 1 px só fica se estiver de fato isolado entre cores diferentes). A tinta não é alvo nem
    fonte. Duas passadas (um ponto limpo pode soltar outro)."""
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
    cruz = ndimage.generate_binary_structure(2, 1)
    out = idx.copy()
    if modo == "fora":
        borda = ndimage.binary_dilation(op, cruz) & ~op
    elif modo == "dentro":
        borda = op & ndimage.binary_dilation(~op, cruz)
    else:
        raise ValueError("contorno: fora | dentro | nenhum")
    out[borda] = tinta
    return out


def _para_rgba(idx: np.ndarray, pal: np.ndarray) -> np.ndarray:
    out = np.zeros(idx.shape + (4,), np.uint8)
    m = idx >= 0
    out[m, :3] = pal[idx[m]]
    out[m, 3] = 255
    return out


def processar(saida: str | Path, paleta: dict, cfg: dict, recolor: dict | None = None) -> dict:
    saida = Path(saida)
    mani = json.loads((saida / "_render" / "manifesto.json").read_text(encoding="utf-8"))
    cores = list(paleta["cores"])
    fam_de = {h: n for n, f in paleta["familias"].items() for h in f["rampa"]}
    fam_de[paleta["tinta"]] = "_tinta"
    familia = [fam_de.get(h, "_") for h in cores]
    protegidos = {i for i, h in enumerate(cores)
                  if paleta["familias"].get(fam_de.get(h, ""), {}).get("tipo") == "emissivo"}
    pal = np.array([hex_rgb(h) for h in cores], np.uint8)
    pal_saida = pal.copy()
    if recolor:
        for i, h in enumerate(cores):
            if h in recolor:
                pal_saida[i] = hex_rgb(recolor[h])
    tinta = cores.index(paleta["tinta"])
    modo = cfg.get("contorno", "fora")
    rel = {"acoes": {}, "cores": len(cores), "avisos": list(mani.get("avisos") or [])}
    todas, tags = [], []
    for nome_a, a in mani["acoes"].items():
        ms = duracoes(a["quadros"], a["fps"])
        for d in mani["direcoes"]:
            arqs = sorted((saida / "_render" / nome_a).glob(f"{d}_*.png"))
            if not arqs:
                continue
            idxs, soltos = [], 0
            for arq in arqs:
                im = np.asarray(Image.open(arq).convert("RGBA"))
                op = im[..., 3] >= 128
                idx = np.full(op.shape, -1, int)
                if op.any():
                    idx[op] = _encaixar(im[..., :3][op][None], pal)[0]
                idx, k = limpar_soltos(idx, familia, protegidos, tinta)
                soltos += k
                idxs.append(contorno(idx, tinta, modo))
            quadros = [_para_rgba(i, pal_saida) for i in idxs]
            est = f"{nome_a}_{d}"
            ms_d = ms[:len(quadros)] if len(quadros) == len(ms) else [int(1000 / a["fps"])] * len(quadros)
            spritesheet.salvar(quadros, saida, est, ms_d, est, None, True)
            pes = [int(np.nonzero((i >= 0).any(1))[0].max()) for i in idxs if (i >= 0).any()]
            alturas = [int(np.ptp(np.nonzero((i >= 0).any(1))[0]) + 1) for i in idxs if (i >= 0).any()]
            rel["acoes"][est] = {"quadros": len(quadros), "ms": ms_d, "soltos_limpos": soltos,
                                 "pisca_%": round(100 * pisca(idxs, ciclo=True), 2),
                                 "pe_linha": [min(pes), max(pes)] if pes else None,
                                 "altura_px": [min(alturas), max(alturas)] if alturas else None}
            try:                         # boas práticas (docs/boas-praticas.md), com a tolerância de render 3D
                from .. import boas_praticas as BPR
                prot = [h for i, h in enumerate(cores) if i in protegidos]
                res = BPR.checar_animacao(quadros, {"acao": a.get("tipo", nome_a), "render3d": True,
                                                    "protegidas": prot, "contorno": paleta["tinta"],
                                                    "paleta": [("#%02x%02x%02x" % tuple(c)) for c in pal_saida],
                                                    "limites": cfg.get("limites_praticas") or {}})
                rel["acoes"][est]["praticas_falhas"] = [r["id"] for r in res if not r.get("passa", True)]
            except Exception as e:      # noqa: BLE001  a checagem nunca derruba o pós
                rel["acoes"][est]["praticas_erro"] = str(e)[:200]
            tags.append((est, len(todas) + 1, len(todas) + len(quadros)))
            todas += [(q, m) for q, m in zip(quadros, ms_d)]
        # partes: só encaixa nas cores do contrato
        pp = saida / "_partes" / nome_a
        if pp.is_dir():
            from .. import mapa_partes as M
            cont = np.array(list(M.CORES.values()), np.uint8)
            dst = saida / "partes" / nome_a
            dst.mkdir(parents=True, exist_ok=True)
            for arq in sorted(pp.glob("*.png")):
                im = np.asarray(Image.open(arq).convert("RGBA"))
                op = im[..., 3] >= 128
                out = np.zeros_like(im)
                if op.any():
                    out[op, :3] = cont[_encaixar(im[..., :3][op][None], cont)[0]]
                    out[op, 3] = 255
                Image.fromarray(out).save(dst / arq.name)
    rel["prancha"] = str(_prancha(saida, mani, cfg))
    rel["aseprite"] = _aseprite(saida, todas, tags, [("#%02x%02x%02x" % tuple(c)) for c in pal_saida])
    (saida / "pos.json").write_text(json.dumps(rel, ensure_ascii=False, indent=1), encoding="utf-8")
    return rel


def mapa_recolor(velha: dict, nova: dict) -> dict:
    """B7: cor antiga -> cor nova pela posição na rampa de cada família (e a tinta). Família ou tom a mais na nova
    paleta não muda nada (o render já está feito); tom a menos fica com a cor antiga."""
    mapa = {}
    for nome, f in velha["familias"].items():
        g = nova["familias"].get(nome)
        if not g:
            continue
        for a, b in zip(f["rampa"], g["rampa"]):
            if a != b:
                mapa[a] = b
    if velha.get("tinta") and nova.get("tinta") and velha["tinta"] != nova["tinta"]:
        mapa[velha["tinta"]] = nova["tinta"]
    return mapa


def _prancha(saida: Path, mani: dict, cfg: dict, k: int = 3) -> Path:
    """Uma linha por ação × direção, quadros lado a lado, ampliada k×, fundo verde de conferência."""
    linhas = []
    for nome_a in mani["acoes"]:
        for d in mani["direcoes"]:
            png = saida / f"{nome_a}_{d}.png"
            js = saida / f"{nome_a}_{d}.json"
            if not png.exists():
                continue
            linhas.append(np.asarray(Image.open(png).convert("RGBA")))
    if not linhas:
        return saida
    W = max(l.shape[1] for l in linhas)
    f = np.concatenate([np.pad(l, ((0, 2), (0, W - l.shape[1]), (0, 0))) for l in linhas], 0)
    im = Image.fromarray(f)
    bg = Image.new("RGBA", (im.width * k, im.height * k), (104, 160, 87, 255))
    bg.alpha_composite(im.resize(bg.size, Image.NEAREST))
    dst = saida / "prancha.png"
    bg.save(dst)
    return dst


def _aseprite(saida: Path, quadros: list, tags: list, paleta: list[str]) -> str | None:
    exe = config.achar_aseprite()
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
    lua = Path(__file__).resolve().parents[1] / "motor" / "exportar_aseprite.lua"
    subprocess.run([exe, "-b", "--script-param", f"spec={sp}", "--script", str(lua)], capture_output=True,
                   text=True, encoding="utf-8", errors="replace", timeout=600)
    return str(destino) if destino.exists() else None
