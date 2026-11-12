# Relatório — Experimento A3 (Blender nativo), macaco-golem

Data: 2026-11-11. Referência: `referencia/stone_gorilla_ficha.png` (ficha "Stone Gorilla Boss", paleta de 8 cores).
Custo: R$ 0. Só Blender 5.2.3 LTS já instalado + Python local + Horys. Nenhum add-on, API ou download.

## Como reproduzir
```bash
cd experimentos/animacao-3d
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup -P blender/golem.py -- --saida . --altura 207
python processar.py
```
`golem.py` constrói o modelo, o rig e as ações, salva `blender/golem.blend` e renderiza (~6 s). `processar.py` passa
os renders pelo motor de sequência do Horys (~13 s) e grava folhas, GIFs e `metricas.json`.

## O que foi feito
- **Modelo low-poly por código** (~120 peças rígidas): crânio flutuante com olhos acesos, boca aberta, presas,
  fumaça roxa, peitoral com medalhão, ombreiras com espinhos, manoplas, punhos, pernas em A, tufos de pelo, 4 lascas
  de pedra flutuando. Pedra facetada e pelo liso; contorno de 1 px por casco invertido.
- **Rig**: 24 ossos. Cada peça presa a um osso (pedra não deforma). Pernas em IK com o pé preso a um alvo no chão;
  cabeça e pedras em ossos próprios para movimento secundário.
- **Animações no 3D**: idle com 4 quadros (respiração no peito e nos ombros, cabeça atrasada, pedras flutuando) e
  walk com 8 quadros a 8 fps. No walk, o pé de apoio recua em velocidade constante (ciclo no lugar, sem deslizar).
  O pé no ar sobe em arco. O corpo fica baixo no contato, com giro de quadril e contragiro do peito. Braço oposto à
  perna; cabeça e pedras atrasam 1–2 quadros.
- **Render**: Eevee, câmera ortográfica a 32°, fundo transparente, filtro 0, toon de 3 faixas por material (Shader
  to RGB + rampa constante), luz de cima e da direita. **Escala e posição da câmera fixas para as duas ações**,
  calculadas uma vez da união de todos os quadros. Dois renders: nativo 256 (bruto) e 4× (para o Horys).
- **Horys**: preset `render3d` (escala fixa, sem normalizar altura por quadro, sem regularizar borda por quadro, sem
  anti-cintilação), quantização conjunta na paleta, redução por moda 4× → 256, validação V01–V13, folha Godot.

## Resultado medido (depois do Horys)
| | Idle | Walk |
|---|---|---|
| Canvas | 256×256 em todos | 256×256 em todos |
| Altura visual | 191–195 px | 188–198 px |
| Cores | 9 (bruto: 60) | 9 (bruto: 60) |
| Alpha só 0/255 | sim | sim |
| Pixel solto piscando | 0,7% | 0,9% |
| Silhueta × quadro 0 (IoU mín.) | 0,88 | 0,70 |
| Validação | **APROVADA** | 1 grave: V06 deriva x 6,2 px (limite 5,1), do giro e do balanço proposital; aviso V07 pés 13 px = profundidade do passo em 3/4 |

## Revisão artística (pixel-art-director, independente)
| Rodada | Aceitação | Silhueta | Walk | Idle | Pixel | Consistência |
|---|---|---|---|---|---|---|
| 1 | 50 | 42 | 38 | 55 | 60 | 72 |
| 2 | 58 | 50 | 58 | 58 | 60 | 72 |
| 3 | **62** | 58 | 64 | 60 | 62 | 70 |

Para comparar: boss parado desenhado 84, rig 2D 55, SpriteKiln 46.

**O que o render 3D resolveu de vez:** consistência (72, a melhor nota de todas as tentativas), nada some nem
pipoca entre quadros, escala fixa, pé plantado por construção, loop fechado, paleta única. Tudo automático e
reprodutível em segundos.

**O que ainda falta (é modelagem, não pipeline):** o crânio ainda lê como capacete (faltam órbitas fundas, cavidade
nasal e maçãs saindo do contorno). O laranja das lascas e espinhos compete com olhos e medalhão. As manoplas são
caixas sem dedos. Os tufos de pelo somem no contorno. O musgo claro parece luz. O walk ainda pede squash no contato
e passada maior. A vista de frente esconde parte da passada: vale renderizar também `se` e `e`.

## Rodada 3 (direções s, se, e)
Crânio remodelado (cúpula, lombadas, órbitas com brilho, cavidade nasal, maçãs), laranja só em olhos, medalhão e
uma lasca, punhos com nós, espiral nas manoplas, tufos maiores, musgo em cachos, passada ±0,35 com squash no contato,
idle com cabeça viva. Três direções na MESMA escala (`renders/*_{s,se,e}_*`, `previews/walk_direcoes_2x.png`).
Revisor: **se** é a melhor vista ("perto de entregável"); **s** ok; **e** reprova (corpo fino de perfil, rosto
escondido atrás da ombreira, sem corcunda de gorila). Próximo: corcunda de 15–20° com a cabeça à frente, tronco
×1,4 em profundidade, crânio ×1,2 afundado nos ombros, braços ±30° no perfil, fumaça envolvendo o pescoço.

## O que o experimento mudou no Horys
- `render3d` agora **desliga a anti-cintilação**: num render determinístico ela não tem ruído para tirar, e herdar a
  cor do quadro anterior deixou rastro no medalhão e nos olhos (peças internas se movem sem mudar a silhueta).
- V09 passou a medir **pixel solto piscando** (manchas de até 2 px). A métrica antiga contava como pisca a borda
  que sobe 1 px e volta na respiração.
- V08 compara só o x do pivô: em 3/4, a origem no chão fica acima da ponta do pé da frente.
- V12b mede a cabeça **alinhada pela própria cabeça**: o quique do corpo não é mudança de forma.

## Veredito
O Blender nativo é viável como **backend de animação**: entrega consistência estrutural que nenhuma tentativa
anterior entregou, custo zero, ~20 s do script ao spritesheet. A nota artística (58) ainda não chega ao "pronto"
(≥ 80). O que falta é a qualidade do modelo e da animação, não o pipeline. Próximo passo: rodada 3 com as correções
do revisor (crânio, emissivos, manoplas, squash, pelo, musgo, direções `se`/`e`). Só depois comparar com
PixelatorPlus/Blockbench.

## Arquivos
- `blender/golem.py` (fonte do modelo, rig, animação e render) · `blender/golem.blend` (editável) ·
  `blender/golem_r1.py` (rodada 1, histórico)
- `renders/{idle,walk}_{bruto256,x4,horys}/` + `manifest.json`
- `spritesheets/golem_{idle,walk}.{png,json,gif}` (Horys) e `golem_{idle,walk}_bruto.*`
- `previews/`: `referencia_vs_modelo.png`, `{idle,walk}_bruto_vs_horys.{png,gif}`, `*_horys_3x.gif`, `*_horys_1x.png`
- `metricas.json` (antes × depois)
