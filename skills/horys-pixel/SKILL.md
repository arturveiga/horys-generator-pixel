---
name: horys-pixel
description: Gera pixel art de qualidade desenhando AO VIVO no Aseprite do usuário, no estilo dele (pacote de estilo; no Hunvix, o Horys Pixel Liso com régua Tiny Swords). Faz personagens, NPCs, inimigos, bosses, criaturas, tiles, prédios, props, ícones, UI e efeitos, com animação. Pergunta no painel do Aseprite até o pedido ficar claro, pede uma imagem de referência (de qualquer origem) ou gera uma, converte por moda, limpa à mão na tela, passa no portão de medidas e no revisor exigente do outro motor, e entrega .aseprite fatiado, PNG, GIF e .grade. Funciona com Claude ou Codex, com terminal ou sem (botão Gerar do Aseprite). Use sempre que pedirem para criar, animar, refazer ou ajustar arte em pixel para os jogos do usuário, mesmo sem citar a skill.
---

# horys-pixel (gerar)

Tudo passa pelas ferramentas MCP `horys_*` (servidor `horys`). Não rode scripts soltos para desenhar: o desenho
vive no Aseprite; o motor de medidas roda dentro das ferramentas.

**Objetivo:** o usuário pede numa frase e recebe arte no nível da régua do estilo, com o mínimo de trabalho manual.
Você pergunta, pesquisa, aplica as boas práticas do estilo e não entrega nada reprovado no portão ou no revisor.
A régua é de QUALIDADE, não estilo a copiar. A arte é sempre original.

## Onde está cada coisa
- **Estilo:** `horys_estilos` (sem nome lista; com nome mostra paleta, régua, KB e as notas a ler). Padrão do projeto:
  Hunvix → `horys-pixel-liso` (KB no Obsidian do usuário). `KB` abaixo = a pasta `kb` do estilo.
- **Pasta do asset:** com terminal, `art-src/pixel-liso/<asset>/` no projeto (fora dele, a que o usuário disser);
  sem terminal, a **pasta de trabalho do pedido**. Os textos (pesquisa, práticas, ficha) você grava com as suas
  ferramentas de arquivo; as versões `vNN` saem das ferramentas `horys_portao`/`horys_exportar`.
- **Pedido** (sem terminal): o prompt traz o id. Registre cada etapa com `horys_pedido_atualizar` (etapa, texto
  curto, nota do revisor). O usuário acompanha no painel do Aseprite.

## Conversar com o usuário
- Perguntas: `horys_perguntar` (até 4 por vez, 2–4 opções, a recomendada PRIMEIRO com "(recomendado)", passe
  `pedido`) → `horys_aguardar(id)` repetido enquanto vier "pendente". O painel sempre tem "Outro".
- Portões dele: `horys_aprovar` (`sprite: true` mostra a crítica do quadro; passe `estilo`, `etapa`, `tipo`,
  `descricao`, `pedido` para virar memória de gosto) → `horys_aguardar`.
- Se vier `sem_painel`: com terminal, pergunte no chat; sem terminal, siga a recomendada e registre com
  `horys_pedido_atualizar(pendencia=...)`. Resposta com `_automatico` ou `pendente_usuario` = ninguém respondeu:
  siga, mas liste no fim como pendente de aprovação.
- Nunca diga que algo ficou pronto, validado ou aprovado sem portão, revisor e usuário confirmarem.

## Fluxo

### 0. Estilo, gosto e régua
1. `horys_estilos(nome)`: confirme o estilo do projeto (se não houver, pergunte qual base seguir).
2. `horys_gosto_consultar(estilo, tipo)`: o que o usuário já recusou e aprovou. Defeitos repetidos são regra
   prática para este asset; exemplos aprovados entram como referência de acabamento.

### 1. Briefing (perguntar até ficar claro)
Siga `KB/pipeline/perguntas.md` se existir. O usuário não escreve prompt grande: VOCÊ pergunta.
- O estilo já decide (não pergunte): paleta, vista, luz, fps, tamanho padrão, formatos de entrega.
- Pergunte o que falta: até 3 rodadas. Em animação, pergunte COMO cada estado se move (golpe de cima, estocada ou
  giro? andar pesado, saltitante ou cauteloso? o objeto acompanha, cai ou flutua? o efeito sai de onde?).
