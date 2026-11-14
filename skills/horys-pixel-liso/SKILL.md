---
name: horys-pixel-liso
description: Gera pixel art de qualidade no estilo Horys Pixel Liso do Artur, com boas práticas universais de pixel art e sem régua externa: a régua é o próprio Artur (o pedido dele e o que ele já aprovou). Faz personagens, NPCs, inimigos, bosses, criaturas, tilesets, prédios, props, ícones, UI e efeitos, com animação. Pergunta o que for preciso até o pedido ficar claro, pesquisa referências do que foi pedido, extrai do Obsidian as boas práticas que valem para aquele asset, desenha pixel a pixel numa grade de texto, passa num portão de medidas e num revisor exigente (nota de 0 a 100 e inventário completo já na v01) que compara com o pedido e com os assets que o Artur já aprovou. Use sempre que pedirem para criar, animar, refazer, ajustar ou revisar arte em pixel para os jogos do Artur, mesmo sem citar a skill.
---

# Horys Pixel Liso (v4.5: referência fiel limpa por cima, Aseprite ao vivo pelo horys, base de ofício, A/B cego)

**Animação de um design já escolhido:** use também `skills/horys-pixel-liso-animacao/SKILL.md` (no repo horys-generator-pixel).
Ela detalha plano temporal, fidelidade, franja/overlap e evidências de reprodução. O pedido atual e a ficha aprovada
prevalecem sobre limites genéricos de cores, fps e proporções abaixo. Não repita perguntas já respondidas nem
exija novo sim para trabalho já autorizado. No Hunvix, documentação fica no Obsidian conforme o AGENTS.md.

**Objetivo:** o Artur é dev indie. Ele pede em uma frase e recebe arte que ele aprova, com o mínimo de
trabalho manual. A skill faz o resto: pergunta, pesquisa, aplica as boas práticas da base e não entrega nada que
reprove nas medidas ou no revisor.

**A régua é o Artur.** Não há pacote de referência. O padrão é o pedido dele (a ficha) e os assets que ele já
aprovou (`<trabalho>/_aprovados/` e `KB/estilo/aprovados.md`, com as palavras dele). Por cima valem sempre as **boas
práticas universais de pixel art** (silhueta com espaço negativo, formas orgânicas, material legível, volume em
cachos, técnica limpa). O revisor só libera o asset para ir ao Artur; quem aprova é ele. A arte é sempre original.


## Fluxo

### 0. O Artur é a régua (antes de tudo)
- Leia `KB/estilo/aprovados.md` e olhe os PNGs de `<trabalho>/_aprovados/` (config `aprovados`): é o padrão que ele
  já aceitou. O `_regua.png` mostra o asset ao lado deles.
- Quando o Artur **aprovar** um asset: copie o quadro principal para `_aprovados/<projeto>_<tipo>_<asset>_<estado>.png`
  e registre em `aprovados.md` a data e as palavras dele (o que gostou, o que pediu). Quando ele **reprovar**,
  registre também (o que não quer mais). É assim que a régua cresce.
- O portão (`medir.py`) não é régua de estilo: as métricas do perfil 32 foram calibradas num corpus de teste
  (config `corpus_teste`, hoje a Eldiran 32x32, CC0) só para garantir que pegam ruído, borrão e quadro parado.
  Figura acima de 40 px (perfil 64) usa metas herdadas, sem calibração.

### 0a. Duas exigências antes de tudo (Artur, 2026-11-13; sem exceção)
1. **Imagem de referência EM PIXEL ART.** Todo asset começa de uma imagem em pixel art (nativa ou ampliada, com
   blocos de pixel visíveis, paleta curta, sem degradê, antialias nem blur). Ilustração lisa, foto, render ou
   concept "pintado" **não servem**. Sem ela, peça ao Artur ou gere pelo Codex/ChatGPT (3b/3c) já em pixel art e no
   ângulo pedido. Confira antes de seguir: `horys_asset_novo` recusa a imagem que não for pixel art (mede a grade de
   blocos, o erro dentro dos blocos e o número de cores) e diz por quê.
