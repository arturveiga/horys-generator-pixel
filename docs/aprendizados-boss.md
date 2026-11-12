# Aprendizados: boss macaco-golem (2026-11-08 a 2026-11-10)

Boss de ~198 px, ≤ 16 cores, contorno de 1 px. Base estática aprovada: v17/v19 com 84% no revisor.
Animação: rig 2D chegou a 55%; SpriteKiln puro a 46%. Nenhuma passou. Plano novo em [plano.md](plano.md).

## Forma

- **Tamanho pela densidade do design.** Com 151 px e contorno de 2 px a limpeza apagava crânio, presas e runas;
  com 198 px e contorno de 1 px o design sobreviveu. Mudar de tamanho exige gerar de novo, não reduzir.
- **Crânio de frente**, simétrico, com os dois olhos âmbar acesos: boss encara o jogador.
- **Pernas em "A"**: canelas abertas para fora, pés virados para fora. Pernas retas e paralelas deixam o boss duro.
- **Pivô no centro dos pés**: a sombra nasce no pivô; pivô errado = sombra deslocada.
- **Sombra fixa**: não cresce com o corpo nem com a pilha da morte.
- Conversão por paleta fechada do boss; nunca moda direto da referência detalhada (27 cores, rosto destruído).
- Revisor desde a v01 com inventário completo; corrigir a lista inteira rende saltos grandes.

## Animação

- **Rig 2D de partes recortadas não serve para boss** (teto ~55%): frestas nas juntas, degraus de rotação,
  braços sem ombro nem cotovelo, pés que não saem do chão e corpo que desliza.
- **SpriteKiln puro tem teto (~46%)**: placas, juntas, pelo e espiral de 1 px não saem do shading procedural.
  Serve como guia de pose e timing.
- **Gerador de imagem não mantém escala entre quadros**: varia tamanho, detalhe e paleta; a animação treme.
  Pele gerada só fica estável se os quadros saem numa grade única.
- Decalque estático em peça que gira quebra o volume.
- Retoque à mão quadro a quadro não escala.
- Perguntar como cada estado se move antes de animar ("hit" era ambíguo).

## Referências de movimento

- Andar pesado ~8 fps; a massa lidera o quique, crânio, fumaça e pedras atrasam 1–2 quadros.
- Golpe pesado (Slynyrd, Pixelblog 56): antecipação de 1 quadro, smear só no arco, 1 quadro de quique no impacto.
  https://www.slynyrd.com/blog/2025/5/23/pixelblog-56-top-down-character-attack-animation
- Packs de golem: andar 8–12 quadros, ataque 8–20, morte 10–20.
