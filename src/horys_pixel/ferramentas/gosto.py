"""Memória de gosto: cada Aprovar/Refazer vira registro; aprovados viram exemplos e conjunto de treino."""
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

from .. import config
from .registro import BOOL, STR, ErroFerramenta, LISTA_STR, ferramenta, texto


def pasta_gosto(estilo: str) -> Path:
    try:
        from .. import estilos
        return Path(estilos.pasta_dados(estilos.carregar(estilo), "gosto"))
    except Exception:
        p = config.pasta("estilos-dados") / estilo / "gosto"
        p.mkdir(parents=True, exist_ok=True)
        return p


def registrar(estilo: str, etapa: str, aprovado: bool, comentario: str = "", defeitos=None, tipo: str = "",
              descricao: str = "", png: bytes | None = None, extra: dict | None = None) -> dict:
    pg = pasta_gosto(estilo)
    reg = {"t": time.time(), "data": time.strftime("%Y-%m-%d %H:%M"), "estilo": estilo, "etapa": etapa,
           "aprovado": bool(aprovado), "comentario": comentario or "", "defeitos": list(defeitos or []),
           "tipo": tipo or "", "descricao": descricao or "", **(extra or {})}
    if png:
        sub = pg / ("aprovados" if aprovado else "recusados")
        sub.mkdir(parents=True, exist_ok=True)
        nome = time.strftime("%Y%m%d-%H%M%S") + f"-{etapa or 'x'}"
        (sub / f"{nome}.png").write_bytes(png)
        (sub / f"{nome}.json").write_text(json.dumps(reg, ensure_ascii=False, indent=1), encoding="utf-8")
        reg["imagem"] = str(sub / f"{nome}.png")
    with open(pg / "registro.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(reg, ensure_ascii=False) + "\n")
    return reg


def registrar_aprovacao(dados: dict, resposta: dict):
    """Chamado pelo horysd quando o usuário responde um horys_aprovar que tinha 'estilo'. Resposta automática
    (o usuário não respondeu: 'pendente_usuario') não é gosto: não vira aprovado nem recusado."""
    if resposta.get("pendente_usuario"):
        return None
    registrar(dados["estilo"], dados.get("etapa") or "", bool(resposta.get("aprovado")),
              resposta.get("comentario") or "", tipo=dados.get("tipo") or "", descricao=dados.get("descricao") or "",
              extra={"pedido": dados.get("pedido"), "arquivo": dados.get("arquivo"), "quadro": dados.get("quadro")})


def ler_registros(estilo: str) -> list[dict]:
    arq = pasta_gosto(estilo) / "registro.jsonl"
    if not arq.exists():
        return []
    out = []
    for l in arq.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(l))
        except json.JSONDecodeError:
            pass
    return out


@ferramenta("horys_gosto_registrar", """Guarda uma aprovação ou recusa do usuário na memória de gosto do estilo.
'capturar': true salva a imagem composta do quadro ativo (aprovados viram exemplo e conjunto de treino).
(Respostas do horys_aprovar com 'estilo' já são registradas sozinhas.)""",
            {"estilo": STR, "etapa": STR, "aprovado": BOOL, "comentario": STR, "defeitos": LISTA_STR, "tipo": STR,
             "descricao": STR, "capturar": BOOL}, ["estilo", "aprovado"])
async def gosto_registrar(ctx, a):
    png = None
    if a.get("capturar"):
        import base64
        from .. import pixels
        from .desenho import ler_rgba
        st = await ctx.sprite_atual()
        rgba = await ler_rgba(ctx, None, int(st["sprite"].get("quadro_ativo") or 0))
        x0, y0, x1, y1 = pixels.recorte(rgba, 2)
        png = base64.b64decode(pixels.png_b64(rgba[y0:y1, x0:x1]))
    r = registrar(a["estilo"], a.get("etapa") or "", a["aprovado"], a.get("comentario") or "", a.get("defeitos"),
                  a.get("tipo") or "", a.get("descricao") or "", png)
    return [texto(f"registrado ({'aprovado' if r['aprovado'] else 'recusado'})")]


@ferramenta("horys_gosto_consultar", """O que o usuário já aprovou e recusou neste estilo: comentários recentes,
defeitos que mais se repetem (candidatos a regra) e exemplos aprovados do mesmo tipo para usar como referência.""",
            {"estilo": STR, "tipo": STR}, ["estilo"])
async def gosto_consultar(ctx, a):
    regs = ler_registros(a["estilo"])
    if not regs:
        return [texto("sem registros de gosto ainda neste estilo.")]
    tipo = a.get("tipo")
    recus = [r for r in regs if not r["aprovado"]]
    aprov = [r for r in regs if r["aprovado"]]
    defeitos = Counter(d for r in recus for d in r.get("defeitos") or [])
    linhas = [f"{len(aprov)} aprovações, {len(recus)} recusas."]
    if defeitos:
        linhas.append("Defeitos que mais voltam (candidatos a regra; proponha ao usuário antes de mudar o estilo):")
        linhas += [f"- {d} ({n}×)" for d, n in defeitos.most_common(8)]
    coment = [r for r in regs if r.get("comentario")][-10:]
    if coment:
        linhas.append("Comentários recentes:")
        linhas += [f"- [{'ok' if r['aprovado'] else 'refazer'}] {r.get('etapa')}: {r['comentario']}" for r in coment]
    ex = [r["imagem"] for r in aprov if r.get("imagem") and (not tipo or r.get("tipo") == tipo)][-5:]
    if ex:
        linhas.append("Exemplos aprovados" + (f" ({tipo})" if tipo else "") + ":")
        linhas += [f"- {p}" for p in ex]
    return [texto("\n".join(linhas))]
