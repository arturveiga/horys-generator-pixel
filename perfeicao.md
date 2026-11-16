# Perfeição: como chegar a pixel art e animação no Aseprite a ~80%

Análise de 2026-11-13. Nenhum código foi alterado. Este documento junta o que foi lido, medido e visto em:

- **Plugins e kits:**
  - `aseprite-ai-artist` (zip nos Downloads);
  - o **Blender Pixel Kit** (o addon do vídeo);
  - `agent-sprite-forge`;
  - `sprite-forge`.
- **Projetos no D:**
  - os dois Noct;
  - `D:\horys-generator`;
  - `pixelfx` e `sprite-studio`;
  - ComfyUI, Hunyuan3D, os packs KayKit e a Eldiran.
- **Este repo:** o histórico de testes.
- **PixelLab:** só para entender o mecanismo.

---

## 0. Resposta curta

1. **Nada do que existe hoje chega a 80% sozinho.** Nem o ai-artist, nem o horys, nem os Noct, nem o Pixel Kit, nem o SpriteKiln.
2. **Todo resultado que passou de 80 até hoje pegou a forma emprestada de uma imagem pronta:**
   - o conceito do boss (84);
   - a referência simples do ChatGPT (gorila, 84 estático);
   - a figura Eldiran recolorida (ranger, 83).

   Nenhuma forma inventada pelo agente passou:
   - a grade à mão sobre base empacou em 79;
   - o mecha do horys saiu desconexo;
   - o modelo em `bpy` deu 49 e o Blender, 62.
3. **Regra-mãe: o agente não inventa forma.** Ele copia, encaixa e limpa.
   - **A forma** vem de um *master*: uma imagem em pixel art já no tamanho final, gerada no Codex, com todas as vistas na mesma imagem.
   - **O movimento** vem de um *esqueleto*: a pose de um boneco 3D (SpriteKiln, Blender + KayKit) ou um corpo-base em pixel.
   - **O Aseprite** é a mesa de retoque.
4. **Caminho recomendado (seção 6), só com Codex e Claude Code:**
   - **Humanoides: "Base + Pele" (P3, com a colagem do P1).** Um corpo-base animado (Eldiran CC0 ou o seu) resolve o movimento uma vez. Cada personagem novo é só a roupa:
     1. O Codex veste a base ("A ÚNICA MUDANÇA: vista esta figura como…").
     2. A leitura na grade da base separa as células que mudaram.
     3. A colagem leva a roupa para cada quadro.
     4. O agente limpa as juntas no Aseprite.
     5. O revisor faz A/B cego e você retoca.
   - **Monstros: P1.**
     1. Master do Codex com 4 vistas numa imagem.
     2. Pose de um proxy 3D (SpriteKiln) com uma cor por parte.
     3. Colagem dos pixels do master.
     4. Limpeza e retoque.
5. **Antes de qualquer teste novo:**
   - Arrumar o processo: uma skill curta, um motor só, daemon reiniciado.
   - Colocar 3 a 5 sprites aprovados em `_aprovados`. Hoje a pasta está vazia: "o Artur é a régua" ainda não tem régua.
6. **Limite da arte:**
   - Humanoides em chibi de 32 px; monstros de 48 px com massas simples.
   - 4 direções, com o oeste espelhado.
   - Até 20 cores por personagem, contorno de 1 px e 2 a 3 tons por material.
   - Nenhum detalhe menor que 2 px. Boss grande só depois.
7. **Decisões que são suas (seção 10):**
   - ~~Aceitar uma rota de vídeo~~: decidido em 13/11, **só Codex e Claude Code**.
   - Usar ou não o corpo-base da Eldiran (CC0).
   - Qual MCP do Aseprite fica.
   - Congelar o estilo.

---

## 1. O que "80%" quer dizer aqui

Definição proposta, para medir e não discutir no olho:

- **Você só retoca.** Você muda no máximo cerca de 20% dos pixels de cada quadro. Isso se mede pelo diff entre a entrega e o seu retoque; `horys_gosto_do_retoque` já existe para isso.
- **Passa no revisor** (PASSA, aceitação ≥ 80, sem defeito grave) **e no seu olho** (sim ou não).
- **Na animação:**
  - a identidade é a mesma em todos os quadros e direções (altura, paleta, linha do pé);
  - o movimento lê como movimento, não como deslize.

Por que não basta a nota do revisor:
- Ele já deu falso positivo: o médico v16 passou e o andar só deslizava.
- A própria skill admite que notas de chamadas diferentes não são comparáveis.
- Na galeria do ai-artist, o mesmo modelo, na mesma tarefa, tirou 7 e 3.

O seu sim/não e o % de retoque são as medidas que valem.

---

## 2. Inventário: o que cada coisa é de verdade

### 2.1 aseprite-ai-artist (pebbly, MIT, v0.8.3), nos Downloads

**O que é:** um servidor MCP com extensão Lua. O agente desenha na janela aberta do Aseprite.
- Cada mudança é um Ctrl+Z.
- 18 ferramentas.
- O "grid loop": o agente digita um caractere por pixel, relê a tela no mesmo formato (`look ascii`), corrige só os caracteres errados e escreve de volta.
- Base de ofício: 62 regras, cerca de 400 modelos e 2006 paletas.
- Skills: studio, brief, concept, draw, shade, rig, animate, review, fix, export e tileset.
- Um crítico (`pixel-critic`) faz leitura a frio e A/B cego.
- Tem modo headless.

**De onde vem a forma:**
- O LLM digita todos os pixels.
- A skill `concept` só escreve o prompt; você gera a imagem fora.
- A referência entra como camada travada a 50% de opacidade, reduzida por vizinho mais próximo e sem ajuste à grade.
- A skill proíbe explicitamente "pixelizar o conceito".

**Animação:**
- Uma camada por parte; a animação copia, move e redesenha as células (cels).
- Não tem osso nem IK. Só gira 90/180/270 graus.
- 8 direções existem só como texto de regra.

**Qualidade medida pelos próprios autores** (um juiz, uma rodada por célula):
- Opus fez média de **3,5/10** em 24 rodadas. Personagens ficaram em **0 a 4/10**, a faixa de "placeholder".
- Só 2 rodadas chegaram a 7 ou mais, as duas na casa (geometria rígida).
- O mago cumpriu 15/15 critérios e levou 3/10 de ofício.
- Com o crítico, a casa foi de 3 para 8 (custou US$ 36,92 contra US$ 11,18) e a árvore caiu de 4 para 1.
- Cada rodada custou de US$ 5,7 a 36,9 e levou de 18 a 107 min.
- Não há nenhuma rodada avaliada a 32 px ou menos.
- Acima de ~32 px de largura, digitar a grade degrada; a própria ADR-0010 admite isso. Tudo da vitrine com 48 px ou mais foi calculado por script.

**No nosso mecha 64×64:**
- Manteve a massa e a proporção da referência.
- O miolo ficou manchado e sem rosto. Não chega a 80.

**Já portado para o horys:**
- As 62 regras e 2006 paletas, idênticas.
- Os modos de `horys_ver` (comparar, onion, filmstrip, diff).
- A trava de paleta por ΔE e o formato de leitura e escrita.

**Ainda não portado:**
- `tileset`: exporta `.tres` do Godot 4, inclusive blob47.
- `cel` tween/oscillate/link.
- `recolor` shade/hue_shift e `palette` ramp/analyze/extract.
- Importação de referência dividida em quadros, e `sample_palette`.
- `validate expect`.
- A guarda do loop de correção: tira um snapshot, desfaz qualquer correção que mexa em mais de ¼ da camada, no máximo 3 rodadas.
- A sessão headless longa e o texto em bitmap.

**Veredito:** é a melhor *encanação* e o melhor *texto de ofício*, mas **não é fonte de forma**.
- Serve como mesa de retoque ao vivo, ou como fonte de peças para portar.
- Não vale investir em digitar a grade como fonte principal de forma acima de 32 px.

### 2.2 Blender Pixel Kit (o addon do vídeo)

Vídeo: "NEW FREE Addon Has Everything You Need for Pixel Art (Blender Eevee)". Arquivo: `blender_pixel_kit_v1.3.1.zip`, do SouthernShotty, grátis.

