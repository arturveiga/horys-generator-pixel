# Refactor: referência primeiro, gerador trocável e animação por sequência

Data: 2026-11-09. Origem: a sessão de 09/11, o `resumo.md`, o `docs/aprendizados-boss.md` e os padrões de entrada no
cofre (`pixel-liso/pipeline/padroes/`). Este arquivo substitui a linha "SpriteKiln como base" do `TODO.md`, que fica
como histórico (fases 0–3 de lá continuam valendo no código).

## Objetivo

1. **Chegar a "90%":** zero defeito **estrutural** no revisor. O **acabamento** vai marcado no Aseprite para o usuário
   finalizar, e os toques dele voltam como gosto do projeto.
2. **Sem dependência do Codex:** qualquer gerador de imagem (Codex, ChatGPT, Gemini, vídeo) entra pelo mesmo padrão.
3. **Animação bem desenhada** (L6: antecipação, arco, overlap, squash, redesenho real) **com a identidade da base**.

## Diagnóstico

| O que | Nota | Por que parou |
|---|---|---|
| Base parada (golem v19): conceito chapado → conversão → limpeza | 84% | funcionou; depende de referência boa |
| Animação: rig de partes recortadas | ~55% | rotacionar partes não redesenha; frestas, degraus, pé deslizando |
| Animação: Kiln puro | ~46% | sem detalhe de superfície (placas, juntas, espiral de 1 px) |
| Animação: Kiln + pele ComfyUI + decalque (r5) | 50% | forma em bloco do Kiln; pele cintila fora da grade única |
| Desenho do agente do zero | — | sai geométrico (golem de 96 px com cara de robô) |

Toda tentativa de animar escolheu um lado só: **consistência sem desenho** (Kiln, rig) ou **desenho sem consistência**
(pose gerada por pose). E o acabamento atual (`horys_converter`, `limpar`, `afinar`) trata **uma imagem**, não uma
sequência: mesmo com quadros bons, a conversão cria cintilação. Precisamos das duas coisas: **uma fonte que desenha o
movimento e um motor que trata a sequência como um todo.**

## Arquitetura alvo

```
PARADO
pedido → ficha do tipo (padrões) → prompt de tradução (+ amostra da paleta)
       → usuário gera onde quiser → PORTÃO DE ENTRADA → converter (moda) → limpar → portão → revisor
       → entrega com o acabamento marcado → toques do usuário → gosto

ANIMADO
base aprovada (+ guia de pose do Kiln/Noct 3D, opcional) → prompt de poses (grade) ou vídeo
       → PORTÃO DE ENTRADA → MOTOR DE SEQUÊNCIA → portão → revisor → entrega → gosto
```

| Camada | Estado | Onde |
|---|---|---|
| Padrões de entrada (fichas por tipo) | escrito no cofre; falta no código | Fase 1 |
| Prompt de tradução e portão de entrada | novo | Fase 1 |
| Conversão e limpeza de uma imagem | existe | `ferramentas/estilo.py`, `motor/conceito.py` |
| **Motor de sequência** | **novo (o gargalo)** | Fase 2 |
| Fontes de movimento (grade, vídeo, Kiln) | Kiln existe; o resto é experimento | Fase 3 |
| Revisor com estrutural × acabamento, marcas e gosto | parcial | Fase 4 |

## Quem faz o quê

| Executor | Faz |
|---|---|
| **Claude Code** (terminal) | código, testes, lotes, scripts, revisão visual das saídas |
| **Artur** | gera as imagens e vídeos nos geradores externos, aprova silhueta, cor e animação, autoriza commits e downloads |
| Revisor (`horys-pixel-liso-revisor`) | nota de cada rodada; não edita nada |

Cada tarefa tem "pronto quando". Marque `[x]` com a evidência (teste verde, imagem olhada ou commit). `[~]` = parcial.

---

## Fase 0: chão firme

