# Achados: gerar pixel art consistente (perfil 32) — Codex foi o mais eficiente (2026-11-12)

Teste: uma personagem original, a **lenhadora** (chibi 32 px no estilo da régua Eldiran, que o Artur escolheu para o
Hunvix), por vários caminhos. Tudo em `C:\Users\artur\Documents\pixel-liso\teste32\`. Nenhum asset do Hunvix foi
tocado. Nada commitado.

## Resultado por caminho

| Caminho | Pasta | Portão | Revisor | Leitura |
|---|---|---|---|---|
| Recolorir a régua (p05 da Eldiran) | `ranger/v04` | passa | **83% PASSA** | Prova o pipeline, mas é arte de outra pessoa. |
| Desenho à mão em texto, sobre o boneco-base da régua | `lenhadora/v04` | passa | 79% (machado não lê) | Cada rodada só tapou buraco; não deu salto de qualidade. |
| Codex: ilustração grande → reduzida para 32 px | `lenhadora/codex/v05` | passa | 62% | O conceito é ótimo, mas na redução cada detalhe vira 1–2 px e some (machado, colete). |
| Blender: modelo em blocos → render 32 px (método do vídeo) | `lenhadora/blender/v02` | passa | 49% | Andar e direções coerentes de graça; a modelagem em `bpy` é o gargalo (cabeça "ovo com chapéu"). |
| **Codex nativo: sprite já em 32 px ampliado, lido na grade** | `lenhadora/nativo` | passa | **66% (frente parada)** | Melhor desenho até agora: xadrez, colete, mechas e machado legíveis. |
| Codex nativo: andar a partir das 4 poses do boneco | `lenhadora/nativo/andar/v02` | passa | 61% | A cabeça fica parada e as pernas alternam, mas braços e machado quase não mexem. |

## O que funcionou no Codex

1. **Gerar já pequeno, não reduzir.** O pedido "pixel art 32x32 ampliada 16x com vizinho mais próximo, cada pixel um
   quadrado sólido numa grade fixa" deu pixel art de verdade (a ideia da PixelLab). A redução de ilustração grande
   é o que mata o detalhe.
2. **Referência visual anexada** (`conceito.py gerar --img`): 3 figuras da régua ampliadas 16x + a faixa das 20 cores
   (`nativo/referencia.png`). O Codex copiou proporção, contorno e densidade.
3. **Iterar com a crítica do revisor** (img-to-img): mandar o sprite atual ampliado + a lista numerada de correções
   (`nativo/prompt2.md`). Ele atendeu quase tudo numa rodada (xadrez regular, colete largo, machado maior).
4. **Animação por pose:** anexar o sprite + as 4 poses do andar do boneco-base branco da régua (linha 0 da folha
   Eldiran) e pedir uma tira de 4 quadros (`nativo/andar/prompt.md`). Saiu coerente: mesma cabeça, pernas alternando.
5. **Leitura nativa da grade** (`nativo/r2/ler_grade.py`): acha o período da grade pelas bordas de cor, lê o
   **centro** de cada bloco (mediana 7x7) e casa com a cor mais próxima (OKLab). Não borra nem reduz. O `limpar`
   comum apagava o xadrez.
6. **Tira de animação** (`nativo/andar/montar_andar.py`): separa os quadros pelas colunas de fundo, usa **um período
   só para a tira inteira** (calcular por quadro errou: 15–18 linhas em vez de 35) e alinha os quadros.

## O que falhou ou ainda falha

- **Tamanho do bloco não é o pedido.** O Codex devolve 1254 ou 2172 px de largura com blocos de 35–38 ou de 16 px,
  não os 16 pedidos. A leitura precisa detectar o período (autocorrelação a partir de 8 px).
- **Cores não são as pedidas.** Ele usa tons próximos, mas não os hex exatos, e muda de rodada para rodada (a pele
  veio rosada numa, pêssego na outra). Tons vizinhos (luz do cabelo × pele, sombra do cabelo × couro, calça escura
  × colete) se confundem na troca para a paleta. Remendei com troca **por região** (cabeça, pernas), que é frágil.
- **Alinhamento da animação:** alinhar pelo centro das botas faz o corpo andar de lado (85% de mudança); alinhar pela
  cabeça mata o quique. O certo é alinhar pelo **pé** e deixar o quique que o desenho tiver.
- **Movimento tímido:** na tira de andar ele mexe as pernas, mas quase não balança os braços nem o machado, e na
  passagem as pernas viram um bloco. Precisa de instrução de pose mais explícita (quique de 1 px, braço ±2 px,
  objeto com 1 quadro de atraso, vão entre as pernas).
- **Altura:** sai com 33–35 px; a régua tem 32. Pedir "altura máxima 32 com contorno" explicitamente.
- **Ruído no cabelo:** de 58 a 76 pixels órfãos por quadro, que vêm do próprio desenho do Codex (degraus de luz
  espalhados).
- **Faltam:** lado e costas (pela ideia do "rotate": anexar a frente aprovada e pedir as outras vistas na mesma grade).

## Bugs e limites da skill encontrados

- No perfil 32 o `_regua_anim.png` não é gerado e o `_checagem.txt` ainda escreve "vs Tiny". Falta a régua animada
  contra a Eldiran (`pNN_s.png`).
- O `G01` errava com prop na mão (o machado deslocava o "pé"); corrigido com folga de ±3 px no encaixe.
- Fork não chama subagente: o revisor tem que ser chamado pela sessão principal.

## Arquivos úteis

- Prompts: `lenhadora/nativo/prompt.md` (frente nativa), `prompt2.md` (correção), `andar/prompt.md` (tira de andar).
- Referências montadas: `nativo/referencia.png`, `nativo/ref_rodada2.png`, `andar/ref_andar.png`.
- Leitura: `nativo/r2/ler_grade.py`, `nativo/andar/montar_andar.py`.
- Geração: `python ~/.agents/skills/horys-pixel-liso/scripts/conceito.py gerar --prompt <md> --saida <pasta> --img <png>`
  (cerca de 1 min por imagem).

## O que procurar na web (para o Artur)

- Como forçar **grade exata e paleta exata** em gerador de imagem (prompt, grade de referência sobreposta, "pixel art
  upscaled x8 nearest neighbor", tamanho de saída múltiplo do bloco).
- Ferramentas de **"pixel art de imagem de IA"**: detectar a grade e reamostrar um pixel por bloco (ex.: o que
  "Pixel Snapper", "unfake.js" ou "pixel-perfect" fazem), para comparar com o `ler_grade.py`.
- Como a PixelLab e a Retro Diffusion fazem **rotação** e **animação por esqueleto**, e se dá para imitar com o Codex
  (sprite + pose de palito, ou sprite + boneco-base).
- Fluxos de **sprite sheet consistente** com modelo de imagem genérico: referência fixa, uma vista por vez, "mesmo
  personagem, mesma grade", e checagem entre quadros.
