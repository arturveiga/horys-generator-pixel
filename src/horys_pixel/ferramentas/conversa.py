"""Conversa com o usuário pelo painel do Aseprite: perguntas, aprovações e andamento."""
from __future__ import annotations

import base64
from pathlib import Path

from .. import pixels
from .registro import BOOL, INT, OBJ, STR, ErroFerramenta, ferramenta, texto

PERGUNTAS = {"type": "array", "description": "1 a 4 perguntas",
             "items": {"type": "object", "properties": {
                 "pergunta": STR, "cabecalho": STR, "multipla": BOOL,
                 "opcoes": {"type": "array", "items": {"type": "object",
                                                       "properties": {"rotulo": STR, "descricao": STR}}}}}}


@ferramenta("horys_perguntar", """Faz até 4 perguntas ao usuário no painel do Aseprite (como o AskUserQuestion).
Cada pergunta: {pergunta, cabecalho (até 12 letras), opcoes:[{rotulo, descricao}] (2–4, a recomendada primeiro e com
'(recomendado)'), multipla?}. O painel sempre oferece 'Outro'. Devolve um id NA HORA; chame horys_aguardar(id) para
receber as respostas. Se não houver painel, devolve 'sem_painel' e você pergunta no chat (ou segue a recomendada,
se estiver rodando sem terminal).""",
            {"titulo": STR, "perguntas": PERGUNTAS, "pedido": STR}, ["perguntas"])
async def perguntar(ctx, a):
    ps = a["perguntas"]
    if not 1 <= len(ps) <= 4:
        raise ErroFerramenta("de 1 a 4 perguntas por vez")
    for p in ps:
        if not p.get("pergunta") or not (2 <= len(p.get("opcoes") or []) <= 4):
            raise ErroFerramenta("cada pergunta precisa de texto e de 2 a 4 opções")
    if not ctx.ponte.conectado:
        return [texto("sem_painel: o Aseprite não está conectado. Pergunte no chat; sem terminal, siga a opção "
                      "recomendada e registre a decisão.")]
    i = ctx.pend.criar("pergunta", {"titulo": a.get("titulo"), "perguntas": ps, "pedido": a.get("pedido")})
    ok = await ctx.ui("ui_perguntar", {"id": i, "titulo": a.get("titulo") or "Horys pergunta", "perguntas": ps})
    if not ok:
        ctx.pend.resolver(i, None, estado="sem_painel")
        return [texto("sem_painel: o painel não abriu. Pergunte no chat ou siga a recomendada.")]
    _agendar_automatico(ctx, i, a.get("pedido"), {p["pergunta"]: p["opcoes"][0]["rotulo"] for p in ps})
    return [texto(f"id: {i}\nperguntas no painel do Aseprite. Agora chame horys_aguardar com id='{i}'.")]


def _agendar_automatico(ctx, i: str, pedido: str | None, resposta: dict):
    """Modo autônomo do pedido: sem resposta em 'autonomo_s' segundos, segue a recomendada (registrada como tal)."""
    import asyncio
    p = ctx.pedidos.ler(pedido) if pedido else None
    espera = (p or {}).get("autonomo_s")
    if not espera:
        return

    async def depois():
        await asyncio.sleep(float(espera))
        it = ctx.pend.obter(i)
        if it and it["estado"] == "pendente":
            ctx.pend.resolver(i, {**resposta, "_automatico": f"sem resposta em {espera} s: seguiu a recomendada"},
                              estado="automatico")
            await ctx.ui("ui_fechar", {"id": i})
    asyncio.ensure_future(depois())


@ferramenta("horys_aprovar", """Portão do usuário: mostra no painel o que aprovar (texto e, se 'imagem' = caminho de
PNG ou 'sprite' = true, a imagem) com os botões Aprovar / Refazer e um comentário. Devolve um id na hora; use
horys_aguardar(id). Passe 'estilo', 'etapa', 'tipo' e 'descricao' para a resposta virar memória de gosto.""",
            {"titulo": STR, "texto": STR, "imagem": STR, "sprite": BOOL, "quadro": INT, "estilo": STR, "etapa": STR,
             "tipo": STR, "descricao": STR, "pedido": STR}, ["titulo"])
async def aprovar(ctx, a):
    if not ctx.ponte.conectado:
        return [texto("sem_painel: mostre no chat e pergunte; sem terminal, registre como pendente no pedido.")]
    from PIL import Image
    im = None
    if a.get("imagem"):
        p = Path(a["imagem"])
        if not p.exists():
            raise ErroFerramenta(f"imagem não existe: {p}")
        im = Image.open(p).convert("RGBA")
    elif a.get("sprite"):
        from .desenho import ler_rgba
        st = await ctx.sprite_atual()
        q = int(a.get("quadro", st["sprite"].get("quadro_ativo") or 0))
        im = pixels.critica(await ler_rgba(ctx, None, q)).convert("RGBA")
    extra = {}
    if im is not None:
        # RGBA cru: a extensão monta a imagem sem gravar arquivo (sem pedido de permissão do Aseprite)
        k = min(1.0, 512 / max(im.size))
        if k < 1:
            im = im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.NEAREST)
        extra = {"imagem_rgba": base64.b64encode(im.tobytes()).decode("ascii"), "imagem_w": im.width,
                 "imagem_h": im.height}
    dados = {k: a.get(k) for k in ("titulo", "texto", "estilo", "etapa", "tipo", "descricao", "pedido")}
    if a.get("sprite"):
        try:
            st = await ctx.sprite_atual()
            dados["arquivo"] = st["sprite"].get("arquivo")
            dados["quadro"] = int(a.get("quadro", st["sprite"].get("quadro_ativo") or 0))
        except Exception:
            pass
    i = ctx.pend.criar("aprovacao", dados)
    ok = await ctx.ui("ui_aprovar", {"id": i, "titulo": a["titulo"], "texto": a.get("texto") or "", **extra})
    if not ok:
        ctx.pend.resolver(i, None, estado="sem_painel")
        return [texto("sem_painel: o painel não abriu.")]
    _agendar_automatico(ctx, i, a.get("pedido"), {"aprovado": True, "comentario": "", "pendente_usuario": True})
    return [texto(f"id: {i}\naprovação no painel. Chame horys_aguardar com id='{i}'.")]