2. **Ângulo de câmera declarado**: `top-down` (de cima), `3/4 top-down` (RPG, vê topo e frente), `lateral`
   (plataforma), `frontal`, `3/4 frontal` ou `isometrico`. **Sempre pergunte** se o pedido não disser, e confira
   que a referência está nesse ângulo; referência em outro ângulo = peça outra. O ângulo vai na ficha, no prompt do
   gerador ("pixel art, <ângulo>"), na `praticas.md` (regras 37 e 47 da base de ofício) e no revisor.
Sem as duas, não há ficha, não há `horys_asset_novo` e não há pixel.

### 0b. Briefing: perguntar até ficar claro
Siga `KB/pipeline/perguntas.md`. O Artur não deve precisar escrever um prompt grande: **você** pergunta.
- **A primeira rodada de perguntas sempre tem as duas exigências do 0a** (referência em pixel art e ângulo), a menos
  que o pedido já traga as duas.
- **O estilo já decide**, então não pergunte: paleta, luz, 10 fps, tamanho padrão, formatos de entrega.
- **Pergunte o que falta**, com `AskUserQuestion`: até 4 perguntas por rodada, até 3 rodadas, recomendada primeiro.
- **Sempre que houver animação**, pergunte **como** cada estado se move, não só quais estados existem. Exemplos:
  - ataque: golpe de cima, estocada ou giro?
  - andar: pesado, saltitante ou cauteloso?
  - o objeto acompanha, cai ou flutua?
  - o efeito sai de onde?
- **Contorno:** para personagem novo, pergunte se é anil de 2 px, contorno fino ou sem borda escura. O médico usa
  o fino (`contorno suave`).
- **Não aceite resposta vaga:** converta em valor. "Não sei" vale a opção recomendada.
- Feche com o **resumo de confirmação** (modelo em `perguntas.md`) e "posso seguir?". Só desenhe depois do sim.
- Se o pedido já responde tudo, não pergunte de novo: mostre o resumo e peça o sim.

### 1. Pesquisa de referências do pedido (web)
Faça de 3 a 6 buscas e abra de 2 a 4 páginas boas, em duas frentes:
- **Tema:** o que faz esse tipo ser reconhecido de longe (silhueta, objeto-assinatura, cores) e o clichê a evitar.
- **Movimento:** como jogos e packs top-down bons animam **cada estado pedido**. Anote quantos quadros, onde fica
  a antecipação e o impacto, o que atrasa (follow-through) e como o efeito entra. Comece pela banca
  (`KB/analise/banca-de-qualidade.md`) e pelos Slynyrd 55 e 56.

Grave `<raiz>/<asset>/pesquisa.md` com os achados, o link de cada fonte e 2 ou 3 opções de design (se o design
não veio pronto). Extraia **princípios**. Nunca copie sprite, personagem ou paleta.

### 2. Boas práticas da base (obrigatório, antes de qualquer pixel)
Leia, nesta ordem:
1. `KB/estilo/estilo.md`;
2. `KB/tecnicas/checklist.md`, inteiro;
3. `KB/analise/banca-de-qualidade.md`, o padrão de cada estado;
4. a banca do tipo de asset:
   - estado de **dano, derrota ou morte** → `KB/analise/dano-e-morte.md`, com o "Padrão para o Hunvix" e as
     decisões do Artur;
   - **efeito** (poeira, fogo, explosão, cura, impacto, projétil) → `KB/analise/banca-de-efeitos.md`;
   - **cenário** (tile, água, árvore, arbusto, pedra, prédio, recurso) → `KB/analise/banca-de-cenario.md`;
5. a técnica do tipo de asset (`KB/tecnicas/personagens.md`, `animacao.md`, `efeitos.md`, `tilesets.md`,
   `terreno.md`, `vila.md`, `props-e-itens.md`, `boss.md`...);
