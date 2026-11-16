"""Ferramentas do corpo-base Eldiran 32x32 (CC0) no fluxo Base + Pele (perfeicao.md, P3).

horys_base_eldiran  fatia o corpo nu da folha Eldiran: quadros 1x, base.png (3 vistas), base.json, mapas de partes
horys_pele_animar   pele feita por horys_vestir sobre base.png -> folhas por ação/direção (PNG+JSON+GIF)

A lógica pura vive em horys_pixel.base_eldiran. Nenhuma delas cria forma.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from .. import base_eldiran as B
from .. import pixels
from .registro import INT, STR, ErroFerramenta, ferramenta, imagem, texto


@ferramenta("horys_base_eldiran", """
Fatia o CORPO-BASE da Eldiran 32x32 (CC0; decisão do Artur 14/11: "usa a base do eldiran", só esqueleto, não régua)
em 'saida' (padrão art-src/base32/eldiran): quadros/<acao>_<dir>_NN.png (idle 1 + andar 4; s, n, e; w = e espelhado;
canvas 40x40, pés na mesma linha), base.png (3 vistas de descanso lado a lado, para horys_vestir), base.json
(layout, durações, origem, licença) e partes/<acao>_<dir>_NN.png (mapa de partes checado). As costas (n) são
derivadas da frente com o rosto apagado: a linha nua da folha não tem costas. 'folha': outra cópia da folha.
""", {"saida": STR, "folha": STR}, [])
async def base_eldiran(ctx, a: dict) -> list:
    try:
        info = B.extrair(a.get("saida") or B.SAIDA_PADRAO, a.get("folha") or B.FOLHA_PADRAO)
    except (FileNotFoundError, ValueError) as e:
        raise ErroFerramenta(str(e))
    out = Path(a.get("saida") or B.SAIDA_PADRAO)
    msg = (f"base Eldiran: {len(info['quadros'])} quadros em {out / 'quadros'}, base.png {info['canvas']} por "
           f"vista, licença {info['licenca']}.")
    if info["derivados"]:
        msg += " DERIVADO: " + " | ".join(info["derivados"])
    msg += (" PARTES REPROVADAS: " + " | ".join(info["partes_falhas"])) if info["partes_falhas"] else \
        " Mapas de partes: forma fechada ok em todos."
    base = np.array(Image.open(out / "base.png").convert("RGBA"))
    return [texto(msg), imagem(pixels.png_b64(Image.fromarray(base).resize(
        (base.shape[1] * 6, base.shape[0] * 6), Image.NEAREST)))]


@ferramenta("horys_pele_animar", """
Anima uma PELE sobre a base Eldiran: 'pele' = pele.png de horys_vestir feita sobre <base_dir>/base.png. A pele é
cortada por vista, levada a cada quadro de cada ação/direção pelos mapas de partes (pele.propagar), composta sobre
o quadro da base e gravada em 'saida' como <acao>_<dir>.png/.json/.gif (w = e espelhado) + animar.json. Aviso =
parte que muda de forma no quadro: limpar à mão.
""", {"base_dir": STR, "pele": STR, "saida": STR, "raio": INT}, ["base_dir", "pele", "saida"])
async def pele_animar(ctx, a: dict) -> list:
    try:
        r = B.animar_pele(a["base_dir"], a["pele"], a["saida"], raio=int(a.get("raio") or 6))
    except (FileNotFoundError, ValueError) as e:
        raise ErroFerramenta(str(e))
    msg = f"{len(r['folhas'])} folhas em {a['saida']}: {', '.join(r['folhas'])}."
    if r["avisos"]:
        msg += f" AVISOS ({len(r['avisos'])}): " + " | ".join(r["avisos"][:12])
    tira = np.array(Image.open(r["folhas"]["andar_s"]["png"]).convert("RGBA"))
    return [texto(msg), imagem(pixels.png_b64(Image.fromarray(tira).resize(
        (tira.shape[1] * 6, tira.shape[0] * 6), Image.NEAREST)))]
