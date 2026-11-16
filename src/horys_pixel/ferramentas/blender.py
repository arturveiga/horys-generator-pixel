"""Ferramentas do pipeline Blender do horys (perfeicao.md §14): paleta (passo 0), inspecionar, render e recolor.

A paleta vem ANTES de tudo e o Artur aprova o paleta.json (horys_aprovar_arquivo); o render final recusa paleta
não aprovada (a prévia não). O modelo 3D dá consistência e movimento; o horys dá a paleta, o pixel e o acabamento.
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

from .. import pixels
from .. import travas as T
from .registro import BOOL, INT, STR, ErroFerramenta, ferramenta, imagem, texto


@ferramenta("horys_blender_paleta", """
PASSO 0 do pipeline Blender: a PALETA da arte. Sem 'familias': propõe as cores-base do 'conceito' (k-médias OKLab
sem o fundo, 'n' cores, padrão 8) para você dar nome às famílias. Com 'familias' [{nome, base #hex, tons 2|3,
tipo toon|emissivo, rampa (opcional, pronta)}]: monta as rampas com giro de matiz (a base fica no meio; sombra
para o azul, luz para o amarelo), a 'tinta' do contorno, confere ≤ 20 cores e quase-iguais, grava
<saida>/paleta.json e paleta.png. Depois mostre ao Artur e registre o sim com horys_aprovar_arquivo(paleta.json):
o render final recusa paleta não aprovada.
""", {"saida": STR, "conceito": STR, "n": INT, "familias": {"type": "array", "items": {"type": "object"}},
      "tinta": STR}, ["saida"])
async def blender_paleta(ctx, a: dict) -> list:
    from ..blender import paleta as BP
    out = Path(a["saida"])
    out.mkdir(parents=True, exist_ok=True)
    if not a.get("familias"):
        if not a.get("conceito"):
            raise ErroFerramenta("passe 'familias' ou um 'conceito' para propor as cores-base")
        im = np.asarray(Image.open(a["conceito"]).convert("RGBA"))
        prop = BP.propor(im, int(a.get("n") or 8))
        fams = [{"nome": f"familia_{i + 1}", "base": p["base"], "tons": 3} for i, p in enumerate(prop)]
        pal = BP.montar(fams)
        BP.amostra(pal).save(out / "paleta_proposta.png")
        return [texto("cores-base do conceito (da mais usada para a menos usada):\n"
                      + "\n".join(f"- {p['base']} ({p['fracao']:.0%})" for p in prop)
                      + "\nDê nome às famílias (o material de cada uma) e chame de novo com 'familias'."),
                imagem(pixels.png_b64(BP.amostra(pal)))]
    try:
        pal = BP.montar(a["familias"], a.get("tinta"))
    except (KeyError, ValueError) as e:
        raise ErroFerramenta(f"família inválida: {e}")
    (out / "paleta.json").write_text(json.dumps(pal, ensure_ascii=False, indent=1), encoding="utf-8")
    BP.amostra(pal).save(out / "paleta.png")
    msg = (f"paleta: {len(pal['cores'])} cores, {len(pal['familias'])} famílias, tinta {pal['tinta']}. Gravado em "
           f"{out / 'paleta.json'}. Mostre ao Artur e registre o sim (horys_aprovar_arquivo).")
    if pal["avisos"]:
        msg += " AVISOS: " + " | ".join(pal["avisos"])
    return [texto(msg), imagem(pixels.png_b64(BP.amostra(pal)))]


@ferramenta("horys_blender_inspecionar", """
Lista coleções (com as peças), empties, armatures, actions e materiais de um .blend, para montar a config do
personagem (rig por pivôs, regras de material). Roda o Blender headless; não altera o arquivo.
""", {"blend": STR}, ["blend"])
async def blender_inspecionar(ctx, a: dict) -> list:
    from .. import blender as B
    exe = B.achar_blender()
    if not exe:
        raise ErroFerramenta("Blender não encontrado (preferência 'blender')")
    tmp = Path(tempfile.mkdtemp(prefix="horys_insp_")) / "insp.json"
    script = Path(B.__file__).with_name("inspecionar.py")
    r = await asyncio.to_thread(subprocess.run, [exe, "-b", a["blend"], "--python", str(script), "--", str(tmp)],
                                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    if not tmp.exists():
        raise ErroFerramenta("o Blender não leu o arquivo:\n" + (r.stdout + r.stderr)[-1500:])
    return [texto(tmp.read_text(encoding="utf-8")[:20000])]


@ferramenta("horys_blender_render", """
RENDER do personagem pelo pipeline Blender do horys: 'config' = JSON do personagem (blend, paleta, rig por pivôs,
papeis, materiais, camera {quadro, altura_px, angulo}, luz, acoes {nome: {tipo andar|idle|timeline, quadros, fps,
amplitude}}, direcoes, contorno fora|dentro|nenhum, partes). No Blender: rig de empties, andar/idle procedural (pé
de apoio parado, IK de 2 segmentos), toon com a paleta e limiares calibrados pela área (a base domina), câmera do
jogo enquadrada por todas as poses, lote ações × direções e o passe de partes. No pós: paleta travada, pixel solto,
contorno 1 px, folha/JSON/GIF por ação_direção, prancha.png, personagem.aseprite (tags) e partes/. 'previa': 4
quadros por direção (não exige paleta aprovada). Leva de segundos a minutos (devolve id; horys_aguardar).
""", {"config": STR, "saida": STR, "previa": BOOL}, ["config", "saida"])
async def blender_render(ctx, a: dict) -> list:
    from .. import blender as B
    from ..blender import pos
    try:
        cfg = B.ler_config(a["config"])
    except (OSError, ValueError) as e:
        raise ErroFerramenta(str(e))
    if not cfg.get("paleta"):
        raise ErroFerramenta("config sem 'paleta': faça a paleta primeiro (horys_blender_paleta)")
    if not a.get("previa"):
        try:
            T.exigir_aprovado(cfg["paleta"], "a paleta")
        except T.Travado as e:
            raise ErroFerramenta("TRAVADO: " + str(e))
    pal = json.loads(Path(cfg["paleta"]).read_text(encoding="utf-8"))

    try:
        T.exigir_aprovado(cfg["blend"], "o modelo 3D")
    except T.Travado as e:
        raise ErroFerramenta("TRAVADO: " + str(e) + " Publique o .glb no Estúdio e espere o Artur aprovar o 3D.")

    def trabalho():
        r = B.rodar(cfg, pal, a["saida"], previa=bool(a.get("previa")))
        if not r["ok"]:
            return {"erro": "o Blender falhou", "log": r["log"]}
        rel = pos.processar(a["saida"], pal, cfg)
        return {"manifesto": {k: v for k, v in r["manifesto"].items() if k != "materiais"}, "pos": rel}

    if ctx is None:                    # chamada direta (testes, CLI)
        return [texto(json.dumps(trabalho(), ensure_ascii=False)[:6000])]
    i = ctx.pend.criar("blender", {"config": a["config"], "saida": a["saida"]})

    async def rodar():
        try:
            res = await asyncio.to_thread(trabalho)
            ctx.pend.resolver(i, res, estado="erro" if "erro" in res else "respondido")
        except Exception as e:          # noqa: BLE001
            ctx.pend.resolver(i, {"erro": str(e)}, estado="erro")
    asyncio.ensure_future(rodar())
    return [texto(f"id: {i}\nBlender renderizando em {a['saida']}. Chame horys_aguardar com id='{i}'; depois "
                  f"veja {Path(a['saida']) / 'prancha.png'}.")]


@ferramenta("horys_blender_recolor", """
RECOLOR depois do render (B7), sem rodar o Blender de novo: 'paleta' = o paleta.json novo (mesmas famílias, tons
trocados); cada cor antiga vira a nova da mesma família e posição na rampa. Refaz o pós (folhas, GIFs, prancha,
.aseprite) em 'saida'.
""", {"saida": STR, "paleta": STR, "config": STR}, ["saida", "paleta"])
async def blender_recolor(ctx, a: dict) -> list:
    from .. import blender as B
    from ..blender import pos
    saida = Path(a["saida"])
    velha_p = saida / "_render" / "paleta.json"
    if not velha_p.exists():
        raise ErroFerramenta(f"{velha_p} não existe: renderize antes (horys_blender_render)")
    velha = json.loads(velha_p.read_text(encoding="utf-8"))
    nova = json.loads(Path(a["paleta"]).read_text(encoding="utf-8"))
    cfg = B.ler_config(a["config"]) if a.get("config") else {"contorno": "fora"}
    mapa = pos.mapa_recolor(velha, nova)
    rel = await asyncio.to_thread(pos.processar, saida, velha, cfg, mapa)
    prancha = Path(rel["prancha"])
    res = [texto(f"recolor: {len(mapa)} cores trocadas. Prancha {prancha}.")]
    if prancha.is_file():
        im = Image.open(prancha)
        im.thumbnail((900, 900))
        res.append(imagem(pixels.png_b64(im)))
    return res


@ferramenta("horys_blender_3d", """
ETAPA DE APROVAÇÃO DO 3D (antes de qualquer pixel): exporta o modelo com o rig e cada ação da config como
<stem>_<acao>.glb animado, ao lado do .blend. O Artur abre no Estúdio, gira, vê as 8 direções no ângulo do jogo,
aponta defeitos no próprio modelo e aprova. Só depois disso horys_blender_render roda (trava).
""", {"config": STR}, ["config"])
async def blender_3d(ctx, a: dict) -> list:
    from .. import blender as B
    try:
        cfg = B.ler_config(a["config"])
    except (OSError, ValueError) as e:
        raise ErroFerramenta(str(e))
    r = await asyncio.to_thread(B.exportar_3d, cfg)
    if not r["ok"]:
        raise ErroFerramenta("o Blender falhou:\n" + r["log"][-1500:])
    arqs = [v["arquivo"] for v in r["manifesto"]["acoes"].values()]
    return [texto("3D animado pronto para o Estúdio (o Artur aprova antes do pixel):\n" + "\n".join(arqs))]
