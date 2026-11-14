# Pesquisa: Horys Pixel Liso a 16 e 32 px, top-down, sem depender do Tiny Swords

- **Data:** 2026-11-11. **FASE 1** (só pesquisa). Nenhum script foi alterado (hashes em `evidencias.md`).
- **Exemplo real:** `C:\Users\artur\workspace\repos\horys\horys-generator-pixel\art-src\pixel-liso\dragao_16`.
- **Legenda das fontes:**
  - **[lido]**: página aberta e lida;
  - **[busca]**: só o resumo da busca;
  - **[título]**: a página abriu, mas sem conteúdo (vídeos do YouTube).
  - O que não abriu está em `evidencias.md`.
- **Esforço:** **P** = até meio dia; **M** = cerca de 1 dia; **G** = 2 dias ou mais.

## Resumo

1. **O portão reprova o dragão pelo tamanho, não pela arte.**
   - O monge do Tiny tem 9,7 "órfãos" por quadro e passa: são 0,33% de 2.894 px.
   - O dragão tem 10,8 por quadro e reprova: são 4,9% de 220 px.
   - Contando o vizinho diagonal, como fazem o pxl e o spritebox, 70% dos órfãos do dragão somem. Eram linhas
     diagonais de 1 px, técnica normal a 16 px.
2. **A mancha média (M05) também mede área.** O dragão tem 4,7 px. O Tiny tem de 48 a 97 px, numa área de 11 a 19
   vezes maior.
3. **Nenhuma ferramenta pública normaliza órfão por tamanho.** As boas (pxl, spritebox, pixel-workbench) trocam a
   porcentagem por **regras de pixel**:
   - pixel isolado também na diagonal;
   - de baixo contraste com os vizinhos (ruído);
   - com exceções declaradas (olho, brilho, par simétrico).
   O artigo de Kuo et al. (2016) mede o jaggy como razão por trecho de linha, o que não depende do tamanho.
4. **Recomendação: perfis por tamanho (16, 32 e 64+).**
   - O perfil 64+ fica idêntico ao de hoje (46/46 e 19/19).
   - Os perfis 16 e 32 ganham métricas de pixel e uma régua do mesmo tamanho (Ninja Adventure, CC0, no 16).
   - Cada perfil tem a sua calibração, com o mesmo `calibrar.py`.
5. **Vista.** O `.grade` só tem uma vista, e o dragão saiu de perfil.
   - Solução: desenhar por **direção** (s, n, e e diagonais; o w espelha).
   - Ordem de Slynyrd: frente, costas, lado, diagonais.
   - Checagens entre direções e uma **guia** do SpriteKiln, medida por IoU de silhueta. O SpriteKiln já está
     instalado (MIT) e usa a câmera de 38° do jogo.
6. **Contorno e paleta: o perfil decide.** A 16 px, contorno de 1 px escuro ou selout, 2 a 3 tons por material e
   passos de valor maiores.
7. **Texto frágil.** Primeiro, ferramentas de edição segura (`put`, `diff`, `anim`). Depois, peças reutilizáveis
   com âncora (carimbos), como o pxart e o MCP do Aseprite já fazem.

## 0. O que medi no exemplo (`dragao_16`)

| Folha | Área opaca por quadro | Órfãos (vizinhança 4) por quadro | Órfãos (vizinhança 8) por quadro | Vizinhança 8 e baixo contraste (ΔL < 0,10) | Mancha média (M05) | Portão hoje |
|---|---|---|---|---|---|---|
| Tiny, peão idle | 2.469 px | 1,5 (0,06%) | 0,2 | 0,2 | 90,3 | passa |
| Tiny, monge idle | 2.894 px | 9,7 (0,33%) | 2,2 | 1,2 | 48,6 | passa |
| Tiny, guerreiro idle | 4.117 px | 4,2 (0,10%) | 0,1 | 0,0 | 96,5 | passa |
| dragão v02 idle | 220 px | 10,8 (4,90%) | 3,2 | 1,8 | 4,7 | reprova M04 e M05 |
| dragão v03 voo | 220 px | 10,5 (4,76%) | 3,2 | 1,8 | 4,8 | reprova M04 e M05 |
| dragão híbrido v05 idle | 268 px | 5,8 (2,15%) | 3,0 | 2,2 | 10,0 | reprova M04 e M05 |

Como medi:
- A coluna de vizinhança 4 e a mancha vêm do `medidas.json` do `medir.py` atual.
- As outras colunas vêm de um script de teste no scratchpad (`exp/orfaos.py`). Ele tira o contorno e o brilho da
  conta, como o `medir.py`.

O que mais o exemplo mostra:
- O `_regua.png` põe o dragão de 17 px ao lado do peão de 64 px: a comparação não informa nada. O `_regua_anim.png`
  compara com a ovelha, num quadro de 128 px.
- No `comparacao.png`, o Liso desenhou o dragão **de perfil**: asa em leque plano e corpo em tubo. O SpriteKiln mostra
  o dorso e a asa vistos de cima. A ficha pedia "3/4 de cima".
- O híbrido (`hibrido_compor.py` e `hibrido_dirs.py`) usou a base do SpriteKiln com cabeça e asas desenhadas à mão,
  ancoradas nos sockets. Deu frente e costas coerentes (`hibrido/v04/direcoes_7x.png`).

## 1. Portão preso ao Tiny

### Achados

**No `medir.py`:**
- As metas são fixas e foram calibradas em figuras de 64 a 84 px:
  - `ORFAOS_MEDIA, ORFAOS_MAX = 0.006, 0.010`;
  - `CLUSTER_MIN` de 40 a 45 (28 a 30 com contorno fino);
  - `RETA_MIN = 8`;
  - `redesenho(raio=6)`;
  - faixas de quique em px.
- **Órfão em porcentagem cresce com 1/área.** Com o mesmo número de pixels únicos (olho, brilho, botão), uma figura
  4× menor na altura tem cerca de 16× a porcentagem. Em 220 px, o limite de 0,6% vale 1,3 px por quadro: um olho e
  um brilho já reprovam.
- **O `medir.py` usa vizinhança 4.** A 16 px, a linha diagonal de 1 px é técnica normal. Com vizinhança 8, os
  órfãos do dragão caem de 10,8 para 3,2 por quadro.
