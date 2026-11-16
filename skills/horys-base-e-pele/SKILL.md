---
name: horys-base-e-pele
description: Fluxo único de personagem e monstro em pixel art do Artur (perfeicao.md, P1 + P3) — o agente NÃO inventa forma; a forma vem de um master do Codex lido na grade, o movimento vem de um corpo-base ou de um proxy (SpriteKiln) e o agente só copia, encaixa e limpa. Use para criar, vestir, animar ou refazer personagem/monstro/robô em pixel para os jogos do Artur, mesmo sem citar a skill. Substitui horys-pixel, horys-pixel-liso e horys-pixel-liso-animacao para personagem novo.
---

# Base + Pele (v1, 2026-11-14)

Regra-mãe: **o agente não inventa forma acima de 16 px.** Forma = master do Codex aprovado pelo Artur. Movimento =
corpo-base ou proxy. Aseprite = mesa de retoque. O Artur é a régua (`_aprovados`, `KB/estilo/aprovados.md`).

## Envelope (não sair dele sem o Artur pedir)
- Humanoide chibi 32 px (quadro 48×48), cabeça 40–45%. Monstro/robô 48 px (até 64), 3–5 massas. Boss só depois.
- ≤ 20 cores, contorno escuro 1 px, 2–3 tons por material, luz de cima-esquerda, nada menor que 2×2 px.
- Câmera top-down 3/4 fixa do jogo. Direções S, N, L; oeste = leste espelhado.
- idle 2–4 · andar 4 (≤ 6) · ataque 3–5 · dano 2 · morte 3–4; 100–160 ms por quadro.

## Horys Estúdio (onde o Artur vê, risca, aprova e ajusta a paleta)
`horys estudio --app` (ou `horys_estudio_abrir`): pastas agrupadas, inspetor com zoom e player, riscar e "Mandar ao
chat", aprovar/reprovar (vira a régua em `_aprovados`), paleta com recolor, boas práticas e botão do Blender.
Quando ele disser "veja os pedidos", leia `horys_estudio_pedidos`, faça, e responda com `horys_estudio_responder`
(com a imagem nova). Toda entrega vai para uma pasta que o Estúdio mostra (`art-src/<asset>/...`).

## Humanoide 32 px: base da Eldiran (decisão do Artur, 14/11)
Corpo-base aprovado em `art-src/base32/eldiran/` (idle + andar, S/N/L; O espelhado; mapas de partes por quadro).
`horys_pedido_codex` modo `vestir` com `base.png` → `horys_vestir` → `horys_pele_animar` (leva a roupa a todos os
quadros). A base de costas foi derivada da frente: confira o cabelo/nuca.

## Rota Blender (a melhor quando há modelo 3D, 14/11)
O modelo 3D dá consistência e movimento; o horys dá a paleta, o pixel e o acabamento (perfeicao.md §14).
**Ordem obrigatória (pedido do Artur):** modelar → `horys_blender_3d` (modelo + uma .glb animada por ação) → o
Artur vê no Estúdio (gira, 8 direções no ângulo do jogo, aponta defeitos no modelo) → corrigir os pedidos →
ele APROVA o 3D → só então paleta + pixel. Nunca renderizar pixel antes da aprovação (a trava recusa). No fim, o
resultado final é visto no Estúdio ("Ver resultado final": todas as direções animando juntas).
0. **Paleta primeiro**: `horys_blender_paleta` (conceito → cores-base → famílias de 2–3 tons, ≤ 20 cores, tinta)
   → Artur aprova (`horys_aprovar_arquivo` no paleta.json). Sem isso o render final recusa.
1. `horys_blender_inspecionar` no .blend → config do personagem (rig por pivôs de coleções/peças, papéis,
   regras de material, câmera do jogo, ações, direções). Exemplo: `art-src/robo/blender/robo.json`.
2. `horys_blender_render` com `previa` → olhar a prancha → render completo (andar/idle procedural, limiares de luz
   calibrados pela área, enquadramento por todas as poses, contorno 1 px, .aseprite com tags, mapas de partes).
3. Revisor em A/B cego → `horys_blender_recolor` para ajustar cor sem renderizar de novo → Artur.

## Checklist da rota 2D (as ferramentas travam o passo seguinte)
1. **Ficha** (5 linhas): nome, função, 3 cores, silhueta numa frase, o que NÃO pode ter.
2. **Master**: `horys_pedido_codex` modo `master` (conceito anexo, `ficha`, `altura`, `paleta`, vistas frente/lado/
   costas, `extras` p.ex. a arma) → 3 tentativas. Escolha a melhor; tentativa ruim se descarta, não se conserta.