**O que faz:** só prepara a cena.
- **Render:** Eevee, `filter_size 0` (sem anti-aliasing), view transform Standard, resoluções de 16 a 256 px. Renderiza já no tamanho final, sem redução depois.
- **Câmeras:** frontal ortográfica (90°) ou isométrica (54,7356° e 45°), com escala ortográfica e grade de fundo.
- **Materiais:**
  - `Flat`: cor chapada.
  - `Flat UV`: uma imagem de paleta com amostragem Closest.
  - `Toon`: Shader to RGB, depois dither, depois uma rampa constante de 3 faixas.
  - `Image to Pixel`: células voronoi com ajuste de cor.
- **Contorno:** dilatação do alfa no compositor. O padrão é **2 px**; para o nosso estilo, use 1.
- **Preview:** mostra os pixels no viewport.

**O que não faz:**
- Não anima.
- Não renderiza as direções em lote.
- Não monta spritesheet.
- Não quantiza a paleta final nem limpa.
- Não fala com o Aseprite.
- Não tem câmera top-down 3/4: a inclinação de 30–45° do Hunvix e da vila tem que ser ajustada à mão.

O Blender 5.2 já está instalado (`C:\Program Files\Blender Foundation\Blender 5.2`); o addon pede 4.0 ou mais.

**Veredito:** é a metade "configurações de render" de um caminho 3D → pixel. O SpriteKiln já faz o equivalente com SDF. Combina com os rigs do KayKit para gerar **pose**, não arte final.

### 2.3 KayKit (CC0), nos Downloads

- **Personagens:**
  - 6 heróis: Barbarian, Knight, Mage, Ranger, Rogue e Rogue_Hooded.
  - 4 esqueletos: Mage, Minion, Rogue e Warrior.
- **Esqueleto e animações:** todos usam o mesmo `Rig_Medium`, com animações prontas em `Rig_Medium_General` e `Rig_Medium_MovementBasic` (FBX e GLB).
- **Texturas:** atlas de paleta minúsculos (13–15 KB).

**Veredito:** fonte grátis e legal de **movimento** para um boneco humanoide (proxy). A proporção é a do KayKit (atarracada), então serve de pose para a colagem, não de visual final.

### 2.4 agent-sprite-forge (0x0funky, MIT, 5,7 mil estrelas, v0.6.0 de 13/11/2026)

**O que é:** skills para Claude Code, Codex e Grok: `generate2dsprite`, `video2dsprite`, `generate2dmap`, `generate2dmedia` e `codeart2d`.

**Pipeline v0.4:**
1. **Master:** um *master still* gerado pelo `image_gen` do Codex, logado e sem chave de API.
2. **Clipes:** um clipe image-to-video por ação. A rota é o Grok CLI ou uma API paga: xAI, BytePlus Seedance, ou fal (Kling, Veo, Luma, MiniMax, Wan, Vidu, LTX).
3. **Portões:** área, pés, identidade, zoom, giro, bordas, fundo, objeto extra, movimento, pose final, vazamento de cor e tempo. Até 3 tentativas por ação.
4. **Recorte e registro:** recorte suave do fundo e registro do quadro.
5. **Ciclos e tempo:** escolhe o loop por medida e encurta golpes ao tempo do jogo (ataque de 4,1 s para 0,7 s).
6. **Acabamento:**
   - HD;
   - ou pixel: redução nítida, paleta de até 32 cores, contorno seletivo, alfa binário.
7. **Exportação:** SpriteFrames do Godot, JSON do Aseprite, atlas.

**Medido na raposa 48×64:**
- Cores por quadro: de 594–709 para **16–19**.
- Níveis de alfa: de 199 para **2**.
- Pixels soltos por quadro: de 732 para **75**.

**"Pixel looks" (0.6.0)** é o achado principal:
- **Master:** `pixel_look.py master` mede a grade da *própria* imagem, cujos blocos são irregulares (de 15 a 30 px). Tira uma cor chapada por célula. Mantém a proporção, duplicando linhas quando o bloco não é quadrado. Fecha o contorno por regra.
  - Resultado: 33×55, 48 cores, zero pixel mole.
  - Um redimensionamento comum da mesma imagem dá 1.033 cores.
- **Elenco:** o personagem novo é desenhado *ao lado do master, na mesma imagem* ("THE ONLY CHANGE: add a SECOND figure… on the same pixel grid… as tall"). Assim herda o tamanho de pixel e a altura.
- **Pose:** "Reproduce the attached image… THE ONLY CHANGE: …". A imagem é relida na grade do master e só as células que mudaram são aproveitadas.
  - Os modelos devolvem de 90% a 99,8% das células iguais.
  - Na pose com espada, 217 células mudaram e 91% do master ficou.
- **Vista:** desenhada ao lado do master, com as cores puxadas para a paleta dele.
- **Movimento:**
  - o clipe de vídeo é relido na grade e na paleta do sprite;
  - a cabeça fica travada, porque o rosto "ferve" no vídeo;
  - a passada é medida para o pé não deslizar;
  - o ataque usou 21 desenhos de 145 quadros.

**"Hibit" (0.5.0):** nunca pede "pixel art" ao modelo.
- Pede arte chapada, sem contorno, com no máximo 3 tons por material.
- Depois reduz com voto da maioria em células de 8×8, usando uma paleta aprendida da imagem.
- A histerese temporal corta de 10% a 40% da cintilação entre quadros.
- Alfa binário e contorno com a cor do próprio sprite.

**Limites declarados:**
- Validado em pouco material: uma folha e um clipe.
- O ataque gerado em vídeo costuma girar o corpo todo.
- O rosto ferve no vídeo.
- Sprite de ~80×110 ou mais fica com só 4 px de vídeo por pixel e as sombras piscam.
- As medidas numéricas não aprovam anatomia.
- A importação no Godot e no Aseprite não foi verificada.
- "Um master é um pouco mais simples que a imagem dele."

**Conflito com a sua regra:**
- Master, elenco, pose e vista rodam **só com o Codex**.
- **O vídeo precisa do Grok ou de uma API paga.**
- Sem vídeo, dá para fazer poses-chave por edição (`ask-pose`), ainda só com o Codex.

**Veredito:** é a resposta mais completa a "como". Duas ideias valem de qualquer jeito:
- Tudo de novo é desenhado *ao lado do master aprovado*, na mesma imagem.
- Só as células que mudaram são aproveitadas; o resto fica idêntico, pixel por pixel.

### 2.5 sprite-forge (isabellagreco1997, MIT, 6 estrelas)

**O que é:** um kit em Python com skill para o Claude. As etapas:
- **extract:** recorta o personagem.
- **snap:** testa tamanhos de célula de 3 a 12 px e a fase, buscando a menor variação dentro de cada célula; tira a mediana da célula e quantiza.
- **dump:** um mapa ASCII da paleta.
- **parts:** um mapa de partes por polígono.
- **re-pose:**
  - apaga o membro;
  - **restaura o que estava embaixo a partir da imagem original**;
  - redesenha o membro com uma mini-linguagem `Limb`/`Pose`: a perna escrita linha a linha, com deslocamento por quadro.
- **idle:** o corpo inteiro sobe e desce, o cabelo vem um quadro atrasado e há uma piscada. **Nunca move uma parte contra outra**, porque isso abre emenda.
- **walk:** pernas redesenhadas a cada quadro (contato, recuo, passagem), com "slip factor" = 1,0.

O arquivo `LESSONS.md` tem 17 críticas do artista, cada uma virando regra.

**Limites:**
- Feito para plataforma, com vista lateral ou 3/4.
- A mini-linguagem só cobre pernas.
- Assume grade uniforme de 3 a 12 px, o que quebra com os blocos variáveis do gpt-image.
- Não faz direções e não fala com o Aseprite.

**Veredito:** copiar as regras:
- "o que não mexe fica idêntico";
- "restaure, não adivinhe";
- "slip factor";
- a tabela de lições.

E a ideia de **membros pré-desenhados por pose** para um corpo-base.

### 2.6 noct-asset-forge v2.5.0 (`D:\noct-asset-forge`)

- **Como desenha:** o agente escreve código TypeScript de desenho, uma classe `PixelCanvas` com linha, círculo, polígono, matriz, dither Bayer e contorno simples. Um Chromium headless rasteriza.
- **O que sai:** uma tira de quadros e um atlas próprio.
- **Medição:** só `inspect`, básico.
- **Aseprite:** nenhuma ligação.
- **Melhor resultado no D:** o aldeão chibi de frente, com ~75–80% como estático. Ele foi feito por scripts Python de pixel, fora do Noct.
  - Andar de lado: ~50%.
  - Os outros: 40–55%, cara de "programmer art".