6. `KB/tecnicas/fundamentos.md` (contorno, cor, formas e textura valem para todo asset).
7. **A base de ofício** (62 regras, ~400 modelos de grade, 2006 paletas, vinda do aseprite-ai-artist, MIT), pelo
   MCP horys: `horys_oficio` `{acao:'indice'}` e depois 2 ou 3 regras do assunto (`{acao:'regra', regra:'34'}`).
   Tabela rápida: personagem → 30, 31, 36; rosto e olhos → 32, 33; mãos, pés, arma na mão → 34; cabelo, roupa,
   armadura → 35, 23; direções e top-down → 37, 47; qualquer animação → 40 + 41/42/43/44 do estado; capa, cabelo e
   cauda em movimento → 45, 46; animais → 50–53; monstro → 54, 36; cenário → 60–67; perspectiva e objetos → 70–75;
   efeitos → 80–82; UI e ícone → 83, 84; cor e material → 20, 22, 23, 24; técnica e tamanho pequeno → 10–14;
   revisão → 07, 92. Sem o MCP, os arquivos estão em
   `C:/Users/artur/workspace/repos/horys/horys-generator-pixel/src/horys_pixel/oficio_dados/regras/`.
   **É ofício, não régua:** número de pixel de mão, ordem de dedos, quadros de andar. Se bater com a ficha ou com um
   aprovado do Artur, vale o Artur. Regras do ofício que valem para o asset entram na `praticas.md` com a fonte
   (`oficio:34 regra 1`).
   **Modelos:** `{acao:'modelos', filtro:'hands'}` e `{acao:'modelo', nome, cores:{papel:'#hex da paleta'}}` mostram
   a grade pronta. Use como ponto de partida para a parte (mão, pé, pose-chave de andar), trocando as cores pela
   paleta do asset e **adaptando à pose**; nunca entregue o modelo como está.

Depois escreva `<raiz>/<asset>/praticas.md`. Esse arquivo é o contrato que o revisor cobra. Ele tem:
- **de 10 a 25 regras que valem para este asset**, uma por linha, verificáveis e com a fonte (nota da KB ou link).
  Exemplos:
  - "sombra no chão com a largura do corpo";
  - "cabelo em 3 cachos de luz, não chapado";
  - "linha interna separa o braço do tronco".
- **o plano de quadros de cada estado:** número de quadros e ms, qual quadro é cada pose-chave (contato, passagem,
  antecipação, impacto, recuperação), o que atrasa e quanto, e a meta de medida do estado (ver
  `KB/revisao/metricas.md`; por exemplo, andar: muda ≥ 40% e redesenho ≥ 30%).

### 3. Ficha
Grave `<raiz>/<asset>/ficha.md`: tamanho, vista, contorno, rampas da paleta, elementos, estados e quadros, exceções
pedidas pelo usuário e decisões. Formato em `KB/pipeline/formato-ficha.md`.
- **Confira a paleta contra a referência antes de qualquer pixel.** Meça em OKLCH os valores (L) dos materiais
  principais da referência e veja se a paleta tem tons perto deles. Buraco de valor (no construtor, nada entre o
  contorno L 0,31 e o terracota L 0,58, e o couro escuro virou rosado e chapado) é decisão do Artur: proponha a rampa
  nova (passos de L de ~0,10, sombra girando o matiz) e registre na nota da paleta do projeto antes de desenhar.

### 3b. Conceito pelo Codex, antes do pixel (obrigatório para personagem, inimigo, boss e criatura)
Detalhes em `KB/pipeline/conceito.md`. O Claude monta o prompt, o Codex gera a arte e o Claude a transforma em
pixel art de verdade.
1. Escreva `<raiz>/<asset>/conceito/prompt.md` a partir da ficha, da `praticas.md` e da paleta (hex de cada tom).
   - Ponha o que o Artur aprovou como **princípios escritos** (e, se for arte dele, anexe).
   - Só anexe arte própria ou de licença livre (CC0); obra protegida, descreva o que importa nela. A referência do próprio Artur
     só se anexa no fluxo de asset fiel (3c).
   - Peça 2–3 opções, uma por imagem, em fundo `#ffffff`.
