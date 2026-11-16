"""Gera docs/ferramentas.md a partir do registro de ferramentas (a documentação sempre bate com o código)."""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from horys_pixel.ferramentas import registro  # noqa: E402

registro.carregar_todas()
GRUPOS = {"desenho": "Desenho (ponte com o Aseprite)", "conversa": "Conversa (painel do Aseprite)",
          "estilo": "Estilo", "partes": "Partes (fatiamento modular)", "pedidos": "Pedidos", "gosto": "Memória de gosto", "treino": "Treino",
          "kiln": "SpriteKiln (base 3D animada)",
          "sequencia": "Sequência (animação de qualquer fonte)", "entrega": "Entrega e retoque",
          "oficio": "Ofício (base de pixel art)", "pele": "Base + Pele (master, partes, vestir, animar, travas)",
          "vfx": "Efeitos (pixelfx)", "aiartist": "Tileset, paleta e guarda de correção (portado do ai-artist)",
          "guia_kiln": "Guia de pose do SpriteKiln (cor por parte)",
          "blender": "Pipeline Blender (paleta, render 3D para pixel, recolor)",
          "estudio": "Horys Estúdio (interface)", "boas_praticas": "Boas práticas (checagem)",
          "base_eldiran": "Corpo-base Eldiran"}
por_grupo = {}
for f in registro.REGISTRO.values():
    por_grupo.setdefault(f.funcao.__module__.rsplit(".", 1)[-1], []).append(f)
linhas = ["# Ferramentas MCP", "",
          "Gerado por `scripts/gerar_docs_ferramentas.py` a partir do código — não edite à mão.", "",
          "Coordenadas 0-based, (0,0) no canto de cima à esquerda; quadros e camadas 0-based.", ""]
for chave, titulo in GRUPOS.items():
    fs = por_grupo.get(chave, [])
    if not fs:
        continue
    linhas += [f"## {titulo}", ""]
    for f in fs:
        props = ", ".join(f"`{p}`" + ("*" if p in f.esquema.get("required", []) else "")
                          for p in f.esquema.get("properties", {}))
        linhas += [f"### `{f.nome}`", "", f.descricao, "", f"Parâmetros: {props or '—'} (`*` = obrigatório)", ""]
(RAIZ / "docs" / "ferramentas.md").write_text("\n".join(linhas), encoding="utf-8")
print(f"{len(registro.REGISTRO)} ferramentas em docs/ferramentas.md")