- **Licença:** "todos os direitos reservados". Usar e modificar pode; redistribuir, não.

**Veredito:** nada essencial. A única ideia útil é o compositor "camadas + tabela de deslocamento por pose".

### 2.7 noct-asset-forge-3d-bb-v2 (`D:\noct-asset-forge-3d-bb-v2`)

**O que é:** um pipeline 3D procedural em Python.
- Gera modelos low-poly em BBModel, com UV e pintura de textura.
- O `AnimationEditor` tem FK, IK e checagens numéricas.
- Exporta GLB.
- `forge capture` tira vistas ortográficas, gira a câmera, escolhe o tempo do clipe e renderiza com fundo transparente e sem luz.

**O que tem no projeto hunvix:**
- 16 assets.
- O `hunter_chibi` tem idle, walk, run, shoot e hit.
- O KayKit foi importado cru.
- Não há nenhum render.

**Falta a metade de trás:** captura em lote, redução, paleta, contorno, spritesheet e .aseprite.

**Veredito:** é um gerador de pose possível, mas duplica o SpriteKiln. Só vale se a pose do SpriteKiln não bastar.

### 2.8 `D:\horys-generator` (fork do Noct, parado desde 30/10)

- 8 personagens, cada um em 4 direções paradas de 32×40, desenhados por código e sem animação.
- `tools/hunvix-noct-to-aseprite.lua` empacota tiras de PNG num .aseprite com camadas e tags.
- ~60–70% como estáticos.

**Veredito:** arquivar.

### 2.9 pixelfx (patch-gg, MIT), em `D:\pixelfx` (clone, não é seu)

- 244 efeitos de pixel art escritos em código, recoloríveis por rampa.
- Exporta folha + JSON do Aseprite, GIF e MP4, e tem checagem de loop.
- `src/core/rig.js` é um boneco de 24×38 com esqueleto 3D e IK, posado **direto em pixel nativo**.

**Veredito:** **os efeitos visuais (VFX) estão resolvidos** (~80% ou mais): use o pixelfx como está, com o crédito MIT. O `rig.js` é o melhor exemplo de "pose 3D direto no pixel" que existe no D:.

### 2.10 sprite-studio (2Cloud-S, sem LICENSE), em `D:\sprite-studio` (clone)

**O que é:** um app Tauri. Pega uma prancha de poses e:
1. passa pelo Pixel Snapper (tamanho de pixel automático, 16 cores);
2. remove o fundo chroma;
3. normaliza cada quadro numa célula fixa, com pivô;
4. alinha os quadros com onion skin;
5. exporta folha, GIF e manifest.

Sem licença: não copie o código, reimplemente as ideias.

**Veredito:** a ideia útil é "célula fixa + pivô + alinhamento por onion". O horys já tem conversor e colagem.

### 2.11 Este repo (horys-generator-pixel)

**Inventário:**
- 62 ferramentas `horys_*` no código e 31 arquivos de teste, rodando contra um Aseprite falso.
- **Usadas ao vivo, com prova:** status, sprite_novo, pixel_map, ver, salvar, asset_novo, importar_kiln, limpar, portao e revisar.

**Ponte instável.** O `horysd.log` de 13/11 tem:
- "o Aseprite não está conectado";
- "não respondeu 'salvar' em 60 s".

**As adições de 13/11 nunca rodaram ao vivo:**
- São elas: `oficio`, os modos de `ver`, a trava ΔE e a referência em pixel art com ângulo.
- O daemon subiu às 19:24 e os arquivos foram escritos às 20:53–20:56.
- A sessão MCP expõe 61 ferramentas, sem `horys_oficio`.

**O portão e o revisor ao vivo rodam o motor antigo.**
- `horys_portao` roda `python -m horys_pixel.motor.grade`, sem os perfis 16/32 e sem as checagens D01–D05 e G01.
- `motor/revisor_prompt.md` ainda fala de Tiny Swords.
- 4 testes de `test_motor_equivalencia` falham.

**As especificações se contradizem:**
- A KB diz "Régua: Tiny Swords", com 64–72 px.
- `skills/horys-pixel` fala em cozy de 20–24 px, mas o passo 4 diz 192 e 64–72.
- A `pixel-liso` v4.5 diz "não há régua externa", com 32 px.
- A `pixel-liso-animacao` manda usar primeiro outro MCP (o "sloplink").
- `agents/revisor.md` ainda usa Tiny Swords.

**A leitura obrigatória soma cerca de 170 KB:** SKILL 28 KB, notas da KB 129 KB, prompt do revisor 11 KB.

**Só testado em unidade, sem nenhum resultado de arte:**
- `partes_*`, `colagem`, `guia_poses` e `sequencia`;
- `entrega`, `gosto_do_retoque` e `pedido_*`;
- `estilo_novo` e `estilo_calibrar`.

**Nunca rodou:** `treino` (LoRA).

**Veredito:** **os ossos certos já estão aqui**: colagem, partes, conversor nativo, portão e gosto do retoque. Mas o processo, do jeito que está escrito, não dá para seguir. Arrume isso antes (seção 11).

### 2.12 SpriteKiln

**O que é:** de uma spec SDF sai pixel art em 8 direções, animada e coerente entre quadros. Está em uso:
- no Hunvix: 8 personagens cozy adotados em 11/11;
- no vila_monstros: chama, gorila, lobisomem e nuvem.

**O que se viu:**
- **Aldeão:** a animação passou no portão sem mudança, mas o "sombreado do render é picotado".
- **Boss:** o andar foi de 34 para 44 e depois 46.
- **Gorila cozy:** você gostou.
- **No olho:**
  - a chama em 8 direções está razoável (~65–75);
  - o lobisomem tem cara de "bolha 3D" (~55–65);
  - os personagens do Hunvix leem, mas são minúsculos e se mexem pouco.

**Veredito:** é a **melhor fonte de pose e consistência** que você tem. É fraco em ofício e em fidelidade ao design.

### 2.13 Difusão local (ComfyUI) e Hunyuan3D

**Máquina:** RTX 3060 Laptop com 6 GB de VRAM e 32 GB de RAM.
- SDXL base + ControlNet xinsir (canny/depth/openpose) + IP-Adapter plus ViT-H **rodam**: 1,1 a 2,3 s por passo, 26–28 passos, **43 a 60 s por imagem** (logs de 09/11).

**Testes de 09/11** (`D:\comfyui\ComfyUI\output`):
- `kilncn` (render do Kiln como ControlNet): reproduziu o render low-poly e não virou pixel art.
- `kilnmix`: pseudo-pixel, com a caveira solta do corpo.
- `h_andar`, `h_ataque`, `h_morte`: um golem HD bonito, mas não é pixel.
- O andar do boss deu 40 (50 com decalques).

**Falta peça:** `models/loras` está vazio. **Nenhum LoRA de pixel art foi testado.**

**Hunyuan3D-2mini/2mv** (em `D:\hf-cache`): uma variante de malha nunca foi avaliada, e os renders saíram ruidosos.

**Veredito:** viável, mas lento. Não é o caminho principal. Fica como pesquisa (P4).

### 2.14 Codex `image_gen` (gpt-image)

| Teste | Nota | Observação |
|---|---|---|
| Referência detalhada reduzida | 49 | |
| Referência simples na paleta e no tamanho | 70 | depois 84 estático e 81 no andar por deslocamento |
| Ilustração reduzida a 32 px | 62 | |
| Pixel art direto a 32 px | 66 | só a frente |
| Andar a partir de 4 poses | 61 | "movimento tímido"; as cores mudam de rodada para rodada |
| Robô a 32 px | — | 72–79% dos pixels mudando por quadro |
| **Pirata: virada em 4 vistas numa imagem** (`art-src/pirata-anchor/pirata-anchor-v01.png`) | nunca avaliada | identidade coerente; com pose do SpriteKiln virou 8 direções × 4 quadros, a animação multi-direção mais coerente do repo |

**Veredito:** é a melhor fonte de **forma estática**, desde que a imagem:
- seja pedida no tamanho final;
- seja simples;
- traga todas as vistas numa imagem só;
- seja lida na grade dela mesma.

É ruim como fonte de animação quadro a quadro.