2. `python S/conceito.py gerar --prompt <...>/prompt.md --saida <...>/conceito --img KB/estilo/paleta-horys-liso.png`
3. O revisor julga na etapa `conceito` (L1, L3 e L4, com nota) e o Artur escolhe a opção.
4. `python S/conceito.py converter <conceito_0N.png> --legenda <estado>.grade --altura <px> --saida <...>.grade`
   gera o **ponto de partida** no tamanho real e com as cores travadas.
5. **Limpe à mão** a partir dele, nesta ordem:
   - silhueta e vãos;
   - contorno interno;
   - manchas e cachos;
   - rosto.
   Só então gere a v01 para o portão.
- A imagem de IA **nunca** vira asset. A animação continua desenhada por você a partir do quadro base.

### 3c. Asset fiel a uma referência do Artur (ficha diz "fiel" ou "1:1")
Exemplo completo: `art-src/pixel-liso/construtor` (v04). **Limpe por cima da conversão; nunca redesenhe do zero na
grade.** Redesenhar foi o que deixou v01–v03 longe da referência.
1. **Referência feita para converter.** Escreva `<asset>/conceito/prompt_chatgpt.md` (modelo: o do construtor) para o
   Artur gerar no ChatGPT, anexando a **própria referência dele** (é dele, pode anexar) e uma amostra das cores
   (`paleta_<asset>.png`). O prompt pede, em itens numerados:
   - **pixel art de verdade, no ângulo da ficha**: blocos de pixel quadrados e do mesmo tamanho em toda a imagem,
     paleta curta com os hex da ficha, contorno de 1 px, sem degradê, antialias, blur nem "pixel falso" de tamanhos
     misturados (exigência do Artur de 2026-11-13; a imagem passa pelo teste de pixel art do `horys_asset_novo`);
   - o mesmo design, vista do jogo, proporção (massa de cima ~60%), vãos, o rosto com o que precisa sobreviver no
     tamanho do jogo, as cores com o papel de cada hex, luz em crescentes e a lista do que não fazer;
   - **fundo liso de uma cor que não está no personagem** (com creme ou branco, use verde `#3DBE5B`: o creme fica a
     ~0,04 do branco em OKLab, dentro da tolerância da remoção de fundo).
   Uma imagem só; correção se pede no mesmo chat, citando o item.
2. **Converter** (referência em pixel art ampliada: `--nativo`, que acha o bloco e a fase da grade e amostra um pixel
   por bloco; senão, por moda, que quantiza a imagem inteira e pega a cor mais frequente de cada bloco):
   `python S/conceito.py converter <img> --legenda <legenda.grade> --altura <px com contorno> --modo moda --tirar-contorno 1 --saida <estado>.grade`
3. **Limpeza mecânica** (só tira ruído e afina; não cria forma):
   `limpar --min 4 --proteger h` → `afinar` (linhas internas a 1 px e nada de contorno colado na borda) →
   `limpar --min 3 --proteger h --proteger-area <rosto>`.
4. **Rosto à mão, por cima, pelas medidas.** Localize olhos, sobrancelha, nariz e boca/bigode na referência em
   resolução cheia (manchas da cor do contorno dentro da pele, por exemplo), converta para coordenadas da grade e
   desenhe ali: olho-grão 2×3 com brilho, sobrancelha de 1 px ligada ao olho, nariz com contorno de 1 px.
   **Julgue em 1× e 2× ao lado da referência**, não no zoom.
5. Corrija cores que caíram na rampa errada (no construtor, a sombra dos aros caiu no cobre em vez da madeira) e
   siga para o portão. As camadas para animar saem depois, por cima do quadro aprovado.
- **Diagnóstico quando sair longe da referência:** ponha lado a lado a referência reduzida com as cores reais, a
  quantização bruta e a sua versão. Se a quantização já for mais parecida que a sua versão, a perda veio do
  desenho; se a reduzida com cores reais for parecida e a quantização não, veio da paleta.
