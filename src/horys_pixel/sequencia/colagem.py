"""Colagem guiada: o gerador (ChatGPT) só diz ONDE cada peça vai; os pixels vêm sempre da arte-mestra aprovada.

Fluxo: mestre = o conceito lido na grade de pixel dele (conceito.grade_nativa + amostrar_nativo, pixel quadrado e
fase pelo Sobel) e travado numa paleta → cada quadro-guia do gerador vai para a MESMA grade (escala: o quadro mais
alto vira a altura do mestre; redução por moda na mesma paleta) → para cada peça declarada (rect no mestre) acha a
posição no quadro por casamento de modelo e cola a peça exata por cima. O que não é peça (perna, braço que balança)
fica como o guia desenhou e é o que sobra para limpar à mão.

Medido no andar de frente do menino de teste (2026-11-12): pixels da cabeça diferentes do quadro 0 caíram de
814/197/807 (guia puro) para 19/0/19 (colado), e o quique (2-1-2-1) saiu sozinho da busca."""
from __future__ import annotations

import numpy as np
from PIL import Image

from ..motor import conceito
from . import fundo, identidade, quantizacao


def _mapear(rgb: np.ndarray, opaco: np.ndarray, paleta_hex: list[str]) -> np.ndarray:
    idx = np.full(opaco.shape, -1, np.int16)
    if opaco.any():
        pal = quantizacao._lab(quantizacao.hex_para_rgb(paleta_hex))
        lab = quantizacao._lab(rgb[opaco][:, :3])
        idx[opaco] = np.linalg.norm(lab[:, None] - pal[None], axis=-1).argmin(1)
    return idx


def paleta_da_imagem(rgb: np.ndarray, opaco: np.ndarray, cores: int = 16) -> list[str]:
    """Paleta de 'cores' cores (corte mediano) só dos pixels da figura."""
    px = rgb[opaco][:, :3].reshape(1, -1, 3).astype(np.uint8)
    pal = Image.fromarray(px).quantize(cores, method=Image.Quantize.MEDIANCUT).getpalette()[:3 * cores]
    return list(dict.fromkeys("#%02x%02x%02x" % tuple(pal[i:i + 3]) for i in range(0, len(pal), 3)))


