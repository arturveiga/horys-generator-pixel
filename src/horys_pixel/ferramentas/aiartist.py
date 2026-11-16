"""Ferramentas portadas do aseprite-ai-artist (pebbly, MIT, v0.8.3), reimplementadas no horys.

horys_tileset          folha de tiles PNG -> TileSet do Godot 4 (.tres), grade ou blob47 com terreno; prancha-guia
horys_paleta_rampa     rampa escuro -> claro com giro de matiz a partir de uma cor base
horys_paleta_analisar  quase iguais (ΔE), rampas achadas, contraste, uso e cores fora da paleta
horys_guarda_correcao  foto da camada, correção, desfaz se mexeu em mais de 1/4 dos pixels opacos; até 3 rodadas
horys_cel_tween        tween / oscilação / cópia de uma camada por vários quadros (deslocamento de pixels)

A lógica pura vive em horys_pixel.tileset, horys_pixel.paleta_ops e horys_pixel.aiartist.
Copyright (c) pebbly (aseprite-ai-artist), licença MIT, para as partes derivadas.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from .. import aiartist as AI
from .. import paleta_ops as PO
from .. import pixels
from .. import tileset as TS
from .desenho import alvo, escrever_rgba, ler_rgba
from .registro import BOOL, INT, STR, ErroFerramenta, ferramenta, imagem, texto

NUM = {"type": "number"}
LISTA = {"type": "array", "items": {"type": "string"}}


def _abrir(caminho: str) -> np.ndarray:
    p = Path(caminho)
    if not p.is_file():
        raise ErroFerramenta(f"arquivo não encontrado: {caminho}")
    return np.array(Image.open(p).convert("RGBA"))


def _amostras(cores: list[str], k: int = 24) -> Image.Image:
    img = Image.new("RGBA", (k * len(cores), k), (0, 0, 0, 0))
    for i, c in enumerate(cores):
        img.paste(Image.new("RGBA", (k, k), pixels.hex_rgba(c)), (i * k, 0))
    return img


# ------------------------------------------------------------------ tileset

@ferramenta("horys_tileset", """
TileSet do Godot 4 (.tres, format=3) a partir de uma folha de tiles PNG. Não precisa do Aseprite.
• layout 'grid' (padrão): um tile por slot com pixel.
• layout 'blob47': 47 tiles de autotile em ordem canônica (máscaras de 8 vizinhos reduzidas, em ordem crescente,
  linha a linha) a partir do slot 'pular'; o .tres sai com terrain_set 0 (cantos e lados) e os peering bits.
  'mascaras' (47 inteiros) troca a ordem se a folha foi desenhada em outra.
• acao 'guia' {saida:.png, tile?, colunas?}: grava a prancha-guia do blob47 (molde para desenhar à mão na ordem
  que o 'blob47' espera).