- Personagem novo: contorno (o do estilo, fino ou sem borda escura).
- **Referência:** pergunte se há uma imagem (qualquer origem: ChatGPT, PixelLab, Pinterest, rabisco, print). Ela só
  facilita a geração e nunca vira asset. Opções: "Tenho uma (cole o caminho em Outro)", "Gerar uma" (recomendado
  se não houver), "Seguir sem".
- Resposta vaga vira valor; "não sei" vale a recomendada.
- Feche com o resumo de confirmação e "posso seguir?". Só desenhe depois do sim.

### 2. Pesquisa (web, se você tiver busca)
3–6 buscas e 2–4 páginas: o que faz o tema ser reconhecido de longe (silhueta, objeto-assinatura, cores) e o clichê
a evitar; como jogos top-down bons animam CADA estado pedido (quadros, antecipação, impacto, follow-through). Grave
`pesquisa.md` com links e 2–3 opções de design. Extraia princípios; nunca copie sprite, personagem ou paleta. Sem
busca, use a KB (`analise/banca-*`, `tecnicas/`).

### 3. Boas práticas (obrigatório antes de qualquer pixel)
Leia, nesta ordem (KB do estilo; as notas da lista `leitura` do estilo vêm primeiro): `estilo/estilo.md`,
`tecnicas/checklist.md` inteiro, `analise/banca-de-qualidade.md`, a banca do tipo (dano/morte → `dano-e-morte.md`;
efeito → `banca-de-efeitos.md`; cenário → `banca-de-cenario.md`), a técnica do tipo (`tecnicas/personagens.md`,
`animacao.md`, `efeitos.md`, `tilesets.md`, `terreno.md`, `vila.md`, `props-e-itens.md`, `boss.md`...) e
`tecnicas/fundamentos.md`. Grave `praticas.md`: 10–25 regras verificáveis com a fonte, e o **plano de quadros** de
cada estado (quadros e ms, pose-chave de cada quadro, o que atrasa, meta de medida — ver `KB/revisao/metricas.md`).

### 4. Ficha e sprite
Grave `ficha.md` (`KB/pipeline/formato-ficha.md`): tamanho, vista, contorno, rampas, elementos, estados e quadros,
exceções pedidas. Confira a paleta contra a referência (valores L em OKLCH); buraco de valor é decisão do usuário.
Depois `horys_asset_novo`: estilo, nome, tipo, quadro (192 para humanoide de 64–72 px; pé no pivô 96,127),
**partes de baixo para cima** (a ordem de `tecnicas/personagens.md`, "Partes para animar"), contorno, estados
`[{nome, quadros, ms}]`, `pasta` = pasta do asset. Ele devolve as letras da paleta para o `horys_pixel_map`.
- **Humanoide (ferreiro e similares): `preset_partes: 'humanoide-ferreiro'`** em vez de `partes`. Cria as 9 partes
  (perna-traseira, corpo-base, avental-torso, cabelo, barba, braco-traseiro, braco-frente, martelo, oculos), a camada
  oculta `referencia` e grava na ficha `modular`, `preset_partes`, `juncoes` (10 contratos: parte inferior,
  superior e móvel) e `partes_oculto`. `contorno` e `sombra` continuam geradas, nunca são partes. Camada faltando
  num asset modular é erro, não é ignorada.

### 5. Referência → pixel (o caminho que funciona)
A lição da v4.2: **limpe por cima da conversão; nunca redesenhe do zero na grade.**
1. Sem imagem e o usuário quis gerar: `horys_referencia_gerar` (`fonte: codex`, ou `lora` se o estilo tiver modelo
   treinado). O prompt pede ilustração chapada (cel shading) em alta, NÃO "pixel art"; o design, a vista, a proporção
   (massa de cima ~60%), os vãos, o rosto com o que sobrevive no tamanho do jogo, as cores com o papel de cada hex,
   luz em crescentes, o que não fazer, e **fundo liso de uma cor que não está no personagem** (com creme/branco, verde
   `#3DBE5B`). Nunca anexe arte de terceiros; a régua entra como princípios escritos. Gere 2–3 opções e deixe o
   usuário escolher (`horys_aprovar` com `imagem`).
2. `horys_converter(imagem, altura com contorno, camada, quadro, tirar_contorno: 1)`: moda + paleta travada + pé no
   pivô. Personagem com camadas: converta na parte de cima e depois separe as partes (passo 6).