### 2.15 Eldiran 32×32 (CC0), em `D:\godot\referencias\eldiran-32`

- Mais de 20 personagens montados como **boneco de papel sobre um mesmo corpo-base**: a primeira linha da folha é o corpo nu.
- Andar de 4 quadros na frente, nas costas e de lado.
- Ranger recolorido: **83, PASSA**. Grade à mão sobre a base: 79.

**Veredito:** é a prova de que "corpo-base + roupa por cima" chega a 80 em 32 px. Usar essa base em produção é decisão sua (seção 10). Pela sua regra, a Eldiran não é régua de estilo; aqui ela entraria só como esqueleto.

### 2.16 PixelLab: só como mecanismo

> O agente de pesquisa foi interrompido e a página da API não abriu. O que segue é o que é público até 2026 e **não foi re-verificado hoje**.

Como o PixelLab resolve:
1. **Modelo treinado em pixel art, gerando na resolução nativa.** Não existe etapa de redução. As famílias públicas são *Pixflux* (texto → pixel) e *Bitforge* (com imagem de estilo). As telas são pequenas.
2. **Condicionamento forte:**
   - imagem de estilo ou referência;
   - imagem inicial com força;
   - paleta forçada;
   - vista (lateral, top-down baixo, top-down alto) e direção;
   - parâmetros de contorno, sombra e detalhe.
3. **Direções:** a função "rotate" gera as outras vistas a partir de uma, presa à referência.
4. **Animação:**
   - um esqueleto de pontos-chave por quadro, estimado do próprio sprite, com o primeiro quadro como referência;
   - ou texto, em tamanho pequeno;
   - modelos de personagem (humanoide, quadrúpede) com animações de esqueleto prontas, então o mesmo movimento serve para personagens diferentes.
5. **Inpainting** para consertar a parte no lugar, quadro a quadro, dentro do Aseprite (pela extensão).
6. **Humano no loop**, dentro do Aseprite.

Seus substitutos, sem pagar ninguém:

| PixelLab | Substituto |
|---|---|
| (1) modelo nativo em pixel | pixel art do Codex no tamanho + leitura da grade própria (ASF `pixel_look`, horys `converter --nativo`) |
| (2) condicionamento | trava de paleta + o master como régua |
| (3) rotate | vistas ao lado do master, numa imagem (pirata, ASF `ask-view`) |
| (4) esqueleto | proxy de pose (SpriteKiln, KayKit) + colagem dos pixels do master (`horys_colagem`), ou vídeo (ASF), se liberado |
| (5) inpainting | edição "THE ONLY CHANGE" + diff na grade, ou o agente com leitura de volta |
| (6) humano no loop | Aseprite ao vivo, pelo horys ou ai-artist |

**O que não dá para copiar** é o modelo treinado em pixel art. Um LoRA seu precisaria de dezenas de sprites aprovados, e hoje você tem zero.

---

## 3. O que já foi tentado e onde quebrou

| Data | Abordagem | Resultado | Onde quebrou |
|---|---|---|---|
| 04–05/11 | grade de texto à mão, régua Tiny Swords | médico v16 PASSA, mas o andar só deslizava (16% de redesenho, meta 30%); gorila v01–v08 sem revisão | agente inventando forma; falso positivo do revisor |
| 05/11 | ref do ChatGPT + conversão por moda (construtor v04) | fiel na 1ª tentativa | primeiro sinal de que "emprestar forma" funciona |
| 07/11 | SpriteKiln → pixel (aldeão) | animação passou no portão sem mudança; falhas de 15 para 6 com paleta + toon | sombreado picotado, órfãos, clusters |
| 08/11 | boss estático, conceito → conversão | 84 em v17/v19 | custou 17 versões; arquivos apagados |
| 08–09/11 | andar do boss | SpriteKiln 34→44→46; + ComfyUI 40 (50 com decalques); recorte 2D ~55; 3 grades de pose reprovadas no portão | gerador não mantém escala; juntas abrem; braço sem ombro e cotovelo; pé não sai do chão |
| 10/11 | HD recortado (golem-caveira) | sem nota | braço solto no cotovelo, duas vezes (você achou) |
| 10/11 | ref ChatGPT + grade exata (gorila 48×64) | detalhada 49 → simples 70 → 84 estático, 81 idle e andar | andar = recorte deslocado, só frente, 4 quadros |
| 11/11 | 3D low-poly no Blender (golem em código) | 50→58→62; consistência 72, a melhor | "o que falta é a qualidade do modelo e da animação"; vista lateral reprova |
| 11/11 | SpriteKiln cozy (gorila), 4 direções | qa limpo; você gostou e adotou no Hunvix | bolha, pouco detalhe |
| 11/11 | pintura procedural sobre render | falhou ("ta se perdendo demais") | carimbo por script sem julgamento |
| 12/11 | bake-off da lenhadora 32 px | recolor Eldiran 83 PASSA; grade sobre base 79; ilustração Codex reduzida 62; bloco Blender 49; Codex pixel direto 66; andar Codex 61 | inventar forma; detalhe some; cor muda por rodada |
| 12/11 | pirata: virada em pixel + pose SpriteKiln → 8 dir × 4 quadros | **nunca avaliado** | falta avaliar |
| 12/11 | colagem guiada + conversor nativo | deriva da cabeça de 814 para 19 px; erro de cor de 36,1 para 32,7 | sem nota de arte |
| 13/11 | mecha 64×64, horys × ai-artist | ai-artist melhor; nenhum chega a 80 | referência detalhada (o tipo que deu 49); agente do horys pulou o fluxo |
| — | LoRA (`treino`) | nunca rodou | `_aprovados` vazio |

---

## 4. Pontos de falha e o que tentar

### F1. O agente inventando forma no tamanho final

- **Evidência:**
  - O mecha do horys saiu com antebraço e pernas soltos e cabeça de "orelha de coelho".
  - A grade à mão sobre base parou em 79 ("cada rodada só tapou buraco").
  - O modelo em `bpy` deu 49 e o Blender, 62.
  - Na galeria do próprio ai-artist, personagens ficam em 0–4/10.
- **Causa:** o LLM conta mal em linhas longas e não tem noção de volume. A pesquisa citada pelo ai-artist mostra o reconhecimento de arte ASCII caindo de ~25% para ~3% conforme o tamanho cresce.
- **O que tentar:**
  - Proibir "desenhar do zero" acima de 16 px.
  - A forma vem sempre de um master (Codex), de um corpo-base ou de um proxy 3D. O agente só copia, encaixa e limpa.
- **Effort:** subir o effort **não resolve** isso. Opus, com o crítico, fez média de 3,5/10 no ai-artist. Gaste effort na limpeza e na revisão, não em inventar.

### F2. Referência detalhada reduzida

- **Evidência:** 49 no gorila, 62 na lenhadora, e o miolo manchado do mecha.
- **Causa:**
  - Detalhe menor que a célula some.
  - O bloco do gpt-image varia: você mediu 19–24 px; o ASF mediu 15–30 px.
  - Amostrar o centro do bloco não serve.
- **O que tentar:**
  1. Pedir pixel art já no tamanho final, simples, com paleta fixa e fundo chapado; foi o prompt que deu 70. Ou usar a rota *hibit*: arte chapada sem contorno, 3 tons por material, e depois o voto da maioria.
  2. Ler a grade da própria imagem: `converter --nativo` do horys; o `pixel_look master` do ASF é a referência de algoritmo, porque lida com blocos irregulares e com a proporção.
  3. Gerar 3 tentativas e escolher uma. Tentativa ruim se descarta, não se conserta à mão.

### F3. Fonte de movimento

- **Evidência:**
  - Gerador de imagem quadro a quadro: a escala e a cor mudam, o movimento fica "tímido" (61) e 72–79% dos pixels mudam por quadro.
  - Recorte 2D: ~55, com as juntas abrindo.
  - 3D e SpriteKiln: consistentes, mas sem ofício (46–62).
  - Andar por deslocamento de partes: 81, mas só de frente.
- **Causa:** nenhuma fonte dá identidade e movimento ao mesmo tempo.
- **O que tentar:** **separar as duas coisas.** A identidade são os pixels do master; o movimento é a pose do proxy. Para cada quadro:
  1. Renderizar o proxy no tamanho final, com uma cor por parte. Isso é o mapa de partes.
  2. Colar os pixels do master parte por parte (`horys_colagem`, que já reduziu a deriva da cabeça de 814 para 19 px).
  3. Limpar só as juntas e as bordas.