- **A mancha média é área dividida pelo número de manchas.** Com o mesmo desenho, ela cai com o quadrado da escala:
  48 × (17/64)² ≈ 3,4 px.
- **`RETA_MIN = 8` é metade de um sprite de 16 px.** O M17 não enxerga primitivas a 16 px (o dragão dá 0,04).
- **O `redesenho` testa deslocamentos de até 6 px.** Isso é 40% da largura do dragão.

**Ferramentas:**
- **pxl** (MIT) [lido]. https://github.com/uilianks/pxl
  - `orphan`: pixel opaco sem vizinho da mesma cor nos 8 vizinhos, com os 4 vizinhos opacos e
    |luma − média dos 8 vizinhos| < 48/255.
  - Ou seja, conta o ruído de baixo contraste. Olho e brilho contrastam e não contam.
  - Os limiares são fixos no código. O limite de 24 cores só vale até 64×64. Só o 1º quadro é checado.
- **spritebox** (MIT) [lido; desenho descrito nas issues]. https://github.com/jmsansan/spritebox/issues/22 ·
  https://github.com/jmsansan/spritebox/issues/23 · https://github.com/jmsansan/spritebox/issues/21
  - `orphan_pixel` usa `orphan_contrast` = 32/255 de luma para não marcar olho e brilho. O pixel totalmente
    isolado sempre conta. Textura fica isenta.
  - Sprite menor que 3×3 é isento. O `pillow_shading` só roda a partir de 8×8.
  - `too_many_colors`: mais de 8 cores abaixo de 32×32, ou mais de 16 em qualquer tamanho.
  - Silenciamento por definição: `lint=allow(CÓDIGO)`, com comentário.
- **pixel-workbench** (MIT) [lido]. https://github.com/cobjams/pixel-workbench
  - `RemoveIsolatedPixelsRule` mantém os clusters de 1 px do interior, os **pares simétricos** (olhos) e os motivos
    repetidos de 3 ou mais pixels.
  - `protect_coords` protege coordenadas escolhidas.
- **codeyoma/aseprite**, issue #29 [lido]. https://github.com/codeyoma/aseprite/issues/29
  - Portão com erro e aviso. Órfão é só aviso. Nenhum limiar depende do tamanho.
  - Licença: EULA do Aseprite. Só a ideia serve.
- **Adopt Pixels** [busca]: o limiar é o número de vizinhos da mesma cor para manter o pixel (contagem, não
  porcentagem). https://astropulse.itch.io/adopt-pixels

**Pesquisa acadêmica:**
- Kuo, Yang e Chu (2016), *Feature-Aware Pixel Art Animation*, Computer Graphics Forum 35(7) [lido, PDF].
  https://doi.org/10.1111/cgf.13038 · PDF: https://purehost.bath.ac.uk/ws/files/148567276/paper1228_CRC_nocopyright.pdf
  - **jaggy**: trincas de trechos (spans) com inclinação não monótona, divididas pelo total de trechos da linha;
  - **spiky**: extremo local implausível, com a largura comparada num raio de 2 px;
  - **coerência temporal**: custo mínimo de edição dos trechos (somar, apagar, trocar, fundir, dividir), dividido
    pelo custo de apagar e redesenhar tudo.
  - As três são razões, por isso não dependem do tamanho.
- Kopf e Lischinski (2011), *Depixelizing Pixel Art* [busca]. A heurística "ilhas" evita deixar um pixel único
  isolado, porque em pixel art um pixel é um traço do desenho.
  https://www.cs.jhu.edu/~misha/ReadingSeminar/Papers/Kopf11.pdf

**Artistas e guias:**
- Slynyrd, Pixelblog 55 [lido]: "At such a small size, one pixel can make a huge difference."
- SpriteGen [lido; blog de produto]: "Avoid stray single pixels", mas o olho de 1 px vale.
- Neta [lido; blog de produto]: "one eye, one buckle" como acento.

### Caminhos

| Caminho | Como | Prós | Contras | Esforço | Licença |
|---|---|---|---|---|---|
| **1A. Escalar pelo tamanho** | Multiplicar as metas por (h/64)² nas medidas de área e por h/64 nas de comprimento: órfãos % × (64/h)²; mancha × (h/64)²; `RETA_MIN` e raio do redesenho × h/64. | Rápido. O perfil 64 fica com fator 1 e a calibração não muda. | Fica cego para ruído pequeno: a 17 px o limite vira 8,5% (18 px por quadro) e a mutação de órfãos passa. É extrapolação, sem régua. | P | — |
| **1B. Métrica de pixel** (ideia de pxl, spritebox e pixel-workbench) | Órfão = isolado na vizinhança 8 e de baixo contraste (ΔL OKLab < 0,10), em contagem absoluta por quadro. Exceções: brilho, contorno fino, `acentos` declarados na grade e par simétrico. | Mede o que o artista chama de sujeira. Deixa o olho e o brilho. Quase não depende do tamanho. | Regra nova, que precisa de calibração. Com o contraste mal escolhido, passa ruído claro. | M | Ideias de projetos MIT, reimplementadas sem copiar código. |
| **1C. Calibrar cada perfil com um corpus do tamanho** | O mesmo método do Tiny: os bons de 16 px (Ninja Adventure) e de 32 px passam; as 19 mutações, refeitas no tamanho, reprovam. | É a mesma prova de hoje (46/46 e 19/19), em cada tamanho. Os números ficam com evidência. | Exige baixar e fatiar o corpus. O estilo do corpus não é o Liso (a régua mede qualidade, não estilo). | M | Ninja Adventure: CC0. Pipoya: licença própria (uso local, sem redistribuir). |

**Escolha:** 1B + 1C. O 1A serve só como valor inicial, antes da calibração. O perfil 64 não muda.

## 2. Régua presa ao Tiny

### Achados

**No projeto:**
- O `config.json` tem uma régua só: `regua` e `regua_por_categoria`, com quadros de 192.
- O `grade.py` sempre põe o `pawn_idle.png` no `_regua` e uma animação do Tiny no `_regua_anim`. A 16 px, a prévia
  compara um dragão de 17 px com um peão de 64 px (`dragao_16/v02/dragao_16_idle_regua.png`).
