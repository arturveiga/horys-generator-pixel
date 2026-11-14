"""Ferramentas da base de ofício: regras por assunto, ~400 modelos de grade e 2006 paletas."""
from __future__ import annotations

import json

from .. import oficio, pixels
from .registro import BOOL, INT, OBJ, STR, ErroFerramenta, ferramenta, imagem, texto

_DESC = """Base de ofício de pixel art (62 regras, ~400 modelos de grade, 2006 paletas com autor). É ofício, não
régua de estilo: a régua é o Artur (ficha e aprovados). Ações:
• 'indice' — lista as regras (00 núcleo, 1x técnica, 2x cor/material, 3x personagem, 4x animação, 5x criaturas,
  6x cenário, 7x objetos/3D, 8x efeitos/UI, 9x estilo).
• 'regra' {regra:'34' ou 'hands-and-feet', secao?:'Rules'|'Mistakes'|'Review'..., sem_modelos?} — lê uma regra.
• 'buscar' {termo} — linhas das regras com todas as palavras (ex.: 'hand 32', 'walk contact').
• 'modelos' {filtro?} — lista modelos de grade (nome, regra, tamanho).
• 'modelo' {nome, cores?:{papel ou letra:'#hex'}, desenhar?:true, x, y, camada, quadro} — mostra o modelo
  (prévia + paleta e linhas prontas para horys_pixel_map). Troque as cores pela paleta do asset com 'cores'.
  'desenhar': true carimba no Aseprite (pontos '.' não mexem). Modelo é ponto de partida: adapte à pose.
• 'paletas' {termo?, tamanho?} — busca paletas (nome, autor, notas).
• 'paleta' {nome} — cores de uma paleta, com autor e fonte."""


@ferramenta("horys_oficio", _DESC,
            {"acao": STR, "regra": STR, "secao": STR, "sem_modelos": BOOL, "termo": STR, "filtro": STR,
             "nome": STR, "cores": OBJ, "desenhar": BOOL, "x": INT, "y": INT, "camada": STR, "quadro": INT,
             "tamanho": INT, "limite": INT}, ["acao"])
async def oficio_ferramenta(ctx, a):
    acao = a["acao"]
    try:
        if acao == "indice":
            return [texto(oficio.indice())]
        if acao == "regra":
            return [texto(oficio.ler_regra(a.get("regra") or a.get("nome") or "", a.get("secao"),
                                           bool(a.get("sem_modelos"))))]
        if acao == "buscar":
            achados = oficio.buscar(a.get("termo") or "", int(a.get("limite") or 30))
            return [texto("\n".join(achados) or "nada encontrado")]
        if acao == "modelos":
            ms = oficio.listar_modelos(a.get("filtro"))
            lim = int(a.get("limite") or 80)
            linhas = [f"{m.nome} ({m.largura}×{m.altura}) — {m.regra}" for m in ms[:lim]]
            extra = f"\n… e mais {len(ms) - lim}" if len(ms) > lim else ""
            return [texto(f"{len(ms)} modelos\n" + "\n".join(linhas) + extra)]
        if acao == "modelo":
            m = oficio.achar_modelo(a.get("nome") or "")
            pal = m.paleta(a.get("cores"))
            rgba, _ = pixels.compor_mapa(pal, m.linhas)
            papeis = {k: v[0] for k, v in m.legenda.items()}
            saida = [imagem(pixels.png_b64(pixels.ampliar(rgba))),
                     texto(f"{m.nome} ({m.largura}×{m.altura}) de {m.regra}\n{m.descricao}\n"
                           f"papéis: {json.dumps(papeis, ensure_ascii=False)}\n"
                           f"paleta: {json.dumps(pal)}\nlinhas:\n" + "\n".join(m.linhas))]
            if a.get("desenhar"):
                from .desenho import pixel_map
                r = await pixel_map(ctx, {"paleta": pal, "linhas": m.linhas, "x": int(a.get("x", 0)),
                                          "y": int(a.get("y", 0)),
                                          **{k: a[k] for k in ("camada", "quadro") if k in a}})
                saida += r
            return saida
        if acao == "paletas":
            ps = oficio.buscar_paletas(a.get("termo") or "", a.get("tamanho"), int(a.get("limite") or 25))
            return [texto("\n".join(f"{k}: {p.get('name')} — {p.get('author', '?')}, {p.get('size')} cores"
                                    for k, p in ps) or "nada encontrado")]
        if acao == "paleta":
            k, p = oficio.paleta(a.get("nome") or "")
            return [texto(f"{k}: {p.get('name')} — {p.get('author', '?')} ({p.get('url') or p.get('source', '')})\n"
                          f"{p.get('notes', '')}\ncores: {json.dumps(p.get('colors', []))}")]
    except KeyError as e:
        raise ErroFerramenta(str(e).strip("'\""))
    raise ErroFerramenta(f"acao inválida '{acao}' (indice|regra|buscar|modelos|modelo|paletas|paleta)")