- [ ] **0.1 · Fechar o estado atual.** O working tree tem mudanças não commitadas (`kiln.py`, `ferramentas/kiln.py`,
  `tests/test_kiln.py`, `docs/ferramentas.md`, `TODO.md`, `docs/aprendizados-boss.md`).
  Pronto quando: o Artur revisou o diff e autorizou o commit (ou disse para segurar).
- [ ] **0.2 · Tirar os experimentos do repo.** Mover `tmp-kiln/` para `~/.horys-pixel/experimentos/golem-kiln/`
  (sem apagar nada) e atualizar os caminhos no `resumo.md`.
  Pronto quando: `git status` não mostra `tmp-kiln/` e os scripts da r5 (`montar.py`, `mix_cn_full.py`) abrem no lugar novo.
- [ ] **0.3 · Suíte verde de base.** `python -m pytest -q` e o teste Lua.
  Pronto quando: número de testes registrado aqui.
- [ ] **0.4 · Revisor sem Codex por padrão.** Em `config.PREFERENCIAS_PADRAO`, `revisor: "claude"`; `cruzado` vira
  opção. Em `horys_revisar`, a reserva só tenta o Codex se ele estiver no PATH **e** a preferência pedir.
  Testes: `test_revisor_padrao_claude`, ajustar `tests/test_revisor_reserva.py`.
  Pronto quando: os testes passam e um `horys_revisar` sem Codex instalado não tenta chamá-lo.
- [ ] **0.5 · Codex fora do caminho obrigatório.** `motor/conceito.py gerar` e `horys_referencia_gerar(fonte: codex)`
  continuam existindo como opção; nada no fluxo padrão nem na `SKILL.md` exige o Codex.
  Pronto quando: `grep -i codex skills/horys-pixel/SKILL.md` só mostra menções opcionais.

## Fase 1: padrões de entrada no código

- [ ] **1.1 · Fichas por tipo em dados.** `src/horys_pixel/padroes/<tipo>.json` com os números das fichas do cofre:
  `quadro`, `pivo`, `altura_alvo` (faixa), `detalhe_min_frac`, `vista`, `camera`, `proporcao`, `canvas_geracao`,
  `ocupacao`, `linha_chao_frac`, `cores_max`, `contorno`, `luz`, `remover`, `animacao` (layout da grade, células,
  escala mínima). Tipos: personagem, criatura-pequena, criatura-grande, boss, prop, arvore, predio, tile, icone,
  retrato, efeito. Texto e justificativa ficam no cofre; os números, aqui.
  Teste: `test_padroes_carregam_e_validam` (todo tipo tem todos os campos; `detalhe_min_frac` = px mínimo ÷ altura alvo).
  Pronto quando: o teste passa e `horys_ficha` mostra o padrão do tipo do asset.
- [ ] **1.2 · `horys_prompt_traducao` (ferramenta nova).** Entrada: tipo, ficha do asset, estilo ou subpaleta,
  descrição do design, referência (caminho, opcional), modo `parado` ou `poses` (com a lista de poses).
  Saída na pasta do pedido: `traducao/prompt.md` (os 11 itens do modelo do cofre, com o % de detalhe calculado do
  tamanho alvo) e `traducao/paleta-<estilo>.png` (amostra com os hex, como a gerada para o macaco em 09/11).
  Em `poses`: grade e escala da ficha, base aprovada como anexo, guia de pose se houver.
  `horys_referencia_gerar` passa a chamar esta ferramenta quando `fonte: manual` (novo padrão).
  Testes: `test_prompt_traducao_parado` e `test_prompt_traducao_poses` (contém itens 1–11, todos os hex, o % certo e
  a regra de anexo da referência de terceiros).
  Pronto quando: os testes passam e o prompt gerado para o macaco bate com `traducao/prompt.md` feito à mão.