- O `KB/estilo/reguas.md` registra uma régua por projeto, não por tamanho.
- No estilo cozy do SpriteKiln, um humano tem 24 px num quadro de 32 (`spritekiln.toml`).

**Corpus livres de top-down pequeno:**
- **Ninja Adventure** (pixel-boy) [lido]. https://pixel-boy.itch.io/ninja-adventure-asset-pack
  - Licença: "Creative Commons Zero v1.0 Universal".
  - "50+ Characters with animations and faceset", marcado como 16×16, top-down.
  - Falta conferir, ao baixar, o quadro e as direções. Um comentário de usuário fala em 4 direções.
- **PIPOYA FREE RPG Character Sprites 32x32** [lido]. https://pipoya.itch.io/pipoya-free-rpg-character-sprites-32x32
  - 64 personagens, com "4-way walking animation".
  - Licença própria: "Not redistribute or resell this assets". Serve para medir no PC, fora do repositório.
- **Universal LPC** [lido]. https://github.com/LiberatedPixelCup/Universal-LPC-Spritesheet-Character-Generator
  - Quadro padrão de 64×64. Fica fora da faixa de 16 e 32 px.
  - A arte tem licenças mistas por peça (CC0, CC-BY-SA, CC-BY, OGA-BY, GPL). O código é GPL-3.0.

**Uma ideia de prévia:** o `pixel look` do ritmo [lido; PR fechado sem mesclar].
https://github.com/typeonce-dev/ritmo/pull/177
- Em cima, cada peça **no tamanho de exibição**, sobre o fundo do jogo, ao lado de um boneco de escala, numa linha de
  chão só.
- Embaixo, cada quadro ampliado, com os avisos circulados.

### Caminhos

| Caminho | Como | Prós | Contras | Esforço | Licença |
|---|---|---|---|---|---|
| **2A. Régua por perfil** | O `config.json` ganha `perfis` (`16`, `32`, `64`), cada um com `regua`, `regua_por_categoria`, quadro e cores de contorno. O `_regua` usa a régua do perfil e amplia os dois sprites para o mesmo tamanho na tela. | A comparação fica justa. O perfil 64 continua com o Tiny. | É preciso escolher e baixar as réguas. | M | Ninja Adventure: CC0. Pipoya: só local. |
| **2B. "Só boas práticas"** | Sem régua, o `_regua` mostra o sprite em 1×, 2× e 4× sobre grama, masmorra e UI, ao lado de um boneco de escala e da versão anterior. | Não depende de pacote nenhum. | Perde a pergunta "aguenta ao lado de quê?". | P | — |
| **2C. Régua = assets aprovados do próprio jogo** | Por exemplo, os personagens cozy do SpriteKiln aprovados pelo Artur viram a régua do Hunvix de 24 a 32 px. | Mede contra o visual real do jogo. | É circular: a régua sai do próprio pipeline. Exige a aprovação do Artur. | P | Arte própria. |

**Escolha:** 2A, com o Ninja Adventure no 16 px. O 2B vale como padrão quando o tamanho não tiver régua. O 2C é
decisão do Artur.

## 3. Uma vista só (o desenho cai em perfil 2D)

### Achados

**No projeto:**
- O `.grade` não tem direção: um arquivo é um estado numa vista.
- A ficha do dragão pedia "3/4 de cima, olhando para a direita". O desenho saiu de perfil (`comparacao.png`).
- Nenhuma medida do portão olha a vista.
- O SpriteKiln do projeto usa pitch de 38° (`spritekiln.toml`).

**Slynyrd:**
- Pixelblog 22 [lido]. https://www.slynyrd.com/blog/2019/10/21/pixelblog-22-top-down-character-sprites
  - Um personagem top-down precisa de "at least 4 directions".
  - Ele desenha cima, baixo e lado; o lado espelha.
  - Em sprite pequeno, a cabeça ocupa "a third to half of the total sprite".
- Pixelblog 55 [lido]. https://www.slynyrd.com/blog/2025/3/24/pixelblog-55-top-down-character-animation
  - Figura de 26×32 (1×2 tiles de 16).
  - 5 orientações desenhadas: frente, costas, lado e 2 diagonais. O lado e as diagonais espelham.
  - Ordem: "I started with the front facing figure, then made the up, and side facing versions. Finally, I saved
    those pesky angles for last".
  - Ele esboça todas as vistas na mesma cena, compara as medidas, alinha na mesma posição e roda como um giro.
  - "The trick is keeping the thickness and length of appendages consistent".
  - Corrida de 6 quadros, com a cabeça descendo 1 px, 1 px e subindo 2 px.
- Pixelblog 36 [lido]: um inimigo simples (slime) em top-down só precisa da vista de frente.
  https://www.slynyrd.com/blog/2022/1/25/pixelblog-36-8-bit-adventure

**Outros:**
- Sandro Maglione [lido; artigo arquivado, de 2023].
  https://www.sandromaglione.com/articles/pixel-art-top-down-game-sprite-design-and-animation
  - Em top-down, "we see more the top of the head".
  - Os olhos ficam mais para baixo na cabeça.
  - Luz de cima: topo mais claro; embaixo da cabeça e nos pés, mais escuro.
  - 3 animações (andar para baixo, para cima e de lado), com o lado espelhado e no mínimo 3 quadros.
- sprite-gen, PR #102 [lido; fechado sem mesclar]. https://github.com/aldegad/sprite-gen/pull/102
  - Elevação de câmera de 35°, escolhida no olho. Com 16°, "read as an eye-level side-scroller". Com 50°, fica
    íngreme demais.
  - As direções espelhadas são registradas com a origem e o sha256.
  - Espelhar é recusado em personagem com lado dominante.
  - O pé é achado pelo alfa (faixa de 16% da altura).
  - Um verificador automático de deriva de direção não foi publicado: o melhor chegou a AUC 0,79 e marcava cerca de
    30% das tomadas boas.
- Pixel Joint [busca]: em top-down, as partes de cima sobrepõem as de baixo e tudo é encurtado.
  http://pixeljoint.com/forum/forum_posts.asp?TID=26380
