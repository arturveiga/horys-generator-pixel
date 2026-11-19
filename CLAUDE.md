# horys-generator-pixel

Recomeço do zero em 2026-11-16. O histórico anterior (notas, resultados e documentos antigos) não vale como base de
decisão: julgue pelo código e pelo que for medido agora. O backup do estado antigo está em `git stash list`
("backup antes do zero 2026-11-16") e no histórico do git.

## Objetivo
Pixel art 2D top-down **constante** a partir de uma referência. Constância em três níveis: entre quadros, entre
direções e entre assets do mesmo jogo.

## Fatos que decidem a arquitetura
- Gerador de imagem não mantém identidade entre quadros: cada imagem redesenha o personagem.
- LLM digitando pixel não sustenta forma acima de ~16 px. Script não inventa forma: só lê, encaixa e limpa.
- Reduzir imagem grande apaga detalhe menor que o pixel final. A arte vem do gerador JÁ na altura final (prompt.md).
- Só geometria renderizada com câmera e luz fixas dá constância por construção: o movimento vem do Blender.

## Fluxo (a ordem é do Artur: arte parada aprovada primeiro, Blender depois)
`comousar.md` é o passo a passo; `prompt.md` diz como a imagem do gerador tem que vir.
1. `horys ler`: imagem do gerador -> arte parada 1x (frente, lado, costas), lida na grade da própria imagem.
2. `horys paleta` -> o Artur aprova arte e paleta (`horys aprovar`, preso ao sha256 do arquivo).
3. Modelo 3D no Blender; `horys gabarito`: render parado nas vistas do jogo x arte aprovada (silhueta >= 85%,
   materiais >= 75%, altura ±8%). Sem gabarito válido, a animação recusa rodar.
4. `horys animar`: ações × 8 direções -> pós (paleta travada, pixel solto, anticintilação, contorno 1 px) ->
   portões (bloqueiam). `horys exportar` só com portões ok.
5. `horys visor`: página local só para ver (porta 8770). Aprovação é pelo terminal, depois que o Artur disser sim.

## Código
- `src/horys_pixel/`: `leitura.py`, `paleta.py`, `cor.py`, `jogo.py`, `asset.py`, `aprovacao.py`, `gabarito.py`,
  `pos.py`, `portoes.py`, `anticintilacao.py`, `folha.py`, `fluxo.py`, `prompt.py`, `cli.py`, `visor/`, `blender/`
  (`dentro.py` roda dentro do Blender: só stdlib + bpy).
- `jogo.json`: contrato do jogo (escala `px_por_metro`, câmera, luz, quadro, direções, portões). Nenhum asset
  sobrescreve. A câmera NUNCA ajusta a escala ao asset.
- `assets/<nome>/`: um asset por pasta (`asset.json`, `gerada.png`, `arte/`, `paleta.json`, `aprovado.json`,
  `blender/`, `saida/`). `saida/` é gerada: não edite.

## Regras de trabalho
- Nunca chame algo visual de bom sem abrir o PNG. Mostre lado a lado com a referência (o visor e `gabarito.png`).
- Portão ou guarda que falha bloqueia; não contorne com flag, não afrouxe limite sem medir e sem o Artur saber.
- Aprovação é do Artur: só rode `horys aprovar` depois que ele disser sim (teste automatizado só em cópia, fora do
  repo, com comentário "TESTE").
- Uma mudança por vez, com teste. Quando uma abordagem falhar 2 vezes, pare e relate.
- Não commite sem o Artur pedir.
- Ambiente: Windows. Instalar: `uv sync --extra dev`. Testes: `uv run --extra dev pytest -q` (ou
  `PYTHONPATH=src python -m pytest -q`). Blender em `C:\Program Files\Blender Foundation\Blender 5.2`.

## Decisões em aberto (pergunte antes de mudar)
1. Ângulo da câmera (hoje 43°), altura do humano (hoje 44 px, a da referência do bonequinho), 8 direções.
2. Projeção da arte aprovada como textura no modelo (para os detalhes da arte aparecerem em todo quadro): ainda não
   existe; hoje o modelo usa cor chapada por família.
3. Animação por armature/Mixamo/KayKit (`timeline`) além das procedurais.