@ferramenta("horys_esperar_imagem", """Entrega do prompt e espera da imagem gerada FORA (ChatGPT, Gemini, Codex, vídeo...).
Mostra no painel do Aseprite o prompt (texto em 'prompt' ou o arquivo 'arquivo_prompt', ex.: traducao/prompt.md do
horys_prompt_traducao) com o botão Copiar e cria a pasta <pasta>/entrada/. A espera destrava quando o usuário salva
uma imagem nessa pasta (o horysd vigia) ou escolhe o arquivo no painel. Devolve um id na hora; chame
horys_aguardar(id): a resposta traz 'imagem' (caminho), que vai direto para o horys_portao_entrada. 'pasta' padrão:
a do 'pedido', senão a pasta acima de traducao/. Sem painel, a vigia da pasta continua: mostre o prompt no chat.""",
            {"prompt": STR, "arquivo_prompt": STR, "pasta": STR, "titulo": STR, "pedido": STR})
async def esperar_imagem(ctx, a):
    import asyncio
    from .. import config
    arq = Path(a["arquivo_prompt"]) if a.get("arquivo_prompt") else None
    prompt = a.get("prompt") or ""
    if not prompt and arq:
        if not arq.is_file():
            raise ErroFerramenta(f"arquivo_prompt não existe: {arq}")
        prompt = arq.read_text(encoding="utf-8")
    if not prompt.strip():
        raise ErroFerramenta("passe 'prompt' ou 'arquivo_prompt' (rode horys_prompt_traducao antes)")
    pasta = a.get("pasta")
    if not pasta and a.get("pedido"):
        pasta = ((ctx.pedidos.ler(a["pedido"]) or {}).get("pasta"))
    if not pasta and arq:
        pasta = str(arq.parent.parent if arq.parent.name == "traducao" else arq.parent)
    if not pasta:
        raise ErroFerramenta("passe 'pasta' (ou 'pedido' ou 'arquivo_prompt')")
    entrada = Path(pasta) / "entrada"
    if not config.caminho_permitido(entrada):
        raise ErroFerramenta(f"pasta não permitida: {entrada}")
    entrada.mkdir(parents=True, exist_ok=True)
    i = ctx.pend.criar("imagem", {"entrada": str(entrada), "arquivo_prompt": str(arq) if arq else None,
                                  "pedido": a.get("pedido")})

    async def fechar_janela(ii):
        await ctx.ui("ui_fechar", {"id": ii})
    asyncio.ensure_future(ctx.pend.vigiar_entrada(i, entrada, fechar_janela))
    ok = await ctx.ui("ui_imagem", {"id": i, "titulo": a.get("titulo") or "Horys: gere a imagem", "prompt": prompt,
                                    "arquivo_prompt": str(arq) if arq else "", "pasta": str(entrada)})
    if a.get("pedido"):
        try:
            ctx.pedidos.atualizar(a["pedido"], etapa="referencia", texto="esperando a imagem gerada em " + str(entrada))
        except KeyError:
            pass
    if not ok:
        return [texto(f"id: {i}\nsem_painel: mostre o prompt no chat e peça para salvar a imagem em {entrada}. "
                      f"A pasta está sendo vigiada; chame horys_aguardar com id='{i}'.")]
    return [texto(f"id: {i}\nprompt no painel; esperando a imagem em {entrada}. Chame horys_aguardar com id='{i}' "
                  "(o usuário pode demorar: continue chamando enquanto estiver pendente).")]


@ferramenta("horys_aguardar", """Espera a resposta de uma pergunta, aprovação, imagem (horys_esperar_imagem),
acabamento (horys_entrega), revisão ou tarefa (id). Espera no
máximo 'segundos' (padrão 45, máx. 55) e devolve o estado: 'respondido' com a resposta, ou 'pendente' — então chame
de novo. O usuário pode demorar: continue chamando enquanto estiver pendente.""",
            {"id": STR, "segundos": INT}, ["id"])
async def aguardar(ctx, a):
    seg = max(1, min(55, int(a.get("segundos", 45))))
    r = await ctx.pend.aguardar(a["id"], seg)
    if r.get("estado") == "pendente":
        return [texto(f"pendente: {a['id']} ainda sem resposta. Chame horys_aguardar de novo.")]
    import json
    return [texto(json.dumps({"id": r["id"], "estado": r["estado"], "resposta": r.get("resposta")},
                             ensure_ascii=False, indent=1))]


@ferramenta("horys_painel", "Mostra uma mensagem de andamento no painel do Aseprite (sem pedido associado).",
            {"etapa": STR, "texto": STR, "nota": INT}, ["texto"])
async def painel(ctx, a):
    ok = await ctx.ui("ui_progresso", {"pedido": "", "etapa": a.get("etapa") or "", "texto": a["texto"],
                                       "nota": a.get("nota")})
    return [texto("mostrado" if ok else "sem_painel")]
