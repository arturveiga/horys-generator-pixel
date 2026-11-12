# Estilo "horys-cozy" — bíblia curta

> RPG cozy top-down em baixa resolução. Escolhido por ser o limite que dá para produzir com qualidade:
> Blender posa e anima, a mão (ou `horys_converter` + `horys_limpar`) só reduz e limpa poucos pixels.

## Em uma frase
Pixel art **pequena, chibi e saturada**: tile 16 px, personagem de 20–24 px, 2–3 tons chapados por material,
sem dithering, sem anti-alias, sem luz dinâmica; animação de poucos quadros e VFX como "adesivos" em loop curto.

## Guia de estilo (os 15 itens)
| # | Item | Decisão |
|---|---|---|
| 1 | Contorno | 1 px, escuro colorido `#2a1f2d` (nunca preto puro) em personagens, props e VFX; cenário (grama, chão) sem contorno |
| 2 | Paleta | `paleta.json`: 11 rampas de 3 tons + contorno + brilho |
| 3 | Tons por material | 2–3 (sombra, base, luz); brilho `#fff6d8` só em ponto de luz/olho |
| 4 | Pintura | chapado, sombra em massa única, sem gradiente |
| 5 | Vista | top-down 3/4; 4 direções (baixo, cima, lado espelhado); 8 só se o jogo pedir |
| 6 | Tema | fantasia cozy |
| 7 | Saturação/temperatura | saturação alta; sombra puxa o matiz para o frio |
| 8 | Fundo | grama em manchas orgânicas de 3–4 verdes, bordas serrilhadas, tufos de poucos pixels |
| 9 | Textura | flat: sem dithering, sem anti-alias, sem sub-pixel |
| 10 | Coerência | escala inteira; tudo passa no portão de medidas e no revisor |
| 11 | Referências | cozy top-down (linha Stardew / Sprout Lands), só como régua de qualidade |
| 12 | Quadros (8 fps) | idle 2–4, andar 4, ataque 3–4, conjurar 3, hit 1–2 (flash branco), morte 4 |
| 13 | Animação | quadro a quadro, troca de folha por estado; bob de 1 px; sem squash forte |
| 14 | Proporções | humanoide 20–24 px, cabeça ~1/3 do corpo; criatura média 24–32 px; boss até 48–64 px |
| 15 | Densidade | props simples de 12–16 px; sombra no chão = elipse escura translúcida |

## VFX e magias
- Sprite separado, por cima do mapa ou no chão, loop de 3–6 quadros.
- 2–3 tons por elemento: água `agua`, terra `pedra`/`terra`, sombra `roxo`, luz `ouro`, fogo `vermelho`/`ouro`.
- Marcador de área no chão: círculo/espiral com contorno claro, por baixo dos personagens.
- Alvo atingido pisca branco chapado 1 quadro.
- Sem partículas, glow, bloom ou luz que ilumine o entorno.
- Escala: magia de área ocupa 3–5× um personagem.

## Pipeline com Blender
1. Blender posa e renderiza **flat/emission, sem luz**, na resolução final (ou 2× e reduz por vizinho mais próximo).
2. `horys_converter` para a paleta, `horys_limpar` para órfãos e contorno.
3. Retoque à mão só onde o portão ou o revisor apontar.

## UI
Pode ser HD (fonte lisa, painéis), fora da grade. Números de dano também.