- Guias de turnaround [busca; não são de pixel art]:
  - linhas horizontais no topo da cabeça, nos olhos, na cintura e nos pés;
  - a mesma linha de chão em todas as vistas;
  - conferir se os olhos ficam na mesma linha.
  - https://www.mimiccartoon.com/post/character-turnaround-sheet-3d-cartoon-model-guide ·
    https://carliannecreates.com/blogs/news/the-secret-to-consistent-turnarounds-step-by-step-guide
- Vídeos do YouTube: só os títulos foram lidos (ver a lista nas fontes e `evidencias.md`).

### Caminhos

| Caminho | Como | Prós | Contras | Esforço | Licença |
|---|---|---|---|---|---|
| **3A. Direções na grade e checagens entre elas** | Blocos `--- s q0`, `--- n q0`, `--- e q0`, `--- se q0`. Diretiva `espelho w=e`. Portão novo, D01 a D05: topo da cabeça e linha do pé iguais (±1 px); linha do olho igual entre s, se e e; pixels por material ±25%; mesma paleta. Prévias `_direcoes.png` (giro com linhas-guia) e `_giro.gif`. | Leva a prática de Slynyrd para o portão. Pega membro que muda de tamanho entre as vistas. | Parser e prévias novos. "Pixels por material" precisa de folga para vista que esconde partes. | M | — |
| **3B. Regras de projeção na `praticas.md` e no revisor** | Critérios: topo da cabeça visível e mais claro; olhos na metade de baixo da cabeça; dorso visível em quadrúpede e dragão; asa vista de cima; sombra sob o centro do corpo. | Barato. O revisor já lê a prancha. | Depende do olho do revisor. | P | — |
| **3C. Vista medida contra a guia 3D** | Cada direção é comparada com a silhueta da guia (problema 4) por IoU, alinhada no pivô. | Pega "desenhou de perfil" sem opinião. | Exige uma guia por asset. | M | SpriteKiln: MIT. |

**Escolha:** 3A + 3B agora. O 3C entra junto com a guia.

## 4. Camada-guia de pose

### Achados

**Como a indústria faz:**
- Dead Cells, por Thomas Vasseur (2018) [lido].
  https://www.gamedeveloper.com/production/art-design-deep-dive-using-a-3d-pipeline-for-2d-animation-in-i-dead-cells-i-
  - O modelo 3D é renderizado "in a very small size and without antialiasing", com PNG, normal map e toon shader.
  - O personagem tem cerca de 50 px.
  - "we still haven't found any solution for flickering pixels".
  - Não houve limpeza à mão, para ser rápido.
- Projeto de aluno (2024) [lido]. https://faeparkinsongamesyr2.wordpress.com/2024/06/01/fmp-3d-to-pixel-art-pipeline/
  - Rampa de 2 cores em "Constant".
  - O contorno foi descartado.
  - Não funcionou em objeto parado.
- codeyoma/aseprite, issue #44 [lido; EULA, só ideia]. https://github.com/codeyoma/aseprite/issues/44
  - Câmera ortográfica numa elevação fixa, z-buffer no tamanho final e sem AA.
  - Faixas de toon, passe de contorno e paleta encaixada.
  - 1, 4, 8 ou 16 direções. Aceite em 32×32 com 8 direções.

**Ferramentas abertas:**
- **SpriteKiln** [lido]. https://github.com/LucasJRamos/spritekiln
  - Licença: MIT. A arte de vitrine tem todos os direitos reservados; os exemplos são CC0.
  - 8 direções top-down 3/4 (ou 4, 1 ou lateral), com espelho.
  - Sockets por quadro, pivô no chão e um QA que acusa partes que somem.
  - Já está no projeto, com pitch de 38° e a escala comum do jogo.
- **atou42/3d-to-pixel-sprite** (MIT) [lido]. https://github.com/atou42/3d-to-pixel-sprite
  - Blender ortográfico, 8 direções.
  - Quantiza na paleta fixa, com alfa 0/255 e uma checagem `--check`.
  - O `compare.py` dá o IoU da silhueta, alinhado na âncora.
- **pseudo-pixel** (MIT) [lido]. https://github.com/craigrusselltiu/pseudo-pixel
  - Imagem → malha (TripoSG, exige GPU NVIDIA) → Blender → spritesheet de 64×64 em 8 direções.
- **PixelArtPipeline** (Unlicense) [lido]: exemplo em Unity do método de Dead Cells.
  https://github.com/Broxxar/PixelArtPipeline
- **Pixelorama** (MIT) [README lido; recursos pelo changelog, via busca]. https://github.com/Orama-Interactive/Pixelorama
  - Camadas 3D rasterizadas no tamanho da tela (versão 0.11.0).
  - Imagem de referência, com a opção de mostrar só a silhueta (versão 0.11.2).
  - Exportação por linha de comando.
  - Serve para o Artur desenhar. Não serve para o agente desenhar.
- **PixelOver** e **Pixel Composer** [busca]: são pagos (EULA). Ficam fora pela regra "só Claude ou Codex".

**No projeto:**
- O híbrido do dragão (base do SpriteKiln com cabeça e asas à mão, ancoradas nos sockets) deu frente e costas
  coerentes.
- Pela memória, o redesenho automático por cima do render falhou no gorila (2026-11-11). O Artur pediu guias para
  desenhar à mão.

### Caminhos

| Caminho | Como | Prós | Contras | Esforço | Licença |
|---|---|---|---|---|---|
| **4A. Guia do SpriteKiln** | Diretiva `guia kiln <spec> <anim>` na grade. O `spritekiln pose --dirs all` gera a silhueta e as partes de cada direção no tamanho final. `numerar --guia` mostra a guia sob as letras. Prévia `_guia.png`. Métrica G01 = IoU da silhueta, alinhada no pivô. Camada `guia` oculta no `.aseprite`, para o Artur. | A câmera e a escala já são as do jogo. Os sockets marcam cabeça e asa. As 8 direções saem coerentes. | Exige um spec por asset (cerca de 1 a 2 h de modelagem). O render não é pixel art: cintila, e parte fina some. | M | MIT, já instalado. |
| **4B. Guia do Blender** | Câmera ortográfica a 35–38°, um material chapado por parte (cor de ID), render no tamanho final sem AA. | Aceita qualquer malha (Meshy, TRELLIS ou feita à mão). | Configurar cena e câmera. É mais lento. | M–G | Blender: GPL (só como ferramenta). |
| **4C. Guia 2D, sem 3D** | 1º passo: bonecos de blocos de 1 a 2 cores por direção (o "dummy" de Slynyrd), com linhas-guia automáticas no topo da cabeça, no olho e no pé. | Nenhuma dependência. | A perspectiva continua no olho de quem desenha. | P | — |

