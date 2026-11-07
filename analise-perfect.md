# Análise final — horys-generator-pixel depois do fatiamento modular

Data: 2026-11-07 · Revisor: Claude Opus 5.5 (revisão independente; nenhum código de produção alterado; nenhum commit)
Escopo: `src/`, `extension/`, `tools/`, `skills/`, `agents/`, `docs/`, `tests/`, prompts do motor e do revisor,
integração Aseprite/MCP. Foco pedido: o que falta para criar **pixel art de alta qualidade de forma confiável**
(fatiamento modular, estilo, silhueta, proporção, paleta, volume, contorno, legibilidade, animação, validação visual,
referências, fluxo de revisão e uso real no Aseprite).

---

## 0. Como esta revisão foi feita (e os limites dela)

- **Leitura integral** de: `src/horys_pixel/partes.py`, `ferramentas/partes.py`, `ferramentas/estilo.py`,
  `ferramentas/desenho.py`, `ferramentas/pedidos.py`, `ferramentas/gosto.py`, `ferramentas/treino.py`,
  `ferramentas/registro.py`, `daemon/pedidos.py`, `daemon/motores.py`, `daemon/contexto.py`, `mcp_ponte.py`,
  `grade_io.py`, `tools/fatiar_ferreiro.lua`, `skills/horys-pixel/SKILL.md`, `motor/revisor_prompt.md`,
  `agents/revisor.md`, `scripts/gerar_agente.py`, `scripts/gerar_docs_ferramentas.py`, `docs/arquitetura.md`,
  `PENDENCIAS.md`, `VALIDACAO-CODEX.md`, `tests/test_partes.py`, `tests/test_partes_ferramentas.py`,
  `tests/aseprite_falso.py`, `tests/conftest.py`, `tests/test_validacao_codex.py`. Leitura parcial dirigida de
  `motor/grade.py` (camadas, montagem, exportação .aseprite, checagem), `motor/medir.py` (métricas M/A/E/T),
  `motor/pixel_review.py`, `extension/handlers.lua` (camada, quadro, escrever, ler) e `docs/ferramentas.md`.
- **Não consegui executar Python nem pytest**: nesta sessão não interativa, todo `python …`/`pytest` exigiu
  aprovação e foi bloqueado. O servidor MCP `horys` também falhou ao conectar (`CONNECTION_CLOSED`), então **não houve
  teste ao vivo no Aseprite**. Tudo abaixo sobre comportamento é **análise estática com rastreamento manual** do
  código; as reproduções estão escritas para você rodar (seção 9).
- A KB do Obsidian (`…\pixel-liso\tecnicas\personagens.md` etc.) **não pôde ser lida** (permissão negada). Onde a
  skill delega para ela, marquei como "não verificado".

### Evidência de que os testes do fatiamento NUNCA rodaram

| Evidência | Valor observado |
|---|---|
| `.pytest_cache/v/cache/nodeids` | última escrita **2026-11-06 08:12**, 139 ids, **nenhum** contém `partes` |
| `.pytest_cache/v/cache/lastfailed` | `tests/test_validacao_codex.py::test_treino_args_nao_contorna_executar_false` (falhou na última execução registrada; o código de `ferramentas/treino.py:48` parece corrigido depois, mas não há execução posterior) |
| `src/horys_pixel/__pycache__/` | **não existe** `partes.cpython-311.pyc` (módulo criado 11-07 10:52 nunca foi importado por este Python) |
| `src/horys_pixel/ferramentas/__pycache__/` | **não existe** `partes.cpython-311.pyc`; `pedidos.cpython-311.pyc` é de 11-05 22:20, mas `pedidos.py` mudou em 11-07 10:49 |
| `tests/__pycache__/` | **não existem** `test_partes*.pyc` |
| Fontes do fatiamento | `partes.py`, `ferramentas/partes.py`, `ferramentas/estilo.py`, `daemon/pedidos.py`, `registro.py`, `mcp_ponte.py`, `revisor_prompt.md`, `SKILL.md`, docs e testes: todos de 11-07 10:48–10:55 |

Conclusão: **o fatiamento modular foi entregue sem nenhuma execução de teste** (nem import). Rastreei à mão os 21
testes de `test_partes.py` e os 8 de `test_partes_ferramentas.py` (geometria, contagens, mensagens): **pela minha
leitura eles devem passar** — mas isso não substitui rodá-los, e (mais importante) eles testam o comportamento
**errado** em dois pontos centrais (achados P0-1 e P0-2).

---

## 1. Resumo executivo

1. **O núcleo técnico é bom e testável** (módulo puro sem Aseprite, contratos de junção validados, relatório
   texto/JSON, vista explodida, dupla checagem de composição com reversão, portão que reprova e exportação que
   recusa por erro de partes). A infraestrutura Aseprite/MCP, a paleta travada, o contorno externo gerado e as
   métricas calibradas do portão continuam sólidas.
2. **Mas o fatiamento modular, como está, não entrega partes animáveis confiáveis.** Três defeitos estruturais:
   - **P0-1 — o fluxo duplica em vez de separar e o validador aprova "fantasmas".** `horys_partes_recortar` só
     *copia* da referência; nada remove os pixels da parte de baixo. A parte de baixo fica com a figura inteira, o
     simulador de buracos nunca acha buraco (a cópia tapa tudo) e a checagem passa. Ao mover o braço, aparece o
     braço velho por baixo. Os próprios testes codificam esse uso.
   - **P0-2 — o passo documentado "referência → recortar" é impossível a partir de partes vazias**: com todas as
     partes vazias, qualquer pixel novo muda a composição, então 100% é recusado.
   - **P0-4 — um preset de ferreiro é imposto a todo humanoide** (martelo, óculos, barba e avental obrigatórios;
     parte vazia = erro; parte desconexa = erro sem exceção para óculos), e a anatomia do preset tem o braço de
     trás *na frente* do corpo e não tem cabeça.
3. **O motor autônomo (botão Gerar) não recebe a skill** (P0-3): o prompt proíbe ler `SKILL.md` e afirma que as
   instruções vieram pelo MCP, mas as instruções MCP só dizem "siga a SKILL.md". Sem briefing, `praticas.md`,
   regras do portão e do revisor, a qualidade fica por conta do acaso.
4. **Estado de validação velho e burlável** (P1-1/P1-2): `partes_checagem.ok` nunca é invalidado, a ficha some ao
   "salvar como", o portão de animação é pulado sem Aseprite conectado e `horys_ficha modular=false` desliga tudo.