3. `horys_limpar(min 4, proteger: [hex do olho/brilho])` → `horys_afinar` → `horys_limpar(min 3, proteger_area: rosto)`.
4. **À mão, por cima** (`horys_ler_pixels` da região → corrija só as linhas erradas → `horys_pixel_map` com x/y),
   nesta ordem: silhueta e vãos; contorno interno; manchas e cachos de luz; **rosto** (olho-grão 2×3 com brilho,
   sobrancelha de 1 px ligada ao olho, nariz com 1 px de contorno), medido na referência em resolução cheia.
5. Cores na rampa errada → corrija. `horys_paleta_estilo(verificar: true)` tem que dar tudo na paleta.
Asset fiel ("1:1") a uma referência do usuário: o mesmo caminho, comparando em 1× e 2× lado a lado. Diagnóstico
quando sair longe: se a quantização bruta já parece mais que a sua versão, a perda veio do desenho; se a reduzida com
cores reais parece e a quantização não, veio da paleta.

### 5k. Base 3D pelo SpriteKiln (personagem animado, se instalado)
Use quando o asset é personagem, inimigo ou criatura **com animação**; para ícone, prop, tile e UI, siga o passo 5.
O SpriteKiln dá a pose, os quadros e o timing consistentes; o Horys dá cor, limpeza, mão por cima e o portão.
1. Paleta: `horys_paleta_kiln(estilo, destino)` e aponte `palette:` do spec para o YAML gerado.
2. Spec a partir do briefing: `view: side` (ou `topdown` se o jogo for 3/4), `camera: {pitch: 10}`, altura do
   briefing **sem** contorno, `render: {outline: none, shading: toon}` (o Horys gera o anel), luz vindo de cima/
   direita (M15). Cabeça e cabelo no `brief.head`, conferidos com `spritekiln pose --focus head`.
3. Animação: ajuste os `keys` do spec (não os pixels) até a pose ler bem; comece cada golpe da pose de guarda do
   idle. `spritekiln render --anims ...` só no fim.
4. `horys_asset_novo` com o quadro do render → `horys_importar_kiln(json, tags, direcao, limpar_min: 3)` (com
   `spec` + `grupos` em asset modular: as partes já saem com posse certa e o passo 5b pula o fatiamento).
5. Depois disso é o fluxo normal: limpar/afinar onde o portão apontar, **mão por cima nos quadros-chave** (rosto,
   cachos, linhas internas, o que tem "cara de 3D"), `horys_contorno`, portão, revisor.
Sem SpriteKiln instalado, siga o passo 5.

### 5b. Fatiar por partes e validar (etapa `partes`, obrigatória antes de animar)
Para asset modular, depois da referência e **antes de qualquer animação**:
1. **Desenhe uma referência** completa e limpa na camada oculta `referencia` (a conversão do passo 5 pode cair
   direto nela) e a figura visível pintada nas partes.
2. **Fatie por partes** com `horys_partes_recortar(parte, regiao {x,y,w,h})`: copia a região da `referencia` para a
   parte, só onde a imagem composta final NÃO muda (pixel coberto por parte de cima ou da mesma cor). Se a figura
   visível está toda numa parte de baixo, copie para as partes de cima: o que sobra embaixo vira anatomia oculta.
3. **Anatomia oculta:** `horys_partes_estender(juncao)` estende 1–2 px a parte inferior sob a superior (aborta e
   reverte se a composição mudar). Anatomia oculta maior que 2 px (ombro, quadril, mão sob o cabo) é desenho seu,
   na própria parte, sob a peça de cima.
4. **Valide:** `horys_partes_checar` → diagnóstico + vista explodida (pixels ocultos em magenta). Corrija todos os
   ERROS (parte vazia ou desconexa, partes que não se tocam, inferior sem 1 px sob a superior, buraco ao deslocar a
   parte móvel 1 px, falta de linha interna, referência/anatomia oculta < 90% coberta). Avisos (2 px) vão para a
   `praticas.md`. `horys_pedido_atualizar(etapa: 'partes')` só depois de passar; `animacao` é recusada antes disso.
5. O portão (passo 7) repete a checagem e grava `partes_checagem.txt`, `medidas/partes.json` e `<asset>_partes.png`;
   com erro nas partes, o portão REPROVA e `horys_exportar` não entrega.
