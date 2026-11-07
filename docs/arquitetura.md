# Arquitetura

## Visão geral

```
 Aseprite (extensão Horys, Lua)        servidor horysd (Python, sempre ligado)              motores
┌───────────────────────────┐        ┌───────────────────────────────────────┐
│ Novo asset: "viking"      │  WS    │ ponte com o Aseprite (única)           │  inicia   ┌──────────┐
│ referência: [img]         │◄──────►│ fila de pedidos e estado de cada um    │─────────►│ claude -p│
│ motor: (•) Claude ( ) Codex│ token  │ ferramentas: desenho · estilo · conversa│          └────┬─────┘
│ [Gerar]                   │        │ portão (medir) e conversão (conceito)  │  inicia   ┌────┴─────┐
│ ── conversa ──            │        │ memória de gosto e conjunto de treino  │─────────►│codex exec│
│ pergunta + opções + outro │        │ fonte de conceito: Codex | LoRA | ref. │          └────┬─────┘
│ [Aprovar] [Refazer]       │        └───────────────▲───────────────────────┘               │
│ nota do revisor           │                        │  MCP: as mesmas ferramentas            │
└───────────────────────────┘          horys-mcp (ponte stdio, uma por cliente) ◄─────────────┘
                                         também usada por Claude Code e Codex abertos no terminal
```

## As peças

### 1. Extensão Horys (Lua, dentro do Aseprite)
- **Janela "Novo asset":** o que criar, referência (opcional), tipo (personagem, inimigo, tile, prop, efeito...),
  projeto (escolhe a régua e a paleta), **motor** (Claude ou Codex) e estados de animação.
- **Painel da conversa:** mostra cada pergunta da skill com as opções, a recomendada primeiro e um campo "outro".
  É o equivalente do `AskUserQuestion`, só que dentro do Aseprite.
- **Portões:** botões Aprovar / Refazer com comentário, na silhueta, na cor do quadro base e na animação.
- **Andamento:** etapa atual, nota do revisor por rodada (ex.: v01 34% → v02 61%) e a camada `revisao` com os
  defeitos marcados no lugar.
- Tudo com a API de extensões do Aseprite (`Dialog` com entry, combobox, radio, file, canvas, button; `WebSocket`).
  **Não mexe no C++ do Aseprite**: o código em `C:\aseprite` fica só para consulta.

### 2. Servidor `horysd` (Python)
- **Processo único e sempre ligado.** É o único que fala com o Aseprite (WebSocket local com token). Resolve o conflito
  de hoje, em que Claude e Codex brigam pela porta (9123/9124).
- **Clientes MCP entram pela `horys-mcp`:** uma ponte stdio fina, uma por cliente, que repassa as chamadas ao
  `horysd`. Claude e Codex podem estar conectados **ao mesmo tempo**.
- **Fila de pedidos:** cada asset é um pedido com estado (briefing, pesquisa, ficha, conceito, conversão, limpeza,
  portão, revisor, animação, entrega) salvo em disco. Se algo cair, o pedido continua de onde parou.
- **Motor por pedido:** ao clicar em Gerar, inicia o motor escolhido sem terminal:
  - `claude -p "<pedido>" --mcp-config <horys.json> --allowedTools "mcp__horys__*" ...`
  - `codex exec "<pedido>"` com o servidor `horys` na configuração.
  Os dois usam o login que você já tem (assinatura), sem chave de API.
- **Motor de estilo embutido:** o `grade`, `medir`, `conceito` e `calibrar` da skill de hoje viram módulos do
  servidor, chamados como ferramentas.

### 3. Skill `horys-pixel` (uma só, para os dois motores)
- O fluxo da `horys-pixel-liso` v4.2 (régua, briefing, pesquisa, práticas, ficha, conceito, conversão por moda,
  limpeza, portão, revisor, animação, entrega), reescrito para usar **só as ferramentas MCP**, sem nada específico de
  um motor.
- **Perguntas e aprovações passam por `horys_perguntar` e `horys_aprovar`.** Com o painel do Aseprite aberto, elas
  aparecem lá; sem ele, caem no chat do motor.
- A mesma pasta é ligada em `~/.claude/skills/horys-pixel` e na pasta de skills do Codex.

### 4. Revisão: o revisor e a skill `horys-pixel-review`
- **Revisor do fluxo:** roda como **outra execução sem terminal**, iniciada pelo servidor, com o prompt do revisor
  atual. **Cruzado por padrão:** se o Claude desenhou, o Codex revisa, e vice-versa. Dá para fixar um motor.
- **Skill `horys-pixel-review`** (a `pixelart-review` de hoje, trazida para cá): revisa **qualquer** PNG ou
  `.aseprite`, mesmo que não tenha saído do gerador. Compara vistas (altura, linha dos pés, cores), aponta degrau
  irregular, contorno dobrado, órfão e assimetria, e mede "IA slop" em telas e conceitos.
- **Um medidor só:** o `pixel_review.py` e o `medir.py` viram um módulo do servidor. O portão do fluxo e a revisão
  avulsa usam as mesmas medidas, e o overlay aparece na camada `revisao` do Aseprite.
- No Aseprite: **Horys › Revisar este sprite**.