**Escolha:** 4A, com o 4C quando não houver spec. A guia é referência: nunca vira asset e nunca é "pintada por
script" (memória `pintura-procedural-falhou`).

## 5. Contorno de 2 px e paleta travada

### Achados

**No projeto:**
- O `grade.py` tem três contornos: `auto` (anil de 2 px), `suave` (1 px) e `nenhum`.
- A 16 px, a ficha do dragão já precisou de exceção: o anil de 2 px "comeria 40% de um sprite de 16 px".
- O estilo cozy do SpriteKiln usa contorno escuro `#2a1f2d`, 2 a 3 tons chapados por material e nenhum dithering.

**Fontes:**
- Neta [lido; blog de produto]. https://neta.art/blog/16x16-pixel-art-rules
  - A 16×16, um contorno fechado de 1 px custa cerca de 50 células, uns 30% da massa.
  - "three colours" por material; de 12 a 16 entradas na paleta do personagem.
  - Contorno seletivo. Nada de preto puro.
- Slynyrd, Pixelblog 36 [lido]: 16×16, com "3 colors in addition to the outline per character".
- spritebox [lido]: mais de 8 cores abaixo de 32×32 vira aviso.
- Pixnote [lido]. https://pixnote.net/en/learn/outlines/
  - O selout é "The pro default".
  - O contorno é o tom mais escuro do material, não `#000`.
  - Não exagerar no AA em sprites de até 16 px.
- Sprite AI [lido; blog de produto]. https://www.sprite-ai.art/guides/how-to-create-16x16-pixel-art
  - Personagem com 5 a 6 cores.
  - Contorno inteiro em personagem; seletivo na maioria dos sprites.
- SpriteGen [lido; blog de produto]. https://spritegen.io/guides/how-to-draw-a-pixel-art-character/
  - Membros com pelo menos 2 px.
  - Cabeça com 40 a 50% da altura a 16 px; de 1:3 a 1:4 a 32 px.
- Maglione [lido]: sombrear o próprio contorno, mais claro no topo iluminado.
- Rampas [busca]: 3 tons por rampa bastam a 16×16, e o valor importa mais que o matiz.
  https://pixnote.net/en/learn/color-palette

### Caminhos

| Caminho | Como | Prós | Contras | Esforço | Licença |
|---|---|---|---|---|---|
| **5A. O perfil decide contorno e cores** | 16 px: contorno de 1 px ou `selout`, até 8–10 cores com o contorno, 2–3 tons por material. 32 px: 1 px ou `selout`, até 12 cores. 64 px: como hoje. | Regra clara por tamanho. O M06 passa a medir pelo modo de contorno. | É preciso calibrar o M06 do `selout`. | M | — |
| **5B. Contorno colorido (selout de material)** | O anel 1 recebe o tom mais escuro do material vizinho e some no lado da luz (como `sem_borda`). O M06 mede "anel 1 escuro" (L baixo), em vez da cor exata. | É o que os guias recomendam. Pesa menos. | Recalibrar o M06 nesse modo. | M | — |
| **5C. Paleta travada por tamanho** | Uma sub-paleta da Liso para 16 e 32 px, com passos de L de pelo menos 0,12 entre tons vizinhos; ou a paleta cozy do SpriteKiln no Hunvix. | Continua travada. O contraste lê em tamanho pequeno. | A paleta é do Artur: ele escolhe. | P | Própria. |

**Escolha:** 5A + 5B. O 5C, com o Artur.

## 6. Escrever pixel em texto é frágil

### Achados

**No projeto:**
- O `grade.py` já confere a largura da linha, a letra sem cor e o pivô, e tem o `numerar` com régua.
- Mas cada quadro reescreve a grade inteira. Uma coluna errada desloca a parte, e o membro muda de tamanho entre
  quadros sem aviso nenhum.
- O híbrido do dragão já usou peças desenhadas uma vez e posicionadas nos sockets.

**Ferramentas:**
- **pxart** (MIT) [lido]. https://github.com/thethirdbearsolutions/pxart
  - Formato `.px`: paleta e grade, parente de XPM2, PuzzleScript, MakeCode e Bitsy.
  - `check` lista todos os erros com código e posição (`E_ROW_WIDTH`, `E_UNKNOWN_KEY`).
  - `put` troca só as linhas de um quadro e confere antes de gravar.
  - `dup`; `compose` (camadas, com relatório de conflito); `paste +h/+v` (espelho).
  - `anim` mostra, por quadro, algo como "shift +0,+1 then 26px (7%)". Também tem `onion`, `diff`, `stats` e
    `pivot`.
- **pixel-workbench** (MIT) [lido].
  - Grade ASCII com `strict` (confere largura e limites) e `offset_x`/`offset_y` para remendar só uma região.
  - Checkpoints, com relatório de regressão.
  - Regressão de animação: tamanho do quadro, paleta, variação do volume opaco, deslocamento do centro de massa e
    âncora (`max_anchor_shift`).
- **pxl** (MIT) [lido]: `pxl ascii` imprime o asset com réguas x e y.
- **ritmo**, PR #177 [lido; não mesclado].
  - Checagens de movimento: `flicker` (pixel solto que pisca), `area` (corpo mudando de tamanho), `skate` (pé
    plantado escorregando) e `seam` (loop que pula).
  - `accept`: um aviso proposital é aceito com motivo. Erro não se aceita.
- **MCP do Aseprite** (já instalado): `pixel_map` com `stamps` e `place` (com espelho) e `x`/`y`; o `read_pixels`
  devolve o mesmo formato.
- Kuo et al. (2016) [lido]: coerência temporal pelo custo de edição dos trechos entre os quadros.

### Caminhos

