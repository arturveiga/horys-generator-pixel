"""Ferramenta do guia de pose do SpriteKiln (perfeicao.md, §13, C9). Não precisa do Aseprite aberto.

horys_guia_kiln   spec do SpriteKiln -> um PNG por quadro de cada ação × direção, uma cor chapada do contrato por
                  parte do corpo (mapa de partes que `mapa_partes.rotulos` lê direto) + guia.json

A lógica vive em horys_pixel.guia_kiln. A spec original não é editada; a derivada e o render bruto ficam em
<saida>/_kiln/.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from .. import guia_kiln as G
from .. import pixels
from .registro import INT, OBJ, STR, ErroFerramenta, ferramenta, imagem, texto

LISTA = {"type": "array", "items": {"type": "string"}}


@ferramenta("horys_guia_kiln", """
Guia de pose de uma spec do SpriteKiln: renderiza cada ação × direção no tamanho final com UMA COR CHAPADA POR
PARTE (sem sombreado, contorno, linha interna, dither, brilho nem sombra) nas cores do contrato de partes
(cabeca ciano, tronco laranja, braco-esq verde, braco-dir roxo, perna-esq amarelo, perna-dir vermelho, arma rosa,
enfeite branco). Grava <saida>/<anim>_<dir>_NN.png e <saida>/guia.json (parte -> cor, motivos, durações, avisos).
Lados: esquerda/direita da IMAGEM na vista de frente (s): parte _L do spec = braco-dir/perna-dir; _R = -esq; a cor
fica presa à parte em todas as direções. Todas as direções são renderizadas de verdade (mirror desligado).
'mapeamento' ({parte: categoria}) corrige a classificação automática (mapeie a parte _L; a gêmea _R segue).
anims/dirs: listas (["idle", "walk"], ["s", "e"]); size: tamanho do quadro (padrão o da spec).
A spec original não é editada.
""", {"spec": STR, "saida": STR, "anims": LISTA, "dirs": LISTA, "size": INT,
      "mapeamento": OBJ}, ["spec", "saida"])
async def guia_kiln(ctx, a: dict) -> list:
    if not Path(a["spec"]).is_file():
        raise ErroFerramenta(f"spec não encontrada: {a['spec']}")
    if not G.spritekiln_disponivel():
        raise ErroFerramenta("spritekiln não está instalado (uv tool install spritekiln)")
    try:
        r = await asyncio.to_thread(G.renderizar, a["spec"], a["saida"], a.get("anims"), a.get("dirs"),
                                    int(a["size"]) if a.get("size") else None, a.get("mapeamento") or None)
    except (ValueError, RuntimeError, FileNotFoundError) as e:
        raise ErroFerramenta(str(e))
    clipes = r["clipes"]
    if not clipes:
        raise ErroFerramenta("o render não devolveu nenhum quadro")
    # prévia: a primeira ação em todas as direções (até 48 quadros)
    primeira = next(iter(clipes)).rsplit("_", 1)[0]
    quadros = [q for k, qs in clipes.items() if k.rsplit("_", 1)[0] == primeira for q in qs][:48]
    contagem: dict[str, int] = {}
    for c in r["partes"].values():
        contagem[c] = contagem.get(c, 0) + 1
    msg = (f"guia de pose: {len(r['arquivos'])} quadros em {len(clipes)} clipes ({', '.join(clipes)}). "
           f"Partes por cor: {contagem}. Índice: {r['indice']}. Spec derivada: {r['spec_guia']}. "
           f"Prévia: {primeira} em todas as direções.")
    if r["avisos"]:
        msg += " AVISOS: " + " | ".join(r["avisos"])
    return [texto(msg), imagem(pixels.png_b64(pixels.filmstrip(quadros)))]
