# Como a imagem tem que vir para cá

A ferramenta lê a imagem do gerador (ChatGPT, Codex ou outro) **na grade de pixels dela** e devolve a arte parada em
1x, sem redesenhar nada. Para isso a imagem precisa seguir este formato. Se não seguir, `horys ler` recusa e diz o
motivo. Nesse caso, gere de novo: não conserte a imagem à mão.

O jeito mais fácil é rodar `horys prompt <asset>`. O comando escreve o pedido já preenchido com os números do jogo
(`jogo.json`) e com a paleta do asset, se ela existir, e salva o texto em `assets/<asset>/prompt.txt`. Cole o texto
no gerador.

## O formato, item por item

| # | Exigência | Por quê |
|---|---|---|
| 1 | **Três vistas do mesmo personagem lado a lado, da esquerda para a direita: frente, lado (olhando para a DIREITA) e costas.** Nada além disso na imagem. | Cada vista vira um arquivo (`frente.png`, `lado.png`, `costas.png`). A ordem e o lado olhando para a direita batem com as direções do jogo (sul, leste, norte). O oeste é o leste espelhado. |
| 2 | **Câmera top-down 3/4 do jogo** (hoje 43°: vê o topo da cabeça e a frente do corpo), igual nas três, sem perspectiva. | O render do Blender usa essa câmera. O gabarito compara a arte com o render no mesmo ângulo. |
| 3 | **Altura exata em pixels de pixel art**: humano = `altura_humano_px` do `jogo.json` (hoje 44 px). Outro tamanho vai em `altura_px` no `asset.json`. As três vistas com a mesma altura e os pés na mesma linha. | É isso que mantém todos os assets na mesma escala. A leitura mede a altura e recusa se fugir mais de 4,5%. |
| 4 | **Pixel art de verdade, ampliada**: pixels quadrados, grandes e nítidos, todos mais ou menos do mesmo tamanho. Sem antisserrilhado, degradê, desfoque, ruído ou meio pixel. | A leitura aguenta blocos que variam alguns px, como o gerador faz, mas não aguenta ilustração lisa. |
| 5 | **Contorno escuro de 1 pixel** em volta da figura. | O render também sai com contorno de 1 px. A leitura afina contorno duplo e fecha as falhas. |
| 6 | **Até 20 cores, 2 a 3 tons por material** (sombra, base, luz), luz vindo de cima à esquerda. Se o asset já tem paleta aprovada, **só as cores dela**. | A paleta é a única fonte de cor do asset: a arte e o render usam as mesmas cores. |
| 7 | **Formas simples**: nada menor que 2×2 pixels; olhos com 1 a 2 pixels. | Detalhe de 1 px pisca na animação. Os portões avisam peça mais fina que 2 px. |
| 8 | **Fundo inteiro de uma cor só, `#FF00FF` (magenta)**, sem degradê, e o magenta não pode aparecer no personagem. | O fundo é removido pela cor. |
| 9 | **Figura inteira com margem**, em pé, postura neutra, braços um pouco afastados do corpo, sem objetos soltos no ar. | Braço colado no corpo não separa no modelo 3D. Figura cortada não tem como ser lida. |
| 10 | Imagem de **1536×1024** (paisagem), em PNG. | Com 44 px de altura, cada pixel vira um bloco de ~15–20 px, o tamanho que a leitura lê melhor. |

Salve como `assets/<asset>/gerada.png`. Também serve pixel art feita à mão, 1x ou ampliada por um inteiro exato
(2x, 3x...): essa é lida sem nenhuma alteração.

## O que NÃO mandar

- Ilustração detalhada, anime, pintura, foto ou render 3D. Detalhe menor que um pixel some na redução.
- Uma vista por imagem. Cada imagem sai numa escala e num tamanho de pixel diferentes.
- Personagem em pose de ação, com sombra no chão, com chão desenhado ou com texto.
- Pixel art "de enfeite", com blocos de tamanhos muito diferentes na mesma imagem (mais de ±30%).

## O pedido (modelo)

Troque o que está entre `< >`. O `horys prompt` já faz isso por você.

```
Gere UMA imagem de pixel art de um personagem para um jogo 2D top-down.

Personagem: <função, roupa, 3 cores principais, silhueta numa frase, o que ele NÃO pode ter>

Formato obrigatório:
1. Três vistas do MESMO personagem lado a lado, da esquerda para a direita: FRENTE, LADO (olhando para a DIREITA) e
   COSTAS. Nada além disso: sem texto, sem rótulo, sem moldura, sem chão e sem sombra no chão.
2. Câmera: top-down 3/4, inclinada 43° acima do horizonte (vê o topo da cabeça e a frente do corpo), igual nas
   três vistas, sem perspectiva.
3. Escala: cada figura com exatamente 44 pixels de altura, do topo da cabeça à sola do pé. As três com a mesma
   altura e os pés na mesma linha horizontal.
4. Pixel art de verdade: pixels quadrados, grandes e nítidos, todos do mesmo tamanho (a imagem é a pixel art
   ampliada sem suavização). Sem antisserrilhado, degradê, desfoque, ruído ou meio pixel.
5. Contorno escuro de 1 pixel em volta de toda a figura.
6. Cores: no máximo 20 no total, 2 a 3 tons por material (sombra, base, luz), luz vindo de cima à esquerda.
7. Formas simples e grandes: nenhum detalhe menor que 2×2 pixels; olhos com 1 a 2 pixels.
8. Fundo inteiro de uma cor só, #FF00FF (magenta), sem degradê. O magenta não pode aparecer no personagem.
9. Figura inteira com margem em volta (nada encostando na borda), em pé, postura neutra, braços um pouco afastados
   do corpo, sem objetos soltos no ar.
Imagem de 1536×1024 (paisagem).
```

## Dicas para o gerador acertar

- Gere 3 tentativas e escolha uma. Tentativa ruim se descarta.
- Se a altura vier errada, `horys ler` diz quantos pixels a figura tem. Peça de novo no mesmo chat: "a figura saiu
  com N pixels de altura; refaça com exatamente 44".
- Se a paleta já estiver aprovada, anexe `assets/<asset>/paleta.png` junto do pedido.