- **Alternativas:**
  - Vídeo (ASF), se você liberar a rota.
  - Poses-chave por edição ("THE ONLY CHANGE"), lidas na grade do master.

### F4. Direções inconsistentes

- **Evidência:**
  - Vistas geradas uma por imagem mudam de altura e de tamanho de pixel; o ASF documenta isso.
  - A virada do pirata, numa imagem só, ficou coerente.
- **O que tentar:**
  - Todas as vistas na mesma imagem (frente, lado, costas; oeste espelhado), lidas com o mesmo tamanho de célula.
  - Medir altura e linha do pé: horys D01–D05 ou o `lineup` do ASF.

### F5. Ruído e clusters (render 3D e redução)

- **Evidência:**
  - SpriteKiln com "sombreado picotado".
  - O mecha do ai-artist manchado.
  - No ASF, o acabamento levou a raposa de 732 para 75 pixels soltos por quadro.
- **O que tentar:**
  - No render: toon de 2–3 faixas e materiais chapados.
  - Na redução: paleta travada, moda por bloco e histerese temporal (para não piscar entre quadros), e depois remover o pixel solto.
  - Só então o agente limpa, com leitura de volta.

### F6. Rosto e detalhe pequeno

- **Evidência:**
  - No vídeo do ASF o rosto "ferve".
  - Na lenhadora, "cada detalhe vira 1–2 px e some".
  - A Eldiran usa rosto liso.
- **O que tentar:**
  - Rosto liso, ou olhos de 1–2 px carimbados iguais em todos os quadros.
  - Travar a cabeça na animação: a cabeça inteira vem do master por colagem (o ASF faz o mesmo com `--head-rows`).

### F7. Um processo que não dá para seguir

- **Evidência:**
  - Cerca de 170 KB de leitura obrigatória.
  - Três skills, a KB e o motor discordando entre si; o Tiny Swords ainda aparece em três lugares.
  - O portão ao vivo roda o motor antigo e 4 testes de equivalência falham.
  - O daemon não foi reiniciado, e a ponte com o Aseprite cai.
  - No mecha, o agente pulou o fluxo.
- **O que tentar,** quando for mexer em código (seção 11):
  - Uma skill só, com checklist de no máximo 2 páginas.
  - Portão e revisor no mesmo motor da skill.
  - Ferramentas que recusam o passo seguinte sem o arquivo do passo anterior. O processo vira trava de ferramenta, não texto.
  - Um teste rápido ao vivo no começo de cada sessão.

### F8. Uma régua sem exemplos e um alvo que muda

- **Evidência:**
  - `_aprovados` está vazio e `KB/estilo/aprovados.md` tem zero sprites.
  - O estilo mudou 5 vezes em 9 dias: Tiny → FlickBorn → cozy → Eldiran → "o Artur é a régua".
  - Os tamanhos foram de 16 a 198 px.
- **O que tentar:**
  - Congelar o estilo por 2 semanas.
  - Você aprova de 3 a 5 sprites; candidatos: o ranger, o aldeão chibi, o gorila cozy e o pirata.
  - Cada aprovação ou reprovação vai registrada com as suas palavras, e o revisor lê esses registros.
  - O master de cada personagem é aprovado **antes** de animar.

### F9. Um revisor ruidoso

- **Evidência:**
  - Falso positivo no médico.
  - As notas não se comparam entre chamadas.
  - No ai-artist, a mesma tarefa deu 7 e 3, e o mago cumpriu 15/15 critérios com 3/10 de ofício.
- **O que tentar:**
  - Trocar a nota absoluta por **A/B cego**: uma correção só fica se ganhar.
  - Medidas objetivas no portão: paleta, pixel solto, linha do pé, altura e % de mudança por quadro calibrado (andar com 15–40% de mudança, não 72–79%).
  - O seu sim/não decide, e o % de retoque fica registrado.

### F10. Escopo inicial grande demais

- **Evidência:** o primeiro alvo de animação foi o boss de 198 px; o melhor andar dele deu 62.
- **O que tentar:**
  1. Humanoide de 32 px (frente, lado, costas), com idle de 2 quadros e andar de 4.
  2. Depois um monstro de 48 px.
  3. O boss por último.

### F11. Difusão local sem as peças certas

- **Evidência:**
  - Roda em ~1 min por imagem, mas `loras` está vazio.
  - O `kilncn` copiou o render low-poly, e o `kilnmix` soltou a caveira do corpo.
- **O que tentar,** se for testar:
  - LoRA de pixel art, ControlNet do proxy, IP-Adapter do master e leitura na grade do master. É pesquisa (P4).
  - Treinar um LoRA seu só depois de ter 30 a 50 sprites aprovados.

### F12. Ferramentas demais

- **Evidência:**
  - 3 MCPs de Aseprite: `aseprite`, `ai-artist` e `horys`.
  - Ainda: 2 Noct, SpriteKiln, ComfyUI, Blender, ASF e sprite-forge.
  - A skill de animação manda usar outro MCP.
- **O que tentar:** escolher uma peça de cada:
  - um MCP de Aseprite, para a mesa de retoque;
  - um gerador de master (o Codex);
  - uma fonte de pose (SpriteKiln, ou Blender + KayKit);
  - um leitor de grade.

  O resto vai para o arquivo.

---

## 5. Limite da arte: o envelope que torna 80% possível

- **Humanoides:** chibi de 32 px de altura com contorno, num quadro de 48×48. A cabeça tem uns 40–45% da altura. Rosto liso ou olhos de 1–2 px.
- **Monstros:** 48 px (até 64), com 3 a 5 massas grandes. Nada de pedrinha, runa ou musgo de um pixel; o gorila provou que isso some.
- **Boss:** 96 px, e só depois que 32 e 48 passarem.
- **Paleta:**
  - no máximo 20 cores por personagem;
  - rampas de 2–3 tons por material;
  - contorno escuro de 1 px (o selout é opcional);
  - a mesma luz em tudo.
- **Câmera:** top-down 3/4, fixa para o jogo inteiro. O render 3D e o prompt do Codex usam o mesmo ângulo.
- **Direções:** S, N e L; o oeste é o leste espelhado (aceito, como na Eldiran). 8 direções só para quem precisa.
- **Animações:**

  | Animação | Quadros |
  |---|---|
  | idle | 2–4 |
  | andar | 4 (no máximo 6) |
  | ataque (antecipação, golpe, recuperação) | 3–5 |
  | dano | 2 |
  | morte | 3–4 |

  Cada quadro tem a sua duração, entre 100 e 160 ms.
- **Detalhe mínimo:** 2×2 px. Nada pode existir em 1 px num quadro e sumir no seguinte.
- **Efeitos:** fora do corpo, pelo pixelfx.

---

## 6. Caminhos (os projetos)

### P1: master + pose + colagem + mesa de retoque (recomendado para monstros)

Para humanoides de 32 px e monstros de 48 px, em 4 direções.

**Você vai precisar de:**
1. **Uma ficha curta do personagem:** nome, função, 3 cores principais, a silhueta numa frase e o que ele NÃO pode ter.
2. **Uma imagem master gerada no Codex:**
   - pixel art já no tamanho final;
   - 4 vistas lado a lado *na mesma imagem* (frente, lado e costas), com a mesma altura e a mesma linha de chão;
   - fundo chapado de cor-chave, a paleta da ficha e poucos tons.

   Gere 3 tentativas; você escolhe uma. O exemplo que funcionou é `art-src/pirata-anchor/pirata-anchor-v01.png`.
3. **A leitura da grade da própria imagem:** sai um sprite 1x por vista, com paleta travada e contorno fechado por regra. Use `converter --nativo`, ou o algoritmo do ASF como referência.
4. **O proxy de pose:** um boneco 3D com a mesma proporção e **uma cor por parte** (cabeça, tronco, braço da frente e de trás, perna da frente e de trás, arma). Opções:
   - (a) uma spec do SpriteKiln, que já usa a câmera do jogo;
   - (b) o KayKit `Rig_Medium` no Blender 5.2 com o Pixel Kit: render no tamanho final, filtro 0, câmera ortográfica top-down 3/4, material Flat por parte e contorno desligado;
   - (c) o `hunter_chibi` do Noct 3D, que já tem idle, walk, run, shoot e hit.

   Um proxy serve para todos os humanoides; para monstros, um por tipo.
