# Decisões

## Tomadas (2026-11-05)
| Decisão | Por quê |
|---|---|
| Nome `horys-pixel`, repo em `workspace/repos/horys/horys-generator-pixel` | pedido do Artur |
| Repo novo, código próprio; o `aseprite-mcp` do sloplink é só inspiração (MIT) | ferramenta que conhece o estilo, não genérica |
| Aseprite é a tela; a grade de texto vira formato interno do portão | desenhar e corrigir junto, ao vivo |
| Servidor em Python | o motor de estilo (`grade`, `medir`, `conceito`, `calibrar`) já é Python |
| Motor escolhido por pedido: Claude ou Codex | os dois falam MCP; perguntas e aprovações viram ferramentas |
| Interface por extensão Lua, sem fork do Aseprite | a API de `Dialog` basta; fork exige manter e compilar |
| REA não entra | o código do Aseprite é aberto (`C:\aseprite`); REA é para binário |
| A ferramenta pede uma imagem de referência de qualquer origem; gerar (Codex ou LoRA local) é opção | a imagem só facilita a geração e nunca vira asset; o Claude não gera imagem |
| **Vai ser distribuído um dia** | por isso: estilo como pacote, nada de arte de terceiros no repo, pesos baixados por quem usa |
| **Estilo como pacote** (`estilos/<nome>/`); o Horys Pixel Liso é o primeiro e aponta para o Obsidian | cada pessoa cria o próprio estilo; a KB do Artur continua sendo a fonte da verdade dele |
| **A `pixelart-review` entra no repo** como a skill de revisão | o medidor dela e o `medir.py` se juntam num só; revisar qualquer PNG ou `.aseprite`, comparar vistas, medir "IA slop" |
| **Treino com kohya-ss/sd-scripts**, perfis por VRAM | CLI e TOML (o agente roda sozinho), cobre SD 1.5 e SDXL, roda em 6–8 GB, Apache-2.0 |

## Padrão até o Artur dizer outra coisa
| Decisão | Padrão |
|---|---|
| Revisor | cruzado (o outro motor revisa) |
| Licença do repo | MIT (a confirmar antes de publicar) |

## Em aberto
- Publicar o Horys Pixel Liso como pacote de exemplo ou deixá-lo só local (a base tem conceitos de cursos, creditados).
- Juntar a `horys-generator` neste repo ou não.
- Suporte a macOS e Linux (Windows primeiro).

## SpriteKiln como gerador de base (TODO 1.2, 2026-11-07)
Fonte: `docs/format.md`, `docs/agent/spec.md`, `docs/agent/style.md` e `spritekiln/pipeline.py` do SpriteKiln (MIT).

| Pergunta | Resposta | Evidência |
|---|---|---|
| (a) Renderiza por parte? | **Não exporta, mas o dado existe.** O render guarda por pixel o id da parte (`gb.gid`); `pipeline.parts_mask(spec, env, yaw, partes)` devolve a máscara dos pixels visíveis de cada parte. Dá posse 100% dos pixels **visíveis**. A anatomia oculta (o que fica sob a peça de cima) não sai: é um z-buffer só. Para ela, renderizar cada parte sozinha (spec filtrado) na mesma câmera. | `pipeline.py:181-190`; `api.py:194-225` usa isso no `pose --focus` |
| (b) Trava uma paleta Horys? | **Sim.** `palette:` aceita arquivo YAML de rampas; cada material aponta para uma rampa (índice 0 = contorno). Dá para gerar a rampa a partir da `paleta` do estilo Horys. | `spec.md:17, 189-220`; `spec.py:157-164` |
| (c) Desliga o contorno dele? | **Sim.** `render: {outline: none}`; linhas internas por `lines: depth` (só onde partes se sobrepõem) ou desligáveis por material (`line: false`). | `spec.md:132-145` |
| (d) Vista lateral? | **Sim.** `view: side` (perfil, direções e/w; w espelhado). `camera: {pitch: 10}` mostra um pouco do topo, próximo do Tiny Swords. | `spec.md:13, 33-49` |
| Saída | atlas PNG + JSON "hash" do Aseprite (+ normal e emissivo), durações por quadro, eventos, sockets e pivô no bloco `spritekiln` | `format.md:9-44` |