3. **Ler a grade**: `horys_base_ler` (grade própria: cortes irregulares + voto da maioria). Paleta da própria imagem
   (sem `paleta`) quando o Codex mudou o tom; com `paleta` quando a ficha manda.
4. **Vista que falta ou ruim**: `horys_pedido_codex` modo `vista` sobre as vistas boas (A ÚNICA MUDANÇA). Nunca
   desenhe a vista à mão.
5. **Aprovar**: `horys_aprovar` (painel) → `horys_aprovar_arquivo` com o `id` (ou `chat: true` + as palavras dele).
   Sem isso vestir e animar recusam.
6. **Partes**: `horys_partes_mapa` (rascunho automático; contrato de cores do `art-src/motion-rigs`). Corrija com
   regiões (retângulos) até FORMA FECHADA ok. Chifre/cabelo/antena = `enfeite`.
7. **Movimento** (escolha um):
   - pequeno (idle, andar de frente/costas): `horys_animar_tabela` (`idle`, `andar-frente`, `andar-lado`);
   - humanoide com base: `horys_pedido_codex` modo `vestir` → `horys_vestir` → `horys_propagar_pele`;
   - grande (ataque, andar de lado): guia do proxy (`horys_guia_kiln`, uma cor por parte) → `horys_propagar_pele`
     ou `horys_colagem`; pose-chave nova: `horys_pedido_codex` modo `pose`.
8. **Limpar** no Aseprite só juntas, bordas e pixel solto, com `horys_ler_pixels` (leitura de volta). Cada correção:
   `horys_guarda_correcao` (desfaz se mexer em > ¼ da camada; no máximo 3 rodadas).
9. **Portão** `horys_portao` → **revisor** em A/B cego (antes × depois) → `horys_ab_registrar`. Correção só fica se
   ganhar. **Entrega** (`horys_entrega` com `pasta`) recusa sem A/B.
10. **Artur**: sim/não + % de retoque (`horys_gosto_do_retoque`). Aprovado vai para `_aprovados`.
- No máximo 2 rodadas falhas por teste; depois pare e relate. Toda arte passa pelo revisor antes do Artur.

## Regras de animação (sprite-forge, MIT)
- **O que não mexe fica idêntico**, pixel por pixel. Mexa parte inteira, nunca redesenhe o resto.
- **Restaure, não adivinhe**: o vão que uma parte deixa vem do quadro de referência ou do vizinho esticado; nunca
  cor inventada. Emenda de 1 px numa junção: a ferramenta fecha; maior: limpe à mão.
- **Slip factor 1,0**: no andar, o pé de apoio não desliza; o deslocamento do corpo = o da passada.
- **Cabelo/chifre/capa 1 quadro atrasado** (`"atraso:cabeca"` na tabela).
- **Cabeça travada**: vem inteira do master em todos os quadros; rosto não "ferve".
- Detalhe de 1 px que some num quadro e volta no outro = defeito. Mudança por quadro de andar: 15–40% dos pixels.
- Ataque gira o tronco no máximo 1 px; quem gira é o braço/arma (pose-chave do Codex ou guia do proxy).

## Lições (cada crítica do Artur vira linha aqui)
| Data | Crítica | Regra |
|---|---|---|
| 04/11 | andar "só desliza" (médico v16) | medir passada; pé de apoio parado |
| 10/11 | ref detalhada reduzida = 49 | pedir pixel art no tamanho final e simples |
| 11/11 | pintura por script "se perde" | script só lê, encaixa e limpa |
| 12/11 | detalhe de 1–2 px some | nada menor que 2×2 |
| 14/11 | robô: vista de lado confusa nas 3 tentativas | pedir a vista sozinha (modo `vista`) |
| 14/11 | robô: andar com poses do Codex "ferve" (tronco redesenhado, 83–97%) | pose do Codex só para pernas/braço; cabeça e tronco travados do master |
| 14/11 | robô: andar de lado ±2 px "marcha no lugar"; de frente 1 px "tremor" | lado ±5–6 px nos contatos; frente: bota sobe 3 px na passagem |

## Não faça
Inventar forma; pedir referência detalhada e reduzir; gerar cada quadro como imagem solta; pintar por cima do render
com script; trocar estilo no meio; começar pelo boss; nota absoluta em vez de A/B; ler a KB inteira antes de cada
asset (a KB é consulta: `KB/` e `skills/horys-pixel-liso/` só quando um passo pedir).
