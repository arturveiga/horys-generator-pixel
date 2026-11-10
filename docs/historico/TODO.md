> Arquivado em 2026-11-09. O plano vigente é [new-task.md](../../new-task.md); as fases 0–3 daqui continuam valendo no código.

# TODO — SpriteKiln como base, Horys como acabamento

Data: 2026-11-07 · Origem: `analise-perfect.md` + comparação com SpriteKiln e NoctAssetForge.

## A ideia

O SpriteKiln (licença MIT, Python puro, `pipx install "spritekiln[mcp]"`) gera a **base**: pose, direções e quadros
consistentes a partir de um modelo 3D procedural em YAML. O Horys faz o **acabamento**: importa para o Aseprite,
aplica paleta e estilo, recebe a mão por cima, passa no portão de medidas e no revisor.

```
briefing (Horys) → spec YAML (SpriteKiln) → render atlas + JSON Aseprite → horys_importar_kiln
→ referencia por quadro → limpar/afinar/mão → portão → revisor → aprovação → exportar
```

Ganho esperado: a consistência entre quadros e direções vem do modelo, não do desenho. E, se o SpriteKiln
renderizar **cada parte separada**, a posse dos pixels sai certa por construção, o que resolve boa parte dos
P0-1/P0-2 sem `recortar`.

Regra: **não copiar código do SpriteKiln para dentro do repo.** Usar como dependência opcional (CLI ou MCP) e
manter o crédito MIT no `THIRD_PARTY.md`, se algum dia algo for vendorizado.

## Quem faz o quê

| Executor | Bom para | Não usar para |
|---|---|---|
| **Claude Desktop** (esta sessão) | decisões de arquitetura, specs de tarefa, olhar imagens, revisar a arte, uso ao vivo no Aseprite pelo MCP, revisar PRs | edição mecânica em massa |
| **Codex** | tarefas fechadas com critério de aceite: um módulo, uma ferramenta, testes de unidade | decisões de design e julgamento visual |
| **Claude Code terminal** | rodar a suíte e lotes longos (render, calibração), git/PR, depurar falhas de teste, scripts | revisão estética |

Cada tarefa abaixo tem dono, entrada e "pronto quando". Marque `[x]` ao concluir e anote o commit. `[~]` = parcial (ver ◐).

---

## Fase 0 — Chão firme (antes de integrar)

- [x] **0.1 · Rodar a suíte inteira e registrar** — *Claude Code terminal*
  `python -m pytest -q` + teste Lua do `test_extensao_lua.py`. Rodar as reproduções 9.1 e 9.2 da análise.
  Pronto quando: resultado colado em `PENDENCIAS.md` (verdes, vermelhos, e se 9.1/9.2 reproduzem).
  ✔ 2026-11-07: `pytest -q` → 176 passaram, 0 falhas (inclui os 29 de partes, que nunca tinham rodado). 9.1 e 9.2 reproduzem (P0-1 e P0-2 confirmados); registrado no `PENDENCIAS.md`.
- [x] **0.2 · Skill no motor Gerar (P0-3)** — *Codex*
  Tirar a proibição de leitura em `daemon/pedidos.py:26-29` para o Claude; entregar as seções da skill no prompt
  ou por `horys_skill(secao)`. Teste `test_prompt_pedido_entrega_skill`.
  Pronto quando: o teste passa e o prompt contém "Briefing", "5b" e "Portão".
  ✔ 2026-11-07: `daemon/pedidos.prompt_pedido` entrega a SKILL.md inteira (sem o cabeçalho YAML), tirou a proibição de ler arquivos e a imposição do preset do ferreiro no prompt. `test_prompt_pedido_entrega_skill`. Obs.: a própria SKILL.md (linha ~73) ainda sugere o ferreiro para humanoide → Fase 3.3.
- [x] **0.3 · Exportar e revisar exigem portão aprovado (P1-8)** — *Codex*
  Pronto quando: `test_exportar_recusa_portao_reprovado` e `test_revisar_recusa_portao_reprovado` passam.
  ✔ 2026-11-07: `horys_exportar` não copia com portão REPROVADO sem `forcar` + `motivo` (grava `entrega.json`); `horys_revisar` recusa pasta com `PORTÃO DE MEDIDAS: REPROVADO` ou `PARTES REPROVADAS` (exceto etapa conceito). Testes em `tests/test_fase0.py`. A exigência de revisor PASS antes de exportar ficou de fora.
- [x] **0.4 · Aprovação automática não vira gosto (P1-13)** — *Codex*
  Pronto quando: `test_gosto_ignora_pendente_usuario` passa.
  ✔ 2026-11-07: `gosto.registrar_aprovacao` ignora resposta automática (`pendente_usuario`).
- [ ] **0.5 · Revisar os PRs da fase 0** — *Claude Desktop*
  ⏸ nada commitado ainda (o repo não tem commits); revisar o diff junto com o Artur antes do primeiro commit.

## Fase 1 — Prova de conceito da ponte (decidir se vale)

