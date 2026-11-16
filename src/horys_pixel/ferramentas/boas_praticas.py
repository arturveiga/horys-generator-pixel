"""Ferramenta MCP das boas práticas (docs/boas-praticas.md). Trabalha com arquivos; não precisa do Aseprite aberto.

horys_boas_praticas  PNG | pasta de quadros | folha PNG+JSON -> <x>_praticas.json + <x>_praticas.png (overlay)

A lógica vive em horys_pixel.boas_praticas (a mesma que o pós-render do Blender e a interface web chamam).
"""
from __future__ import annotations

from PIL import Image

from .. import boas_praticas as BP
from .. import pixels
from .registro import BOOL, INT, STR, ErroFerramenta, ferramenta, imagem, texto

LISTA = {"type": "array", "items": {"type": "string"}}


@ferramenta("horys_boas_praticas", """
Mede as BOAS PRÁTICAS automáticas (ids BP de docs/boas-praticas.md) de um sprite: 'arquivo' = PNG de um quadro,
pasta de quadros PNG, ou folha PNG+JSON (Aseprite/SpriteKiln; uma sequência por tag, ação pelo nome da tag).
Grava <x>_praticas.json (resultado por regra: passa, medida, limite, onde) e <x>_praticas.png (overlay ampliado:
vermelho = grave, amarelo = leve). Contexto opcional: 'protegidas' (cores de 1 px permitidas: olho, brilho,
emissivo), 'contorno', 'paleta', 'chao', 'acao' (idle|andar|correr|ataque|dano|morte), 'loop', 'render3d' (BP40/BP41
só informam), 'altura_alvo', 'perfil' (16|32|64), 'limites' {"BP12": 24}. As regras de olho ficam para o revisor.
""", {"arquivo": STR, "saida": STR, "protegidas": LISTA, "contorno": STR, "paleta": LISTA, "chao": STR,
      "acao": STR, "loop": BOOL, "render3d": BOOL, "altura_alvo": INT, "perfil": STR,
      "limites": {"type": "object"}, "escala": INT}, ["arquivo"])
async def boas_praticas(ctx, a: dict) -> list:
    contexto = {k: a[k] for k in ("protegidas", "contorno", "paleta", "chao", "acao", "loop", "render3d",
                                  "altura_alvo", "perfil", "limites") if a.get(k) is not None}
    try:
        rel = BP.checar_caminho(a["arquivo"], contexto, a.get("saida") or None,
                                int(a["escala"]) if a.get("escala") else None)
    except (ValueError, OSError) as e:
        raise ErroFerramenta(str(e))
    msg = (f"{'APROVADO' if rel['aprovado'] else 'REPROVADO'} nas regras automáticas. "
           f"Graves: {rel['graves'] or '-'}; leves: {rel['leves'] or '-'}.\n{rel['resumo']}\n"
           f"Gravado: {rel['json']} e {rel['png']}. Regras de olho (revisor): {', '.join(rel['regras_de_olho'])}.")
    im = Image.open(rel["png"]).convert("RGBA")
    if max(im.size) > 1600:
        k = 1600 / max(im.size)
        im = im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.NEAREST)
    return [texto(msg), imagem(pixels.png_b64(im))]
