"""Pedidos: criar (como o botão Gerar do Aseprite), acompanhar, atualizar e cancelar."""
from __future__ import annotations

import json

from .registro import INT, STR, ErroFerramenta, LISTA_STR, ferramenta, texto


@ferramenta("horys_pedido_novo", """Cria um pedido de asset e inicia um motor sem terminal (o mesmo que o botão Gerar
do Aseprite). 'motor': claude|codex. Use quando o usuário pedir pelo terminal para o outro motor desenhar, ou para
testar o fluxo completo. 'autonomo_s': se ninguém responder uma pergunta ou aprovação do painel nesse tempo, segue
a recomendada (a aprovação fica marcada 'pendente_usuario').""",
            {"descricao": STR, "tipo": STR, "estilo": STR, "motor": STR, "estados": LISTA_STR, "referencia": STR,
             "tamanho": STR, "iniciar": {"type": "boolean"}, "autonomo_s": INT}, ["descricao"])
async def pedido_novo(ctx, a):
    p = ctx.pedidos.novo({k: v for k, v in a.items() if k != "iniciar"}, "asset")
    if a.get("iniciar", True):
        ctx.pedidos.iniciar(p["id"])
    return [texto(f"pedido {p['id']} criado (motor {p['motor']}, pasta {p['pasta']})")]


@ferramenta("horys_pedido", "Estado de um pedido (ou a lista dos últimos, sem 'id').", {"id": STR})
async def pedido(ctx, a):
    if not a.get("id"):
        return [texto(json.dumps(ctx.pedidos.listar(), ensure_ascii=False, indent=1))]
    p = ctx.pedidos.ler(a["id"])
    if p is None:
        raise ErroFerramenta(f"pedido {a['id']} não existe")
    p = dict(p)
    p["historico"] = p.get("historico", [])[-8:]
    return [texto(json.dumps(p, ensure_ascii=False, indent=1, default=str))]


@ferramenta("horys_pedido_atualizar", """Registra o andamento do pedido e mostra no painel do Aseprite: 'etapa'
(briefing, pesquisa, praticas, ficha, referencia, conversao, limpeza, partes, portao, revisor, aprovacao, animacao,
entrega, concluido), 'texto' curto e 'nota' (aceitação do revisor, 0–100). Também guarda decisões e pendências
('pendencia'). Em asset modular, 'animacao' só é aceita depois de horys_partes_checar sem erros (etapa 'partes').""",
            {"id": STR, "etapa": STR, "texto": STR, "nota": INT, "pendencia": STR}, ["id"])
async def pedido_atualizar(ctx, a):
    if a.get("etapa") == "animacao":
        if not ctx.ponte.conectado:
            raise ErroFerramenta("não é possível liberar animação sem Aseprite conectado")
        try:
            st = await ctx.sprite_atual()
            f = ctx.ficha(st["sprite"].get("horys_id") or st["sprite"]["arquivo"])
        except Exception as e:
            raise ErroFerramenta(f"não foi possível conferir o portão de partes: {e}")
        chec = f.get("partes_checagem") or {}
        if f.get("modular") and not chec.get("ok"):
            raise ErroFerramenta("asset modular: antes de animar, a etapa 'partes' tem que passar — rode "
                                 "horys_partes_checar e corrija os erros (última checagem: "
                                 f"{chec.get('erros', 'nunca rodou')})")
        if f.get("modular"):
            from .partes import checar_asset, hash_checagem
            indices = list(range(len(st["sprite"]["quadros"])))
            _, quadros, _, refs = await checar_asset(ctx, f, st, indices)
            if chec.get("n_quadros") != len(indices) or chec.get("hash") != hash_checagem(f, quadros, refs):
                raise ErroFerramenta("asset modular: checagem desatualizada; pixels, quadros ou contratos mudaram")
    try:
        extra = {}
        if a.get("pendencia"):
            p = ctx.pedidos.ler(a["id"]) or {}
            extra["pendencias"] = (p.get("pendencias") or []) + [a["pendencia"]]
        p = ctx.pedidos.atualizar(a["id"], a.get("etapa"), a.get("texto"), a.get("nota"), **extra)
    except KeyError as e:
        raise ErroFerramenta(str(e))
    return [texto(f"pedido {p['id']}: etapa {p['etapa']}")]


@ferramenta("horys_pedido_cancelar", "Cancela um pedido e encerra o motor dele.", {"id": STR}, ["id"])
async def pedido_cancelar(ctx, a):
    ctx.pedidos.cancelar(a["id"])
    return [texto("cancelado")]
