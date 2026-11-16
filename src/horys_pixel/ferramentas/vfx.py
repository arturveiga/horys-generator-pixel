"""Ferramentas de VFX pelo pixelfx (perfeicao.md, C8). Não precisam do Aseprite aberto.

horys_vfx_listar  efeitos do pixelfx (id, loop, duração, tamanho nativo, se desenha o boneco)
horys_vfx_gerar   efeito -> tira PNG + JSON (durações) recolorida na rampa do personagem + prévia

A lógica vive em horys_pixel.vfx. Os efeitos são do pixelfx (patch-gg, MIT), chamado pelo node num clone local.
"""
from __future__ import annotations

import asyncio

from .. import pixels
from .. import vfx as V
from .registro import BOOL, INT, LISTA_STR, STR, ErroFerramenta, ferramenta, imagem, texto


@ferramenta("horys_vfx_listar", """
Lista os efeitos do pixelfx (patch-gg, MIT; ~244 efeitos de pixel art em código: fogo, explosões, gelo, raio,
arcano, sagrado, sombra, status, natureza, clima, UI, coleta, transições, bichos). filtro: palavras que precisam
aparecer no id ou na descrição (ex.: "fire", "heal", "explosion"). Cada linha: id, loop/once, duração, tamanho
nativo e [boneco] quando o efeito desenha o boneco cinza do pixelfx junto (prefira os sem boneco para VFX solto).
""", {"filtro": STR, "categoria": STR, "sem_boneco": BOOL})
async def vfx_listar(ctx, a: dict) -> list:
    try:
        efeitos = await asyncio.to_thread(V.listar, a.get("filtro"))
    except V.ErroVfx as e:
        raise ErroFerramenta(str(e))
    if a.get("categoria"):
        efeitos = [e for e in efeitos if e["categoria"] == a["categoria"]]
    if a.get("sem_boneco"):
        efeitos = [e for e in efeitos if not e["com_boneco"]]
    linhas = [f"{e['id']}  {'loop' if e['loop'] else 'once'} {e['duracao_s']:g}s  "
              f"{e['tamanho'][0]}x{e['tamanho'][1]}{'  [boneco]' if e['com_boneco'] else ''}  {e['descricao']}"
              for e in efeitos]
    return [texto(f"{len(efeitos)} efeitos do pixelfx (MIT, patch-gg):\n" + "\n".join(linhas))]


@ferramenta("horys_vfx_gerar", """
Gera um VFX do pixelfx recolorido pela rampa do personagem. efeito: id de horys_vfx_listar (ex.: fire/campfire).
rampa: lista de hex do escuro ao claro (a do personagem); o pixelfx recebe a rampa e depois cada pixel vira a cor
da rampa pela luminância (só cores da rampa, alfa binário: abaixo de alfa_minimo some). quadros: quantos quadros
(amostrados por igual; a duração total se mantém; vazio = todos). tamanho: lado do quadrado final em px (recorta na
caixa visível e centraliza; se não couber, reduz e avisa). Grava em saida: <nome>.png (tira horizontal),
<nome>.json (formato do Aseprite, durações em ms, pivô, crédito MIT) e <nome>_previa.png.
""", {"efeito": STR, "rampa": LISTA_STR, "saida": STR, "tamanho": INT, "quadros": INT, "seed": INT,
      "alfa_minimo": INT, "paleta_nativa": BOOL, "nome": STR}, ["efeito", "rampa", "saida"])
async def vfx_gerar(ctx, a: dict) -> list:
    try:
        r = await asyncio.to_thread(
            V.gerar, a["efeito"], a["saida"], list(a["rampa"]),
            tamanho=int(a["tamanho"]) if a.get("tamanho") else None,
            quadros=int(a["quadros"]) if a.get("quadros") else None,
            seed=int(a["seed"]) if a.get("seed") is not None else None,
            alfa_minimo=int(a["alfa_minimo"]) if a.get("alfa_minimo") is not None else 128,
            paleta_nativa=a.get("paleta_nativa", True) is not False,
            nome=a.get("nome") or None)
    except V.ErroVfx as e:
        raise ErroFerramenta(str(e))
    i = r.info
    msg = (f"{i['efeito']}: {i['quadros']} quadros (de {i['quadros_pixelfx']}), {i['tamanho'][0]}x{i['tamanho'][1]} px, "
           f"{i['duracao_ms']} ms, {'loop' if i['loop'] else 'uma vez'}, pivô {i['pivo']}, {len(i['rampa'])} cores.\n"
           f"PNG: {r.png}\nJSON: {r.json}\nPrévia: {r.previa}")
    if i.get("aviso"):
        msg += f"\nAVISO: {i['aviso']}"
    if i["quadros_vazios"]:
        msg += f"\nAVISO: {i['quadros_vazios']} quadro(s) vazio(s) (alfa_minimo alto ou efeito que some)"
    return [texto(msg), imagem(pixels.png_b64(V.previa(r.quadros)))]