| Caminho | Como | Prós | Contras | Esforço | Licença |
|---|---|---|---|---|---|
| **6A. Edição segura, sem mudar o formato** | `grade.py put` troca as linhas de um quadro, confere a largura e mostra o diff. `grade.py diff qA qB`. `grade.py anim` mostra o deslocamento e os px mudados por quadro, como o pxart. Régua de 2 dígitos a cada 5 colunas. Portão novo: px por cor e por parte ±10% entre quadros (aviso); centro de massa e âncora do pé estáveis. | Ganho imediato. Nada a migrar. | Não impede o erro: só mostra. | P–M | Ideias do pxart e do pixel-workbench (MIT). |
| **6B. Peças com âncora (carimbos)** | `parte asa_cima` é desenhada uma vez, com âncora. O quadro lista `@asa asa_cima 12 3 h` e os remendos. Uma variante nova é um desenho novo. | O membro não muda de tamanho sem querer. Espelho e reaproveitamento entre direções. | Formato e parser novos. Tentação de animar só deslizando (o A02 continua cobrando o redesenho). | G | — |
| **6C. Desenhar no Aseprite pelo MCP** | O Aseprite vira a superfície de edição (carimbos, `read_pixels`). A `.grade` é regenerada a partir das camadas. | Visual. O Artur mexe junto. | Duas fontes da verdade. Depende de o MCP estar ligado. | M | Aseprite: EULA (ferramenta do Artur). |
| **6D. Migrar para o pxart** | Trocar a `.grade` pelo `.px`. | Ferramenta pronta. | Perde o contorno automático, as camadas e o portão atuais. | G | MIT. |

**Escolha:** 6A já. Depois, 6B para criatura e personagem. O 6C é uma opção quando o Artur estiver junto.

## 7. Como outros projetos ajustam o portão ao tamanho

- **spritebox:** isenções por tamanho (menor que 3×3; pillow só a partir de 8×8) e limite de cores por tamanho
  (8 abaixo de 32×32; 16 sempre). Silenciamento por definição, com comentário.
- **pxl:** limiares fixos. O limite de cores só vale até 64×64.
- **codeyoma/aseprite:** erro e aviso, sem nada que dependa do tamanho.
- **ritmo:** um aviso pode ser aceito com motivo; um erro não.
- **sprite-gen:** limiares relativos à altura (faixa do pé de 16%). Desistiu de checar a direção automaticamente.
- **Kuo et al.:** métricas em razão (por trecho de linha), sem dependência de escala.
- **Horys hoje:** o `calibrar.py`, em que os bons passam e os estragados reprovam (46/46 e 19/19).
- Nenhum projeto encontrado calibra por corpus. O `calibrar.py` é o método mais forte; falta repeti-lo em cada
  tamanho.

## 8. Recomendação final

Perfis por tamanho, com o perfil 64+ intocado:
1. **Perfis `16`, `32` e `64`**, em `config.json` e `comum.py`.
   - O perfil vem da linha `perfil` da grade, ou da altura da figura em personagem, npc, inimigo, boss, criatura e
     animal.
   - O cenário continua no perfil 64 até ser calibrado.
   - O `medir.py` usa `--perfil 64` por padrão. Assim, quem não passa o perfil vê o comportamento de hoje.
2. **Métricas de pixel nos perfis 16 e 32:**
   - órfão de ruído em vizinhança 8, com contraste, em contagem absoluta;
   - acentos declarados;
   - mancha, retas, raio do redesenho e px de animação escalados;
   - tudo calibrado no corpus do tamanho.
3. **Régua por perfil:** Ninja Adventure (CC0) no 16; no 32, a escolha do Artur; sem régua, "só boas práticas".
4. **Direções na grade**, na ordem frente → costas → lado → diagonais, com as checagens D01 a D05 e as prévias de giro.
5. **Guia do SpriteKiln**, com IoU por direção e a camada `guia` no `.aseprite`.
6. **Contorno por perfil** (1 px ou selout de material). A paleta, o Artur escolhe.
7. **Ferramentas de edição segura**; depois, **peças com âncora**.

## 9. Plano de mudanças no código (FASE 2)

**Regras da FASE 2:**
- fazer backup antes de editar;
- o perfil do Tiny (64+) continua passando na calibração (46/46 e 19/19);
- atualizar `SKILL.md` e `revisor_prompt.md` e rodar `python S/instalar.py`.

**Etapa 0. Backup (P)**
- Copiar `scripts/` para `scripts.bak-2026-11-XX/`.
- Copiar `SKILL.md` para `SKILL.md.bak-v4.2`.
- Copiar as notas da KB que mudam: `revisao/metricas.md`, `revisao/calibracao.md` e `estilo/reguas.md`.
- Rodar `python S/calibrar.py mutacoes` e `python S/calibrar.py metricas` antes de mudar, para ter a linha de base.

**Etapa 1. Perfis e métricas de pixel (M)**
- **`config.json`:** chave `perfis`.
  - `"64"` = os campos atuais (Tiny).
  - `"16"` e `"32"`: `regua`, `regua_por_categoria`, quadro, `contorno_regua`, `brilho_regua`.
  - As chaves de hoje continuam valendo como o perfil 64.
- **`comum.py`:** `perfil_por_altura(h)` (até 20 → 16; de 21 a 40 → 32; acima de 40 → 64), `config_perfil()` e
  `isolados8()`, com o contraste em OKLab.
- **`medir.py`:**
  - `--perfil 16|32|64` (padrão 64) e a tabela `METAS_PERFIL`.
  - **M04 nos perfis 16 e 32:** contagem por quadro de isolados em vizinhança 8 e de baixo contraste. Exceções:
    brilho, contorno fino, `--acentos` e par simétrico. O relatório mostra também o total em vizinhança 8 e a
    porcentagem antiga.
  - **M05:** meta escalada no início. A calibração decide o número final.
  - **M17:** `RETA_MIN` por perfil (64: 8; 32: 5; 16: desligado ou 4, a calibrar).
  - **A02:** raio por perfil (64: 6; 32: 3; 16: 2).
  - **A05, A06 e A07:** faixas em px por perfil.
  - **M06 e M07:** por modo de contorno (`auto`, `suave`, `selout`).
- **`grade.py`:**
  - Diretivas `perfil`, `acentos` e `contorno selout`.
  - O `portao()` passa `--perfil` e `--acentos`.
  - O aviso de altura ("humanoide 64–72") passa a seguir o perfil.

