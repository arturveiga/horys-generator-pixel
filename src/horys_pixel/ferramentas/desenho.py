"""Ferramentas de desenho: a ponte com o Aseprite, no formato barato de paleta + linhas."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .. import config, pixels
from .registro import BOOL, INT, OBJ, STR, ErroFerramenta, ferramenta, imagem, texto

RET = {"type": "object", "description": "{x,y,w,h} ou o texto 'selecao'",
       "properties": {"x": INT, "y": INT, "w": INT, "h": INT}}


def resumo_status(st: dict) -> str:
    s = st.get("sprite")
    if not s:
        return "Aseprite conectado, nenhum sprite aberto."
    cams = ", ".join(f"{c['nome']}{'' if c.get('visivel', True) else ' (oculta)'}" for c in s.get("camadas", []))
    tags = ", ".join(f"{t['nome']}[{t['de']}–{t['ate']}]" for t in s.get("tags", [])) or "nenhuma"
    ms = sorted({q.get("ms") for q in s.get("quadros", [])})
    return (f"Sprite: {s.get('arquivo')} — {s.get('largura')}×{s.get('altura')} {s.get('modo', 'rgb')}\n"
            f"Camadas (de baixo para cima): {cams}\nQuadros: {len(s.get('quadros', []))} (ms {ms}) · Tags: {tags}\n"
            f"Ativos: camada '{s.get('camada_ativa')}', quadro {s.get('quadro_ativo')}")


async def _status(ctx) -> dict:
    return await ctx.aseprite("status")


async def alvo(ctx, args: dict) -> tuple[str | None, int, dict]:
    """Camada e quadro do pedido (padrão: os ativos) e o status."""
    st = await ctx.sprite_atual()
    s = st["sprite"]
    camada = args.get("camada", s.get("camada_ativa"))
    quadro = int(args.get("quadro", s.get("quadro_ativo") or 0))
    nomes = [c["nome"] for c in s.get("camadas", [])]
    if camada is not None and camada not in nomes:
        if args.get("criar_camada", True):
            await ctx.aseprite("camada", {"acao": "criar", "nome": camada})
        else:
            raise ErroFerramenta(f"camada '{camada}' não existe (há: {', '.join(nomes)})")
    n = len(s.get("quadros", []))
    if quadro >= n:
        await ctx.aseprite("quadro", {"acao": "garantir", "total": quadro + 1})
    return camada, quadro, st


async def retangulo(ctx, args: dict, st: dict) -> tuple[int, int, int, int]:
    s = st["sprite"]
    r = args.get("rect") or args.get("ret")
    if r in ("selecao", "selection"):
        sel = await ctx.aseprite("selecao")
        if sel.get("vazia"):
            raise ErroFerramenta("não há seleção no Aseprite")
        return sel["x"], sel["y"], sel["w"], sel["h"]
    if isinstance(r, dict):
        return int(r.get("x", 0)), int(r.get("y", 0)), int(r.get("w", s["largura"])), int(r.get("h", s["altura"]))
    return 0, 0, int(s["largura"]), int(s["altura"])


async def ler_rgba(ctx, camada, quadro: int, x=0, y=0, w=None, h=None) -> np.ndarray:
    args = {"quadro": quadro, "x": x, "y": y}
    if w is not None:
        args.update(w=w, h=h)
    if camada is not None:
        args["camada"] = camada
    d = await ctx.aseprite("ler", args)
    return pixels.array_de_b64(d["rgba"], d["w"], d["h"]).copy()


async def escrever_rgba(ctx, camada, quadro: int, x: int, y: int, rgba: np.ndarray, masc: np.ndarray | None = None):
    h, w = rgba.shape[:2]
    if masc is None:
        masc = np.ones((h, w), np.uint8)
    if not masc.any():
        return 0
    d = await ctx.aseprite("escrever", {"camada": camada, "quadro": quadro, "x": x, "y": y, "w": w, "h": h,
                                        "rgba": pixels.b64_de_array(rgba),
                                        "mascara": pixels.b64_de_array(masc.astype(np.uint8))}, timeout=120)
    return d.get("escritos", int(masc.sum()))


# ------------------------------------------------------------------ status e arquivo

@ferramenta("horys_status", "Conexão com o Aseprite e o sprite ativo (tamanho, camadas de baixo para cima, quadros, "
            "tags). Coordenadas 0-based, (0,0) no canto de cima à esquerda; quadros e camadas 0-based.")
async def status(ctx, a):
    if not ctx.ponte.conectado:
        return [texto("Aseprite NÃO conectado. Peça ao usuário: abrir o Aseprite com a extensão Horys e conferir "
                      "o menu Horys › Conexão e painel. O horysd está rodando.")]
    return [texto(resumo_status(await _status(ctx)))]


@ferramenta("horys_sprite_novo", "Cria um sprite RGB transparente. Para asset do estilo prefira horys_asset_novo "
            "(quadro, pivô, camadas por parte, paleta e tags de uma vez).",
            {"largura": INT, "altura": INT, "nome": STR}, ["largura", "altura"])
async def sprite_novo(ctx, a):
    st = await ctx.aseprite("sprite_novo", {"largura": int(a["largura"]), "altura": int(a["altura"]),
                                            "nome": a.get("nome")})
    ctx.baseline.clear()
    return [texto(resumo_status(st))]


@ferramenta("horys_abrir", "Abre um arquivo (.aseprite, .png...) no Aseprite.", {"arquivo": STR}, ["arquivo"])
async def abrir(ctx, a):
    if not Path(a["arquivo"]).exists():
        raise ErroFerramenta(f"arquivo não existe: {a['arquivo']}")
    st = await ctx.aseprite("abrir", {"arquivo": str(Path(a["arquivo"]).resolve())})
    ctx.baseline.clear()
    return [texto(resumo_status(st))]


@ferramenta("horys_sprites", "Lista os sprites abertos no Aseprite; com 'indice' ou 'arquivo', ativa um deles.",
            {"indice": INT, "arquivo": STR})
async def sprites(ctx, a):
    if "indice" in a or "arquivo" in a:
        st = await ctx.aseprite("selecionar_sprite", {k: a[k] for k in ("indice", "arquivo") if k in a})
        ctx.baseline.clear()
    else:
        st = await _status(ctx)
    linhas = [f"{s['indice']}: {s['arquivo']}" for s in st.get("sprites", [])]
    return [texto("\n".join(linhas) + "\n\n" + resumo_status(st))]


@ferramenta("horys_salvar", "Salva o sprite. 'copia': salva uma cópia e o sprite continua com o nome atual. Só salva "
            "dentro das pastas permitidas e nunca sobrescreve sem 'sobrescrever': true.",
            {"arquivo": STR, "copia": BOOL, "sobrescrever": BOOL})
async def salvar(ctx, a):
    arq = a.get("arquivo")
    if not arq:
        st = await ctx.sprite_atual()
        arq = st["sprite"].get("arquivo")
        if not arq:
            raise ErroFerramenta("informe 'arquivo' para salvar este sprite")
    if arq:
        p = Path(arq).resolve()
        if not config.caminho_permitido(p):
            raise ErroFerramenta(f"pasta não permitida: {p.parent} (preferências: pastas_permitidas)")
        if p.exists() and not a.get("sobrescrever"):
            raise ErroFerramenta(f"já existe {p}; use outro nome ou 'sobrescrever': true se o usuário pediu")
        p.parent.mkdir(parents=True, exist_ok=True)
        arq = str(p)
    d = await ctx.aseprite("salvar", {"arquivo": arq, "copia": bool(a.get("copia"))})
    return [texto(f"salvo: {d.get('arquivo')}")]


# ------------------------------------------------------------------ estrutura

@ferramenta("horys_camada", "Camadas: acao criar|remover|renomear|propriedades|ordem|ativar. Ex.: "
            "{acao:'criar', nome:'cabeca', acima_de:'corpo'}, {acao:'ordem', nomes:[de baixo para cima]}, "
            "{acao:'propriedades', nome:'sombra', opacidade:77, visivel:true}.",
            {"acao": STR, "nome": STR, "novo": STR, "acima_de": STR, "abaixo_de": STR, "visivel": BOOL,
             "opacidade": INT, "nomes": {"type": "array", "items": STR}}, ["acao"])
async def camada(ctx, a):
    return [texto(resumo_status(await ctx.aseprite("camada", a)))]


@ferramenta("horys_quadro", "Quadros (0-based): acao criar|remover|duracao|ativar|garantir. Ex.: "
            "{acao:'criar', depois_de:2, copiar:true}, {acao:'duracao', todos:true, ms:100}, {acao:'garantir', total:8}.",
            {"acao": STR, "indice": INT, "depois_de": INT, "copiar": BOOL, "ms": INT, "todos": BOOL, "total": INT},
            ["acao"])
async def quadro(ctx, a):
    return [texto(resumo_status(await ctx.aseprite("quadro", a)))]


@ferramenta("horys_tag", "Tags de animação: {acao:'criar', nome:'idle', de:0, ate:7} ou {acao:'remover', nome}.",
            {"acao": STR, "nome": STR, "de": INT, "ate": INT}, ["acao", "nome"])
async def tag(ctx, a):
    return [texto(resumo_status(await ctx.aseprite("tag", a)))]


# ------------------------------------------------------------------ pixels

@ferramenta("horys_pixel_map", """Desenha pixels exatos: 'paleta' {letra: '#rrggbb'} + 'linhas' (uma string por linha).
'.' e espaço não mexem; uma letra mapeada para '#00000000' apaga. x/y deslocam o bloco. Carimbos: 'stamps'
{nome:{rows:[...], palette?}} + 'place' [[nome, x, y, 'h'|'v'|'hv'?], ...]. Dado grande: 'arquivo' = um .json com
esses mesmos campos. 'camada' (criada se faltar) e 'quadro' (0-based) usam os ativos se omitidos.""",
            {"paleta": OBJ, "linhas": {"type": "array", "items": STR}, "x": INT, "y": INT, "camada": STR,
             "quadro": INT, "stamps": OBJ, "place": {"type": "array"}, "arquivo": STR})
async def pixel_map(ctx, a):
    d = pixels.carregar_mapa(a)
    pal = d.get("paleta") or d.get("palette") or {}
    try:
        rgba, masc = pixels.compor_mapa(pal, d.get("linhas") or d.get("rows"), d.get("stamps"), d.get("place"))
    except ValueError as e:
        raise ErroFerramenta(str(e))
    camada, q, st = await alvo(ctx, d)
    x, y = int(d.get("x", 0)), int(d.get("y", 0))
    s = st["sprite"]
    h, w = rgba.shape[:2]
    # corta o que cai fora do sprite
    x0, y0 = max(0, -x), max(0, -y)
    x1, y1 = min(w, s["largura"] - x), min(h, s["altura"] - y)
    if x1 <= x0 or y1 <= y0:
        raise ErroFerramenta("o bloco cai inteiro fora do sprite")
    n = await escrever_rgba(ctx, camada, q, x + x0, y + y0, rgba[y0:y1, x0:x1], masc[y0:y1, x0:x1])
    fora = int(masc.sum()) - int(masc[y0:y1, x0:x1].sum())
    return [texto(f"{n} pixels em '{camada}' quadro {q}" + (f" ({fora} fora do sprite, ignorados)" if fora else ""))]


@ferramenta("horys_set_pixels", "Poucos pixels soltos: 'pixels' [[x, y, '#rrggbb'], ...].",
            {"pixels": {"type": "array"}, "camada": STR, "quadro": INT}, ["pixels"])
async def set_pixels(ctx, a):
    camada, q, st = await alvo(ctx, a)
    pts = a["pixels"]
    xs = [int(p[0]) for p in pts]
    ys = [int(p[1]) for p in pts]
    x0, y0 = min(xs), min(ys)
    rgba = np.zeros((max(ys) - y0 + 1, max(xs) - x0 + 1, 4), np.uint8)
    masc = np.zeros(rgba.shape[:2], np.uint8)
    for (x, y, c) in ((int(p[0]), int(p[1]), p[2]) for p in pts):
        rgba[y - y0, x - x0] = pixels.hex_rgba(c)
        masc[y - y0, x - x0] = 1
    n = await escrever_rgba(ctx, camada, q, x0, y0, rgba, masc)
    return [texto(f"{n} pixels em '{camada}' quadro {q}")]


@ferramenta("horys_ler_pixels", "Lê pixels no mesmo formato do horys_pixel_map (paleta + linhas). Sem 'camada' lê a "
            "imagem composta visível. 'rect' {x,y,w,h} ou 'selecao'. Passe a sua 'paleta' para reaproveitar as letras.",
            {"camada": STR, "quadro": INT, "rect": RET, "paleta": OBJ, "composto": BOOL})
async def ler_pixels(ctx, a):
    st = await ctx.sprite_atual()
    s = st["sprite"]
    camada = None if a.get("composto") or "camada" not in a else a["camada"]
    q = int(a.get("quadro", s.get("quadro_ativo") or 0))
    x, y, w, h = await retangulo(ctx, a, st)
    rgba = await ler_rgba(ctx, camada, q, x, y, w, h)
    pal, linhas, _ = pixels.para_linhas(rgba, a.get("paleta"))
    while linhas and not linhas[-1]:
        linhas.pop()
    cab = f"{'composto' if camada is None else repr(camada)}, quadro {q}, origem ({x},{y}), {w}×{h}"
    return [texto(cab + "\npaleta: " + json.dumps(pal) + "\nlinhas:\n" + "\n".join(linhas or ["(vazio)"]))]


@ferramenta("horys_ver", "Mostra o sprite como imagem. 'critica': true = cor | cinza (valores) | silhueta | 1× e 2× "
            "numa imagem pequena (o melhor jeito de julgar). 'rect' amplia um detalhe. Sem camada = composto.",
            {"quadro": INT, "camada": STR, "rect": RET, "critica": BOOL, "escala": INT})
async def ver(ctx, a):
    st = await ctx.sprite_atual()
    s = st["sprite"]
    q = int(a.get("quadro", s.get("quadro_ativo") or 0))
    x, y, w, h = await retangulo(ctx, a, st)
    rgba = await ler_rgba(ctx, a.get("camada"), q, x, y, w, h)
    if a.get("critica", True) and not a.get("rect"):
        img = pixels.critica(rgba)
    else:
        img = pixels.ampliar(rgba, int(a.get("escala") or 0))
    return [imagem(pixels.png_b64(img)), texto(f"quadro {q}, {w}×{h} a partir de ({x},{y})")]


@ferramenta("horys_mudancas", "O que o usuário mudou no Aseprite desde a última vez (1ª chamada só marca o ponto de "
            "partida). Devolve, por camada e quadro, a área mudada e as linhas dela.",
            {"quadros": {"type": "array", "items": INT}})
async def mudancas(ctx, a):
    st = await ctx.sprite_atual()
    s = st["sprite"]
    quadros = a.get("quadros") or list(range(len(s.get("quadros", []))))
    primeira = not ctx.baseline
    saida = []
    for c in s.get("camadas", []):
        for q in quadros:
            atual = await ler_rgba(ctx, c["nome"], q)
            chave = (s.get("arquivo"), c["nome"], q)
            antes = ctx.baseline.get(chave)
            ctx.baseline[chave] = atual
            if antes is None:
                continue
            bb, n = pixels.diff_bbox(antes, atual)
            if bb:
                x0, y0, x1, y1 = bb
                pal, linhas, _ = pixels.para_linhas(atual[y0:y1, x0:x1])
                saida.append(f"'{c['nome']}' quadro {q}: {n} px em ({x0},{y0})–({x1 - 1},{y1 - 1})\npaleta: "
                             f"{json.dumps(pal)}\n" + "\n".join(linhas))
    if primeira:
        return [texto("ponto de partida marcado; chame de novo depois que o usuário mexer.")]
    return [texto("\n\n".join(saida) if saida else "nada mudou.")]


@ferramenta("horys_selecao", "A seleção atual do usuário no Aseprite ('isto', 'aqui'): {x,y,w,h} ou vazia.")
async def selecao(ctx, a):
    sel = await ctx.aseprite("selecao")
    return [texto("sem seleção" if sel.get("vazia") else f"seleção: x={sel['x']} y={sel['y']} w={sel['w']} h={sel['h']}")]


@ferramenta("horys_limpar_camada", "Apaga o conteúdo de uma camada num quadro (ou em todos).",
            {"camada": STR, "quadro": INT, "todos": BOOL}, ["camada"])
async def limpar_camada(ctx, a):
    await ctx.aseprite("limpar_camada", a)
    return [texto(f"camada '{a['camada']}' limpa")]


@ferramenta("horys_desfazer", "Desfaz (ou refaz, com 'refazer': true) passos no Aseprite. Cada chamada de "
            "ferramenta que muda pixels é um passo.", {"passos": INT, "refazer": BOOL})
async def desfazer(ctx, a):
    await ctx.aseprite("refazer" if a.get("refazer") else "desfazer", {"passos": int(a.get("passos", 1))})
    return [texto("ok")]


@ferramenta("horys_copiar", "Copia (e espelha) uma região: 'rect' origem, destino x/y, 'flip' h|v|hv, de/para "
            "camada e quadro. Útil para simetria: desenhe metade e espelhe.",
            {"rect": RET, "x": INT, "y": INT, "flip": STR, "camada": STR, "quadro": INT, "para_camada": STR,
             "para_quadro": INT}, ["rect", "x", "y"])
async def copiar(ctx, a):
    camada, q, st = await alvo(ctx, a)
    x, y, w, h = await retangulo(ctx, a, st)
    rgba = await ler_rgba(ctx, camada, q, x, y, w, h)
    flip = a.get("flip") or ""
    if "h" in flip:
        rgba = rgba[:, ::-1]
    if "v" in flip:
        rgba = rgba[::-1]
    masc = (rgba[..., 3] > 0).astype(np.uint8)
    n = await escrever_rgba(ctx, a.get("para_camada", camada), int(a.get("para_quadro", q)), int(a["x"]),
                            int(a["y"]), np.ascontiguousarray(rgba), masc)
    return [texto(f"{n} pixels copiados")]


@ferramenta("horys_lote", "Várias ferramentas em sequência numa chamada: 'passos' [{ferramenta, args}, ...]. "
            "Para no primeiro erro.", {"passos": {"type": "array"}}, ["passos"])
async def lote(ctx, a):
    from .registro import REGISTRO
    saida = []
    for i, p in enumerate(a["passos"]):
        f = REGISTRO.get(p.get("ferramenta"))
        if f is None or f.nome == "horys_lote":
            raise ErroFerramenta(f"passo {i}: ferramenta inválida {p.get('ferramenta')}")
        r = await f.funcao(ctx, p.get("args") or {})
        saida += [c for c in r if c.get("type") == "text"]
    return saida or [texto("ok")]