def mestre_de_conceito(imagem, paleta_hex: list[str] | None = None, cores: int = 16, cor_fundo: str = "auto",
                       tolerancia: float = 0.08) -> tuple[np.ndarray, list[str], dict]:
    """Conceito em pixel art ampliada → (mestre RGBA recortado na figura, paleta, info da grade).
    Sem 'paleta_hex', a paleta sai do próprio conceito ('cores' cores)."""
    rgb = np.array(Image.open(imagem).convert("RGB")) if not isinstance(imagem, np.ndarray) else imagem[..., :3]
    gx, gy = conceito.grade_nativa(rgb)
    peq = conceito.amostrar_nativo(rgb, gx, gy).clip(0, 255).astype(np.uint8)
    fig = conceito.tirar_fundo(peq, cor_fundo, tolerancia)
    if not fig.any():
        raise ValueError("mestre: nenhuma figura achada depois de tirar o fundo")
    ys, xs = np.nonzero(fig)
    peq = peq[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    fig = fig[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    pal = paleta_hex or paleta_da_imagem(peq, fig, cores)
    mestre = quantizacao.para_rgba(_mapear(peq, fig, pal), pal)
    return mestre, pal, {"bloco": round(float(gx[1]), 2), "fase": (round(float(gx[2]), 2), round(float(gy[2]), 2)),
                         "tamanho": [int(mestre.shape[1]), int(mestre.shape[0])]}


def _recortar_figura(q: np.ndarray) -> np.ndarray:
    ys, xs = np.nonzero(q[..., 3] >= 128)
    return q[ys.min():ys.max() + 1, xs.min():xs.max() + 1] if len(ys) else q


def guias_na_escala(quadros: list[np.ndarray], altura: int, paleta_hex: list[str],
                    cor_fundo: str = "auto") -> list[np.ndarray]:
    """Quadros-guia (RGBA grandes) → mesma grade do mestre: escala ÚNICA (o quadro mais alto = 'altura'), para o
    quique e o agachamento sobreviverem; redução por moda na paleta."""
    quadros = [_recortar_figura(q) for q in fundo.tirar_fundo(quadros, cor_fundo)]
    alto = max(q.shape[0] for q in quadros)
    esc = altura / alto
    out = []
    for q in quadros:
        W, H = max(1, round(q.shape[1] * esc)), max(1, round(q.shape[0] * esc))
        idx = _mapear(q[..., :3], q[..., 3] >= 128, paleta_hex)
        out.append(quantizacao.para_rgba(quantizacao.reduzir_moda(idx, (W, H)), paleta_hex))
    return out


def _na_tela(q: np.ndarray, W: int, H: int) -> np.ndarray:
    """Cola q numa tela WxH, centralizado em x e com os pés na última linha."""
    t = np.zeros((H, W, 4), np.uint8)
    h, w = q.shape[:2]
    x = (W - w) // 2
    t[H - h:, max(0, x):max(0, x) + min(w, W)] = q[:H, :min(w, W)]
    return t


def montar(mestre: np.ndarray, guias: list[np.ndarray], pecas: list[dict], raio: int = 4,
           erro_max: float = 150.0, margem: tuple[int, int] = (10, 4)) -> dict:
    """Cola as peças do mestre em cada guia (já na escala). 'pecas' = [{nome, rect [x, y, w, h] no mestre,
    apagar: 'faixa' (apaga as linhas da peça na largura toda; para cabeça/cabelo acima dos ombros) | 'caixa'
    (apaga o retângulo achado) | 'nada' (padrão), busca (raio), espelho (bool, padrão false), erro_max}].
    As peças são coladas na ordem dada (a última fica por cima). Devolve {quadros (RGBA na tela comum), mestre (na
    tela), relatorio [por quadro e peça], estabilidade {nome: px diferentes do quadro 0 por quadro}}."""
    Hm, Wm = mestre.shape[:2]
    W = max([Wm] + [g.shape[1] for g in guias]) + 2 * margem[0]
    H = max([Hm] + [g.shape[0] for g in guias]) + margem[1]
    mt = _na_tela(mestre, W, H)
    oy, ox = H - Hm, (W - Wm) // 2
    out, rel = [], []
    for i, g in enumerate(guias):
        guia = _na_tela(g, W, H)
        q = guia.copy()
        for p in pecas:
            x, y, w, h = (int(v) for v in p["rect"])
            peca = identidade.recortar(mt, (ox + x, oy + y, w, h))
            r = identidade.achar(guia, peca, (ox + x, oy + y), int(p.get("busca", raio)), bool(p.get("espelho", False)))
            colou = r["erro"] <= float(p.get("erro_max", erro_max))
            if colou:
                modo = p.get("apagar", "nada")
                if modo == "faixa":
                    q[max(0, r["y"]):r["y"] + h] = 0
                elif modo == "caixa":
                    q[max(0, r["y"]):r["y"] + h, max(0, r["x"]):r["x"] + w] = 0
                elif modo != "nada":
                    raise ValueError(f"peça '{p.get('nome')}': apagar '{modo}' inválido (faixa, caixa ou nada)")
                q = identidade.colar(q, peca, r["x"], r["y"], r["espelho"])
            rel.append({"quadro": i, "nome": p.get("nome", "?"), "dx": r["x"] - ox - x, "dy": r["y"] - oy - y,
                        "espelho": r["espelho"], "erro": round(r["erro"], 1), "colou": colou})
        out.append(q)
    estab = {}
    for p in pecas:
        x, y, w, h = (int(v) for v in p["rect"])
        rs = [r for r in rel if r["nome"] == p.get("nome", "?")]
        if not rs:
            continue
        def corte(q, r):
            yy, xx = oy + y + r["dy"], ox + x + r["dx"]
            return q[max(0, yy):yy + h, max(0, xx):xx + w]
        base = corte(out[0], rs[0])
        estab[p.get("nome", "?")] = [int((np.abs(corte(q, r).astype(int) - base.astype(int)).sum(-1) > 0).sum())
                                     if corte(q, r).shape == base.shape else -1 for q, r in zip(out, rs)]
    return {"quadros": out, "mestre": mt, "relatorio": rel, "estabilidade": estab}


def colagem(mestre_img, guia, pecas: list[dict], paleta_hex: list[str] | None = None, cores: int = 16,
            linhas: int | None = None, colunas: int | None = None, prancha: bool | None = None,
            cor_fundo: str = "auto", raio: int = 4) -> dict:
    """Tudo de uma vez: conceito-mestre (imagem) + guia (PNG em prancha/grade, pasta ou lista RGBA) + peças."""
    from . import entradas
    mestre, pal, info = mestre_de_conceito(mestre_img, paleta_hex, cores, cor_fundo)
    if isinstance(guia, list):
        quadros = guia
    else:
        if prancha is None:
            prancha = linhas is None and colunas is None and str(guia).lower().endswith((".png", ".jpg", ".webp"))
        quadros = entradas.carregar(guia, linhas, colunas, None, prancha, cor_fundo)
    guias = guias_na_escala(quadros, mestre.shape[0], pal, cor_fundo)
    r = montar(mestre, guias, pecas, raio)
    r.update({"paleta": pal, "grade": info, "guias": guias})
    return r


def _peca(txt: str) -> dict:
    """'nome:x,y,w,h[:faixa|caixa|nada]' → dict de peça."""
    partes = txt.split(":")
    if len(partes) not in (2, 3):
        raise ValueError(f"peça '{txt}': use nome:x,y,w,h[:faixa|caixa|nada]")
    rect = [int(v) for v in partes[1].split(",")]
    if len(rect) != 4:
        raise ValueError(f"peça '{txt}': o rect tem 4 números (x,y,w,h)")
    return {"nome": partes[0], "rect": rect, "apagar": partes[2] if len(partes) == 3 else "nada"}


def main(argv=None) -> int:
    """horys colagem MESTRE --saida PASTA [GUIA --peca nome:x,y,w,h[:faixa] ...]. Sem GUIA/--peca grava só o
    mestre e a régua (para escolher os rects). Roda local, sem daemon nem Aseprite."""
    import argparse
    import json
    from pathlib import Path

    from . import spritesheet
    ap = argparse.ArgumentParser(prog="horys colagem", description=main.__doc__)
    ap.add_argument("mestre", help="conceito aprovado (pixel art ampliada)")
    ap.add_argument("guia", nargs="?", help="quadros do gerador: prancha PNG, grade (com --linhas/--colunas) ou pasta")
    ap.add_argument("--saida", required=True)
    ap.add_argument("--peca", action="append", default=[], help="nome:x,y,w,h[:faixa|caixa|nada]; repita; a última fica por cima")
    ap.add_argument("--linhas", type=int)
    ap.add_argument("--colunas", type=int)
    ap.add_argument("--paleta", help="#hex separados por vírgula (padrão: tirada do mestre)")
    ap.add_argument("--cores", type=int, default=16)
    ap.add_argument("--busca", type=int, default=4)
    ap.add_argument("--ms", type=int, default=160)
    ap.add_argument("--nome", default="colagem")
    a = ap.parse_args(argv)
    saida = Path(a.saida)
    saida.mkdir(parents=True, exist_ok=True)
    pal = [h.strip() for h in a.paleta.split(",")] if a.paleta else None
    if not a.guia or not a.peca:
        mestre, pal, info = mestre_de_conceito(a.mestre, pal, a.cores)
        Image.fromarray(mestre).save(saida / "mestre.png")
        k = 8
        Image.fromarray(mestre).resize((mestre.shape[1] * k, mestre.shape[0] * k), Image.NEAREST).save(saida / "mestre_8x.png")
        print(f"mestre {info['tamanho'][0]}x{info['tamanho'][1]} (bloco {info['bloco']} px, {len(pal)} cores) → "
              f"{saida / 'mestre.png'}; ampliado 8x em mestre_8x.png (1 px do mestre = 8 px) para escolher os rects")
        return 0
    r = colagem(a.mestre, a.guia, [_peca(p) for p in a.peca], pal, a.cores, a.linhas, a.colunas, None, "auto",
                a.busca)
    Image.fromarray(r["mestre"]).save(saida / "mestre.png")
    for i, q in enumerate(r["quadros"]):
        Image.fromarray(q).save(saida / f"quadro_{i:02d}.png")
    arqs = spritesheet.salvar(r["quadros"], saida, a.nome, a.ms, a.nome)
    json.dump({"paleta": r["paleta"], "grade": r["grade"], "estabilidade": r["estabilidade"],
               "relatorio": r["relatorio"]}, open(saida / "colagem.json", "w", encoding="utf-8"), indent=1)
    falhou = [f"{x['nome']}@{x['quadro']}" for x in r["relatorio"] if not x["colou"]]
    print(f"{len(r['quadros'])} quadros · estabilidade (px ≠ quadro 0): {r['estabilidade']}"
          + (f" · NÃO coladas: {', '.join(falhou)}" if falhou else "") + f" · folha {arqs['png']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