**Etapa 2. Régua e calibração do perfil 16 (M)**
- Baixar o Ninja Adventure para `D:/godot/referencias/ninja-adventure/`, fora do repositório.
- Conferir o quadro, as direções e a altura das figuras.
- **`calibrar.py`:**
  - `--perfil`; os positivos do perfil vêm do `config.json`.
  - As mutações são geradas a partir de um positivo do perfil, com intensidades escaladas: órfãos, contorno preto,
    blur, cores extras, quadro congelado, só desliza (±1 px), pé deslizando (1 a 2 px), corte na borda,
    semitransparente, dither, escala 1,5×.
  - Os relatórios saem por perfil.
- **`grade.py`:** o `_regua` e o `_regua_anim` usam a régua do perfil, ampliando os dois sprites para o mesmo
  tamanho na tela. Sem régua no perfil, a prancha "só boas práticas" (2B).

**Etapa 3. Direções (M)**
- **`grade.py`:**
  - Blocos `--- <dir> qN` e `espelho w=e`.
  - A folha sai por direção, com uma tag por direção no `.aseprite`.
  - Prévias `_direcoes.png` (linhas-guia no topo da cabeça, no olho e no pé, e linha de chão comum) e `_giro.gif`.
- **`medir.py`:** D01 a D05 entre as direções de um mesmo estado (alturas, linha do pé, linha do olho, pixels por
  material, paleta). São graves; a calibração decide quais viram aviso.

**Etapa 4. Guia (M)**
- **`grade.py`:**
  - `guia <png> [dx dy]` e `guia kiln <spec> <anim>`.
  - No modo kiln, o script chama `spritekiln pose --dirs all` e guarda as PNGs em `vNN/_guia/`.
  - `numerar --guia` mostra a guia sob as letras; prévia `_guia.png`.
  - A camada `guia` vai oculta no `.aseprite`, com 40% de opacidade.
- **`medir.py`:** G01 = IoU da silhueta com a guia, alinhada no pivô. A meta inicial é 0,70 no 16 e 0,75 no 32;
  a calibração decide. Teste: o dragão v02 (de perfil) contra a guia do SpriteKiln tem que reprovar.

**Etapa 5. Edição segura (P–M), depois peças (G)**
- **`grade.py`:** `put`, `diff` e `anim`; régua de 2 dígitos.
- **`medir.py`:** variação de px por cor entre quadros, como aviso.
- **Depois:** `parte` e `@peca` com âncora e espelho.

**Etapa 6. Revisor, SKILL e KB (P)**
- **`revisor_prompt.md`:**
  - critérios de top-down 3/4 e de coerência entre direções;
  - no L5, a régua do perfil ou "só boas práticas";
  - a 16 px, olho e brilho de 1 px são acento, não defeito.
  - Depois, rodar `python S/instalar.py`.
- **`SKILL.md`:** seção "Tamanho pequeno (16/32 px)", com perfil, ordem das direções, guia, contorno e paleta por
  perfil e as ferramentas de edição. Na Manutenção, a calibração de cada perfil.
- **KB:** `revisao/metricas.md` (tabela por perfil), `revisao/calibracao.md` (registro), `estilo/reguas.md` (régua
  por tamanho) e `decisoes.md`.

**Aceite da FASE 2:**
1. `calibrar.py mutacoes` e `metricas` no perfil 64: **46/46 e 19/19**, como hoje.
2. `calibrar.py metricas --perfil 16`: todos os positivos do Ninja Adventure passam, e todas as mutações de 16 px
   reprovam pela métrica esperada.
3. Dragão v02 reprocessado:
   - o M04 e o M05 não reprovam mais só pelo tamanho;
   - o G01 acusa a vista de perfil contra a guia;
   - o revisor entra.
4. Os backups existem, e o `instalar.py` rodou depois da mudança no prompt.

**Riscos:**
- **Só escalar deixa o portão cego para ruído a 16 px.** O limite vira 8,5%, e a mutação de órfãos passa. Por isso
  as métricas de pixel e a calibração.
- **Checar direção automaticamente é difícil.** O sprite-gen desistiu (AUC 0,79). As D01 a D05 ficam em medidas
  simples (linhas, alturas, paleta). A semântica fica com o revisor.
- **A guia 3D engana em parte fina e cintila** (Dead Cells; o QA do SpriteKiln). Ela é referência, nunca asset.

## 10. Decisões do Artur antes da FASE 2

1. **Régua de 16 px:** Ninja Adventure (CC0)?
2. **Régua de 32 px:**
   - (a) Pipoya 32×32 (licença própria, só local);
   - (b) personagens cozy do SpriteKiln aprovados;
   - (c) só boas práticas.
3. **Contorno padrão a 16 px:** 1 px escuro, selout ou colorido (tom escuro do material).
4. **Paleta a 16 e 32 px:** sub-paleta da Liso com passos de valor maiores, ou a cozy do SpriteKiln.
5. **Guia:** SpriteKiln (já instalado) ou Blender.

## 11. Fontes

**Artistas e tutoriais**
- [lido] Slynyrd, Pixelblog 22: Top Down Character Sprites (2019):
  https://www.slynyrd.com/blog/2019/10/21/pixelblog-22-top-down-character-sprites
- [lido] Slynyrd, Pixelblog 55: Top Down Character Animation (2025):
  https://www.slynyrd.com/blog/2025/3/24/pixelblog-55-top-down-character-animation
- [lido] Slynyrd, Pixelblog 21: Top Down Objects: https://www.slynyrd.com/blog/2019/9/18/pixelblog-21-top-down-objects
- [lido] Slynyrd, Pixelblog 36: 8-bit Adventure: https://www.slynyrd.com/blog/2022/1/25/pixelblog-36-8-bit-adventure
- [lido] Sandro Maglione, Top-down game Pixel art (2023, arquivado):
  https://www.sandromaglione.com/articles/pixel-art-top-down-game-sprite-design-and-animation
- [lido] Pixnote, Outlines & Anti-Aliasing: https://pixnote.net/en/learn/outlines/
- [lido; blog de produto] Neta, The Rules of 16x16 Pixel Art: https://neta.art/blog/16x16-pixel-art-rules
- [lido; blog de produto] SpriteGen, How to Draw a Pixel Art Character:
  https://spritegen.io/guides/how-to-draw-a-pixel-art-character/