- [x] **1.1 · Instalar o SpriteKiln e fazer um personagem de teste** — *Claude Code terminal*
  `pipx install "spritekiln[mcp,fast]"`, `spritekiln new aldeao --template humanoid`, render de `idle` e `walk`
  em `s,e`, altura 64. Pronto quando: atlas, JSON e GIFs gerados numa pasta `tmp-kiln/` (fora do git).
- [x] **1.2 · Levantar o que o SpriteKiln exporta** — *Claude Desktop*
  Ler `docs/format.md`, `docs/agent/spec.md` e `docs/agent/style.md`. Responder:
  (a) dá para renderizar **por parte** (uma camada por parte do esqueleto)? (b) dá para travar a paleta de um
  estilo Horys? (c) dá para desligar o contorno dele (o Horys gera o próprio)? (d) há vista lateral, que o
  Tiny Swords usa?
  Pronto quando: respostas em `docs/decisoes.md`, com a decisão "integrar sim/não e como".
- [x] **1.3 · Olhar o resultado contra a régua Tiny** — *Claude Desktop*
  Rodar o `horys_portao`/`medir.py` no PNG do 1.1 sem mexer em nada e ver o revisor.
  Pronto quando: notas registradas. Se a base passar perto de 50% de aceitação, seguir; se não, rever a ideia.

**Ponto de decisão:** só seguir para a Fase 2 se 1.2 e 1.3 derem sim.

## Fase 2 — Importação para o Horys

- [x] **2.1 · `horys_importar_kiln`** — *Codex* · spec: `docs/tarefas/fase2-kiln.md`
  Spec escrita pelo Claude Desktop antes (entrada: JSON "hash" Aseprite + atlas; saída: sprite com um quadro por
  frame, a imagem na camada `referencia`, durações e eventos na ficha). Módulo puro testável + ferramenta MCP.
  Pronto quando: teste com atlas sintético reconstrói quadros, durações e tags.
  ✔ 2026-11-07: `src/horys_pixel/kiln.py` (ler_atlas, filtrar) + `ferramentas/kiln.py` (`horys_importar_kiln`); feito pelo Claude Code (Codex não foi usado). Testes em `tests/test_kiln.py`.
- [~] **2.2 · Importação por parte (se 1.2a = sim)** — *Codex*
  Cada parte renderizada vai para a camada da parte no Aseprite; `compor(partes) == referencia` em todo quadro;
  posse 100% por construção. Pronto quando: `horys_partes_checar` passa num humanoide importado, sem `recortar`.
  ◐ 2026-11-07: código feito (`kiln.mascaras_por_parte` roda no venv do Kiln por subprocesso; `kiln.distribuir`; `spec`+`grupos` na importação) e testado contra o Kiln real (máscaras disjuntas). E2E no Aseprite real (2026-11-07, `tmp-kiln/e2e/aldeao-mod`): 22 quadros distribuídos em 4 partes em 15 s, composição = referência. `horys_partes_checar` **reprova (226 erros)**, como previsto: só com pixels visíveis, o braço da frente cobre quase todo o torso de perfil, o `corpo` fica em 2–3 pedaços e não há anatomia oculta (sem-sobreposicao, buraco-1px, cobertura 0%). **Falta 2.2b:** renderizar cada parte isolada para preencher o que fica escondido.
- [~] **2.2b · Anatomia oculta pelo render isolado** — *Claude Code*
  Para cada parte inferior de junção, renderizar só ela (spec filtrado, mesma câmera) e preencher os pixels sob a superior; respeitar `max_oculto_px`. Pronto quando: `horys_partes_checar` do aldeao-mod sem `sem-sobreposicao`/`buraco-1px`/`parte-desconexa` no corpo.
  ◐ 2026-11-08: importador agora renderiza cada grupo isolado, preenche apenas a faixa coberta por camadas superiores
  e limitada por `max_oculto_px` (global ou por parte), preservando a composição pixel a pixel. Testes puros verdes e
  prova no aldeão real adicionou 89 px ocultos ao corpo sem alterar a referência. O fixture antigo ainda tem
  `buraco-1px` no pescoço/ombro e braço traseiro vazio no primeiro quadro; falta calibrar os contratos/grupos e os
  limites por junção antes de marcar concluído.
- [x] **2.3 · Mapeamento de paleta Kiln → estilo Horys** — *Codex*
  Reaproveitar `horys_converter` (moda) por quadro, com a mesma tabela de cores em todos os quadros (sem
  cintilação). Pronto quando: A01–A10 não pioram em relação ao render cru.
  ✔ 2026-11-07: `horys_paleta_kiln` (rampas do estilo → YAML do Kiln) + `limpar_min` na importação (`kiln.limpar_sequencia`, sem boil). Aldeão com min 3: órfãos 2,2–2,9% → 0,5–0,7%, A08 sem piora. Portão: 15 → 6 → **4 falhas** (só M05 cluster 17–19 px e 1 quadro de órfão 1,44%).