- **Sem cota no Codex** (`gerar` sai com código 1): faça 2–3 silhuetas em blocos à mão (`.grade` de 1–2 cores em
  `vNN-conceito/`) e avise o Artur.

### 4. Desenho na grade
- Cada estado é um arquivo `<raiz>/<asset>/<estado>.grade`. O formato completo está no topo de `S/grade.py`.
- O `tipo` da grade escolhe as metas do portão: `personagem`, `npc`, `inimigo`, `boss`, `criatura`, `animal`,
  `efeito`, `tile`, `agua`, `arvore`, `prop`, `recurso`, `predio`, `icone`, `retrato`. Dê ao estado um nome que diga
  o que ele é, porque o nome escolhe a meta: `idle`, `andar`, `ataque`, `trabalhar`, `cura`, `dano`, `morte`;
  nos efeitos, `poeira`, `fogo`, `explosao`, `respingo`.
- Uma letra por cor e `.` = transparente. Escreva **linha por linha, à mão**. Nada de script que gere a **forma**.
  Script só para limpeza mecânica de uma conversão (`conceito.py limpar` e `afinar`, troca de cor numa região):
  fundir ruído, afinar linha e recolorir pode; inventar silhueta, rosto ou volume não.
- Tamanho real do jogo: humanoide com 64–72 px de altura **com** contorno, no quadro 192 (pivô do pé em 96,127).
- Contorno:
  - `contorno auto`: anil de 2 px por fora. Você desenha o preenchimento e as linhas internas de 1 px.
  - `contorno suave`: 1 px por fora, num tom mais leve.
  - `contorno nenhum`: as linhas internas viram a sombra do material vizinho, e só olho, sobrancelha e boca
    ficam escuros.
  - `sombra sim` desenha a elipse do chão.
- Ordem de trabalho:
  1. **silhueta** (1 ou 2 cores);
  2. **cor e luz:** 2 ou 3 tons por material, em **cachos** de luz e sombra, nunca chapado nem pillow;
  3. **linhas internas** separando os planos;
  4. **rosto**;
  5. **poses-chave** do plano de quadros;
  6. **intermediários**.
- Para animar, **redesenhe** a forma a cada quadro (inclinação, squash, braços em arco, ponta atrasada).
  Deslizar partes inteiras reprova no portão (redesenho, A02).
- Para corrigir, edite só as linhas afetadas (Edit). `python S/grade.py numerar <arquivo>` mostra a grade com régua.
- **Camadas (padrão para personagem, inimigo, boss e criatura):** desenhe cada parte num bloco
  `--- q0 @<parte> <dx> <dy>` (o formato está no topo de `S/grade.py`). A ordem dos blocos é a ordem de baixo para
  cima, a de `KB/tecnicas/personagens.md` (Partes para animar). **Pinte a área escondida** de cada parte. Linhas
  internas de 1 px entre partes vão na própria camada; o contorno externo e a sombra são gerados.
  `contorno` e `sombra` são nomes reservados.

### 5. Gerar e passar no portão de medidas
```
python S/grade.py gerar <raiz>/<asset>/<estado>.grade [...] --saida <raiz>/<asset>/vNN
```
- Gera a folha PNG e as prévias:
  - `_8x`, `_silhueta` (1x e 0,5x) e `_regua`: a prancha "boas práticas" (1×, 2×, 4× e 8× sobre grama e
    masmorra) com os aprovados do Artur embaixo, na mesma escala;
  - `_quadros_4x`, o `.gif` e o `_checagem.txt`.
- Roda também o **portão de medidas** (`S/medir.py`; perfil 32 calibrado no corpus de teste). O resultado fica em
  `vNN/medidas/<estado>/` (`medidas.json` e `overlay`).
- **`PORTÃO DE MEDIDAS: REPROVADO` (código 1) = corrija e gere de novo. Não chame o revisor com o portão reprovado.**
  Uma falha medida nunca vira "leve". Se não passar depois de 4 tentativas no mesmo estado, pare e mostre ao
  Artur o melhor resultado, com os números.