- [lido; blog de produto] Sprite AI, 16x16 guide: https://www.sprite-ai.art/guides/how-to-create-16x16-pixel-art
- [busca] Pixel Joint, corrida em 4 direções: http://pixeljoint.com/forum/forum_posts.asp?TID=26380
- [busca] Pixnote, Color Guide: https://pixnote.net/en/learn/color-palette
- [busca] Turnaround (não é de pixel art):
  https://www.mimiccartoon.com/post/character-turnaround-sheet-3d-cartoon-model-guide ·
  https://carliannecreates.com/blogs/news/the-secret-to-consistent-turnarounds-step-by-step-guide
- [falhou] MiniBoss e saint11 (Pedro Medeiros, que é o próprio saint11): https://blog.studiominiboss.com/pixelart ·
  https://saint11.org/blog/pixel-art-tutorials/
- [falhou] https://the-pixel.art/articles/pixel-art-character-design/ ·
  https://www.pixel-editor.com/articles/pixel-art-outlines

**YouTube** (só o título; o conteúdo não abriu)
- [título] Pixel Art Class - Top Down Style Analysis & Tutorial (AdamCYounis, segundo a busca):
  https://www.youtube.com/watch?v=2JCG4fCmeHk
- [título] Pixel Art Class - 8 Directional Walk [Part 1]: https://www.youtube.com/watch?v=aios4kDJZsc
- [título] Top-Down Pixel Art Practice! (Brandon James Greer, segundo a busca):
  https://www.youtube.com/watch?v=9u535Rr4KJM
- [título] Pixel Art Tutorial - Character 4 Directions: https://www.youtube.com/watch?v=OYgh-FrAek4
- [título] 16x16 Character Sprites Drawn In Real Time: https://www.youtube.com/watch?v=Tqa7hy4s7zI
- [título] Drawing → 3D → Pixel Art: My Indie Game Sprite Pipeline: https://www.youtube.com/watch?v=OkgendNuDwQ
- [título] 3D to Pixel - Making a RPG Maker Character Sprite Sheet in Blender: https://www.youtube.com/watch?v=i6JQXtcRSko
- [título] Pixel Art Isometric Sprite Workflow in Blender: https://www.youtube.com/watch?v=q9C0XmhA194
- [título] 3D Animation to Pixel Art with Blender: https://www.youtube.com/watch?v=x93hABp6FCY
- [busca] 16x16 Witch, 4 direções (GB Studio): https://www.youtube.com/watch?v=cQg0PoH5tAc ·
  playlist "Your first pixel art character": https://www.youtube.com/playlist?list=PLrW65LvOdu7L3LM6-jjDc03V0vP5t5jCk

**3D para pixel art**
- [lido] Dead Cells, Thomas Vasseur (2018):
  https://www.gamedeveloper.com/production/art-design-deep-dive-using-a-3d-pipeline-for-2d-animation-in-i-dead-cells-i-
- [lido] FMP 3D to Pixel Art Pipeline (2024): https://faeparkinsongamesyr2.wordpress.com/2024/06/01/fmp-3d-to-pixel-art-pipeline/
- [lido] SpriteKiln (MIT): https://github.com/LucasJRamos/spritekiln
- [lido] 3d-to-pixel-sprite (MIT): https://github.com/atou42/3d-to-pixel-sprite
- [lido] pseudo-pixel (MIT): https://github.com/craigrusselltiu/pseudo-pixel
- [lido] PixelArtPipeline (Unlicense): https://github.com/Broxxar/PixelArtPipeline
- [lido] codeyoma/aseprite #44 e #37 (EULA): https://github.com/codeyoma/aseprite/issues/44 ·
  https://github.com/codeyoma/aseprite/issues/37
- [lido] sprite-gen PR #102 (repositório Apache-2.0): https://github.com/aldegad/sprite-gen/pull/102
- [lido o README] Pixelorama (MIT): https://github.com/Orama-Interactive/Pixelorama
- [busca] PixelOver (pago): https://deakcor.itch.io/pixelover · Pixel Composer (pago): https://makham.itch.io/pixel-composer

**Lint, formato de texto e consistência**
- [lido] pxl (MIT): https://github.com/uilianks/pxl
- [lido] spritebox (MIT): https://github.com/jmsansan/spritebox (issues 21, 22 e 23; PR 40)
- [lido] codeyoma/aseprite #29: https://github.com/codeyoma/aseprite/issues/29
- [lido] pxart (MIT): https://github.com/thethirdbearsolutions/pxart
- [lido] pixel-workbench (MIT): https://github.com/cobjams/pixel-workbench
- [lido] glyphsprite (sem licença encontrada; não reaproveitar): https://github.com/webreactiva/glyphsprite
- [lido] ritmo PR #177: https://github.com/typeonce-dev/ritmo/pull/177
- [busca] Adopt Pixels: https://astropulse.itch.io/adopt-pixels ·
  script de órfãos no fórum do Aseprite: https://community.aseprite.org/t/script-suggestion-selecting-orphan-pixels/17138 ·
  PaletteGuard: https://violetpixel13.itch.io/paletteguard
- [busca] sprite-dicing (MIT; compressão de atlas, não serve para consistência): https://github.com/elringus/sprite-dicing

**Acadêmico**
- [lido] Kuo, Yang e Chu, Feature-Aware Pixel Art Animation, CGF 35(7), 2016: https://doi.org/10.1111/cgf.13038
- [busca] Kopf e Lischinski, Depixelizing Pixel Art, SIGGRAPH 2011:
  https://www.cs.jhu.edu/~misha/ReadingSeminar/Papers/Kopf11.pdf

**Corpus de régua**
- [lido] Ninja Adventure (CC0): https://pixel-boy.itch.io/ninja-adventure-asset-pack
- [lido] PIPOYA 32x32 (sem redistribuir): https://pipoya.itch.io/pipoya-free-rpg-character-sprites-32x32
- [lido] Universal LPC (64×64; licenças mistas):
  https://github.com/LiberatedPixelCup/Universal-LPC-Spritesheet-Character-Generator
- [falhou] https://opengameart.org/content/lpc-character-bases (HTTP 403)