5. **Por ação e direção:** o render do proxy, quadro a quadro, no tamanho final. Isso é o mapa de partes.
6. **A colagem:** os pixels de cada parte vêm do master *daquela vista*, posicionados pelo mapa de partes (`horys_colagem` e a sequência). A cabeça vem inteira e travada.
7. **A limpeza no Aseprite pelo agente:** só juntas, bordas e pixel solto, com leitura de volta (`horys_ler_pixels`). Cada correção passa por A/B cego e fica só se ganhar.
8. **O portão** (medidas), **o revisor** e **você**.

**Quem faz o quê:**
- o Codex gera o master;
- um script lê a grade;
- o SpriteKiln ou o Blender renderiza o proxy;
- um script cola;
- o Claude, com effort alto, limpa;
- um subagente revisor, a frio, compara;
- você retoca e aprova.

**Por que pode dar 80:** a identidade é a sua aprovação (os pixels do master), o movimento é consistente (vem do 3D) e o agente só mexe nas juntas.

**Riscos:**
- **Partes escondidas.** Uma parte que some numa vista e aparece em outra, como o braço de trás. Por isso o master precisa das 4 vistas.
- **Degrau ao girar.** Girar pixel de um membro a 32 px cria degrau. Prefira poses de membro pré-desenhadas, como a mini-linguagem do sprite-forge, a girar pixels.
- **Emenda de 1 px.** Nunca desloque uma parte contra outra sem preencher o que ficou vazio.

**Expectativa (opinião):** estático 80–85; andar 75–80 depois da limpeza; ataque 70–75.

### P2: ASF completo, com vídeo (descartado em 13/11: só Codex e Claude Code)

Do ASF ficam as ideias e a rota do Codex (`image_gen`) para master, vista e pose. O vídeo sai.

**Você vai precisar de:**
- o Codex CLI logado;
- o ASF instalado (MIT, fica fora do horys);
- um sprite aprovado como master;
- **uma rota de vídeo** (Grok CLI ou API paga). Isso quebra a regra "só Claude ou Codex".

**Passos:**
1. O master.
2. As vistas, ao lado do master.
3. Um clipe de vídeo por ação.
4. `pixel_motion` relê cada quadro na grade.
5. Escolha dos desenhos, cabeça travada e passada medida.
6. Exportação em JSON do Aseprite e abertura no Aseprite para retoque.

**Expectativa:**
- estático 80+;
- andar de lado 75–80, com novas tentativas;
- o ataque tende a girar o corpo;
- andar top-down em 4 direções não é o foco deles.

**Sem vídeo:** `ask-pose` por pose-chave, só com o Codex. Dá de 4 a 6 edições por ação.

### P3: corpo-base, "Base + Pele" (boneco de papel), recomendado para humanoides

**Você vai precisar de:** um corpo-base com todas as animações em 4 direções, a 32 px. Opções:
- a linha-base da Eldiran (CC0, já deu 83 com recolor);
- um corpo seu, desenhado por você (2–3 dias);
- o proxy 3D, limpo uma vez à mão.

**Como funciona:**
- Cada personagem novo é um conjunto de camadas por cima da base: roupa, cabelo e arma.
- **O Codex veste a base.**
  1. A base vai com as 3 vistas numa imagem, ampliada sobre cor-chave, junto com "A ÚNICA MUDANÇA: vista esta figura como <ficha>".
  2. A imagem é relida na grade da base.
  3. As células que mudaram viram a camada de roupa.
- **Plano B:** o agente desenha as camadas com leitura de volta, partindo de um master do Codex.
- A animação vem da base: as camadas acompanham cada quadro por colagem.
- **Poses-chave que a base não tem** (um golpe específico): você desenha sobre uma guia, ou o Codex edita o quadro com "A ÚNICA MUDANÇA" e a imagem é relida na grade.

**Expectativa:** humanoides com 80+; é o caminho mais curto para eles. **Não serve para monstros.**

**Nota:** P3 é o P1 trocando o proxy 3D por um corpo-base já pronto em pixel. Os dois combinam.

### P4: difusão local, tipo PixelLab (descartado em 13/11: só Codex e Claude Code)

**Você vai precisar de:**
- um LoRA de pixel art para SDXL (baixar);
- um workflow com ControlNet (openpose ou depth do proxy) e IP-Adapter (o master);
- cerca de 1 min por imagem na 3060;
- leitura na grade do master.

**Expectativa:** incerta. Há risco de anatomia, como a caveira solta do `kilnmix`.

---

## 7. Receitas por tipo de asset

| Asset | Caminho | Você vai precisar de |
|---|---|---|
| Humanoide 32 px (vila, jogos novos; não mexer no Hunvix sem você pedir) | P3, "Base + Pele" | corpo-base animado (uma vez); ficha; o Codex veste a base ("A ÚNICA MUDANÇA"); ações: idle 2, andar 4, ação 3–5 |
| Monstro 48 px (gorila, lobisomem, nuvem, chama) | P1 com proxy SpriteKiln | specs já existentes em `D:\godot\games\vila_monstros\art\specs`; master do Codex simplificado (3–5 massas, mesmo ângulo do Kiln) |
| Boss 96 px ou mais | adiar | quando for: P1 com proxy 3D, colagem por parte e 2 rodadas de limpeza |
| Item ou ícone 16–32 px | Codex no tamanho + leitura de grade, **ou** o agente desenha direto | aqui inventar é aceitável, porque a forma é simples; usar os modelos do ofício |
| Tile ou terreno 16–32 px | o `tileset` do ai-artist, direto | exporta `.tres` do Godot 4, blob47 |
| Efeitos (VFX) | pixelfx | recolorir com a rampa do personagem; não gerar |
| Retrato 64–128 px | Codex + leitura de grade (ou hibit) + limpeza | sem animação, ou só piscar (o idle do sprite-forge) |

**Monstros, caso a caso:**
- Chama e nuvem (formas simples): podem sair do próprio SpriteKiln, só com limpeza.
- Gorila e lobisomem: precisam da colagem do master.

---

## 8. Plano de testes, em ordem

| # | Teste | Quem | Aceite | Custo |
|---|---|---|---|---|
| T0 | Escolher e registrar 3–5 aprovados, com as suas palavras, em `_aprovados` e em `KB/estilo/aprovados.md` | você | a régua existe | 30–60 min |
| T1 | Avaliar o pirata que já existe (8 direções × 4 quadros) no revisor e com você | revisor + você | ≥ 75: P1 vale em princípio | 15 min |
| T2 | Master de 1 humanoide original de 32 px (por exemplo o "Artur" da vila): 3 tentativas de 4 vistas numa imagem, leitura da grade, revisor + você | Codex, script, revisor | estático ≥ 80; alturas e pés iguais entre as vistas | 1 sessão |
| T3 | Andar de 4 quadros × 3 direções: P1 (proxy SpriteKiln + colagem) contra P3 (base Eldiran + roupa), em A/B cego + você | Claude, revisor, você | ≥ 80 e retoque ≤ 20% dos pixels | 1–2 sessões |
| T4 | Monstro de 48 px por P1: primeiro nuvem ou chama, depois o gorila | idem | ≥ 80 estático, ≥ 75 animado | 1–2 sessões |
| T5 | ~~Vídeo pelo ASF~~: cancelado em 13/11 (só Codex e Claude Code) | — | — | — |

**Regras dos testes:**
- No máximo 2 rodadas falhas por teste; depois, parar e relatar.
- Toda arte passa pelo revisor antes de ir para você.
- O % de retoque é sempre registrado.

**Onde gastar effort:**
- **Gerar:** Codex, no normal.
- **Ler a grade e colar:** scripts, sem LLM.
- **Limpar:** Claude (Opus) com **effort alto**, porque julga junta e borda.
- **Revisar:** subagente separado com **effort alto**, leitura a frio e A/B cego.
- **Desenhar do zero:** effort máximo **não** resolve, não gaste.

---

## 9. O que parar de fazer

- Pedir para o agente inventar forma acima de 16 px.
- Pedir referência detalhada e reduzir depois.
- Pintar por cima do render com script.
- Fazer recorte 2D a 32 px sem colagem e sem limpeza de junta.
- Gerar cada quadro de animação como imagem separada no gerador.
- Ler 170 KB obrigatórios antes de cada asset.
- Trocar o estilo ou a régua no meio do caminho.
- Começar pelo boss.
- Usar o Noct como motor: a licença não deixa redistribuir e a saída é "programmer art".
- Treinar um LoRA antes de ter 30–50 sprites aprovados.
- Rodar difusão local sem LoRA de pixel art.
- Dar nota absoluta em vez de A/B.