- O portão inclui o **M17**: no máximo 25% da borda da silhueta em trechos retos de 8 px ou mais (no perfil 32: 5 px e até 70%).
  Acima disso, a figura foi montada com primitivas.
- Olhe você mesmo o `_regua`, o `_8x` e o GIF e anote 3 diferenças concretas contra a ficha e os aprovados. **Não itere no
  próprio olho antes do revisor**: a primeira versão que passar no portão já vai para ele.

### 6. Revisor exigente
- Chame o Agent `subagent_type: "horys-pixel-liso-revisor"` passando:
  - a pasta `vNN`;
  - os estados;
  - os caminhos da `ficha.md` e da `praticas.md`;
  - a etapa;
  - **em asset fiel (3c), a referência do Artur** e uma prancha referência | sprite em 2× e 1×, pedindo que a
    semelhança (rosto, proporção, assinatura, cores) entre no inventário. Sem isso o revisor só compara com as boas práticas.
- **O revisor entra na v01** (a primeira versão que passa no portão). Diga "RODADA 1: inventário completo" e a
  ficha e os aprovados do Artur. Ele lista **todos** os defeitos de uma vez, para que a próxima versão corrija tudo junto.
- Ele julga as boas práticas universais **e** a ficha e os aprovados, confere cada regra da `praticas.md` e devolve um JSON com
  nota de 0 a 100 por critério e `aceitacao` (o percentual de aceitação).
- **PASSA = nenhuma falha grave e aceitação ≥ 80.**
- Se vier `redesenhar_forma: true`, **redesenhe a forma** (volte ao conceito, se preciso), não retoque.
- Mostre ao Artur a nota de cada rodada (por exemplo, "v01: 34% → v02: 61%").
- **No máximo 3 rodadas por etapa.** Depois disso, o olho do Artur decide. Sem PASSA, mostre a melhor versão com os
  defeitos abertos, sem esconder.
- **Leitura a frio:** o revisor escreve o que vê antes de ler o pedido (`leitura_fria`). Se não nomeou o assunto, a
  figura não diz o que você acha que diz: essa é a correção mais importante da rodada.
- **Corrigir sem estragar o que funcionava** (a partir da rodada 2):
  1. **Cópia antes de mexer:** copie a `vNN` inteira (ou a `.grade` e o PNG `_8x`) antes da correção.
  2. **Corrija, não redesenhe:** mude só as linhas que a falha aponta. Se a correção mudou mais de ~25% dos pixels
     opacos de uma camada (`grade.py diff`), foi redesenho: volte à cópia e faça a correção menor. Exceção:
     `redesenhar_forma: true`.
  3. **Decida por comparação, não pela nota:** notas de chamadas diferentes não estão na mesma escala. Ponha o
     `_8x` antigo e o novo como `a.png` e `b.png` em ordem sorteada numa pasta `vNN/ab/` e chame o revisor em
     **modo comparação** com as falhas graves da rodada. Fica a versão que ele escolher; se escolher a antiga,
     volte à cópia. Duas rejeições seguidas encerram as rodadas: mostre ao Artur.

### 6b. Aseprite ao vivo (MCP `horys`, o caminho padrão quando o Aseprite está aberto)
O MCP `horys` (repo `horys-generator-pixel`) traz o motor desta skill (`grade.py`, `medir.py`, `conceito.py`) e desenha
no Aseprite do Artur pela extensão Horys. Confira com `horys_status`; se disser "NÃO conectado", peça para abrir o
Aseprite (a extensão conecta sozinha; senão, menu Horys › Conexão e painel). Sem Aseprite, siga só com a `.grade`.
**Ao vivo não pula nada:** briefing, pesquisa, `praticas.md`, ficha, conversão, portão e revisor continuam valendo.
O Aseprite é a mesa de trabalho; a `.grade` e o portão continuam sendo a fonte e a medida.