'res' é o caminho da textura no projeto Godot (padrão res://<nome da folha>). Grava também <saida>.json.
""", {"acao": STR, "folha": STR, "saida": STR, "tile": INT, "tile_w": INT, "tile_h": INT, "layout": STR,
      "res": STR, "margem": INT, "espaco": INT, "pular": INT, "mascaras": {"type": "array", "items": INT},
      "nome_terreno": STR, "cor_terreno": STR, "incluir_vazios": BOOL, "colunas": INT}, ["saida"])
async def tileset_ferramenta(ctx, a: dict) -> list:
    saida = Path(a["saida"])
    saida.parent.mkdir(parents=True, exist_ok=True)
    if a.get("acao") == "guia":
        t = int(a.get("tile") or 16)
        g = TS.guia_blob47(t, int(a.get("colunas") or 8), mascaras=a.get("mascaras") or None)
        Image.fromarray(g).save(saida)
        return [texto(f"prancha-guia blob47: 47 tiles de {t}×{t}, {int(a.get('colunas') or 8)} colunas, em "
                      f"{saida}"), imagem(pixels.png_b64(pixels.ampliar(g)))]
    if not a.get("folha"):
        raise ErroFerramenta("passe 'folha' (PNG dos tiles) ou use acao 'guia'")
    folha = _abrir(a["folha"])
    tw = int(a.get("tile_w") or a.get("tile") or 16)
    th = int(a.get("tile_h") or a.get("tile") or tw)
    try:
        f = TS.fatiar(folha, tw, th, int(a.get("margem") or 0), int(a.get("espaco") or 0))
        r = TS.godot_tres(f, a.get("res") or f"res://{Path(a['folha']).name}", a.get("layout") or "grid",
                          pular=int(a.get("pular") or 0), mascaras=a.get("mascaras") or None,
                          nome_terreno=a.get("nome_terreno") or "terreno",
                          cor_terreno=a.get("cor_terreno") or "#5a9e4b",
                          incluir_vazios=bool(a.get("incluir_vazios")))
    except ValueError as e:
        raise ErroFerramenta(str(e))
    if saida.suffix.lower() != ".tres":
        saida = saida.with_suffix(".tres")
    saida.write_text(r.texto, encoding="utf-8")
    info = {"tres": str(saida), "folha": str(a["folha"]), "tile": [tw, th], "colunas": f.colunas,
            "linhas": f.linhas, "tiles": r.tiles, "layout": a.get("layout") or "grid",
            "terreno": {f"{f.coord(s)[0]}:{f.coord(s)[1]}": m for s, m in r.terreno.items()}, "avisos": r.avisos}
    saida.with_suffix(".json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    msg = f"TileSet Godot 4: {r.tiles} tiles de {tw}×{th} ({f.colunas}×{f.linhas} slots) em {saida}."
    if r.terreno:
        msg += " Terreno blob47 no terrain_set 0 (cantos e lados)."
    if r.avisos:
        msg += " AVISOS: " + " | ".join(r.avisos)
    return [texto(msg)]


# ------------------------------------------------------------------ paleta

@ferramenta("horys_paleta_rampa", """
Rampa com giro de matiz, do escuro ao claro, com a base no meio: a sombra gira para o azul e perde um pouco de
saturação, a luz gira para o amarelo e satura (rampa que só muda o brilho é a marca de pixel art de máquina).
'passos' (5), 'abertura' (0,55: quanto vai à sombra e à luz), 'giro' (25 graus no extremo).
'adicionar': true acrescenta a rampa à paleta do sprite aberto no Aseprite.
""", {"base": STR, "passos": INT, "abertura": NUM, "giro": NUM, "adicionar": BOOL}, ["base"])
async def paleta_rampa(ctx, a: dict) -> list:
    try:
        r = PO.rampa(a["base"], int(a.get("passos") or 5), float(a.get("abertura") or 0.55),
                     float(a["giro"]) if a.get("giro") is not None else 25.0)
    except ValueError as e:
        raise ErroFerramenta(str(e))
    msg = f"rampa de {a['base']}: {' '.join(r)}"
    if a.get("adicionar"):
        atuais = (await ctx.aseprite("paleta", {"acao": "ler"})).get("cores") or []
        novas = atuais + [c for c in r if c not in atuais]
        await ctx.aseprite("paleta", {"acao": "definir", "cores": novas})
        msg += f" (paleta do sprite agora com {len(novas)} cores)"
    return [texto(msg), imagem(pixels.png_b64(_amostras(r)))]


@ferramenta("horys_paleta_analisar", """
Analisa uma paleta: pares quase iguais (ΔE76 < 'limiar', padrão 3), rampas achadas (matiz/croma OKLCH, escuro ->
claro) com o giro de matiz de cada uma, contraste (extremos e o par usado de menor contraste) e, com imagem, uso por
cor, cores da arte fora da paleta e entradas sem uso. Fonte: 'cores' e/ou 'imagem' (PNG); sem nenhuma das duas
(ou com 'ao_vivo': true) lê a paleta e o quadro 'quadro' do sprite aberto no Aseprite.
""", {"cores": LISTA, "imagem": STR, "limiar": NUM, "ao_vivo": BOOL, "quadro": INT})
async def paleta_analisar(ctx, a: dict) -> list:
    cores = a.get("cores") or None
    img = _abrir(a["imagem"]) if a.get("imagem") else None
    if a.get("ao_vivo") or (cores is None and img is None):
        st = await ctx.sprite_atual()
        q = int(a.get("quadro") if a.get("quadro") is not None else st["sprite"].get("quadro_ativo") or 0)
        img = await ler_rgba(ctx, None, q)
        cores = cores or (await ctx.aseprite("paleta", {"acao": "ler"})).get("cores") or None
    try:
        r = PO.analisar(cores, img, float(a.get("limiar") or 3.0))
    except ValueError as e:
        raise ErroFerramenta(str(e))
    linhas = [f"Paleta: {r['n']} cores — {r['veredito']}."]
    c = r["contraste"]
    linhas.append(f"Contraste: {c['mais_escura']} → {c['mais_clara']} = {c['razao_extremos']}:1 "
                  f"(OKLab L {c['L_min']}–{c['L_max']})"
                  + (f"; menor par {c['menor_par']['a']}/{c['menor_par']['b']} {c['menor_par']['razao']}:1"
                     if c["menor_par"] else ""))
    for rp in r["rampas"]:
        linhas.append(f"Rampa {'neutra ' if rp['neutra'] else ''}{' '.join(rp['cores'])} "
                      f"(giro {rp['giro_matiz']}°)")
    if r["quase_iguais"]:
        linhas.append("Quase iguais: " + ", ".join(f"{d['a']}≈{d['b']} ({d['delta_e']})"
                                                   for d in r["quase_iguais"][:8]))
    if r["fora_da_paleta"]:
        linhas.append("Fora da paleta: " + ", ".join(f"{d['cor']} ({d['pixels']} px)"
                                                     for d in r["fora_da_paleta"][:8]))
    if r["sem_uso"]:
        linhas.append(f"{len(r['sem_uso'])} cor(es) sem uso.")
    return [texto("\n".join(linhas)), texto(json.dumps(r, ensure_ascii=False))]


# ------------------------------------------------------------------ guarda do loop de correção

_GUARDAS: dict[tuple, AI.GuardaCorrecao] = {}


async def _chave(ctx, a: dict) -> tuple[tuple, str, int]:
    if not a.get("camada"):
        raise ErroFerramenta("passe 'camada' (a guarda vale para uma camada num quadro)")
    camada, q, st = await alvo(ctx, {**a, "criar_camada": False})
    s = st["sprite"]
    return (s.get("horys_id") or s.get("arquivo"), camada, q), camada, q


async def _restaurar(ctx, camada: str, q: int, foto: np.ndarray):
    await escrever_rgba(ctx, camada, q, 0, 0, foto, np.ones(foto.shape[:2], np.uint8))


def _texto_rodada(r: AI.Rodada, g: AI.GuardaCorrecao) -> str:
    return (f"rodada {r.numero}: {r.mudados} px mudaram ({r.fracao:.0%} de {r.opacos} opacos) — {r.motivo}. "
            f"Rodadas aceitas: {g.aceitas}/{g.max_rodadas}.")


@ferramenta("horys_guarda_correcao", """
Guarda do loop de correção (fix, não redesenho). Por camada e quadro:
• 'marcar' — tira a foto da camada (recomeça a contagem de rodadas).
• 'aplicar' {passos:[{ferramenta,args}]} — tira a foto se não houver, roda os passos (ex.: horys_pixel_map) e
  confere: se mexeu em mais de 'limite' (1/4) dos pixels opacos, DESFAZ (repõe a foto) e recusa.
• 'conferir' — confere o que mudou desde a foto (correção feita por outras chamadas); recusada = repõe a foto.
• 'restaurar' — repõe a foto. • 'estado' — rodadas e limite.
No máximo 3 rodadas aceitas; depois disso toda correção é desfeita: mostre ao Artur e pergunte.
""", {"acao": STR, "camada": STR, "quadro": INT, "passos": {"type": "array"}, "limite": NUM,
      "max_rodadas": INT}, ["acao", "camada"])
async def guarda_correcao(ctx, a: dict) -> list:
    acao = a["acao"]
    chave, camada, q = await _chave(ctx, a)
    g = _GUARDAS.get(chave)
    if acao == "marcar" or (acao == "aplicar" and g is None):
        g = AI.GuardaCorrecao(await ler_rgba(ctx, camada, q), float(a.get("limite") or AI.LIMITE_REDESENHO),
                              int(a.get("max_rodadas") or AI.MAX_RODADAS))
        _GUARDAS[chave] = g
        if acao == "marcar":
            n = int((g.foto[..., 3] > 0).sum())
            return [texto(f"foto de '{camada}' q{q}: {n} pixels opacos; limite {g.limite:.0%}, "
                          f"{g.max_rodadas} rodadas")]
    if g is None:
        raise ErroFerramenta(f"sem foto de '{camada}' q{q}: use acao 'marcar' antes")
    if acao == "estado":
        return [texto(f"'{camada}' q{q}: {g.aceitas}/{g.max_rodadas} rodadas aceitas, limite {g.limite:.0%}; "
                      + "; ".join(f"r{r.numero} {'ok' if r.aceita else 'recusada'} {r.fracao:.0%}"
                                  for r in g.rodadas))]
    if acao == "restaurar":
        await _restaurar(ctx, camada, q, g.foto)
        return [texto(f"'{camada}' q{q} restaurada da foto")]
    if acao == "aplicar":
        from .registro import REGISTRO
        for i, p in enumerate(a.get("passos") or []):
            f = REGISTRO.get(p.get("ferramenta"))
            if f is None or f.nome in ("horys_lote", "horys_guarda_correcao"):
                await _restaurar(ctx, camada, q, g.foto)
                raise ErroFerramenta(f"passo {i}: ferramenta inválida {p.get('ferramenta')} (camada restaurada)")
            try:
                await f.funcao(ctx, p.get("args") or {})
            except Exception:
                await _restaurar(ctx, camada, q, g.foto)
                raise
    elif acao != "conferir":
        raise ErroFerramenta(f"acao desconhecida: {acao} (marcar, aplicar, conferir, restaurar, estado)")
    foto = g.foto
    r = g.conferir(await ler_rgba(ctx, camada, q))
    msg = _texto_rodada(r, g)
    if not r.aceita and r.mudados:
        await _restaurar(ctx, camada, q, foto)
        msg += " Camada restaurada."
    elif g.esgotada:
        msg += " Rodadas esgotadas: mostre ao Artur e pergunte se segue."
    return [texto(msg)]


# ------------------------------------------------------------------ movimento de célula

@ferramenta("horys_cel_tween", """
Move uma camada ao longo dos quadros 'de'..'ate' (0-based), a partir do quadro 'de':
• modo 'tween' {dx, dy, curva: linear|ease_in|ease_out|ease_in_out|smoothstep} — chega em (dx,dy) no 'ate'.
• modo 'oscilar' {amp_x, amp_y, periodo?, fase?} — seno por quadro (balanço, flutuar, respirar).
• modo 'copiar' — repete o quadro 'de' nos outros (no lugar de "linkar": edição posterior NÃO se propaga).
A ponte não move célula: o tween é deslocamento de pixels, quadro a quadro; o que sai da tela se perde nos quadros
deslocados. Não faz tween de opacidade. Cria os quadros que faltarem.
""", {"camada": STR, "de": INT, "ate": INT, "modo": STR, "dx": INT, "dy": INT, "curva": STR, "amp_x": NUM,
      "amp_y": NUM, "periodo": INT, "fase": NUM}, ["camada", "de", "ate"])
async def cel_tween(ctx, a: dict) -> list:
    de, ate = int(a["de"]), int(a["ate"])
    if ate <= de or de < 0:
        raise ErroFerramenta("precisa de 0 <= de < ate")
    camada, _, _ = await alvo(ctx, {"camada": a["camada"], "quadro": ate, "criar_camada": False})
    modo = a.get("modo") or "tween"
    n = ate - de + 1
    try:
        if modo == "tween":
            desl = AI.deslocamentos_tween(n, int(a.get("dx") or 0), int(a.get("dy") or 0), a.get("curva") or "linear")
        elif modo in ("oscilar", "oscillate"):
            desl = AI.deslocamentos_oscilar(n, float(a.get("amp_x") or 0), float(a.get("amp_y") or 0),
                                            a.get("periodo"), float(a.get("fase") or 0))
        elif modo == "copiar":
            desl = [(0, 0)] * n
        else:
            raise ValueError(f"modo desconhecido: {modo} (tween, oscilar, copiar)")
    except ValueError as e:
        raise ErroFerramenta(str(e))
    origem = await ler_rgba(ctx, camada, de)
    tudo = np.ones(origem.shape[:2], np.uint8)
    for i, (dx, dy) in enumerate(desl):
        if i == 0 and (dx, dy) == (0, 0):
            continue
        await escrever_rgba(ctx, camada, de + i, 0, 0, AI.deslocar(origem, dx, dy), tudo)
    lista = " ".join(f"q{de + i}({dx:+d},{dy:+d})" for i, (dx, dy) in enumerate(desl))
    return [texto(f"'{camada}' {modo} em {n} quadros: {lista}")]
