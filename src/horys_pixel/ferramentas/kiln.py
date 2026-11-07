"""Ferramentas da ponte com o SpriteKiln: importar o render (atlas + JSON) para o Aseprite e gerar a paleta."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from .. import kiln, pixels
from .desenho import escrever_rgba
from .estilo import _estilo, _ficha, _paleta
from .registro import BOOL, INT, LISTA_STR, STR, ErroFerramenta, ferramenta, imagem, texto


def _tira(quadros: list[np.ndarray], lado: int = 900) -> str:
    """Miniatura dos quadros lado a lado em escala INTEIRA (nunca reduz em escala quebrada)."""
    qs = quadros[:12]
    h, w = qs[0].shape[:2]
    tira = np.zeros((h, w * len(qs), 4), np.uint8)
    for i, q in enumerate(qs):
        tira[:, i * w:(i + 1) * w] = q
    k = max(1, lado // max(tira.shape[1], tira.shape[0]))
    im = Image.fromarray(tira, "RGBA")
    if k > 1:
        im = im.resize((im.width * k, im.height * k), Image.NEAREST)
    return pixels.png_b64(im)


@ferramenta("horys_paleta_kiln", """Grava a paleta do estilo no formato de rampas do SpriteKiln (índice 0 = contorno,
depois sombra -> base -> luz), para o spec apontar 'palette:' para ela. 'estilo' (padrão: o da ficha ou o padrão),
'destino' (caminho .yaml).""", {"estilo": STR, "destino": STR}, ["destino"])
async def paleta_kiln(ctx, a):
    nome = a.get("estilo")
    if not nome:
        try:
            _, f, _ = await _ficha(ctx)
            nome = f.get("estilo")
        except Exception:
            nome = None
    est = _estilo(nome)
    pal = _paleta(est)
    try:
        txt = kiln.yaml_paleta_kiln(pal)
    except ValueError as e:
        raise ErroFerramenta(str(e))
    dest = Path(a["destino"])
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(txt, encoding="utf-8")
    nomes = ", ".join(kiln.rampas_do_estilo(pal))
    return [texto(f"paleta gravada em {dest} (rampas: {nomes}). No spec: palette: {dest.name} e, em cada material, "
                  "ramp: <nome da rampa>; render: {outline: none, shading: toon}.")]


@ferramenta("horys_importar_kiln", """Importa um render do SpriteKiln (o JSON que `spritekiln render` grava em
out/<nome>/<nome>.json, com o atlas ao lado) para o sprite ativo: um quadro por quadro do render, na camada
'camada' (padrão 'referencia'), com as durações e as tags (estado sem o sufixo de direção). 'tags': só esses
estados; 'direcao': a vista (padrão a primeira do atlas); 'limpar_min': funde manchas menores que N px em todos os
quadros sem criar boil (sugerido 3). Asset MODULAR: passe 'spec' (o .yaml) e 'grupos' {parte_do_horys: [partes do
spec]} (ou deixe 'grupos' na ficha, chave kiln_grupos) para distribuir cada pixel visível na camada da sua parte;
'resto' recebe o que não cair em grupo nenhum (padrão: a parte de baixo). O sprite tem que ter o mesmo tamanho de
quadro do render (crie com horys_asset_novo quadro=<w>).""",
            {"json": STR, "tags": LISTA_STR, "direcao": STR, "camada": STR, "limpar_min": INT, "spec": STR,
             "grupos": {"type": "object"}, "resto": STR, "substituir": BOOL}, ["json"])
async def importar_kiln(ctx, a):
    chave, f, st = await _ficha(ctx)
    try:
        at = kiln.filtrar(kiln.ler_atlas(a["json"]), a.get("tags"), a.get("direcao"))
    except ValueError as e:
        raise ErroFerramenta(str(e))
    sp = st["sprite"]
    w, h = at.tamanho
    if (int(sp["largura"]), int(sp["altura"])) != (w, h):
        raise ErroFerramenta(f"o render tem quadro {w}x{h} e o sprite ativo {sp['largura']}x{sp['altura']}; "
                             f"crie o asset com horys_asset_novo quadro={w} (ou renderize com --size)")
    nomes = [c["nome"] for c in sp["camadas"]]
    camada = a.get("camada") or ("referencia" if "referencia" in nomes else None)
    if camada is None or camada not in nomes:
        raise ErroFerramenta(f"camada '{camada}' não existe (o sprite tem: {', '.join(nomes)})")

    quadros = at.quadros
    lim = int(a.get("limpar_min") or 0)
    if lim > 1:
        brilho = (_paleta(_estilo(f.get("estilo"))).get("brilho") or "").lstrip("#")
        prot = {tuple(int(brilho[i:i + 2], 16) for i in (0, 2, 4))} if len(brilho) == 6 else None
        quadros = kiln.limpar_sequencia(quadros, lim, prot)

    grupos = a.get("grupos") or f.get("kiln_grupos")
    partes_dist = None
    if f.get("modular") and grupos:
        if not a.get("spec"):
            raise ErroFerramenta("asset modular com 'grupos': passe também 'spec' (o .yaml que gerou o render)")
        ordem = list(f.get("partes") or [])
        faltam = [p for p in grupos if p not in ordem]
        if faltam:
            raise ErroFerramenta(f"grupos com partes que a ficha não tem: {', '.join(faltam)} (tem: {', '.join(ordem)})")
        direcao = (a.get("direcao") or (kiln.direcoes(kiln.ler_atlas(a["json"])) or ["e"])[0])
        partes_dist = {}
        for estado, de, ate in at.tags:
            try:
                ms, nomes_spec = kiln.mascaras_por_parte(a["spec"], estado, list(range(ate - de + 1)), direcao,
                                                         {p: list(v) for p, v in grupos.items()})
            except RuntimeError as e:
                raise ErroFerramenta(str(e))
            sem = sorted({n for v in grupos.values() for n in v} - set(nomes_spec))
            if sem:
                raise ErroFerramenta(f"partes do spec que não existem: {', '.join(sem)} (tem: {', '.join(nomes_spec)})")
            for j in range(ate - de + 1):
                partes_dist[de + j] = kiln.distribuir(quadros[de + j], ms.get(j, {}), ordem, a.get("resto"))

    await ctx.aseprite("quadro", {"acao": "garantir", "total": len(quadros)})
    escritos = 0
    for i, q in enumerate(quadros):
        escritos += await escrever_rgba(ctx, camada, i, 0, 0, q, np.ones(q.shape[:2], np.uint8))
        if partes_dist is not None:
            for parte, img in partes_dist[i].items():
                await escrever_rgba(ctx, parte, i, 0, 0, img, np.ones(img.shape[:2], np.uint8))
        await ctx.aseprite("quadro", {"acao": "duracao", "indice": i, "ms": int(at.duracoes_ms[i])})
    existentes = {t["nome"] for t in (await ctx.sprite_atual())["sprite"].get("tags", [])}
    for estado, de, ate in at.tags:
        if estado in existentes:
            await ctx.aseprite("tag", {"acao": "remover", "nome": estado})
        await ctx.aseprite("tag", {"acao": "criar", "nome": estado, "de": de, "ate": ate})

    f = dict(f)
    f["kiln"] = {"json": str(Path(a["json"]).resolve()), "sha256": at.sha256, "direcao": a.get("direcao"),
                 "tags": [t[0] for t in at.tags], "eventos": {str(k): v for k, v in at.eventos.items()},
                 "pivo": list(at.pivo) if at.pivo else None, "limpar_min": lim, "spec": a.get("spec"),
                 "por_parte": partes_dist is not None}
    if grupos:
        f["kiln_grupos"] = grupos
    if partes_dist is not None:
        f.pop("partes_checagem", None)  # o conteúdo das partes mudou: a checagem antiga não vale mais
    ctx.salvar_ficha(chave, f)

    resumo = ", ".join(f"{n}[{de}–{ate}]" for n, de, ate in at.tags)
    proximo = ("horys_partes_checar → " if partes_dist is not None else "") + \
        "horys_limpar/horys_afinar onde o portão apontar → mão por cima nos quadros-chave → horys_contorno → horys_portao"
    return [texto(f"importados {len(quadros)} quadros {w}x{h} na camada '{camada}'"
                  + (" e distribuídos nas partes" if partes_dist is not None else "")
                  + f" · tags: {resumo}" + (f" · limpeza min {lim}" if lim > 1 else "")
                  + f". Próximo: {proximo}."),
            imagem(_tira(quadros))]