5. **Linhas internas e anatomia oculta geram artefatos** (P1-3/P1-4): a checagem aceita a linha desenhada na parte
   de baixo (que não se move com a móvel), a heurística "escuro < 70" conflita com a regra do próprio revisor ("linha
   interna só onde dois planos se fundiriam"), e `estender` propaga a cor da borda (linha/sombra) para baixo da peça
   de cima, criando faixa escura quando ela se move.
6. **Fora do fatiamento**: não há métrica de proporção, de separação de valores, de fidelidade à referência, de
   pillow/banding nem de consistência por parte entre quadros; as imagens mandadas ao agente/revisor são reduzidas
   em escala **não inteira** (jaggies falsos); a camada `revisao` visível contamina aprovações e medições; aprovação
   automática vira "gosto aprovado"; a exportação entrega portão REPROVADO.

**Veredito:** pronto como **ferramenta acompanhada** para desenhar, medir e revisar; **não pronto** para gerar
personagens modulares animáveis de alta qualidade sem supervisão. O caminho mais curto está na seção 6 (Fases 0–2
resolvem todos os P0 e os P1 do fatiamento).

---

## 2. Mapa de maturidade

Escala: 0 inexistente · 1 esboço · 2 funciona no caso feliz · 3 confiável com supervisão · 4 confiável e testado ·
5 confiável, testado ao vivo e calibrado.

| Área | Nível | Evidência principal | O que falta para subir |
|---|---|---|---|
| Ponte Aseprite (WS, handlers, token) | 4 | `handlers.lua`, testes Lua em batch (VALIDACAO §1) | fila/lock por sprite (P1-12) |
| Paleta travada e limite de cores | 4 | `grade.py:482-493`, M01/M03 em `medir.py` | separação de valores (P2-5) |
| Contorno externo (anel gerado) | 4 | `grade.py:330-339`, M06/M07 calibrados | — |
| Contorno/linha interna | 2 | `partes.py:257-272, 431-442`; `afinar` | política por junção, lado correto (P1-3) |
| Silhueta e legibilidade | 2 | `_silhueta.png` 1×/0,5×, M17, revisor L1 | métrica 0,5×, espaço negativo (P2-5) |
| Proporção e anatomia | 1 | só texto na skill ("massa de cima ~60%") | métrica de proporção, presets corretos (P1-7, P2-5) |
| Volume, luz e material | 2 | M05 cluster, M14/M15 só aviso | pillow/banding, valor (P2-5) |
| Animação (métricas) | 3 | A01–A10 calibrados no Tiny | métricas por parte, arco, deriva de junção (P2-5) |
| Fatiamento modular — validador | 2 | `partes.checar` bom em unidade | exclusividade/fantasma, desconexas, rotação (P0-1, P1-6, P2-1) |
| Fatiamento modular — ferramentas | 1 | `recortar` só copia; `estender` 1–2 px | fatiar por mapa, mover, máscara (P0-2, P1-9) |
| Anatomia oculta | 2 | `estender`, cobertura ≥ 90% | cor do interior, profundidade por junção (P1-4) |
| Referência → pixel (fidelidade) | 2 | `horys_converter` (moda) | métrica de fidelidade, quadro_ref (P1-5) |
| Revisor (LLM cruzado) | 3 | prompt com L1–L7, JSON, reserva | calibração, escala inteira, portão obrigatório (P2-3, P2-6, P1-8) |
| Fluxo autônomo (Gerar) | 1 | VALIDACAO §2: pedido Codex travou | entregar a skill, permissões claras (P0-3) |
| Estado/gates do pedido | 1 | `pedidos.py:40-49` | hash de conteúdo, ficha estável (P1-1, P1-2) |
| Exportação | 3 | `.aseprite` reaberto e conferido pixel a pixel | bloquear REPROVADO, contorno por parte (P1-8, P2-2) |
| Testes | 3 unidade / 1 e2e modular | 29 testes de partes nunca executados | rodar; e2e real; fluxo documentado (P1-11) |
| Docs geradas | 3 | `ferramentas.md` bate com o registro | teste de igualdade byte a byte, README velho (P3-2, P3-4) |

---

## 3. O que já está sólido (não mexer sem motivo)

1. **`partes.py` é puro e coeso**: só NumPy/SciPy, dataclasses `Juncao`/`Preset`/`Problema`/`Relatorio`, saída em
   texto e JSON, código de problema estável (`parte-vazia`, `buraco-1px`…), pontos para marcar. Fácil de evoluir.
2. **Validação de contratos** (`partes.py:56-73`): parte reservada, duplicada, junção com parte inexistente, móvel
   que não é inferior/superior e ordem invertida. Também é aplicada em `horys_ficha` e `horys_asset_novo`
   (`estilo.py:196-200, 230-232`).
3. **Preservação da composição em duas camadas de defesa**: predicado em Python (`_so_composicao_igual`,
   `partes.py:524-536`) e conferência real no Aseprite com reversão (`_aplicar_sem_mudar_composicao`,
   `ferramentas/partes.py:83-98`), com aviso explícito se a reversão falhar. O teste com `estender` sabotado
   (`test_partes_ferramentas.py:116-138`) cobre isso.
4. **Camada faltando é erro explícito** e a ordem das camadas é conferida (`estilo.py:61-75`), inclusive para
   `referencia`; `horys_contorno`, `horys_portao` e `horys_partes_checar` herdam isso.
5. **Portão integrado**: em asset modular, `gerar_versao` roda a checagem nos quadros gerados, grava
   `partes_checagem.txt`, `medidas/partes.json` e `<asset>_partes.png` **depois** do motor (não é apagado) e
   reprova (`estilo.py:480-488`); `horys_exportar` não copia nada com erro de partes (`estilo.py:531-534`).
6. **O `.grade` e o `grade.py` já guardam pixels ocultos por camada** (`grade.py:203-238, 355-386`) e o `.aseprite`
   exportado é reaberto e comparado pixel a pixel com a folha (`grade.py:426-464`).
7. **Revisor atualizado**: L7 cobra partes e manda abrir os três artefatos (`revisor_prompt.md:32, 44`);
   `agents/revisor.md` foi regenerado (cabeçalho de `gerar_agente.py` + prompt; mtimes coerentes).
8. **Docs de ferramentas regeneradas**: as descrições de `horys_partes_*` em `docs/ferramentas.md:289-318` batem
   com o código.
9. **Portão de medidas calibrado** (M01–M17, A01–A10, E01–E07, T01–T02) com régua Tiny e mutações (46/46 bons,
   19/19 estragados, segundo `PENDENCIAS.md` e `VALIDACAO-CODEX.md`).

---

## 4. Achados por prioridade

Formato de cada achado: **Tipo** (Bug/Risco · Arquitetura · Conhecimento · Opcional) · **Evidência** · **Impacto** ·
**Causa** · **Recomendação** · **Critério de aceite** · **Comprovação** (teste automático ou manual).

### P0 — bloqueiam qualidade confiável

#### P0-1 · O fatiamento duplica a figura e o validador aprova "fantasmas"
- **Tipo:** Bug de projeto + lacuna de validação.
- **Evidência:**
  - `partes.recortar` (`partes.py:547-563`) só escreve na parte de destino; nada remove da parte de origem.
  - SKILL 5b.2 (`skills/horys-pixel/SKILL.md:102-104`): "Se a figura visível está toda numa parte de baixo, copie
    para as partes de cima: o que sobra embaixo vira anatomia oculta."
  - `_simular` (`partes.py:386-411`) monta `outras` com **todas** as outras partes (`394-397`); se a parte de baixo
    contém a figura inteira, `descoberto = movel & ~novo & ~outras` é sempre vazio → nunca há buraco.
  - `_cobertura` (`partes.py:414-428`) dá 100% pelo mesmo motivo; não existe limite de profundidade da anatomia
    oculta nem checagem de exclusividade.
  - Os testes codificam o padrão: `test_partes.py:241-250` e `test_partes_ferramentas.py:141-156` põem a figura
    inteira na `base` e copiam para `topo`; a `base` continua com tudo.
- **Impacto:** a checagem passa, a vista explodida mostra muito magenta (só um humano percebe) e, ao animar, a parte
  de baixo mostra a cópia velha da parte de cima: **braço/martelo/cabelo fantasma**, com contorno interno e tudo.
  É exatamente o defeito que o fatiamento deveria impedir.
- **Causa:** o invariante escolhido ("a composição não muda") é necessário, mas não suficiente; faltou o invariante
  de **posse**: cada pixel visível pertence a uma parte, e a parte de baixo só pode ter, sob a de cima, anatomia
  própria e limitada.
- **Recomendação:**
  1. Nova checagem `fantasma` (erro): para cada junção, `oculto = inferior ∩ superior`; reprovar se
     (a) a profundidade oculta passar de `max_oculto_px` da junção (padrão 4; ombro/quadril podem declarar 6–8), ou
     (b) os pixels ocultos repetirem a forma da superior (IoU de `oculto` com a superior ≥ 0,6), ou
     (c) os pixels ocultos contiverem cores de linha/contorno da superior na borda dela (linha fantasma).
  2. Nova checagem `posse` (erro) quando houver `mapa-partes` (P1-9): cada pixel visível do quadro base tem que vir
     da parte que o mapa indica.
  3. `_simular` deve considerar como "cobertura legítima" só a parte **inferior da junção** e as partes que estão
     **acima da móvel**; partes abaixo da inferior que não são da junção não podem tapar buraco da junção.
  4. Corrigir os testes que codificam a duplicação e acrescentar o caso "figura inteira na base" esperando
     `fantasma`.
- **Critério de aceite:** a cena "figura inteira na parte de baixo + cópia na de cima" reprova com `fantasma`; a
  cena "parte de baixo com 2 px de anatomia sob a de cima, na cor do interior" passa; o ferreiro real fatiado passa
  sem nenhum pixel de linha da superior escondido na inferior.
- **Comprovação:** reprodução 9.1 (hoje `rel.ok == True`, deveria ser `False`); teste novo
  `test_fantasma_figura_inteira_na_base_reprova`; manual: no Aseprite, ocultar a camada de cima e conferir que a de
  baixo não mostra a silhueta da de cima.

#### P0-2 · "Referência → recortar" não funciona a partir de partes vazias
- **Tipo:** Bug (fluxo documentado impossível).
- **Evidência:** `_so_composicao_igual` (`partes.py:524-536`) compara a composição **das partes**. Com todas as
  partes vazias, `antes` é transparente e qualquer pixel novo muda `depois` → `ok` vazio, tudo recusado. A docstring
  da ferramenta (`ferramentas/partes.py:166-170`), as instruções MCP (`mcp_ponte.py:30-31`), o retorno de
  `horys_asset_novo` (`estilo.py:274-277`) e o prompt do pedido (`daemon/pedidos.py:38-40`) mandam "desenhe a
  referência completa → fatie com horys_partes_recortar".
- **Impacto:** o agente recebe "0 px copiados, N px recusados", improvisa (pinta à mão em cada parte, converte na
  parte errada) e cai em P0-1. Fluxo não determinístico, impossível de revisar.
- **Causa:** um único invariante serve para dois propósitos diferentes: *fatiar* (o alvo é igualar a referência) e
  *editar* (o alvo é não mudar o que já existe).
- **Recomendação:** separar em dois modos explícitos:
  - `horys_partes_fatiar(quadro_ref, mapa='mapa-partes' | regioes=[{parte, regiao|mascara|selecao}])`: parte da
    referência, **distribui cada pixel para exatamente uma parte** (posse), e o invariante passa a ser
    `compor(partes) == referencia` no quadro base (igualdade exata, cor e alfa).
  - `horys_partes_recortar` continua como edição incremental (composição não muda), mas ganha `mover: true`
    (copia para a parte de cima e **apaga da de baixo** o que ficou coberto e não é anatomia declarada).
- **Critério de aceite:** a partir de partes vazias + referência + mapa, o asset fica com composição idêntica à
  referência e posse 100%; `recortar` sem nada visível embaixo devolve mensagem orientando `fatiar`.
- **Comprovação:** reprodução 9.2 (hoje tudo recusado); teste novo `test_fatiar_de_partes_vazias_iguala_referencia`.

#### P0-3 · O motor sem terminal não recebe a skill
- **Tipo:** Arquitetura (fluxo autônomo).
- **Evidência:** `daemon/pedidos.py:26-29` diz "As instruções operacionais do horys-pixel já foram fornecidas pelo
  servidor MCP. NÃO tente ler SKILL.md nem qualquer arquivo local: nesta sessão não há ferramenta de leitura de
  arquivos." Mas `mcp_ponte.INSTRUCOES` (`mcp_ponte.py:23-31`) só diz "siga a skill horys-pixel (SKILL.md do repo)".
  E o motor Claude **tem** `Read/Write/Edit/Glob/Grep` (`motores.py:18`); a skill exige gravar `pesquisa.md`,
  `praticas.md` e `ficha.md` (`SKILL.md:56, 64, 67`) e o revisor precisa desses caminhos (`estilo.py:689-700`).
  `VALIDACAO-CODEX.md:84-86` registrou o pedido Codex travado exatamente por isso.
- **Impacto:** no botão Gerar, o motor não vê briefing, práticas, plano de quadros, limites do portão, regras do
  revisor nem o passo 5b. Qualidade imprevisível; revisor sem `praticas.md` (L7 vira nota vazia).
- **Causa:** prompt escrito para contornar um sintoma (Codex sem leitura) virou regra para os dois motores.
- **Recomendação:** (1) entregar o conteúdo da skill no próprio prompt (ou por recurso/ferramenta MCP
  `horys_skill(secao)`), (2) remover a proibição de ler arquivos para o Claude e (3) para o Codex, garantir leitura
  da pasta do pedido (já é o `-C pasta`), (4) teste que confira que o prompt do pedido contém as seções
  "Briefing", "5b" e "Portão".
- **Critério de aceite:** um pedido Gerar (Claude e Codex) produz `praticas.md` e `ficha.md` na pasta do pedido e
  chama `horys_revisar` com esses caminhos.
- **Comprovação:** teste `test_prompt_pedido_entrega_skill`; manual: pedido real "aldeão idle 1 quadro" até o portão.

#### P0-4 · Preset de ferreiro imposto a todo humanoide, com partes obrigatórias e anatomia errada
- **Tipo:** Arquitetura + Bug de regra.
- **Evidência:**
  - `daemon/pedidos.py:35-37`: "Para personagem humanoide, horys_asset_novo DEVE receber
    preset_partes='humanoide-ferreiro'".
  - `partes.py:80-97`: 9 partes fixas (martelo, óculos, barba, avental incluídos); `checar` dá **erro**
    `parte-vazia` para qualquer parte sem pixel (`partes.py:312-314`).
  - Ordem: `braco-traseiro` fica **acima** de `corpo-base` e `avental-torso` (`partes.py:83-84`, junções 91-92): o
    braço de trás é desenhado na frente do torso.
  - Não há `cabeca` (cabelo, barba e óculos se apoiam em `corpo-base`), nem perna da frente.
- **Impacto:** um mago, uma criança ou um guarda sem óculos/barba/martelo **nunca passa** no portão modular; o
  agente é empurrado a inventar barba/óculos ou a burlar a ficha (P1-1). Mesmo no ferreiro: cabeça não inclina sem
  mover o corpo inteiro; o braço de trás tapa o avental.
- **Causa:** o preset nasceu da migração de um asset específico (`tools/fatiar_ferreiro.lua`).
- **Recomendação:**
  1. Preset base `humanoide` (de baixo para cima): `braco-traseiro`, `perna-traseira`, `corpo`, `perna-frente`,
     `cabeca`, `cabelo`, `braco-frente`, com junções ombro/quadril/pescoço; acessórios como **extras opcionais**
     (`avental`, `barba`, `oculos`, `ferramenta`), cada um com `opcional: true` (vazio = aviso ou ausente).
  2. `humanoide-ferreiro` vira variante do base (herda e adiciona extras).
  3. Escolha do preset pelo briefing, não por regra fixa no prompt.
  4. Ordem por direção: `vista: direita|esquerda|frente` troca qual braço/perna é "traseiro".
- **Critério de aceite:** personagem sem acessórios passa no portão modular; ferreiro mantém as 10 junções
  equivalentes; o braço de trás fica atrás do torso na pilha.
- **Comprovação:** testes `test_preset_base_sem_extras_passa`, `test_braco_traseiro_abaixo_do_corpo`; manual:
  ferreiro 192×192 em pose de martelada com o braço de trás visível atrás do avental.

### P1 — alto impacto

#### P1-1 · Estado de validação velho e portão de animação burlável
- **Tipo:** Bug/Risco.
- **Evidência:** `partes_checagem` é gravado só em `ferramentas/partes.py:132-134` e **nunca invalidado** (busca por
  `partes_checagem` no repo: só esse ponto e o teste). O portão (`ferramentas/pedidos.py:40-49`): só roda se
  `ctx.ponte.conectado`; exceção vira `f = {}` (portão pulado); usa a ficha do **sprite ativo**, não do sprite do
  pedido; só bloqueia o rótulo `animacao` (nada impede criar quadros e animar). `horys_ficha` aceita
  `modular=false`, `partes_oculto=[]` ou `juncoes` arbitrárias (`estilo.py:172-203`) sem registro de exceção.
- **Impacto:** checar com 1 quadro, depois editar as partes ou acrescentar 7 quadros, e a etapa `animacao` continua
  liberada; o agente pode "consertar" uma reprovação desligando o modular.
- **Causa:** o resultado da checagem não está amarrado ao conteúdo checado.
- **Recomendação:** gravar `partes_checagem = {ok, erros, avisos, n_quadros, hash}` onde `hash` = SHA-256 das
  camadas de partes (+ referência + ficha de contratos) de todos os quadros; o portão recalcula o hash e exige
  igualdade. Mudanças em `modular`, `juncoes`, `partes_oculto`, `preset_partes` exigem `motivo` e ficam em
  `excecoes` na ficha (visíveis ao revisor). Sem Aseprite conectado, recusar (não pular).
- **Critério de aceite:** qualquer pixel alterado numa parte após a checagem faz `animacao` ser recusada com
  "checagem desatualizada".
- **Comprovação:** teste `test_checagem_fica_velha_ao_mudar_pixel`, `test_ficha_modular_false_exige_motivo`,
  `test_portao_animacao_sem_aseprite_recusa`.

#### P1-2 · A ficha é indexada pelo nome do arquivo
- **Tipo:** Bug/Risco.
- **Evidência:** `contexto.py:46-57`: arquivo `fichas/<nome-sanitizado>.json`; a chave é `sprite.arquivo`
  (`estilo.py:49-56`). `horys_salvar` sem `copia` muda o nome do sprite (`desenho.py:127-146`).
- **Impacto:** depois de "salvar como", `_ficha` diz "sem ficha" e o asset **deixa de ser modular** para o portão
  e para o gate de animação; dois sprites novos com o mesmo nome (`asset`) compartilham ficha.
- **Recomendação:** guardar um `horys_id` (UUID) em `sprite.properties` do Aseprite (API 1.3) e indexar a ficha por
  ele; ao salvar, migrar; ao abrir, ler o id.
- **Critério de aceite:** salvar com outro nome mantém a ficha; dois sprites com o mesmo nome têm fichas distintas.
- **Comprovação:** teste com o Aseprite falso + teste Lua de `properties`; manual: salvar como e rodar o portão.

#### P1-3 · Linha interna: lado errado, heurística conflitante e cor errada
- **Tipo:** Bug + Conhecimento.
- **Evidência:**
  - `_frontier_linha` (`partes.py:257-272`) conta linha nos **dois** lados (`fr = (b & dil(a_vis)) | (a_vis & dil(b))`,
    `rgb = where(b, sup, inf)` em `265`). Linha pintada na parte de baixo conta como válida, mas **não acompanha** a
    parte móvel: ao mover o braço, a linha fica no torso (linha fantasma).
  - Sem `cores_linha`, "linha" é luminância < 70 (`partes.py:271`); com elas, só cores de contorno da paleta.
    `revisor_prompt.md:25` exige "linha interna só onde dois planos se fundiriam"; o validador dá **erro** em toda
    junção sem linha escura (`partes.py:437-439`), empurrando o agente a contornar tudo (peso de linha errado no
    Pixel Liso).
  - `_cores_linha` inclui `sem_contorno` (`ferramentas/partes.py:40`), que são cores de **efeito sem contorno**,
    não cores de linha.
- **Recomendação:** política por junção: `linha: obrigatoria | por_contraste | proibida` (padrão `por_contraste`).
  Em `por_contraste`, erro só se ΔL (OKLab) entre os lados < 0,08 em mais de 50% da fronteira e não houver linha;
  a linha (quando houver) tem que estar **na parte móvel** (para `movel == superior`, contar só `b & dil(a_vis)`).
  Tirar `sem_contorno` das cores de linha.
- **Critério de aceite:** cabelo claro sobre testa clara sem linha → erro; barba escura sobre pele sem linha →
  passa (contraste); linha desenhada no torso sob o braço → erro `linha-no-lado-errado`.
- **Comprovação:** três testes novos com essas cenas; reprodução 9.3.

#### P1-4 · `estender` propaga a cor da borda (linha/sombra) para debaixo da peça de cima
- **Tipo:** Bug de qualidade.
- **Evidência:** `_cor_do_vizinho` (`partes.py:504-515`) pega a cor do vizinho imediato; em `estender`
  (`partes.py:566-589`) o vizinho é a borda da inferior junto da superior — justamente onde ficam linha interna e
  sombra de oclusão.
- **Impacto:** ao mover a superior 1–2 px, aparece uma faixa escura dupla (linha + cópia da linha).
- **Recomendação:** cor da extensão = moda das cores da inferior a 2–4 px **para dentro**, excluindo cores de
  linha/contorno e a sombra mais escura da rampa; opcional `cor` explícita.
- **Critério de aceite:** inferior com borda escura de 1 px estendida 2 px → pixels novos na cor do preenchimento.
- **Comprovação:** teste `test_estender_nao_propaga_linha`.

#### P1-5 · Preservação da composição contra a referência não é verificada
- **Tipo:** Lacuna de validação.
- **Evidência:** `checar` só mede cobertura alfa da referência ≥ 90% (`partes.py:320-331`): sem precisão (partes
  podem ter pixels a mais), sem cor (pixels podem estar recoloridos) e tolerando 10% perdido. A referência é lida
  em todos os quadros (`ferramentas/partes.py:43-48`); no Aseprite real, `quadro criar copiar` copia as células
  (`handlers.lua:452-453`), inclusive a referência, então quadros animados são comparados com a pose parada (falso
  erro numa martelada grande, ou cobertura sem sentido).
- **Recomendação:** `quadro_ref` na ficha; nesse quadro, exigir `compor(partes) == referencia` exato (lista de
  diferenças em `medidas/partes.json`, exceções declaradas); nos outros quadros, não usar a referência.
- **Critério de aceite:** recolorir 1 px numa parte no quadro base reprova com `composicao-difere-da-referencia`;
  quadros 1..N não são comparados com a referência.
- **Comprovação:** testes `test_quadro_ref_igualdade_exata`, `test_referencia_ignorada_fora_do_quadro_ref`.

#### P1-6 · Partes desconexas permitidas (óculos, cabelo, bigode) e peças finas
- **Tipo:** Bug de regra.
- **Evidência:** `parte-desconexa` é sempre erro (`partes.py:315-319`). Óculos em 64–72 px costumam ser duas lentes
  com ponte de 1 px escondida ou omitida; cabelo dos dois lados do rosto e bigode separado da barba também são
  desconexos. Peça de 1 px de espessura (armação) nunca atinge profundidade 2 → aviso permanente
  `sobreposicao-curta` (`partes.py:350-352`).
- **Recomendação:** no preset/ficha, por parte: `componentes_max` (óculos 2, cabelo 3, barba 2) e
  `espessura_fina: true` (aviso de profundidade suprimido; exige `max_oculto_px` menor). Desconexão acima do máximo
  continua erro, com os pontos de cada pedaço.
- **Critério de aceite:** óculos com duas lentes separadas passa; três pedaços reprova.
- **Comprovação:** `test_oculos_duas_lentes_permitido`, `test_oculos_tres_pedacos_reprova`.

#### P1-7 · Z-order fixo por camada e ausência de pivô/cabeça
- **Tipo:** Arquitetura + Conhecimento.
- **Evidência:** a ordem de camadas vale para todos os quadros (`grade.py:226`: "a ordem global decide o
  empilhamento em todos os quadros"); `Juncao` não tem pivô nem amplitude (`partes.py:30-40`).
- **Impacto:** na martelada, o martelo passa atrás da cabeça no armar e na frente no golpe: impossível sem duplicar
  camadas; sem pivô, não dá para simular rotação nem planejar arcos.
- **Recomendação:** permitir partes "espelho" (`martelo-tras` e `martelo-frente`, só uma não vazia por quadro, com
  checagem) e `pivo: [x, y]` + `giro_max_graus` por junção (usado por P2-1 e pelo plano de quadros).
- **Critério de aceite:** martelada com troca de profundidade passa no portão; a ficha registra o pivô do ombro.
- **Comprovação:** teste de partes-espelho; manual no Aseprite com 6 quadros de ataque.

#### P1-8 · Entrega e revisão sem portão obrigatório
- **Tipo:** Bug de processo.
- **Evidência:** `horys_exportar` copia para o destino mesmo com portão REPROVADO (só erros de partes bloqueiam;
  `estilo.py:546`: "entregue mesmo assim só se o usuário quis", mas nada verifica que o usuário quis).
  `horys_revisar` não confere `_checagem.txt` (`estilo.py:689-727`), apesar de a skill proibir revisor com portão
  reprovado (`SKILL.md:134`). Não há exigência de revisor PASS nem de aprovação do usuário para exportar.
- **Recomendação:** `horys_exportar` exige `codigo == 0` **e** (revisor PASS ou `aprovado_usuario` registrado) para o
  mesmo hash de conteúdo; senão, só com `forcar: true` + `motivo`, gravado em `entrega.json`. `horys_revisar`
  recusa vNN com `PORTÃO DE MEDIDAS: REPROVADO` ou `PARTES REPROVADAS` (exceto `etapa: conceito`).
- **Critério de aceite:** exportar com M01 falhando não copia nada sem `forcar`.
- **Comprovação:** `test_exportar_recusa_portao_reprovado`, `test_revisar_recusa_portao_reprovado`.

#### P1-9 · Ferramentas de fatiamento grosseiras (só retângulo, sem mover, sem mapa)
- **Tipo:** Arquitetura de ferramenta.
- **Evidência:** `_regiao` aceita só `{x,y,w,h}`/lista (`ferramentas/partes.py:74-80`); não aceita a seleção do
  Aseprite (`desenho.py:50-60` já sabe ler `selecao`); `recortar` aceita `quadros` mas usa só o primeiro
  (`ferramentas/partes.py:178`). Não existe ferramenta para mover pixels de uma parte para outra nem para apagar
  da parte de baixo o que é da de cima.
- **Impacto:** cabelo, barba e mãos não são retângulos; recortes retangulares geram posse errada e desconexões.
- **Recomendação:** camada oculta `mapa-partes` (cada parte numa cor chapada, desenhada por cima da referência;
  revisável na vista explodida) + `horys_partes_fatiar` (P0-2) + `horys_partes_mover(de, para, mascara|selecao|cor)`
  com o invariante de composição. `regiao: 'selecao'` em `recortar`.
- **Critério de aceite:** fatiar o ferreiro por mapa gera posse 100% e composição idêntica; mover um tufo de cabelo
  do corpo para `cabelo` não muda a composição.
- **Comprovação:** testes com mapa sintético; manual com seleção laço no Aseprite.

#### P1-10 · Skill contraditória e padrões de camada perigosos
- **Tipo:** Conhecimento/Doc + Bug de padrão.
- **Evidência:** `SKILL.md:87-88` manda "converta na parte de cima e depois separe as partes"; `SKILL.md:100-101`
  manda a conversão "cair direto" na `referencia`. `horys_converter`, `horys_limpar` e `horys_afinar` usam como
  padrão a **última parte** (`estilo.py:368, 396`): no preset, `oculos`. `SKILL.md:125-126` diz "Deslizar parte
  inteira reprova (A02)", mas o objetivo do modular é justamente mover partes.
- **Recomendação:** em asset modular, `converter/limpar/afinar` sem `camada` = `referencia` (ou erro pedindo
  camada); reescrever 5/5b como um fluxo único (seção 7); doutrina explícita: partes movem para **blocar a pose e
  segurar volumes**, e cada quadro-chave ainda tem redesenho de forma (A02 continua valendo para o resultado).
- **Critério de aceite:** nenhuma frase da skill manda converter numa parte; teste que lê a SKILL e falha se achar
  "converta na parte de cima".
- **Comprovação:** teste textual da skill + `test_converter_modular_padrao_referencia`.

#### P1-11 · Testes do fatiamento não executados e sem e2e real
- **Tipo:** Risco de processo.
- **Evidência:** seção 0. Além disso, o Aseprite falso diverge do real: `quadro criar` não copia células
  (`aseprite_falso.py:157-158`), não modela células ligadas nem `drawSprite`; as cenas são 24×24/64×64 sintéticas.
- **Recomendação:** rodar já a suíte inteira; adicionar um teste Lua/batch no Aseprite real com o fluxo modular
  (criar preset → fatiar → estender → checar → portão → exportar → reabrir); fixture do ferreiro 192×192 real
  (a partir do `.aseprite` legado) como teste de regressão; corrigir o falso para copiar células em `copiar: true`.
- **Critério de aceite:** CI local com 100% verde incluindo `tests/lua` e o e2e modular; cache do pytest com os ids
  `test_partes*`.
- **Comprovação:** `python -m pytest -q` e o comando do teste Lua do `test_extensao_lua.py`.

#### P1-12 · Troca de sprite no meio de operações compostas
- **Tipo:** Risco (herdado do VALIDACAO P1-2, agora mais exposto).
- **Evidência:** `partes_checar` faz até 10 leituras por quadro; `estender` lê 9 camadas, escreve, lê composto,
  talvez reverte; tudo sobre o sprite ativo do Aseprite, sem identidade de sprite nas requisições.
- **Impacto:** o usuário troca de aba no meio e a escrita/reversão cai no sprite errado.
- **Recomendação:** cada requisição leva `sprite_id` (o `horys_id` de P1-2); o Lua recusa se o ativo for outro;
  lock por sprite no daemon durante ferramentas compostas.
- **Critério de aceite:** com troca de aba simulada no meio de `estender`, nada é escrito e a ferramenta falha
  com mensagem clara.
- **Comprovação:** teste no Aseprite falso alternando `selecionar_sprite` entre chamadas.

#### P1-13 · Aprovação automática vira gosto "aprovado"
- **Tipo:** Bug (laço de aprendizado).
- **Evidência:** `conversa.py:101` resolve com `aprovado: True, pendente_usuario: True`; `gosto.registrar_aprovacao`
  (`gosto.py:41-45`) ignora `pendente_usuario`.
- **Impacto:** silêncio do usuário vira "exemplo aprovado"; `horys_gosto_consultar` passa a recomendar defeitos.
- **Recomendação:** registrar como `pendente` (nem aprovado nem recusado) e excluir de exemplos/treino.
- **Critério de aceite:** aprovação automática não aparece em "Exemplos aprovados".
- **Comprovação:** teste de `gosto` com resposta automática.

### P2 — importantes para qualidade alta

| ID | Tipo | Evidência | Impacto | Recomendação | Aceite / comprovação |
|---|---|---|---|---|---|
| P2-1 | Arquitetura | `_simular` só translada ±1/±2 px (`partes.py:386-411`) | braço gira no ombro; buraco de rotação não é pego | rotação NN de ±10°/±20° em torno do `pivo` da junção (P1-7) + translação | teste com braço retangular girando 15° abre buraco sem anatomia; fecha com anatomia circular no ombro |
| P2-2 | Arquitetura | contorno é anel global (`grade.py:330-339`); partes exportadas sem contorno próprio (`grade.py:355-386`) | impossível usar as partes como recorte/rig no motor do jogo | decidir alvo: (a) só Aseprite quadro a quadro (documentar) ou (b) exportar `contorno` por parte para cut-out | decisão registrada em `docs/decisoes.md`; se (b), teste de exportação por parte |
| P2-3 | Bug visual | `_miniatura` e `partes_checar` reduzem com `NEAREST` em escala não inteira (`estilo.py:139-144`; `ferramentas/partes.py:144-147`) | o agente/revisor vê jaggies e pixels de tamanhos diferentes que não existem | escolher a maior escala inteira que cabe (ou dividir a vista em páginas) | teste: toda imagem devolvida tem pixels-lógicos de tamanho constante |
| P2-4 | Bug | `horys_marcar` deixa `revisao` visível (`estilo.py:607`); leituras compostas usam `drawSprite` com camadas visíveis (`handlers.lua:633-636`): `horys_aprovar` (`conversa.py:79`), `horys_ver`, `horys_regua`, `horys_medir_arquivo` sem caminhos, `horys_gosto_registrar capturar` | marcas magenta entram na aprovação, no gosto e na medição (falso "fora da paleta") | `ler` composto ignora `revisao`/`referencia`/`mapa-partes` sempre (parâmetro `excluir` no Lua) | teste: marcar e depois medir o composto sem cor magenta |
| P2-5 | Lacuna de métrica | `medir.py` não mede proporção, separação de valores, pillow/banding, tangência, fidelidade à referência, consistência por parte | defeitos de forma/volume só dependem do LLM | ver seção 8 (métricas novas M18–M24 e P01–P04) com calibração no Tiny | cada métrica com bons/estragados em `calibrar.py` (todos os bons passam, todos os estragados reprovam) |
| P2-6 | Processo | revisor é uma amostra LLM, sem conjunto de calibração (só o portão é calibrado) | PASSA/NAO_PASSA instável entre rodadas (ex.: 54→57→55% no PENDENCIAS) | conjunto ouro (aprovados/recusados do Artur), medir concordância; 2 amostras e usar a pior | concordância ≥ 85% com o olho do Artur no conjunto ouro |
| P2-7 | Bug de UX | `H.camada ordem` põe as listadas no fundo (`handlers.lua:431-433`); `_partes` sugere `acao=ordem` só com as partes (`estilo.py:73-74`) | `sombra`/`contorno` sobem acima das partes | mensagem com a lista completa (`sombra, contorno, partes…, referencia, revisao`) ou `ordem` preservar camadas não listadas no lugar | teste no falso e no Lua |
| P2-8 | Processo | `horys_asset_novo tipo=personagem` sem preset é aceito; a obrigação está só no prompt | o motor pode pular o modular | em modo pedido, personagem/inimigo/boss sem preset exige `motivo` | teste de recusa |
| P2-9 | Risco | revert de `estender` é uma 2ª escrita (`ferramentas/partes.py:92`); backup prometido em `docs/arquitetura.md:117` não existe | histórico do Aseprite poluído; sem ponto de volta por etapa | `app.transaction` única por ferramenta composta no Lua + cópia `.aseprite` em `backups/` antes de `fatiar/estender/mover` | teste: 1 `horys_desfazer` desfaz a ferramenta inteira |
| P2-10 | Validação visual | vista explodida estática | o olho não vê o que abre ao mover | `<asset>_partes_movimento.gif`: cada parte móvel deslocada/girada no limite, buracos em magenta | arquivo gerado pelo portão e citado no revisor (L7) |
| P2-11 | Teste | falso não copia células, não tem células ligadas, `ler` ignora opacidade de célula | testes passam onde o real falha | alinhar o falso ao real nesses três pontos | testes existentes continuam verdes |
| P2-12 | Conhecimento | a skill exige notas da KB do Horys (`SKILL.md:60-64`) mesmo para estilos sem KB (`exemplo`) | o motor trava ou inventa | fallback explícito: `estilo.md` + práticas universais embutidas | teste textual + pedido com estilo `exemplo` |

### P3 — limpeza e conforto

| ID | Evidência | Recomendação |
|---|---|---|
| P3-1 | `tools/fatiar_ferreiro.lua:18` usa `spr.layers[1]` (que num asset do horys é `sombra`) quando não há `desenho`; coordenadas fixas (`:29-37`); só quadro 1; não grava ficha | recusar sem `desenho`; documentar como só-leitura de migração; ou remover depois de P1-9 |
| P3-2 | `README.md:6-8, 57` e `docs/fases.md:5` dizem "126 testes" e "v0.1 de ponta a ponta"; não citam o modular | atualizar números e estado real (e2e Codex não completou) |
| P3-3 | `partes_checar` não valida índices de `quadros` (`ferramentas/partes.py:130`) e `[0,0]` com 2 quadros conta como "todos" | usar `_quadros_alvo` e `set(indices) == set(range(n))` |
| P3-4 | o teste de docs só confere cabeçalhos (`test_partes.py:276-283`) | gerar em memória e comparar byte a byte com `docs/ferramentas.md` |
| P3-5 | a extensão não tem menu para checar partes nem mostra a vista explodida | `Horys › Checar partes` chamando `horys_partes_checar` e mostrando a imagem |
| P3-6 | `_pontos` devolve os 24 primeiros em ordem raster (`partes.py:193-195`) | devolver bbox + centróide + até 24 pontos espalhados, prontos para `horys_marcar` |
| P3-7 | `_cores_linha` engole qualquer exceção (`ferramentas/partes.py:34-39`) | capturar só `ErroFerramenta`/`KeyError` e avisar no relatório |
| P3-8 | `RESERVADAS_PARTES` (`partes.py:21`) e `grade_io.RESERVADAS` (`grade_io.py:14`) são duas listas | uma fonte só (e incluir `mapa-partes`) |

---

## 5. Verificações pedidas explicitamente

| Item | Situação | Veredito | Achados |
|---|---|---|---|
| Preservação de composição (edição) | predicado + leitura real + reversão | **Sólido** | — |
| Preservação de composição (fatiar a referência) | só cobertura alfa ≥ 90%, sem cor e sem precisão | **Falha** | P0-2, P1-5 |
| Partes ocultas (anatomia) | cobertura de faixa 1/2 px; sem limite de profundidade; cor da borda | **Parcial / risco de fantasma** | P0-1, P1-4 |
| Junções | contratos bons; só translação; sem pivô; preset com ordem errada | **Parcial** | P0-4, P1-7, P2-1 |
| Overlays (`revisao`, magenta, overlays do portão) | vista explodida correta; `revisao` visível contamina leituras | **Bug** | P2-4, P2-3 |
| Linhas internas | lado errado aceito; heurística escura conflita com o revisor | **Falha** | P1-3 |
| Estado velho de validação | `partes_checagem` sem hash nem invalidação; gate pulável | **Falha** | P1-1, P1-2 |
| Partes desconexas permitidas (óculos) | sempre erro | **Falha** | P1-6, P0-4 |
| Exportação | `.aseprite` conferido; bloqueia erro de partes; não bloqueia portão reprovado | **Parcial** | P1-8, P2-2 |
| Docs geradas | `ferramentas.md` coerente; agente coerente; README/fases velhos | **Ok com ressalvas** | P3-2, P3-4 |
| Testes não executados pelo Sonnet | 29 testes de partes nunca rodaram (cache/pycache) | **Pendente** | P1-11 |

---

## 6. Plano em fases

### Fase 0 — Estancar (½–1 dia)
1. Rodar `python -m pytest -q` inteiro e `tests/test_extensao_lua.py` no Aseprite real; registrar o resultado
   (P1-11).
2. P0-3: entregar a skill ao motor sem terminal; remover a proibição de leitura para o Claude.
3. P1-1/P1-2: `horys_id` em `sprite.properties`; hash de conteúdo em `partes_checagem`; gate recusa sem Aseprite;
   exceções de ficha com motivo.
4. P1-8: exportar e revisar exigem portão aprovado (ou `forcar` + motivo).
5. P1-13: aprovação automática não vira gosto.
**Saída:** suíte verde, pedido Gerar com `praticas.md`, nenhum caminho para animar/exportar com estado velho.

### Fase 1 — Fatiamento correto (2–4 dias)
1. Camada `mapa-partes` + `horys_partes_fatiar` (posse 100%, `compor == referencia` no `quadro_ref`) (P0-2, P1-5,
   P1-9).
2. `horys_partes_mover` e `recortar(mover: true, regiao: 'selecao')` (P1-9).
3. Checagens novas: `fantasma`, `posse`, `profundidade-oculta-max`, `linha-no-lado-errado`, política de linha por
   junção, `componentes_max`, `espessura_fina` (P0-1, P1-3, P1-6).
4. `estender` com cor do interior (P1-4).
5. Corrigir os testes que codificam duplicação; fixture real do ferreiro 192×192.
**Saída:** ferreiro real fatiado por mapa, sem fantasma, passando no portão; a cena "figura inteira na base" reprova.

### Fase 2 — Presets e anatomia (2–3 dias)
1. Preset `humanoide` base com cabeça, pernas e braços na ordem certa por vista; extras opcionais; ferreiro como
   variante (P0-4).
2. `pivo` e `giro_max_graus` por junção; partes-espelho para troca de profundidade (P1-7).
3. Converter/limpar/afinar com padrão `referencia` em asset modular; skill 5/5b reescrita (P1-10).
**Saída:** personagem sem acessórios passa; martelada com troca de profundidade possível.

### Fase 3 — Movimento e animação (2–3 dias)
1. Simulação com rotação em torno do pivô (P2-1) e GIF de estresse (P2-10).
2. Métricas por parte entre quadros (P01–P04, seção 8).
3. Doutrina "partes blocam, quadro-chave redesenha" no plano de quadros e no revisor L6/L7.
**Saída:** idle e ataque do ferreiro com 4–6 quadros passando portão, partes e revisor.

### Fase 4 — Qualidade visual geral (3–5 dias)
1. Escala inteira em todas as imagens devolvidas (P2-3); camadas auxiliares fora do composto (P2-4).
2. Métricas novas M18–M24 calibradas no Tiny com mutações (P2-5).
3. Conjunto ouro e calibração do revisor; 2 amostras (P2-6).
**Saída:** revisor e portão concordam ≥ 85% com o olho do Artur no conjunto ouro.

### Fase 5 — Uso real no Aseprite (contínuo)
1. E2E Lua do fluxo modular; falso alinhado ao real (P1-11, P2-11).
2. Lock/identidade de sprite (P1-12); transação única + backup (P2-9).
3. Menu `Checar partes` e vista explodida no painel (P3-5).

---

## 7. Fluxo modular recomendado (para a skill, depois das Fases 1–2)

1. Briefing decide **vista** (direita/esquerda/frente), **preset** (`humanoide` + extras) e **quadro_ref** (0).
2. Referência convertida em `referencia` (nunca numa parte) → limpar → afinar → mão por cima (silhueta, vãos,
   linhas internas, cachos, rosto) → `horys_paleta_estilo verificar` → `horys_portao` da referência como quadro
   único (já tem que passar: forma antes de fatiar).
3. Pintar `mapa-partes` (uma cor chapada por parte, por cima da referência); revisar a vista do mapa.
4. `horys_partes_fatiar` (posse 100%, composição == referência).
5. Anatomia oculta: `horys_partes_estender` (1–2 px, cor do interior) e, onde a junção declara mais
   (ombro/quadril/pescoço), desenho à mão **sem linha** sob a peça de cima, respeitando `max_oculto_px`.
6. `horys_partes_checar` + GIF de estresse; corrigir erros; avisos para a `praticas.md`.
7. Só então criar quadros: copiar o quadro anterior, mover/girar partes para blocar a pose, **redesenhar** as
   formas (dobras, squash, ponta atrasada), checar partes a cada quadro-chave.
8. `horys_portao` → `horys_revisar` → aprovação do usuário → `horys_exportar`.

---

## 8. Lacunas de conhecimento do agente e métricas a criar

### 8.1 O que o agente precisa aprender (e onde escrever)
Escrever em `KB/tecnicas/partes.md` (ou na skill, se a KB não for portátil) com exemplos em pixels:
1. **Anatomia oculta**: o que pintar sob o braço (o torso continua, com a mesma rampa e **sem** linha), formato de
   "bola" no ombro/quadril para sobreviver a giros de 10–20°, quanto esconder (2–4 px; 6–8 no ombro em ataque).
2. **Dono da linha interna**: a linha que separa duas partes pertence à parte **da frente** (a que se move sobre a
   outra); linha só onde os dois planos se fundiriam no valor (ΔL baixo).
3. **Ordem por vista**: braço/perna do lado de lá ficam abaixo do corpo; troca de profundidade usa parte-espelho.
4. **Peças finas e desconexas**: óculos em 64–72 px (armação de 1 px, brilho de 1 px, ponte opcional), bigode
   separado da barba, mechas de cabelo dos dois lados.
5. **Partes vs redesenho**: mover partes é para blocar pose e manter volume; o quadro-chave final é redesenhado
   (A02 continua cobrando).
6. **Proporção do humanoide no Pixel Liso/Tiny** (64–72 px): razão cabeça/altura, largura de ombro, comprimento de
   braço até o quadril, pé no pivô — hoje só "massa de cima ~60%" em texto (não verificado na KB).
7. **Valor e cluster**: 2–3 tons por material, crescente de luz 10–20% e de sombra 30–40% (já no revisor), sem
   pillow shading; teste do cinza antes de cor.

### 8.2 Métricas novas sugeridas (calibrar no Tiny antes de reprovar)
| ID | Mede | Como | Severidade inicial |
|---|---|---|---|
| M18 | proporção | altura da cabeça (do mapa de partes ou do topo até o queixo) / altura total; largura de ombro / altura | aviso → grave depois de calibrado |
| M19 | leitura a 0,5× | IoU da silhueta reduzida 2× (moda) e reampliada vs original; espaço negativo (furos internos ≥ 2 px) | grave |
| M20 | separação de valores | pares de cores vizinhas com ΔL (OKLab) < 0,04 em > 5% da fronteira | grave |
| M21 | pillow shading | correlação entre distância à borda e L dentro de cada material (> 0,7 = pillow) | grave |
| M22 | banding | faixas paralelas de 1 px de cores consecutivas da rampa seguindo a borda | aviso |
| M23 | tangência | pontos onde duas formas/partes se tocam em 1 px sem sobrepor | aviso |
| M24 | fidelidade à referência | IoU da silhueta e ΔE médio vs referência reduzida (asset "fiel") | grave no modo fiel |
| P01 | volume por parte | variação de área de cada parte entre quadros (cabeça ±5%) | grave |
| P02 | cor por parte | cores novas numa parte que não existiam no quadro base | aviso |
| P03 | deriva de junção | o pivô estimado da junção não pode saltar > 2 px sem a parte-mãe mover | grave |
| P04 | posse | pixels visíveis vindos de parte diferente do `mapa-partes` no quadro base | erro |

---

## 9. Reproduções (rode com `PYTHONPATH=src python -I -c "..."` ou num teste)

### 9.1 P0-1 — fantasma aprovado (hoje passa; deveria reprovar)
```python
import numpy as np
from horys_pixel import partes as P
ref = np.zeros((24, 24, 4), np.uint8)
ref[4:14, 4:14] = (200, 60, 60, 255)          # torso
ref[6:12, 12:20] = (60, 60, 200, 255)         # braço por cima
base = ref.copy()                              # "figura inteira na parte de baixo" (SKILL 5b.2)
topo = np.zeros_like(ref); topo[6:12, 12:20] = (60, 60, 200, 255)
rel = P.checar(None, [{"base": base, "topo": topo}], partes=["base", "topo"],
               juncoes=[P.Juncao("j", "base", "topo", "topo")], ignorar_linha=True)
print(rel.ok)          # esperado hoje: True  → a base guarda um braço azul inteiro por baixo do braço
```

### 9.2 P0-2 — recorte a partir de partes vazias (hoje recusa tudo)
```python
r = P.recortar({"base": np.zeros_like(ref), "topo": np.zeros_like(ref)}, ["base", "topo"], "base", ref,
               (0, 0, 24, 24))
print(r.alterados, r.recusados, int((ref[..., 3] > 0).sum()))   # esperado hoje: 0 136 136
```

### 9.3 P1-3 — linha no lado errado aceita
```python
base = np.zeros((24, 24, 4), np.uint8); base[2:10, 2:10] = (200, 170, 120, 255)
topo = np.zeros_like(base); topo[4:12, 6:14] = (120, 170, 200, 255)
base[3, 5:11] = base[3:11, 5] = (20, 20, 40, 255)     # linha pintada NA BASE, em volta do topo
rel = P.checar(None, [{"base": base, "topo": topo}], partes=["base", "topo"],
               juncoes=[P.Juncao("j", "base", "topo", "topo")])
print([p.codigo for p in rel.problemas if "linha" in p.codigo])   # esperado hoje: nenhum erro de linha
```

### 9.4 P1-1 — estado velho (manual, Aseprite falso ou real)
1. `horys_asset_novo preset_partes=…`, desenhar algo válido, `horys_partes_checar` → `ok: true`.
2. Apagar metade de uma parte com `horys_pixel_map`.
3. `horys_pedido_atualizar(id, etapa='animacao')` → **hoje aceita**; deveria recusar.

---

## 10. Checklist de qualidade ANTES de gerar (pixel algum antes disto)

- [ ] Estilo confirmado (`horys_estilos`), régua disponível ou fallback declarado; `horys_gosto_consultar` lido
      (sem aprovações automáticas contaminando — P1-13).
- [ ] Briefing fechado com "sim": tipo, vista (direita/esquerda/frente), altura alvo com contorno (humanoide 64–72),
      estados e como cada um se move, contorno (auto/suave/nenhum), exceções do usuário anotadas.
- [ ] Referência escolhida e com fundo liso de cor fora do personagem; para asset fiel, a referência em resolução
      cheia está na pasta.
- [ ] `praticas.md` com 10–25 regras verificáveis + plano de quadros (pose-chave, ms, o que atrasa, meta A01/A02).
- [ ] `ficha.md` com rampas, limite de cores, objeto-assinatura, proporção alvo (cabeça/altura), e — se modular —
      preset, extras, `quadro_ref`, pivôs e partes com `componentes_max`/`espessura_fina`.
- [ ] `horys_asset_novo` com preset correto para a anatomia (não o ferreiro por padrão — P0-4); ordem de camadas
      conferida em `horys_status`.
- [ ] O motor tem a skill completa no contexto (P0-3) e permissão de gravar na pasta do asset.
- [ ] Nada de `horys_converter/limpar/afinar` sem `camada` explícita em asset modular (P1-10).
- [ ] Antes de fatiar: a referência sozinha passa no portão (forma, paleta, contorno, cluster, M17) e em
      `horys_ver critica` (silhueta lê em 1× e 0,5×, teste do cinza ok).

## 11. Checklist ANTES de animar (asset modular)

- [ ] `mapa-partes` existe e cobre 100% da referência; vista do mapa revisada.
- [ ] Fatiamento com posse 100% e `compor(partes) == referencia` no `quadro_ref` (P0-2, P1-5).
- [ ] Nenhuma parte com fantasma: profundidade oculta ≤ `max_oculto_px`, sem cópia da forma da superior, sem linha
      da superior escondida na inferior (P0-1).
- [ ] Toda junção: inferior entra ≥ 2 px (ou declara `espessura_fina`), cor do interior (não da borda) (P1-4).
- [ ] Linha interna na parte **da frente**, só onde o contraste não separa os planos (P1-3).
- [ ] Desconexas só onde declarado (óculos 2, cabelo ≤ 3, barba/bigode 2) (P1-6).
- [ ] Simulação: translação ±1/±2 px **e** giro ±10°/±20° no pivô sem buraco; GIF de estresse olhado (P2-1, P2-10).
- [ ] Ordem de camadas certa para a vista; troca de profundidade planejada com parte-espelho (P1-7).
- [ ] `horys_partes_checar` em **todos** os quadros, com hash atual gravado (P1-1); ficha estável após salvar (P1-2).
- [ ] Contorno/sombra regenerados (`horys_contorno`) e portão do quadro base aprovado; `revisao` oculta antes de
      qualquer leitura composta (P2-4).
- [ ] Usuário aprovou silhueta e cor do quadro base (`horys_aprovar sprite: true`), com resposta real (não
      automática).

---

## 12. Matriz de testes

Status: **E** = existe e executado (cache de 11-06) · **N** = existe, **nunca executado** · **F** = falta.

| # | Cenário | Nível | Arquivo / sugestão | Status | Achado |
|---|---|---|---|---|---|
| 1 | preset ferreiro válido, 10 junções, oculto = inferiores | unidade | `test_partes.py::test_preset_humanoide_ferreiro` | N | — |
| 2 | ficha modular completa pelo preset | unidade | `test_campos_ficha_modular` | N | — |
| 3 | contratos inválidos (reservada, ordem, móvel) | unidade | `test_contratos_invalidos` | N | — |
| 4 | aprovado, profundidade ≥ 2, sem buraco | unidade | `test_checar_aprovado` | N | — |
| 5 | sem sobreposição + buraco 1 px | unidade | `test_sem_sobreposicao_e_buraco_em_1px_sao_erros` | N | — |
| 6 | sobreposição de 1 px só avisa | unidade | `test_sobreposicao_de_1px_so_avisa` | N | — |
| 7 | não se tocam / vazia / desconexa / camada faltando | unidade | 2 testes | N | — |
| 8 | cobertura da anatomia oculta < 90% | unidade | `test_cobertura_da_anatomia_oculta_abaixo_de_90` | N | — |
| 9 | cobertura da referência | unidade | `test_cobertura_da_referencia` | N | P1-5 (só recall) |
| 10 | linha interna presente/ausente | unidade | `test_linha_interna` | N | P1-3 (lado não testado) |
| 11 | quadro ruim apontado | unidade | `test_checar_por_quadro_aponta_o_quadro_ruim` | N | — |
| 12 | vista explodida com magenta | unidade | `test_vista_explodida_pinta_ocultos_de_magenta` | N | — |
| 13 | estender 1/2 px preserva composição | unidade | `test_estender_so_pixels_cobertos` | N | P1-4 (cor da borda não testada) |
| 14 | recortar só onde a composição não muda | unidade | `test_recortar_so_onde_a_composicao_nao_muda` | N | **codifica P0-1** |
| 15 | revisor L7 e agente sincronizado; docs citam ferramentas | doc | 2 testes | N | P3-4 |
| 16 | asset_novo modular: camadas, ficha, recusas | integração falso | `test_partes_ferramentas.py` | N | — |
| 17 | checar sem desenho reprova e bloqueia animação | integração falso | idem | N | P1-1 (não testa velho) |
| 18 | camada faltando é erro em checar/contorno/portão | integração falso | idem | N | — |
| 19 | estender preserva e reverte se mudar | integração falso | idem | N | — |
| 20 | recortar via ferramenta | integração falso | idem | N | **codifica P0-1** |
| 21 | portão reprova e exportar recusa por partes | integração falso | idem | N | P1-8 (portão M não bloqueia) |
| 22 | figura inteira na base reprova (`fantasma`) | unidade | `test_fantasma_figura_inteira_na_base_reprova` | F | P0-1 |
| 23 | fatiar de partes vazias iguala a referência | unidade + falso | `test_fatiar_de_partes_vazias_iguala_referencia` | F | P0-2 |
| 24 | prompt do pedido contém a skill | unidade | `test_prompt_pedido_entrega_skill` | F | P0-3 |
| 25 | preset base sem extras passa; braço de trás atrás | unidade | `test_preset_base_sem_extras_passa` | F | P0-4 |
| 26 | checagem velha após mudar pixel / adicionar quadro | falso | `test_checagem_fica_velha_ao_mudar_pixel` | F | P1-1 |
| 27 | gate sem Aseprite recusa; `modular=false` exige motivo | falso | 2 testes | F | P1-1 |
| 28 | ficha sobrevive a "salvar como"; nomes iguais não colidem | falso + Lua | `test_ficha_por_horys_id` | F | P1-2 |
| 29 | linha no lado errado; contraste dispensa linha | unidade | 3 testes | F | P1-3 |
| 30 | estender usa cor do interior | unidade | `test_estender_nao_propaga_linha` | F | P1-4 |
| 31 | igualdade exata no `quadro_ref`; referência ignorada fora dele | unidade | 2 testes | F | P1-5 |
| 32 | óculos 2 lentes passa; 3 pedaços reprova | unidade | 2 testes | F | P1-6 |
| 33 | parte-espelho (martelo atrás/frente) | unidade | `test_parte_espelho_troca_profundidade` | F | P1-7 |
| 34 | exportar/revisar recusam portão reprovado | falso | 2 testes | F | P1-8 |
| 35 | mover por seleção/máscara sem mudar composição | falso | `test_partes_mover_selecao` | F | P1-9 |
| 36 | converter em asset modular cai na `referencia` | falso | `test_converter_modular_padrao_referencia` | F | P1-10 |
| 37 | e2e modular no Aseprite real (criar→fatiar→checar→portão→exportar→reabrir) | Lua batch | `tests/lua/test_modular.lua` | F | P1-11 |
| 38 | troca de sprite no meio de `estender` | falso | `test_troca_de_sprite_aborta` | F | P1-12 |
| 39 | aprovação automática não vira gosto aprovado | unidade | `test_gosto_ignora_pendente_usuario` | F | P1-13 |
| 40 | giro no pivô abre buraco sem anatomia redonda | unidade | `test_simular_rotacao` | F | P2-1 |
| 41 | imagens devolvidas em escala inteira | unidade | `test_miniatura_escala_inteira` | F | P2-3 |
| 42 | `revisao` visível não entra em leitura composta | falso + Lua | `test_composto_ignora_revisao` | F | P2-4 |
| 43 | métricas M18–M24/P01–P04 com bons/estragados | calibração | `calibrar.py` | F | P2-5 |
| 44 | concordância do revisor com conjunto ouro | manual/lote | `docs/revisor-calibracao.md` | F | P2-6 |
| 45 | 1 desfazer desfaz a ferramenta composta | Lua | `test_transacao_unica` | F | P2-9 |
| 46 | regressão: `test_treino_args_nao_contorna_executar_false` | unidade | `test_validacao_codex.py` | E (falhou em 11-06; código mudou depois, sem nova execução) | — |

### Testes manuais no Aseprite (roteiro curto)
1. **Fantasma:** fatiar o ferreiro, ocultar `braco-frente` → o torso não pode mostrar contorno/forma de braço.
2. **Estresse:** mover `braco-frente` 2 px e girar 15° no ombro → sem buraco, sem faixa escura.
3. **Óculos:** duas lentes separadas → checagem passa; apagar a ponte de um lado do cabelo → só desconexão
   declarada.
4. **Salvar como:** salvar o asset com outro nome → `horys_ficha` ainda mostra `modular` e o hash.
5. **Overlay:** `horys_marcar` → `horys_aprovar sprite:true` → a imagem do painel não mostra as cruzes magenta.
6. **Escala:** vista explodida de 10 partes → cada pixel lógico com o mesmo tamanho na imagem.

---

## 13. Ordem de ataque sugerida (uma linha por PR)

1. Rodar a suíte e registrar (P1-11). 2. Skill no motor (P0-3). 3. Hash + `horys_id` + gate (P1-1, P1-2).
4. Exportar/revisar com portão (P1-8). 5. Gosto pendente (P1-13). 6. `mapa-partes` + `fatiar` + `mover` (P0-2, P1-9).
7. `fantasma`/`posse`/profundidade + correção dos testes (P0-1). 8. Linha interna e `estender` (P1-3, P1-4).
9. `quadro_ref` (P1-5). 10. Desconexas/finas (P1-6). 11. Preset base + vista + extras (P0-4). 12. Pivô, giro,
partes-espelho (P1-7, P2-1). 13. Escala inteira e composto limpo (P2-3, P2-4). 14. Métricas novas e calibração do
revisor (P2-5, P2-6). 15. E2E Lua, lock de sprite, transação única (P1-12, P2-9, P2-11).