Ordem ao vivo:
1. **Documento:** `horys_asset_novo` (quadro, pivô, camadas por parte, paleta e tags) ou `horys_sprite_novo`.
   Nome e caminho novos em `<asset>/vNN`; nunca por cima de arquivo do Artur sem ele pedir.
2. **Trava de paleta:** na primeira `horys_pixel_map`, passe `trava: [hex da ficha]`. Toda cor fora é puxada para a
   mais próxima e a resposta diz o que mudou; ΔE > 12 = falta o tom na paleta: avise o Artur, não desligue.
3. **Referência como guia:** com referência (3b/3c), ponha a conversão por moda numa camada `referencia` (oculta para
   exportar) e desenhe por cima nas camadas das partes. `horys_ver {modo:'comparar'}` mostra referência | arte; nomeie
   as 3–5 maiores diferenças e corrija só essas, depois de cada etapa (silhueta, materiais, sombra).
4. **Etapas, uma chamada cada, olhando entre elas** (`horys_ver` com crítica: cor, cinza, silhueta, 1×):
   silhueta (1–2 cores) → materiais chapados → luz e sombra em cachos → linhas internas → contorno (`horys_contorno`)
   → rosto → limpeza (`horys_limpar`, só mecânica). Cada `horys_pixel_map` é um Ctrl+Z para o Artur.
5. **Corrigir:** `horys_ler_pixels` da região (as letras ficam fixas por cor no sprite) → troque só os caracteres
   errados → `horys_pixel_map` com o mesmo `x`/`y`. Partes repetidas: `stamps`/`place`; espelho: `horys_copiar`.
   Mão, pé e pose-chave: parta de um modelo (`horys_oficio {acao:'modelo', nome, cores, desenhar:true, x, y,
   camada}`) e adapte.
6. **Animação:** `horys_ver {modo:'filmstrip'}` para o ciclo, `{modo:'onion', camada:<parte>}` nos intermediários e
   `{modo:'diff', de, ate}` para conferir o que uma edição mexeu.
7. **Fechar a versão:** traga o resultado para a `.grade` (`horys_ler_pixels` por camada) e rode o portão
   (`horys_portao` ou `grade.py gerar`). Revisor como no passo 6 (leitura a frio, A/B cego).
- **Retoque do Artur:** `horys_mudancas` (1ª chamada marca o ponto), "corrige isto" = `rect: 'selecao'`.
  Depois do retoque, `horys_gosto_do_retoque` aprende com o que ele mudou.
- **Perguntas e aprovações** no painel do Aseprite: `horys_perguntar` / `horys_aprovar` + `horys_aguardar`.
- O MCP `aseprite` antigo (sloplink, `aseprite_*`) e o `ai-artist` ficam só como alternativa; não misture dois
  servidores no mesmo documento.

### 7. Portões do Artur
- Personagem: briefing (passo 0), silhueta e cor do quadro base, e animação.
- Mostre sempre o `_8x`, o `.gif` e o `_regua`. Se ele estiver em outro aparelho, use SendUserFile.

### 8. Entrega
- PNG da folha, GIF, `.grade` (a fonte editável) e o **`.aseprite` fatiado**. O `grade.py gerar` grava
  `vNN/<nome>_<estado>.aseprite` sozinho, pelo Aseprite em modo batch (`S/exportar_aseprite.lua`, caminho em
  `config.json` → `"aseprite"`): camadas `sombra` (opacidade 77), `contorno` e uma por parte, tag do estado,
  paleta da legenda. Ele reabre o arquivo e compara com a folha pixel a pixel; o resultado sai no `_checagem.txt`
  (`ok .aseprite: ...` ou `ERRO`). Grade sem camadas sai numa camada `desenho`. Sem Aseprite, avise.
- No Hunvix, os assets prontos vão para `assets/generated/<asset>-vN/`. Integração no jogo só se pedirem.

## Tamanho pequeno (perfis 16 e 32)

