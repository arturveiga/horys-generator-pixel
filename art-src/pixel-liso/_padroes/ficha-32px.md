---
asset: <nome>
tipo: personagem          # personagem | inimigo | boss | criatura | prop | icone | efeito | tile
projeto: geral
tamanho: 32px             # quadro 32x32 (boss: quadro 48 ou 64 com a mesma densidade)
vista: top-down 3/4       # frente, lado, costas; esquerda = espelho do lado
paleta: paleta propria    # `paleta <arquivo.json>` no .grade; rampas de 3 a 4 tons com hue shift
cores_max: 12             # `limite_cores 12` (ate 16 com equipamento); efeito: 4 a 6
contorno: suave           # 1 px, cor escura da paleta, nunca preto puro
sombra: sim
regua: padroes universais # SEM Tiny Swords. Referencias so para olhar: Kenney Tiny (16 px) e personagens de 24 a 32 px de packs top-down (conferir licenca)
excecoes_ao_estilo:
  - "o portao de medidas e calibrado no Tiny (64 px+): resultado de orfaos e tamanho de mancha e IGNORADO; vale so a contagem de cores, a altura e quanto muda entre quadros"
  - "contorno de 1 px, nao 2 px"
---
## Proporcao e forma
- Personagem de 24 a 28 px de altura dentro do quadro de 32, pes na linha 29 ou 30.
- Cabeca com ~1/3 da altura (chibi); corpo e feijao; maos e pes de 2 a 3 px.
- Nada com 1 px de espessura exceto olho, brilho, linha interna e fiapo de efeito.
- Silhueta com espaco negativo (entre bracos, pernas e cauda); nada vira bloco.
- Olho: 1 a 2 px escuros + 1 px de brilho; boca de 1 a 2 px ou nenhuma.

## Cor
- Ate 12 cores; 2 a 3 tons por material; sombra fria, luz quente e pastel.
- Luz de cima e da frente, em cachos de >= 4 px; sem pillow shading, sem dithering, sem degrade.
- O escuro de verdade fica no contorno; o preenchimento fica em valores medios e claros.

## Animacao
- 8 a 10 fps. Idle 4 quadros; andar 6; ataque 4 a 6 (antecipacao, impacto segurado, recuperacao).
- Redesenhe a forma em cada quadro: squash/stretch com massa constante, partes soltas atrasadas.
- Comprimento de membros igual em todos os quadros (so muda com squash intencional).

## Como julgar (sem o portao do Tiny)
1. `grade.py gerar` so para gerar PNG/GIF/.aseprite e ler cores, altura, % que muda entre quadros.
2. Skill `pixelart-review` no PNG (paleta, orfaos, contorno dobrado, degraus, pes, quadros parados).
3. Revisor `horys-pixel-liso-revisor` com "regua: so padroes universais" e esta ficha como contrato.
4. Julgar sempre em 1x e 2x, nao no zoom.
