"""Entrega a 90%: o acabamento marcado para o usuário (4.2) e o gosto aprendido com o retoque dele (4.3)."""
from __future__ import annotations

import numpy as np

from .. import entrega, retoque
from .desenho import ler_rgba
from .estilo import _estilo, _ficha, _paleta, marcar
from .gosto import registrar
from .registro import BOOL, INT, STR, ErroFerramenta, LISTA_STR, ferramenta, texto


@ferramenta("horys_entrega", """Estado de ENTREGA a partir do JSON do revisor ('resultado'): pronto = zero defeito
estrutural E aceitação >= 'limite' (padrão 80). Os defeitos de ACABAMENTO viram marcas na camada 'revisao' (as
coordenadas que o revisor deu em 'onde') e uma lista guardada na ficha (acabamento_pendente) para o usuário
finalizar no Aseprite. Se estiver pronto, a lista também abre no painel (botão 'Terminei o retoque') e a resposta traz
um id: horys_aguardar(id) devolve o que o usuário marcou como feito; depois rode horys_gosto_do_retoque.
'marcar': false só avalia.""",
            {"resultado": {"type": "object"}, "limite": INT, "quadro": INT, "marcar": BOOL}, ["resultado"])
async def entrega_ferramenta(ctx, a):
    av = entrega.avaliar(a["resultado"], int(a.get("limite") or entrega.LIMITE_PADRAO))
    linhas = [("PRONTO PARA ENTREGA" if av["pronto"] else "AINDA NÃO ESTÁ PRONTO") + f": {av['motivo']} "
              f"(aceitação {av.get('aceitacao')}, limite {av.get('limite')})"]
    if av["estruturais"]:
        linhas.append("Estruturais (corrigir antes de entregar):")
        linhas += [f"- {d.get('id')} {d.get('onde', '')}: {d.get('correcao', '')}" for d in av["estruturais"]]
    pend = []
    pontos, rets = [], []
    for d in av["acabamento"]:
        p, r = retoque.coordenadas(d.get("onde", ""))
        pontos += p
        rets += r
        pend.append({"id": d.get("id"), "onde": d.get("onde", ""), "correcao": d.get("correcao", ""),
                     "estado": d.get("estado")})
    if pend:
        linhas.append("Acabamento (o usuário finaliza no Aseprite):")
        linhas += [f"- {x['id']} {x['onde']}: {x['correcao']}" for x in pend]
    if a.get("marcar", True) and pend:
        try:
            chave, f, st = await _ficha(ctx)
            f = dict(f)
            f["acabamento_pendente"] = pend
            ctx.salvar_ficha(chave, f)
            if pontos or rets:
                q = a.get("quadro")
                args = {"pontos": pontos, "retangulos": rets, "limpar": True}
                if q is not None:
                    args["quadro"] = int(q)
                linhas.append((await marcar(ctx, args))[0]["text"])
        except ErroFerramenta as e:
            linhas.append(f"(não consegui marcar no Aseprite: {e})")
    if a.get("marcar", True) and pend and av["pronto"]:
        i = ctx.pend.criar("acabamento", {"itens": pend})
        itens = [{"id": x.get("id") or "", "onde": x.get("onde") or "", "correcao": x.get("correcao") or x.get("id")
                  or "acabamento"} for x in pend]
        if await ctx.ui("ui_acabamento", {"id": i, "titulo": "Horys: acabamento para finalizar", "itens": itens}):
            linhas.append(f"id: {i}\nLista de acabamento no painel. Quando o usuário clicar 'Terminei o retoque', "
                          f"horys_aguardar(id='{i}') devolve o que ele marcou; então rode horys_gosto_do_retoque.")
        else:
            ctx.pend.resolver(i, None, estado="sem_painel")
            linhas.append("(sem painel: passe a lista de acabamento no chat)")
    return [texto("\n".join(linhas))]


@ferramenta("horys_gosto_do_retoque", """Depois do retoque do usuário: compara a camada 'camada' do quadro 'quadro' com
o PNG 'antes' (a versão entregue) e resume o que ele mudou por categoria (rosto, brilho, contorno, cor, forma).
Grava o resumo na memória de gosto do estilo (horys_gosto_registrar) com as categorias mais mexidas como defeitos;
as que se repetem viram candidatas a regra da praticas.md do projeto (proponha ao usuário).""",
            {"antes": STR, "camada": STR, "quadro": INT, "estilo": STR, "etapa": STR, "tipo": STR, "registrar": BOOL},
            ["antes"])
async def gosto_do_retoque(ctx, a):
    from pathlib import Path
    from PIL import Image
    arq = Path(a["antes"])
    if not arq.exists():
        raise ErroFerramenta(f"imagem 'antes' não encontrada: {arq}")
    antes = np.array(Image.open(arq).convert("RGBA"), dtype=np.uint8)
    chave, f, st = await _ficha(ctx)
    est = _estilo(a.get("estilo") or f.get("estilo"))
    depois = await ler_rgba(ctx, a.get("camada"), int(a.get("quadro", st["sprite"].get("quadro_ativo") or 0)))
    if depois.shape != antes.shape:
        raise ErroFerramenta(f"tamanhos diferentes: antes {antes.shape[:2]}, depois {depois.shape[:2]}")
    cat = retoque.categorizar(antes, depois, _paleta(est).get("contorno"))
    s = retoque.resumo([cat])
    defeitos = retoque.defeitos_do_resumo(s)
    msg = retoque.texto_do_resumo(s)
    if a.get("registrar", True) and s["total"]:
        registrar(est.nome, a.get("etapa") or "retoque", True, msg, defeitos, a.get("tipo") or f.get("tipo") or "",
                  f.get("descricao") or "", None)
        msg += ". Registrado no gosto do estilo; defeitos: " + (", ".join(defeitos) or "nenhum acima de 15%")
    return [texto(msg)]