- [ ] **1.3 · Entrega da imagem pelo painel.** O painel do Aseprite mostra o prompt com um botão "copiar" e espera a
  imagem numa pasta `entrada/` do pedido (ou um arquivo arrastado). `horys_aguardar` destrava quando a imagem chega.
  Arquivos: `extension/ui.lua`, `ferramentas/conversa.py`, `daemon/pedidos.py`.
  Pronto quando: e2e no Aseprite real com uma imagem de teste.
- [ ] **1.4 · `horys_portao_entrada` (ferramenta nova).** Mede a imagem antes da conversão:
  - fundo liso (cantos com ΔE OKLab < tolerância) e a cor do fundo ausente na figura;
  - figura inteira, com margem ≥ 5%;
  - linha dos pés (última linha opaca) e ausência de sombra no chão;
  - escala: figura ≥ 3× a altura alvo;
  - grade: N figuras, alturas iguais (±3%) e chão comum;
  - chapado: número de cores depois de agrupar em OKLab e fração de bordas suaves (degradê);
  - prévia no tamanho final (vizinho mais próximo) ao lado da imagem, para o teste de olho.
  Saída: APROVADO ou REPROVADO, com cada falha escrita como correção citando o item do prompt.
  Módulo puro `entrada.py` + ferramenta. Testes com imagens sintéticas (fundo em degradê, figura cortada, sombra,
  grade com escalas diferentes, imagem boa).
  Pronto quando: os testes passam, a `conceito-chapado.png` do golem aprova e a `macaco.png` original reprova pelos motivos certos.
- [ ] **1.5 · Conversão exige portão de entrada.** `horys_converter` recusa imagem sem `entrada_checagem.txt`
  aprovado, salvo `forcar` + `motivo` (mesmo padrão do `horys_exportar`).
  Teste: `test_converter_recusa_entrada_reprovada`.
- [ ] **1.6 · Skill reescrita.** `skills/horys-pixel/SKILL.md`, passo 5: ficha do tipo → `horys_prompt_traducao` →
  o usuário gera → `horys_portao_entrada` → `horys_converter`. A seção 5k (Kiln) vira "guia de pose" (Fase 3).
  Pronto quando: um pedido novo pelo motor Gerar segue o fluxo sem citar o Codex.
- [ ] **1.7 · Teste real: macaco pelo padrão.** O Artur gera com `traducao/prompt.md`; portão de entrada; conversão
  a 198 px; limpeza; portão; revisor. Comparar com a v19 (84%).
  Pronto quando: nota registrada aqui, com a melhor versão e a lista de defeitos.

- [ ] **1.8 · Pivô do conversor pelo centro dos pés.** O `horys_converter` usou o pixel opaco mais baixo como pivô
  (x=49 de 138) e jogou o boss frontal 19 px para a direita (macaco-golem-p2 v01). O pivô tem que ser o centro do vão
  entre os pés (ou o centro da caixa da linha de baixo). Teste com figura simétrica de dois pés.
- [ ] **1.9 · Sombra gerada.** No v04/v05 a sombra do `horys_contorno` ficou com 0,74 da base (regra 0,75–1,0) e
  o topo cortado reto entre os pés. Ajustar a largura e não recortar a elipse.

**Resultado do 1.7 (2026-11-09):** a imagem do prompt de tradução passou no portão de medidas na **v01** (0 falhas;
a v19 levou 17 versões). Revisor: v01 60% → v04 65% (centralizar, tirar musgo e bege, crânio à mão), sem
`redesenhar_forma`. O que falta é acabamento (pelo, medalhão, dedos, pedras facetadas, M10), marcado no Aseprite.

## Fase 2: motor de sequência (o gargalo)

Módulo novo `src/horys_pixel/sequencia/` (puro, testável, sem Aseprite), com uma ferramenta MCP por cima.
Recebe N quadros de **qualquer fonte** e devolve pixel art animada e consistente.

- [ ] **2.1 · Entradas.** Pasta de PNGs, uma grade (PNG + linhas × colunas) ou um vídeo (MP4 → quadros com `ffmpeg`,
  se instalado; sem `ffmpeg`, erro claro). O atlas do Kiln entra por adaptador (`kiln.ler_atlas`).
  Teste: `test_sequencia_entradas` (as 3 formas viram a mesma lista de quadros RGBA).