- [x] **2.4 · Ponte de spec: briefing → YAML** — *Claude Desktop*
  Seção nova na `SKILL.md`: como transformar o briefing (altura, vista, proporção, objeto-assinatura) num spec
  do SpriteKiln e quando usar a base Kiln em vez de desenhar do zero (personagem animado: sim; ícone/prop: não).
- [x] **2.5 · Suíte + e2e da importação** — *Claude Code terminal*
  Pronto quando: suíte verde e um aldeão `idle` 4 quadros importado, convertido e passando no portão.
  ◐ 2026-11-07: suíte **181 verdes** (incl. 10 de `test_kiln.py`); importação testada no Aseprite falso. E2E no Aseprite real feito: render Pixel Liso → `horys_importar_kiln` (22 quadros, 3 tags, limpeza 3) → `horys_contorno` → `horys_portao` → `.aseprite` reaberto e igual à folha. Portão: **2 falhas por estado** — M03 cores 13–18 (limite 10; aço, madeira e efeitos somam rampas) e M05 cluster 26–29 px (meta 45). Achados no caminho: `.mcp.json` dependia de `CLAUDE_PLUGIN_ROOT` (corrigido com fallback) e `partes.py` quebrava o relatório em `parte-desconexa` (corrigido + teste). Próximo para aprovar: menos rampas no spec e mão por cima (3.1).

## Fase 3 — Acabamento e qualidade

- [ ] **3.1 · Mão por cima nos quadros-chave** — *Claude Desktop (ao vivo no Aseprite)*
  Limpar o "cara de 3D": rosto, cachos, linhas internas, squash e ponta atrasada. Registrar em `praticas.md`
  o que sempre precisa de retoque.
- [x] **3.2 · Fatiamento: corrigir só o que a importação não cobre** — *Codex*
  P1-3 (linha no lado certo), P1-4 (`estender` com cor do interior), P1-6 (desconexas declaradas).
  Se a importação por parte não funcionar, aqui entram P0-1/P0-2 completos (`mapa-partes`, `fatiar`, `fantasma`).
  ✔ 2026-11-07: junções ganharam política de linha (`por_contraste`/`obrigatoria`/`proibida`) e a linha só vale no
  lado móvel; `estender` busca a moda do interior e pode excluir cores de linha; `componentes_max` e
  `espessura_fina` permitem peças declaradamente desconexas/finas. Testes de óculos e linha escura incluídos.
- [x] **3.3 · Preset humanoide base (P0-4)** — *Codex*
  Alinhar as partes com o esqueleto do template `humanoid` do SpriteKiln para os nomes baterem.
  ✔ 2026-11-07: preset `humanoide` sem acessórios obrigatórios, com braços/pernas/corpo/cabeça na ordem de pilha;
  `humanoide-ferreiro` continua variante específica. Teste `test_preset_humanoide_base_sem_extras_e_ordem_kiln`.
- [x] **3.4 · Estado e ficha confiáveis (P1-1, P1-2)** — *Codex*
  Hash de conteúdo em `partes_checagem`; `horys_id` em `sprite.properties`.
  ✔ 2026-11-07: checagem grava SHA-256 de contratos, partes, referência e quadros; o gate recalcula e recusa
  checagem desatualizada ou Aseprite desconectado. A ficha usa `horys_id` persistido em `sprite.properties`, com
  migração/alias das fichas antigas; alterações de contrato exigem motivo e invalidam a checagem.
- [x] **3.5 · Escala inteira e composto limpo (P2-3, P2-4)** — *Codex*
  ✔ 2026-11-07: miniaturas só reduzem por divisor inteiro exato; vista explodida escolhe escala inteira 4×..1×;
  leitura composta ignora por padrão `revisao`, `referencia` e `mapa-partes` no Lua e no Aseprite falso.
  Teste `test_composto_ignora_revisao_e_referencia`. Suíte completa: **186 passaram**.
- [ ] **3.6 · Calibração** — *Claude Code terminal* (lote) + *Claude Desktop* (olho)
  Rodar portão e revisor em 10 personagens Kiln+Horys; Artur aprova ou recusa; medir a concordância.

## Fase 4 — Uso real

- [ ] **4.1 · Ferreiro do Hunvix pelo fluxo novo** — *Claude Desktop*
  `idle` e martelada, 2 direções, até a exportação. Comparar com o ferreiro feito à mão.
- [ ] **4.2 · Atualizar README, `docs/fases.md` e a skill** — *Codex*
- [ ] **4.3 · PR final e limpeza dos `tmp-*`** — *Claude Code terminal*

---

## Regras de passagem entre executores

1. Toda tarefa para o Codex sai com: arquivos envolvidos, comportamento esperado, nome dos testes e "pronto quando".
   Quem escreve é o Claude Desktop.
2. Toda entrega do Codex passa pela suíte no Claude Code terminal antes de ser marcada.
3. Nada é marcado `[x]` sem evidência (teste verde, imagem olhada ou commit citado).
4. Um executor por arquivo de cada vez; conflito → quem chegou depois espera.
