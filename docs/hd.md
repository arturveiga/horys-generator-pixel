# Ramo HD: sprites ilustrados animados por esqueleto

Data: 2026-11-09. Estado: **plano, nada implementado.** Fazer depois, numa branch ou fork próprio (`hd`), sem mexer
no fluxo de pixel art.

## Por que

O fluxo de pixel art bate num teto que o código não resolve:

| Medida | Resultado |
|---|---|
| Parado, melhor caso (golem v19) | 84%, em 17 versões |
| Parado, fluxo novo (1.7) | 65% |
| Animação (Kiln, rig de partes, pele + decalque, grade do gerador) | 46–55% |

As causas:

1. **Redução de ~450 px para ~96 px:** rosto, runas e mãos ficam com 2–3 px, e a moda apaga. O rosto do golem virou
   mancha em todas as rodadas de 09/11.
2. **O gerador não mantém escala, chão nem passada entre quadros:** três grades seguidas reprovaram no portão de
   entrada em 09/11.
3. **Girar partes quebra a pixel art:** o rig deu ~55% por frestas e degraus.

No HD as três somem: não há redução, o esqueleto mantém o mesmo desenho em todos os quadros e girar a arte em alta
resolução não quebra nada.

## O que é

- O sprite usa a arte do gerador quase como ela sai: ilustração chapada (cel shading), contorno grosso, cores lisas,
  com **~256–400 px de altura no jogo**.
- A animação é **cut-out por esqueleto**: a arte é recortada em partes, e ossos com pivôs nas juntas animam por
  rotação e translação (Godot 4 `Skeleton2D` + `Polygon2D`/`Sprite2D` e `AnimationPlayer`).
- Referências de visual: Hades, Darkest Dungeon, Don't Starve.

## Custos e riscos

- **Muda a cara do jogo.** Se o `D:\godot\games\vila_monstros` já está em pixel art (tiles, personagens, filtro
  nearest), tudo teria que mudar de estilo, ou o boss destoa. **Conferir primeiro.**
- **Consistência entre assets:** cada imagem gerada sai com um traço diferente. Precisa de um guia de estilo HD fixo
  (contorno, paleta, luz, proporção) em todo prompt, e de retoque.
- **Peso:** texturas grandes. Atlas por personagem e mipmaps desligados no 2D.
- **Animação de esqueleto lê "flutuante"** se não tiver antecipação, overlap e squash. As regras L6 da `praticas.md`
  continuam valendo.

## O que se reaproveita do horys-pixel

| Peça | Arquivo | Uso no HD |
|---|---|---|
| Padrões por tipo | `src/horys_pixel/padroes/*.json` | vista, câmera, proporção, cortes; precisa de campos HD (altura em px no jogo, espessura do contorno) |
| Prompt de tradução | `src/horys_pixel/traducao.py` | os 11 itens; trocar o "orçamento de detalhe" (sem redução) e pedir **partes separáveis** (braços sem cobrir o tronco) |
| Portão de entrada | `src/horys_pixel/entrada.py` | fundo liso, figura inteira, margem, chapado; a escala mínima muda |
| Remoção de fundo | `src/horys_pixel/motor/conceito.py` (`tirar_fundo`) | igual |
| Registro de grade | `src/horys_pixel/sequencia/registro.py` | igual, se usar grade de poses como guia |
| Painel e pedidos | `extension/`, `daemon/` | perguntar e aprovar com o Artur |

**Não se aproveita:** conversão por moda, paleta travada, contorno de 2 px, limpeza de órfãos, M10 e o portão de
medidas de pixel art.

## O que entra de novo

1. **Perfil de estilo HD** (`estilos/<nome>-hd/`): sem redução, paleta como guia (não travada), espessura do contorno
   relativa à altura.
2. **Recorte em partes** (`hd/partes.py`):
   - cabeça, tronco, braço, antebraço+punho, coxa, perna+pé (por lado), mais acessórios (pedras flutuantes, fumaça);
   - **sobreposição nas juntas**: cada parte se estende por baixo da vizinha, para a rotação não abrir fresta;
   - a máscara das partes vem de um passo assistido: o Artur marca no Aseprite ou num editor simples, ou a
     segmentação é sugerida e o Artur ajusta. Não inventar forma por script.
   - pintar por baixo o que a parte da frente escondia (o gerador pode fazer, com a máscara como guia).
3. **Exportação para o Godot 4** (`hd/godot.py`):
   - um PNG por parte (ou atlas) + uma cena `.tscn` com `Skeleton2D`, `Bone2D` nos pivôs e as partes presas aos ossos;
   - pivôs e ordem de desenho (z-index) vindos de um `rig.json`.
4. **Animações** (`hd/animacao.py`):
   - poses-chave em `rig.json` (ângulos por osso, deslocamento do quadril), interpoladas no `AnimationPlayer`;
   - andar de frente e de lado: contato, descida, passagem, com sobe-desce do quadril, contra-balanço dos braços e
     overlap nas pedras flutuantes e na fumaça;
   - prévia em GIF/MP4 renderizada pelo Godot headless, para revisar sem abrir o editor.
5. **Revisor HD**: critérios novos (silhueta por pose, arco, pé deslizando, fresta em junta, leitura no tamanho do
   jogo) no lugar das métricas de pixel.

## Top-down

- **Vista:** 3/4 de cima, de frente (baixo) e de lado (direita; esquerda = espelho, `scale.x = -1`).
- **Costas (cima):** precisam de uma segunda arte de tronco e cabeça; o esqueleto é o mesmo.
- **Perfil:** precisa da sua própria arte recortada, com o mesmo `rig.json` em outra vista (outros pivôs).

## Protótipo (primeiro passo, quando for fazer)

Caso de teste: o boss golem-caveira (`C:\Users\artur\.horys-pixel\experimentos\golem-caveira\conceito.png`).

1. Conferir o estilo do `vila_monstros` e registrar a decisão em `docs/decisoes.md`.
2. Gerar a arte top-down de frente pelo prompt de tradução (vista 3/4 de cima, partes separáveis).
3. Recortar em partes com sobreposição nas juntas; pintar o que ficou escondido.
4. Montar `rig.json` e a cena `Skeleton2D`; animar o andar de frente (4–6 poses-chave).
5. Renderizar o GIF e mostrar ao Artur.

**Pronto quando:** o andar roda no Godot, sem fresta nas juntas e sem pé deslizando, e o Artur decide se o HD vale para
os bosses (ou para o jogo todo).

## Decisões em aberto

1. O `vila_monstros` muda de estilo inteiro ou o HD fica só para bosses?
2. Recorte: máscara feita à mão pelo Artur ou segmentação sugerida e ajustada?
3. Ferramenta de esqueleto: `Skeleton2D` nativo do Godot (sem dependência) ou Spine/DragonBones (licença e
   importador)?