- [ ] **2.2 · Fatiar e tirar o fundo por célula.** Reaproveitar a remoção por inundação do `conceito.py`.
- [ ] **2.3 · Registro.** Alinhar escala e posição de todos os quadros pela linha dos pés, pela altura de referência
  (a base aprovada) e pelo pivô da ficha; corrigir deriva de câmera (vídeo).
  Pronto quando: num caso sintético com deriva de escala e posição, a deriva final fica ≤ 1 px.
- [ ] **2.4 · Escolha de quadros (vídeo).** Medir altura dos pés e silhueta por quadro e escolher os N quadros do plano
  da `praticas.md` (contato e passagem no andar; antecipação, impacto e quique no golpe). Quadros extras só antes ou
  depois das chaves, nunca entre elas (lição do Dead Cells).
  Teste: num vídeo sintético de andar, escolhe os quadros de contato certos.
- [ ] **2.5 · Quantização conjunta.** Um mapeamento único material → rampa para todos os quadros (agrupamento OKLab
  sobre a união dos quadros, depois a subpaleta do estilo), e redução por moda até a altura alvo.
  Teste: `test_quantizacao_conjunta_estavel` (uma região parada recebe a mesma cor em todos os quadros).
- [ ] **2.6 · Trava de identidade.** Peças declaradas na ficha (`decalques`: crânio, medalhão, olho, runa) recortadas
  da base aprovada e coladas em cada quadro na posição achada por casamento de modelo (translação e espelho; rotação
  só por RotSprite, nunca vizinho direto). Generaliza o `montar.py` da r5, que subiu o L4.
  Teste: peça deslocada 3 px é achada e colada sem borda.
- [ ] **2.7 · Anti-cintilação.** Um pixel só muda de cor entre quadros se a forma mudou ali (máscara de movimento por
  diferença de silhueta); se não mudou, herda o quadro anterior. Métrica nova no `medir.py`: **% de pixels que piscam**
  (mudam e voltam em 2 quadros), com meta calibrada no Tiny.
  Pronto quando: a métrica separa a r4 (cintilava) da r5 do golem e o motor zera a cintilação num caso sintético.
- [ ] **2.8 · Limpeza da sequência.** `kiln.limpar_sequencia` (órfãos sem boil), a busca gulosa do M10 (1 px por vez,
  só aceita se o M10 cair), o contorno e a sombra fixa no pivô, aplicados a todos os quadros com as mesmas regras.
- [ ] **2.9 · `horys_sequencia` (ferramenta MCP).** Entrada → quadros no Aseprite (camada da ficha, durações e tags
  do plano) → pronto para o portão.
  Pronto quando: e2e no Aseprite real com a r5 do golem como entrada, portão rodando no fim.
- [ ] **2.10 · `horys_importar_kiln` vira adaptador.** A importação do Kiln passa a usar o motor (registro, quantização
  e limpeza), sem duplicar código.
  Pronto quando: `tests/test_kiln.py` continua verde e o resultado não piora no portão.

## Fase 3: fontes de movimento (experimento A/B)

- [ ] **3.1 · Guia de pose.** `horys_guia_poses`: renderiza no Kiln (ou no Noct 3D) as poses do plano em silhueta, em
  grade, com a mesma escala e o mesmo chão, para anexar ao prompt de poses.
  Pronto quando: a grade do andar do golem sai com 4–8 silhuetas alinhadas.
- [ ] **3.2 · A/B no andar de frente do golem.** Mesmo motor de sequência e mesmo revisor para as três fontes:
  - (a) grade de poses no gerador de imagem, com o guia e a v19 anexados (o Artur gera);
  - (b) vídeo a partir do conceito chapado (Veo, Kling ou Runway pelo Artur; ou Wan local, se couber nos 6 GB da RTX 3060: verificar antes);
  - (c) a r6 do Kiln (linha de base, já montada no `tmp-kiln/out-final4/`).
  Pronto quando: tabela com L3, L4, L6 e aceitação das três, com os GIFs lado a lado.