---

## 10. Decisões que são suas

1. **Rota de vídeo:** decidido em 13/11, **só Codex e Claude Code**. Fica sem Grok, sem API paga e sem ComfyUI. O movimento vem da base (P3) ou do proxy (P1), e as poses-chave novas vêm de edição no Codex ("A ÚNICA MUDANÇA"). Blender, SpriteKiln, Aseprite e scripts continuam, porque são ferramentas comandadas pelo Claude Code, não geradores.
2. **Corpo-base:** usar a base da Eldiran (CC0) em produção, só como esqueleto e não como régua, ou desenhar a sua?
3. **MCP do Aseprite:** qual fica como mesa de retoque, o `horys` ou o `ai-artist`? Hoje a ponte do horys cai e o ai-artist é mais maduro na parte de ferramentas.
4. **Tamanho:** confirmar humanoide de 32 px e monstro de 48 px.
5. **Estilo:** congelar por 2 semanas, e com quais 3–5 aprovados.
6. **Teste:** em qual jogo testar (sugestão: vila_monstros, sem mexer no Hunvix).

---

## 11. Arrumação do processo (para quando for mexer em código)

Nada disto foi feito; é o backlog.

1. Reiniciar o `horysd` e confirmar que `horys_oficio` aparece.
2. Pôr o portão e o revisor ao vivo no mesmo motor da skill (perfis 16/32, D01–D05, G01) e consertar os 4 testes de `test_motor_equivalencia`.
3. Juntar `horys-pixel`, `horys-pixel-liso` e `horys-pixel-liso-animacao` numa skill só:
   - tirar o Tiny Swords da KB, do `revisor_prompt.md` e de `agents/revisor.md`;
   - checklist de no máximo 2 páginas;
   - a KB vira consulta, não leitura obrigatória.
4. Fazer as ferramentas travarem o passo: por exemplo, `horys_colagem` recusa rodar sem master aprovado, e a entrega recusa sem A/B do revisor.
5. Escrever um leitor de grade "própria" no estilo do ASF (blocos irregulares + proporção) e comparar com o `converter --nativo` na mesma imagem.
6. Fazer um gerador de mapa de partes: render por parte, com uma cor por parte, no tamanho final, a partir do SpriteKiln ou do Blender. Em lote: 4 direções × as ações.
7. Portar do ai-artist:
   - `tileset` (Godot 4, blob47);
   - `cel` tween/oscillate;
   - `palette` ramp/analyze;
   - a guarda do loop de correção;
   - a sessão headless longa.
8. Teste rápido ao vivo no começo da sessão: conectar, criar, desenhar, ler, salvar.

---

## 13. Centralização: tudo neste repo (plano de código)

Pedido de 13/11: tudo centralizado no `horys-generator-pixel`, e não espalhado entre ai-artist, ASF, sprite-forge,
Noct, pixelfx e SpriteKiln. Só Codex e Claude Code. Pode virar extensão do Aseprite: o repo já gera
`dist/horys-pixel.aseprite-extension`.

**Divisão:**
- **Extensão Lua:** a ponte com o Aseprite (camadas, cels, tags, ler e escrever pixels) e os painéis.
- **Daemon Python:** a lógica (ler grade, vestir, propagar, portão, revisor).
- **Codex:** só gera imagem.

| # | Item | Origem | Estado |
|---|---|---|---|
| C1 | `pele.py`: `ler_master`, `vestir`, `propagar` + ferramentas `horys_base_ler`, `horys_vestir`, `horys_propagar_pele` | ideia do ASF (MIT) e do sprite-forge (MIT), reimplementada | **feito em 13/11** (6 testes sintéticos) |
| C2 | Mapa de partes da base (cor por parte) e checagem de forma fechada por parte | novo, usa `partes.py` | **feito em 14/11**: `mapa_partes.py` (contrato do motion-rigs, rascunho, regiões, forma fechada) + `horys_partes_mapa`; animação por tabela `horys_animar_tabela` |
| C3 | Pedido "A ÚNICA MUDANÇA" pronto, via `horys_referencia_gerar`: base ampliada sobre chave + texto + 3 tentativas | ASF `ask-pose`/`ask-view` | **feito em 14/11**: `pedido_codex.py` + `horys_pedido_codex` (master, vestir, vista, pose; 3 tentativas); leitor de grade própria (`pele.ler_grade_propria`, item 5 da §11) e `horys_pose_ler` (cabeça travada, sem halo) |
| C4 | Portão e revisor ao vivo no motor da skill (perfis 16/32, D01–D05, G01); consertar os 4 testes de `test_motor_equivalencia` | interno | **feito em 14/11**: o pacote é o motor único; scripts da skill viraram invólucros; revisor sem Tiny Swords; testes de equivalência passam |
| C5 | Uma skill só ("base-e-pele"), com checklist de 1–2 páginas; tirar o Tiny Swords da KB, de `revisor_prompt.md` e de `agents/revisor.md` | interno | **feito em 14/11**: `skills/horys-base-e-pele/SKILL.md` (5 KB); as skills antigas apontam para ela. Falta: `estilos/horys-pixel-liso.exemplo.json` ainda cita a régua Tiny |
| C6 | Travas de passo: vestir recusa base não aprovada; entrega recusa sem A/B do revisor | interno | **feito em 14/11**: `travas.py` (aprovação presa ao sha256; A/B em ab.json), `horys_aprovar_arquivo`, `horys_ab_registrar`; vestir/animar/entrega recusam |
| C7 | Portar do ai-artist: `tileset` (Godot 4, blob47), `cel` tween/oscillate/link, `palette` ramp/analyze, guarda do loop de correção, sessão headless longa | ai-artist (MIT) | **feito em 14/11**: `tileset.py` (Godot 4 .tres, blob47), `paleta_ops.py` (rampa, análise), `aiartist.py` (guarda de correção, tween/oscilar por deslocamento). Falta: cel link/opacidade real (a ponte não tem), sessão headless |
| C8 | Efeitos: embutir o pixelfx (MIT, com crédito) como gerador de VFX recolorido pela rampa do personagem | pixelfx | **feito em 14/11**: `vfx.py` chama o pixelfx por `node` (D:\pixelfx), recolore pela rampa; `horys_vfx_listar`, `horys_vfx_gerar` |
| C9 | Guia de pose: render do SpriteKiln ou do Blender no tamanho final, uma cor por parte, em lote (direções × ações) | SpriteKiln, Pixel Kit | **feito em 14/11**: `guia_kiln.py` + `horys_guia_kiln` (spec derivada com material chapado por parte, render em lote, cores do contrato) |
| C10 | Ponte: diagnosticar as quedas ("Aseprite não está conectado", "salvar em 60 s") ou trocar pelo modelo de ponte do ai-artist | ai-artist | **feito em 14/11**: espera a extensão conectar (12 s), tempo por comando (salvar 180 s), alertas de `save_file` silenciados; `horys teste-vivo`. Precisa reinstalar a extensão (a instalada é de 05/11) |
| C11 | Regras de animação na skill: congela o que não mexe, restaura em vez de adivinhar, slip factor, cabelo com 1 quadro de atraso, tabela de lições | sprite-forge | **feito em 14/11**: regras e tabela de lições na skill `horys-base-e-pele`; `animar` congela o que não mexe e só fecha emenda de junção |
| C12 | Empacotar: extensão + daemon num instalador só; reiniciar o horysd depois de cada mudança | interno | **parcial em 14/11**: `horys reiniciar`; `instalar --tudo` reempacota a extensão antes; a skill nova entra no instalador. Falta um instalador único (.exe/.cmd) |

**Ordem:** C2 e C3 (para vestir o primeiro personagem), C4 a C6 (processo), C9 e C11 (animação), C7, C8, C10 e
C12 (consolidação).

## 12. Fontes

