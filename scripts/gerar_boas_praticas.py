"""Gera docs/boas-praticas.md a partir de src/horys_pixel/boas_praticas.json (a fonte única das regras BP).

Rode depois de mudar o JSON: uv run python scripts/gerar_boas_praticas.py
"""
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
d = json.loads((RAIZ / "src" / "horys_pixel" / "boas_praticas.json").read_text(encoding="utf-8"))

GRUPOS = [("forma", "Forma e silhueta"), ("contorno", "Contorno"), ("cor", "Cor e paleta"), ("luz", "Luz e sombra"),
          ("clusters", "Clusters e ruído"), ("linhas", "Linhas e curvas"), ("animacao", "Animação"),
          ("direcoes", "Direções e consistência"), ("leitura", "Leitura no jogo")]

CAB = """# Boas práticas de pixel art (horys)

> Gerado de `src/horys_pixel/boas_praticas.json` por `scripts/gerar_boas_praticas.py`. Não edite à mão.
> Versão {versao}.

Um livro de regras só, sem repetição, juntando as notas do Obsidian (`pixelart/`), o ofício portado do
aseprite-ai-artist (`oficio_dados/regras/`), as lições do sprite-forge e do agent-sprite-forge (MIT), o portão do
motor (`motor/medir.py`, `sequencia/validar.py`), a skill pixelart-review e as lições do próprio Artur.
**Não há régua externa: a régua é o Artur** (a ficha e os sprites em `_aprovados`). Quando a ficha registrar
outra decisão, a ficha vence.

## Envelope (perfeicao.md §5)
- Humanoide chibi 32 px (quadro 48×48, cabeça 40–45%); monstro 48 px (até 64) com 3–5 massas.
- ≤ 20 cores; contorno escuro de 1 px (selout aceito); 2–3 tons por material; luz de cima-esquerda.
- Nada menor que 2×2 px, salvo olho e brilho (cores protegidas). Nada existe em 1 px num quadro e some no outro.
- Linha dos pés estável. idle 2–4 · andar 4 (≤ 6) · ataque 3–5 · dano 2 · morte 3–4; 100–160 ms por quadro.
- Mudança de 15–40% dos pixels por quadro de andar é **diretriz, não portão**: num render 3D o bob do corpo mexe
  tudo, então BP40 e BP41 só informam com `render3d`.

## Como usar
- Código: `horys_pixel.boas_praticas` — `checar_quadro(rgba, contexto)`, `checar_animacao(quadros, contexto)`,
  `checar_direcoes(vistas, contexto)`, `overlay(rgba, resultados)`, `checar_caminho(arquivo, contexto, saida)`.
- MCP: `horys_boas_praticas` (PNG, pasta de quadros ou folha PNG+JSON) grava `<x>_praticas.json` e o overlay
  `<x>_praticas.png` (vermelho = grave, amarelo = leve).
- Revisor: cita os ids BP; as regras de **olho** são dele, as automáticas vêm do JSON (não conte pixel a olho).
- Severidade: **grave** aparece em 1× ou quebra o envelope (reprova); **leve** só ampliado (vira ajuste).
- Contexto: `protegidas` (olho, brilho, emissivo), `contorno`, `paleta`, `chao`, `acao`, `loop`, `render3d`,
  `altura_alvo`, `perfil` (16/32/64), `limites` (`{{"BP12": 24}}`).

Regras: {n} ({auto} automáticas, {olho} de olho).
"""


def limite(r):
    lim = r["limite"]
    if isinstance(lim, dict):
        return ", ".join(f"{k}: {v}" for k, v in lim.items())
    if isinstance(lim, list):
        return "–".join(str(x) for x in lim)
    return str(lim)


regras = d["regras"]
auto = sum(1 for r in regras if r.get("metrica"))
linhas = [CAB.format(versao=d["versao"], n=len(regras), auto=auto, olho=len(regras) - auto)]
for g, titulo in GRUPOS:
    rs = [r for r in regras if r["grupo"] == g]
    linhas.append(f"\n## {titulo}\n\n| id | regra | por quê | medida (limite) | sev. | fonte |\n|---|---|---|---|---|---|")
    for r in rs:
        if r.get("metrica"):
            med = f"`{r['metrica']}`: {r.get('medida', '')} ({limite(r)})"
        else:
            resto = str(r["limite"])[4:].strip(": ()")
            med = "olho do revisor" + (f" — {resto}" if resto else "")
        linhas.append(f"| {r['id']} | {r['titulo']} | {r['porque']} | {med} | {r['severidade']} | "
                      f"{', '.join(r['fonte'])} |")
linhas.append("\n## Fontes\n")
for k, v in d["fontes"].items():
    linhas.append(f"- **{k}**: {v}")
(RAIZ / "docs" / "boas-praticas.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
print(f"docs/boas-praticas.md gerado ({len(regras)} regras, {auto} automáticas)")