- [ ] **3.3 · Fonte padrão por tipo.** Registrar em `docs/decisoes.md` e no cofre qual fonte vale para personagem,
  criatura e boss, e atualizar as fichas.

## Fase 4: entrega a 90% e aprendizado

- [ ] **4.1 · Revisor com estrutural × acabamento.** Em `motor/revisor_prompt.md`, cada defeito ganha
  `classe: estrutural|acabamento`. "Pronto para entrega" = zero estrutural **e** aceitação ≥ 80.
  `redesenhar_forma` continua sendo estrutural.
  Teste: o parser do JSON aceita a classe e calcula o estado de entrega.
- [ ] **4.2 · Marcas de acabamento na entrega.** Os defeitos de acabamento viram marcas (`horys_marcar`) na camada
  `revisao` e uma lista no painel, para o usuário finalizar.
- [ ] **4.3 · Gosto automático.** Depois do retoque do usuário, `horys_mudancas` → resumo do que ele mudou por
  categoria (rosto, brilho, contorno, cor) → `horys_gosto_registrar`. Regras recorrentes sobem para a `praticas.md`
  do projeto.
  Pronto quando: um retoque real vira uma entrada de gosto consultável no próximo pedido.
- [ ] **4.4 · Calibração dos 90%.** 5 assets pelo fluxo novo (personagem, criatura, boss, prop e ícone); o Artur dá
  nota; medir a concordância revisor × Artur.
  Pronto quando: concordância registrada e o limite de entrega ajustado se precisar.

## Fase 5: limpeza e documentação

- [ ] **5.1 · Docs.** README, `docs/arquitetura.md`, `docs/fases.md`, `docs/ferramentas.md` e `docs/protocolo.md`
  com o fluxo novo.
- [ ] **5.2 · Arquivar o que saiu do caminho.** Scripts do ComfyUI (`scripts_mix`) e a montagem da r5 vão para
  `~/.horys-pixel/experimentos/`; o rig de partes fica só para personagem pequeno, não para boss.
- [ ] **5.3 · Instalação.** `horys instalar --tudo` sem Codex por padrão (`--codex` continua opcional).
- [ ] **5.4 · `TODO.md` arquivado** em `docs/historico/` com um link para este arquivo.

---

## Caminho crítico

`0.4 → 1.1 → 1.2 → 1.4 → 1.7` (o parado pelo padrão novo) e, em paralelo depois do 1.1,
`2.1 → 2.3 → 2.5 → 2.7 → 2.9 → 3.2` (a animação). O 2.6 (trava de identidade) é a parte de pesquisa: fazer depois do
2.5 e medir o ganho no 3.2.

## Fora do escopo

- Criar motor 3D ou gerador de imagem próprio.
- Vendorizar o SpriteKiln ou as forjas Noct: ficam como dependências opcionais.
- Anexar arte de terceiros (régua Tiny ou outra obra) em qualquer prompt.

## Decisões em aberto

1. **Fonte da verdade das fichas:** proposta = números no repo (`padroes/*.json`), texto no cofre. Confirmar.
2. **Vídeo local:** o Wan cabe nos 6 GB? Se não, a fonte (b) depende de conta num serviço pago.
3. **Limite de entrega:** "zero estrutural + aceitação ≥ 80" ou subir o limite depois da calibração (4.4).

## Regras de execução

1. Uma tarefa por vez, na ordem do caminho crítico, salvo pedido do Artur.
2. Nada marcado sem evidência. Suíte verde antes de marcar qualquer tarefa de código.
3. Commit só com autorização do Artur. Download de terceiros (modelos, pacotes) também.
4. Mudança de estilo ou de padrão vai para `docs/decisoes.md` e para o `decisoes.md` do cofre.