**Locais:**
- **Downloads:** `aseprite-ai-artist-main.zip` (v0.8.3), `blender_pixel_kit_v1.3.1.zip` e os `KayKit_*_FREE.zip`.
- **Projetos no D:**
  - `D:\noct-asset-forge`, `D:\noct-asset-forge-3d-bb-v2` e `D:\horys-generator`;
  - `D:\pixelfx` e `D:\sprite-studio`;
  - `D:\comfyui` (os logs e `ComfyUI\output`) e `D:\hf-cache`.
- **Referências e jogos:**
  - `D:\godot\referencias\eldiran-32`;
  - `D:\godot\games\hunvix\assets\cozy\personagens`;
  - `D:\godot\games\vila_monstros\art\specs`.
- **Saídas de testes:** `C:\Users\artur\Documents\pixel-liso` (teste32/ranger, `_aprovados`).
- **Este repo:**
  - `comparacao/mecha` e `art-src/pirata-anchor`;
  - `saida/gorila*` e `experimentos/animacao-3d`;
  - `docs/` e `skills/`;
  - o histórico do git.

**Externas:**
- https://github.com/0x0funky/agent-sprite-forge: README, `docs/known-limitations.md` e `skills/generate2dsprite/references/pixel-looks.md`.
- https://github.com/isabellagreco1997/sprite-forge: README, `SKILL.md`, `docs/LESSONS.md` e `spriteforge/gridsnap.py`.
- https://superhivemarket.com/products/blender-pixel-kit: a página do addon do vídeo.
- https://github.com/patch-gg/pixelfx: o pixelfx.
- https://www.youtube.com/watch?v=gH9z3vi33xg: o vídeo; só o título foi lido.
- PixelLab: conhecimento público, **não verificado nesta sessão**.

## 14. O robô do Codex (14/11): o Blender é o segredo

Resultado que o Artur achou excelente: `Documents/Codex/2026-11-14/veja-o-perfeicao-md/outputs` (andar de 16
quadros em 4 direções, idle de 24, 128 px, 17 cores). Comparado ao robô do fluxo 2D (art-src/robo, revisor 74):
movimento real (joelho dobra, passada longa, bob e balanço), câmera top-down de verdade e volume igual em todas as
direções. Perde em contraste (sombreado chapado de render) e na vista de lado (chifre vira placa).

**Como o Codex fez (work/):**
1. `model.py` (775 linhas): modela o robô em bpy a partir do conceito, ~250 peças rígidas nomeadas e presas num
   empty; materiais por família (cobalto, marfim, ouro, violeta, ciano emissivo). `refine.py`/`suavizar.py`: bevel
   nas cascas, placas ajustadas.
2. `idle.py`/`walk.py`: "rig" de empties de controle (cabeça, tronco, ombro, cotovelo, coxa, canela, bota) com
   pivôs mecânicos. Andar procedural: pé de apoio em linha reta no chão (fase 0,61 de apoio), IK de 2 segmentos
   resolvido à mão, calcanhar/ponta, pé que sobe em seno, bob 2×/ciclo, giro do tronco, braço oposto, cabeça em
   contrafase. 16 quadros a 12 fps.
3. Pixel Kit: EEVEE, filtro 0, 128 px, material toon, contorno por dilatação no compositor.
4. `horys-render-setup.py`: troca as rampas toon pela paleta de 16 cores (hex), mistura luz facetada (normal·luz)
   com o Shader-to-RGB, reposiciona as luzes.
5. Câmera girada à mão para top-down 3/4; as 4 direções giram o empty do robô.
6. `horys-import.py`: encaixa cada pixel na paleta (RGB ponderado 3,5,3) e consolida pixel solto dentro da
   armadura; `horys-export.py`: folha, JSON, GIF.

**O Pixel Kit (SouthernShotty, v1.2, ~3,4 mil linhas, sem arquivo de licença):** só prepara a cena — render
(EEVEE, filtro 0, Standard), câmera frontal 90° ou iso 54,7°, materiais Flat/Flat UV/Toon com dither/Image-to-Pixel,
contorno por dilatação (padrão 2 px), prévia no viewport. Não tem: câmera top-down 3/4, rampa da paleta do jogo,
quantização, lote de direções × ações, animação, folha/JSON/Aseprite, limpeza. Tudo isso o Codex fez à mão.

**Melhorias (reimplementar no horys, não forkar: o kit não declara licença):**
- B1 câmera do jogo: top-down 3/4 com pitch fixo do projeto e escala ortográfica pela altura-alvo em px.
- B2 materiais toon por família com a rampa do estilo (hex) + luz facetada, gerados do pacote de estilo.
- B3 pós-render no Python: paleta travada (OKLab), contorno 1 px (selout opcional), pixel solto, anti-cintilação
  temporal (`sequencia`), folha + JSON + GIF + .aseprite com tags.
- B4 lote: direções (gira a âncora) × ações, num comando.
- B5 andar/idle procedural genérico (o `walk.py` parametrizado: pivôs de quadril/joelho/tornozelo, passada,
  altura do pé, bob), para qualquer bípede de peças rígidas ou armature.
- B6 passe de mapa de partes (cor chapada por parte) para colar pixels de um master quando quiser (P1).
- B7 recolor da paleta depois do render (o Artur quer ajustar as cores).

**Feito em 14/11** (`src/horys_pixel/blender/`, ferramentas `horys_blender_*`, testes `tests/test_blender.py`):
B0 paleta (passo 0, aprovação obrigatória), B1 câmera do jogo + enquadramento pela união das poses, B2 toon por
família com limiares calibrados pela área (22/56/22), B3 pós (paleta travada, ponto solto, contorno 1 px, folha,
GIF, .aseprite com tags), B4 lote ações × direções, B5 rig de empties por pivôs + andar/idle procedurais, B6 mapas de
partes, B7 recolor sem re-render. Robô: render completo em ~23 s (`art-src/robo/blender/v02`); A/B cego contra o do
Codex: **o nosso venceu 60 × 55** (venceu de lado e de costas; o do Codex venceu de frente pelo rosto claro). Recolor
com o marfim quente e o azul marinho que o revisor pediu: `v03`.

**Próximo:**
- Câmera: a 43° os chifres somem de frente (igual no Codex). O ângulo é do jogo todo; testar 30–35°.
- Vista de lado do modelo (chifre vira placa): é geometria do .blend, não do pipeline.
- Interface estilo Noct (pedido do Artur): prévia do render/quadros, riscar na imagem e mandar como prompt ao
  chat ("altera isso aqui"), como o preview do Blender.

## 15. Decisões de 14/11 e o código que fechou o plano

Decisões do Artur: base da Eldiran como esqueleto dos humanoides; robô aprovado ("confirmar o robo ai inicialmente
ta aprovado"); sem régua Tiny; validação fica para as artes novas (não reaproveitar projetos antigos).

Feito:
- **Horys Estúdio** (`horys estudio --app`, `horys_estudio_*`, `src/horys_pixel/estudio/`): pastas agrupadas, grade,
  inspetor com zoom de pixel, player de folha com onion, riscar (caneta, caixa, círculo, seta, texto) e mandar ao
  chat ou ao motor, aprovar/reprovar (vira `_aprovados` + trava), paleta com recolor, boas práticas com overlay,
  prévia/render do Blender, lista de pedidos com as respostas do agente. Servidor só stdlib, 127.0.0.1 + token.
- **Boas práticas** (`docs/boas-praticas.md`, 53 regras, 35 automáticas; `boas_praticas.py`, `horys_boas_praticas`):
  Obsidian + 62 regras do ai-artist + sprite-forge LESSONS + pixel-looks; ligadas no pós do Blender e no Estúdio;
  o revisor cita os ids BP.
- **Base Eldiran** (`art-src/base32/eldiran`, `horys_base_eldiran`, `horys_pele_animar`): idle + andar S/N/L, mapas
  de partes por quadro, aprovada. A base de costas foi derivada da frente (a folha não tem o corpo nu de costas).
- **Régua** (`aprovados.py`): aprovação com as palavras do Artur, cópia em `_aprovados`, trava por sha256. O robô
  v03 e a paleta dele são os primeiros aprovados. Tiny Swords saiu do estilo e do revisor.
- **Instalador único** `instalar.cmd` (dependências, extensão reempacotada, plugin, horysd reiniciado, atalho do
  Estúdio).

Falta (só validação, com arte nova): T2 humanoide pela base Eldiran, T4 monstro pelo Blender, calibrar os limites das
boas práticas para render 3D (o robô falha BP25/26/32/33/35 com os limites de pixel à mão), câmera 30–35°.