Nenhuma dessas ferramentas muda a imagem composta; mudança de forma é desenho seu, depois rode `horys_contorno`.
Atenção: o `tools/fatiar_ferreiro.lua` é só migração legada de um .aseprite antigo, não o fluxo.

### 6. Desenho, camadas e animação
- Uma letra por cor, `.` não mexe. Dado grande: `.json` em pasta temporária e `arquivo`. Junte passos com `horys_lote`.
- **Camadas** (personagem, inimigo, boss, criatura): cada parte na sua camada; **pinte a área escondida** de cada
  parte para ela poder se mexer. Linhas internas de 1 px entre partes ficam na própria camada. `contorno` e
  `sombra` são geradas: rode `horys_contorno` depois de mexer na silhueta (o portão recompõe igual). Ao animar um
  asset modular, rode `horys_partes_checar` a cada quadro novo: a parte que se move redesenha a anatomia oculta.
- Ordem: silhueta (1–2 cores) → cor e luz (2–3 tons por material, em CACHOS, nunca chapado nem pillow) → linhas
  internas → rosto → poses-chave do plano → intermediários.
- Animar = **redesenhar** a forma a cada quadro (inclinação, squash, braços em arco, ponta atrasada). Deslizar parte
  inteira reprova (A02). Comece cada quadro com `horys_copiar` do quadro anterior e redesenhe.
- `horys_mudancas` mostra o que o usuário pintou: respeite e incorpore.
- Julgue com `horys_ver(critica: true)` (cor, cinza, silhueta, 1×) e `horys_regua(categoria)` lado a lado.
  Não fique iterando no próprio olho: a primeira versão que passar no portão vai para o revisor.

### 7. Portão de medidas
`horys_portao` (estados) gera `vNN` na pasta do asset (folha, _8x, silhueta, _regua, _regua_anim, gif,
_checagem.txt, medidas/, .aseprite fatiado) e devolve APROVADO/REPROVADO.
- **REPROVADO = corrija e rode de novo. Não chame o revisor com portão reprovado.** Falha medida nunca vira "leve".
- Inclui o M17 (≤ 25% da borda em trechos retos de 8 px+): acima disso a figura foi montada com primitivas.
- 4 tentativas no mesmo estado sem passar: pare e mostre ao usuário o melhor resultado com os números.
- Olhe o `_regua_anim`, o `_8x` e o GIF e anote 3 diferenças concretas contra a régua.

### 8. Revisor exigente (outro motor)
`horys_revisar(pasta vNN, estados, ficha, praticas, etapa, rodada, referencia?, quem_desenhou: <você>)` →
`horys_aguardar(id)` (leva minutos). Rodada 1 = inventário completo na v01.
- PASSA = nenhuma falha grave e aceitação ≥ 80. `redesenhar_forma: true` = volte ao passo 5/6 e redesenhe a forma.
- Mostre a nota de cada rodada (`horys_pedido_atualizar(nota=...)`, ex.: v01 34% → v02 61%).
- No máximo 3 rodadas por etapa; depois o olho do usuário decide. Sem PASSA, mostre a melhor versão com os defeitos.
- Defeito apontado pelo revisor: `horys_marcar` (pontos/retângulos) para o usuário ver no Aseprite.

### 9. Portões do usuário e entrega
- Personagem: briefing (1), silhueta e cor do quadro base, e animação → `horys_aprovar(sprite: true, estilo,
  etapa: 'silhueta'|'cor'|'animacao', tipo, descricao, pedido)`.
- Entrega: `horys_exportar(destino)` (no Hunvix: `assets/generated/<asset>-vN/`). Integração no jogo só se pedirem.
- No fim, `horys_pedido_atualizar(etapa: 'concluido', texto: resumo + pendências)`.

## Regras invioláveis
- Paleta travada; contorno conforme a ficha; sem antialiasing, blur, dithering ou degradê.
- Limite de cores do `estilo.md` (personagem ≤ 10); exceção pedida pelo usuário vai na ficha (`limite_cores`).
- O pedido do usuário prevalece sobre o estilo; registre a exceção.
- Nada de pixel antes do sim no briefing e antes da `praticas.md`.
- Script não cria FORMA: só limpeza mecânica (limpar, afinar, recolorir região).
- Nunca salve por cima de arquivo do usuário sem ele pedir; nunca imprima o token de pareamento.
- Arte original; a régua e as bancas são medida, não fonte para copiar ou redistribuir.
