---
asset: <nome>
tipo: personagem          # personagem | inimigo | criatura | prop | icone | efeito | tile
projeto: geral
tamanho: 16px             # quadro 16x16 (criatura/boss pequeno: quadro 32 com a mesma densidade)
vista: top-down 3/4       # frente, lado, costas; esquerda = espelho do lado
paleta: paleta propria    # `paleta <arquivo.json>` no .grade; rampas de 3 tons com hue shift
cores_max: 8              # `limite_cores 8`; efeito: 3 a 4
contorno: suave           # 1 px, cor escura da paleta, nunca preto puro
sombra: sim               # elipse no chao, largura do corpo
regua: padroes universais # SEM Tiny Swords. Referencias so para olhar: Kenney Tiny (CC0, 16 px)
excecoes_ao_estilo:
  - "o portao de medidas e calibrado no Tiny (64 px+): resultado de orfaos e tamanho de mancha e IGNORADO; vale so a contagem de cores, a altura e quanto muda entre quadros"
  - "contorno de 1 px, nao 2 px"
---
## Proporcao e forma
- Personagem de 12 a 14 px de altura dentro do quadro de 16, pes na linha 14 ou 15.
- Cabeca com ~1/3 da altura (chibi); corpo e feijao; maos e pes de 1 a 2 px.
- Nada com 1 px de espessura exceto olho, brilho, linha interna e osso de asa/ferramenta.
- A silhueta numa cor so lê como o personagem em 1x e 0,5x.
- Olho: 1 px escuro (2 px de altura se der) + 1 px de brilho.

## Cor
- Ate 8 cores; 2 a 3 tons por material; sombra mais fria, luz mais quente.
- Luz de cima e da frente, em cachos; sem pillow shading, sem dithering, sem degrade.
- Tom claro/saturado so onde a acao acontece.

## Animacao
- 8 fps (125 ms). Idle 2 a 4 quadros; andar 4; ataque 3 a 4 (antecipacao, impacto segurado, volta).
- Redesenhe a forma em cada quadro; o corpo muda no maximo 1 px de altura por quadro.
- Ponta de assinatura (cauda, mecha, asa) atrasa 1 quadro.

## Como julgar (sem o portao do Tiny)
1. `grade.py gerar` so para gerar PNG/GIF/.aseprite e ler cores, altura, % que muda entre quadros.
2. Skill `pixelart-review` no PNG (paleta, orfaos, contorno dobrado, degraus, pes, quadros parados).
3. Revisor `horys-pixel-liso-revisor` com "regua: so padroes universais" e esta ficha como contrato.
4. Julgar sempre em 1x e 2x, nao no zoom.