Desde 2026-11-12 (FASE 2 da `pesquisa-16-32.md`). Figura de até 40 px com contorno: perfil 32; até 20 px: perfil 16.
A grade declara `perfil 32` (ou o `grade.py` deduz pela altura). Não há régua externa em nenhum perfil (a régua é o Artur).

- **Corpus de teste do 32** (só para as métricas, não é régua): Eldiran "32x32 RPG Character Sprites" (CC0), em `D:/godot/referencias/eldiran-32/fatias`
  (quadro 36; `pNN_s/n/e.png`). O Artur escolheu esse estilo para o Hunvix: chibi, contorno escuro de 1 px, rosto liso.
  O 16 ainda não tem corpus de teste.
- **Contorno:** `contorno suave` (1 px, `cor_contorno #18122c`) ou `contorno selout` (o tom mais escuro da rampa do
  material vizinho). Nunca o anil de 2 px: ele come o sprite.
- **Direções:** um arquivo por direção (`andar_s.grade`, `andar_n.grade`, `andar_e.grade` com `direcao s|n|e`; no `e`,
  `espelho w`). Desenhe nesta ordem: frente, costas, lado, diagonais. Passe todos no mesmo `gerar`: sai a prancha
  `<nome>_<estado>_direcoes.png` e o portão conjunto (`_conjunto.txt`) com D01 (altura), D02 (linha do pé), D03 (área:
  s/n ±10%, lado 60–90% da frente), D04 (aviso: material que some) e D05 (cores exclusivas de uma direção).
- **Guia:** `guia <png> [dx dy]` (guia do SpriteKiln com `spritekiln pose --dirs all`, ou a referência). Sai o
  `_guia.png` e o G01 (IoU da silhueta no pivô; meta 0,75 no 32 e 0,70 no 16). `numerar --guia` mostra a guia como `:`.
  A guia é referência: nunca vira asset nem é "pintada" por script.
- **Edição segura:** `grade.py diff <arq> q0 q1` (o que mudou, por linha) e `grade.py anim <arq>` (deslocamento, pé,
  px mudados e px por letra; avisa parte mudando de tamanho).
- **Portão do 32** (calibrado no corpus de teste): ruído = pixel isolado na vizinhança 8 e de baixo contraste, em px/quadro
  (até 20); andar muda ≥ 15% por quadro; até 20 cores em personagem; bordas retas até 0,70; sem meta de miolo escuro.

## Regras invioláveis
- Paleta travada; contorno conforme a ficha; sem antialiasing, blur, dithering ou degradê.
- Limites de cor do `estilo.md` (personagem ≤ 10; o script confere). Uma exceção pedida pelo usuário vale e vai na
  ficha e na grade (`limite_cores`).
- O pedido do usuário prevalece sobre o estilo. Registre a exceção na ficha.
- Nada de desenhar antes do sim no resumo do briefing e antes de existir a `praticas.md`.
- Nada começa sem imagem de referência em pixel art e sem ângulo declarado (0a).
- Nunca diga que algo ficou pronto, validado ou aprovado sem o portão, o revisor e o usuário confirmarem.
- Arte original. O corpus de teste e a banca não são asset: não copie como asset final.

## Manutenção
- Calibração por perfil: `python S/calibrar.py --perfil 32 mutacoes` e `python S/calibrar.py --perfil 32 metricas`
  (saída em `<trabalho>/_calibracao32`; em 2026-11-12: 72/72 bons e 15/15 ruins). `--perfil 32` é o padrão; 16 e 64 não têm corpus de teste.
- Mudou `scripts/revisor_prompt.md`? Rode `python S/instalar.py` (regenera o agente do Claude e o do Codex).
- Mudou uma meta do `medir.py`? Rode `python S/calibrar.py mutacoes` e depois `python S/calibrar.py metricas`.
  Os bons do corpus de teste têm que passar todos e os estragados têm que reprovar todos (em 2026-11-12: 72/72 e 15/15).
  Registre em `KB/decisoes.md`.
- Aprendeu uma boa prática nova? Ela vai para `KB/tecnicas/checklist.md`, com a fonte. Não vai para esta SKILL.