### 4b. Estilos
O estilo é um **pacote** (paleta, bíblia, regras, régua, metas, gosto, treino) que cada pessoa cria. Ver
[estilos](estilos.md). Todo pedido roda dentro de um estilo; o Horys Pixel Liso é o primeiro.

### 5. Imagem de referência (de qualquer origem)
A imagem só existe para **facilitar a geração**: decide forma, proporção e apelo, e **nunca vira asset**.
- **Padrão: a ferramenta pede.** No briefing, o painel pede uma imagem de referência, venha de onde vier (ChatGPT,
  PixelLab, Pinterest, um rabisco seu, um print). O motor converte por moda e limpa por cima.
- **Se você não tiver uma,** ela pode gerar: pelo **Codex** (geração de imagem embutida; o Claude não gera imagem) ou,
  quando existir, pelo **modelo local treinado** ([treino](treino.md)). Gerar é opção, não etapa obrigatória.
- O motor pode também **montar o prompt** para você gerar a imagem fora, como a skill faz hoje no fluxo "fiel".
- Referência de terceiros serve de guia, mas **não entra no conjunto de treino**, a não ser que a licença permita.

## Fluxo de um pedido (pelo Aseprite)

1. Você preenche a janela e clica em Gerar → o `horysd` cria o pedido e inicia o motor escolhido.
2. O motor lê a régua e a KB e faz o **briefing** por `horys_perguntar` (até 3 rodadas de até 4 perguntas).
   Fecha com o resumo e espera o seu "sim".
3. Pesquisa de referências e `praticas.md` (o contrato que o revisor cobra).
4. Ficha e paleta conferida contra a referência.
5. **Referência:** o painel pede a sua imagem (qualquer origem). Sem imagem, oferece gerar (Codex ou modelo local) ou
   te entrega o prompt para gerar onde quiser. Com várias opções, você escolhe no painel.
6. **Conversão por moda** direto no Aseprite: quadro, uma camada por parte, paleta travada.
7. **Limpeza ao vivo**, nesta ordem: silhueta, contorno interno, cachos, rosto. Você pode pintar junto; o motor lê as
   suas mudanças e as respeita.
8. **Portão de medidas** no sprite aberto. Reprovou: corrige e mede de novo (até 4 vezes).
9. **Revisor** (cruzado), com nota e inventário completo já na v01. Até 3 rodadas.
10. Portão seu: silhueta e cor → Aprovar / Refazer.
11. **Animação** por estado, como tags no mesmo arquivo, com o mesmo ciclo de portão e revisor.
12. **Entrega:** `.aseprite` fatiado, PNG da folha, GIF e a grade de texto (formato interno do portão).
13. Cada aprovação e recusa vai para a **memória de gosto** e, os aprovados, para o **conjunto de treino**.

## Fluxo pelo terminal
Você conversa no Claude Code ou no Codex como hoje. A skill usa as mesmas ferramentas e o Aseprite mostra o desenho.
Sem o painel aberto, as perguntas aparecem no chat.

## Fatiamento modular em partes
`src/horys_pixel/partes.py` (sem Aseprite, só arrays RGBA) define o preset `humanoide-ferreiro` (9 partes, de baixo
para cima) e ~10 contratos de junção (parte inferior, superior e móvel), o validador por quadro e junção (parte vazia
ou desconexa, partes que se tocam, inferior ≥ 1 px sob a superior, buraco ao mover a parte móvel 1–2 px nas 8
direções, linha interna, cobertura ≥ 90%), a vista explodida (ocultos em magenta), o recorte da camada oculta
`referencia` e a extensão da anatomia oculta (1–2 px). Recorte e extensão só escrevem em pixels cobertos: a imagem
composta nunca muda (conferida antes e depois; se mudar, reverte). A ficha ganha `modular`, `preset_partes`,
`juncoes` e `partes_oculto`; em asset modular camada faltando é erro. O portão repete a checagem
(`partes_checagem.txt`, `medidas/partes.json`, `<asset>_partes.png`) e erro nas partes reprova a versão e a
exportação. `motor/grade.py` e o `.grade` não mudam (já guardam pixels ocultos por camada). A etapa `partes` do pedido
vem antes da animação. `tools/fatiar_ferreiro.lua` é só migração legada.

## Segurança
- WebSocket só em `127.0.0.1`, com token e desafio HMAC (como no sloplink). O token nunca aparece no chat nem em log.
- Nada de executar Lua arbitrária vinda do motor: só comandos conhecidos.
- Salvar só dentro das pastas de projeto configuradas; nunca por cima de arquivo seu sem pedir.
- Backup automático do sprite antes de cada etapa que muda pixels.

## Riscos conhecidos
- **Pergunta que espera muito:** uma chamada de ferramenta que fica esperando a sua resposta pode estourar o tempo
  limite do cliente MCP. Plano: `horys_perguntar` devolve um id na hora e `horys_aguardar` espera em fatias curtas.
- **Execução sem terminal e permissões:** cada motor precisa da lista de ferramentas liberadas (MCP do horys e os
  scripts). Isso fica numa configuração gerada pelo `horysd`, sem afrouxar o resto do seu ambiente.
- **Codex sem cota:** a fonte de conceito cai para referência ou modelo local, e o painel avisa.
