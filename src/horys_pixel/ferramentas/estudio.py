"""Ferramentas do Horys Estúdio: abrir a interface, ler os pedidos que o Artur riscou e responder a eles."""
from __future__ import annotations

import base64
from pathlib import Path

from ..estudio import pedidos as PD
from .registro import BOOL, INT, STR, ErroFerramenta, ferramenta, imagem, texto


@ferramenta("horys_estudio_abrir", """
Abre o HORYS ESTÚDIO (interface local estilo Noct): pastas agrupadas, grade, inspetor com zoom de pixel, player de
folha com onion, riscar na imagem e mandar o pedido ao chat, aprovar/reprovar (vira régua), paleta com recolor, boas
práticas e render do Blender. Sobe o servidor em 127.0.0.1 (uma vez) e devolve a URL com o token; 'navegador' abre
a janela ('app': janela sem barra, Edge/Chrome).
""", {"navegador": BOOL, "app": BOOL, "porta": INT})
async def estudio_abrir(ctx, a: dict) -> list:
    from ..estudio import servidor
    url = servidor.iniciar(int(a.get("porta") or 0))
    if a.get("navegador", True):
        servidor.abrir_navegador(url, bool(a.get("app")))
    return [texto(f"Horys Estúdio: {url}")]


@ferramenta("horys_estudio_pedidos", """
Lê os PEDIDOS que o Artur fez no Horys Estúdio (riscos + texto sobre uma imagem). Padrão: os pendentes, com a
imagem anotada de cada um, o arquivo do asset, o quadro e as marcas em pixels do sprite. Depois de atender, chame
horys_estudio_responder (o Artur vê a resposta na interface). 'estado': pendente | em_andamento | feito | todos.
""", {"estado": STR, "max": INT})
async def estudio_pedidos(ctx, a: dict) -> list:
    lista = PD.listar(a.get("estado") or "pendente")[: int(a.get("max") or 5)]
    if not lista:
        return [texto("nenhum pedido " + (a.get("estado") or "pendente") + " no Estúdio.")]
    saida = []
    for p in lista:
        def _m(m):
            if m.get("tipo") == "3d":
                return (f"#{m.get('n')} 3D em {m.get('posicao')} (normal {m.get('normal')}), câmera {m.get('orbita')}, "
                        f"animação {m.get('animacao') or '—'} t={m.get('tempo')}: '{m.get('nota')}'")
            return f"{m.get('tipo')} q{m.get('quadro')} {(m.get('pontos') or [])[:4]}" + (f" '{m['texto']}'" if m.get('texto') else "")
        marcas = "; ".join(_m(m) for m in p.get("marcas") or [])
        saida.append(texto(f"PEDIDO {p['id']} ({p['estado']}, {p['criado']})\nasset: {p.get('asset')}\nquadro: "
                           f"{p.get('quadro')}\nnota: {p.get('nota') or '(só riscos)'}\nmarcas (pixels do sprite): "
                           f"{marcas or '—'}\nimagem anotada: {p.get('anotado')}"))
        for arq in ([p["anotado"]] if p.get("anotado") else []) + list(p.get("vistas") or [])[:8]:
            if Path(arq).is_file():
                saida.append(imagem(base64.b64encode(Path(arq).read_bytes()).decode("ascii")))
    return saida


@ferramenta("horys_estudio_responder", """
Responde a um pedido do Horys Estúdio: 'texto' (o que foi feito), 'estado' (feito | em_andamento | pendente |
descartado) e opcional 'imagem' (caminho da versão nova, para o Artur comparar na interface).
""", {"id": STR, "texto": STR, "estado": STR, "imagem": STR}, ["id", "texto"])
async def estudio_responder(ctx, a: dict) -> list:
    try:
        p = PD.responder(a["id"], a["texto"], a.get("estado") or "feito", a.get("imagem"))
    except (KeyError, ValueError) as e:
        raise ErroFerramenta(str(e))
    return [texto(f"pedido {p['id']}: {p['estado']}")]