**Decisão:** integrar **sim**, como dependência opcional, chamando a API Python dele (não só a CLI), porque a posse
por parte só existe internamente (`parts_mask`). Configuração padrão para o Horys: `view: side`, `pitch: ~10`,
`outline: none` (o Horys gera o anel), paleta gerada do estilo, `lines: depth`.

Riscos: `parts_mask` é função interna (pode mudar entre versões → fixar versão e cobrir com teste); a anatomia
oculta por render isolado pode não bater pixel a pixel com o composto (cluster/limpeza dependem da vizinhança);
o visual de "3D pixelizado" ainda precisa da medição da 1.3 antes de investir na Fase 2.

### TODO 1.3 — base SpriteKiln crua no portão do Horys (2026-11-07)
Aldeão `view: side`, altura 61–63 px, quadro 96, paleta `gothic`, sem contorno, sem nenhum tratamento do Horys.
`medir.py --tipo personagem --contorno-px 0 --com-efeito` (idle 6, correr 8, ataque 8). Resultado: 15 falhas, 4 avisos.

| Grupo | Resultado | Leitura |
|---|---|---|
| Animação (A01–A08) | **passa** (só avisos: quique do correr 1,4 px, sem sombra no chão) | a consistência que buscávamos vem pronta: linha do pé estável, massa estável, sem boil, sem quadros repetidos |
| Paleta e cores (M01, M03) | falha: 23–26 cores fora da paleta Horys (limite 13) | esperado: paleta `gothic`. Resolve com a paleta do estilo no spec (2.3) |
| Valor (M08) | falha: ~60% do preenchimento escuro | esperado da `gothic` e da luz padrão; trocar paleta e luz |
| Órfãos (M04) e cluster (M05) | falha: 3,7–5% de órfãos, cluster médio 8–9 px (meta 45) | **o problema real**: o sombreado do render é picotado, longe do Tiny. Precisa de limpeza (`horys_limpar`) e/ou `shading: flat/toon` |
| Contorno | não medido (0 px pedido) | o Horys gera o anel depois |

**Conclusão:** seguir para a Fase 2. A animação já passa no portão sem retoque; o que falha é cor e cluster,
justamente o que o Horys trata. Antes de codar a importação, testar `shading: toon` + paleta Horys no spec para
ver quanto do M04/M05 some sem limpeza.

### Teste: paleta Horys + `shading: toon` no spec (2026-11-07)
Spec `aldeao_horys.yaml` (cópia do aldeão): rampas da `paleta_padrao.json` com o contorno `#1c1828` no índice 0,
`render: {outline: none, shading: toon}`. Mesma medição da 1.3.

| Métrica | Cru (`gothic`, soft) | Paleta Horys + toon |
|---|---|---|
| Falhas | 15 | **6** |
| Cores (M03, limite 13) | 23–26 | **11–12, todas da paleta (M01 passa)** |
| Escuro (M08) | ~60% | **0%** |
| Órfãos (M04) | 3,7% | 2,2–2,9% (ainda falha) |
| Cluster médio (M05, meta 45) | 8–9 px | 12–13 px (ainda falha) |
| Luz (M15) | — | aviso: luz vem da esquerda; o Horys espera da direita/cima |

Conclusão: cor e valor se resolvem **só com o spec**. O picotado (M04/M05) melhora, mas não some: fica para o
`horys_limpar` na importação (tarefa 2.3) ou para `thresholds`/`min_run` no spec. A luz se acerta no estilo do
SpriteKiln (`light`) para bater com o M15.
