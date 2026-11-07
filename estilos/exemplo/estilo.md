# Estilo "exemplo" — bíblia curta

> Pacote genérico e original (licença MIT), feito para testar o fluxo do horys-pixel e servir de modelo para o seu
> próprio estilo. Não tem régua: o portão usa as metas universais do motor e as prévias `_regua` ficam de fora.

## Em uma frase
Pixel art **chapada e legível**: massas grandes de cor, contorno escuro único de 2 px, 3 tons por material com
*hue shift* (sombra mais fria, luz mais quente) e nada de ruído.

## Guia de estilo (os 15 itens)
| # | Item | Decisão |
|---|---|---|
| 1 | Contorno | 2 px, cor única `#1c1828` (o "contorno" da paleta); efeitos sem contorno |
| 2 | Paleta | 17 cores: 5 rampas de 3 tons + contorno + brilho (`paleta.json`, `.gpl`, `.hex`) |
| 3 | Tons por material | 3 (sombra, base, luz); o brilho `#fbf5e6` só em ponto de luz |
| 4 | Estilo de pintura | chapado em blocos, sombra em cachos grandes |
| 5 | Vista | 3/4 de cima, personagem olhando para a direita |
| 6 | Tema | livre (decida por jogo) |
| 7 | Saturação e temperatura | croma moderado; sombra fria, luz quente |
| 8 | Fundo | um tom a menos e menos saturado que os personagens |
| 9 | Textura | flat: sem dithering, sem antialiasing |
| 10 | Coerência | todo asset passa no portão de medidas e no revisor |
| 11 | Referências | a definir por quem usar o pacote |
| 12 | Quadros | idle 4–6, andar 6–8, ataque 4–6, a 10 fps |
| 13 | Estilo de animação | cartoon: antecipação, squash & stretch, redesenho a cada quadro |
| 14 | Proporções | humanoide de 48–64 px de altura, 2 a 2,5 cabeças |
| 15 | Densidade de assets | a definir por jogo |

## Rampas
`pele`, `folha`, `céu`, `tijolo` e `madeira`, sempre na ordem sombra → base → luz.
