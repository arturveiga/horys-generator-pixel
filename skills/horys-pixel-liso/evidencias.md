# Evidências: o que não fiz, e por quê (2026-11-11)

Este arquivo acompanha a `pesquisa-16-32.md` (FASE 1). Cada item diz o que ficou de fora, o motivo e a prova.

## 1. Não mudei nenhum script (a FASE 1 proíbe)

- **Motivo:** o pedido diz "Não altere nenhum script na FASE 1" e "PARE e mostre o resumo ao Artur antes da FASE 2".
- **Prova:** sha256 e data de modificação, medidos depois da pesquisa. Todos os arquivos são de 2026-11-05.

| Arquivo | sha256 | Modificado |
|---|---|---|
| `SKILL.md` | `085cc71e82d63be86458e5721149ac2fda819f460af431402dfa6bc7b368b9c5` | 2026-11-05 21:27 |
| `scripts/calibrar.py` | `b8ab293647a4ea287c0aa82a115fe7981189ab27de703727a06ac15d75e62bfd` | 2026-11-05 11:21 |
| `scripts/comum.py` | `aa7c01749470ac539f8f6369ffd41140885b7fef2efa3b10a042917d6d101d92` | 2026-11-05 14:44 |
| `scripts/conceito.py` | `e9f585e0bea554dfc113939d25ad1101c6f6d258ffffdea2d6b386a85a474c0f` | 2026-11-05 20:56 |
| `scripts/config.json` | `e1748dba3d1772084a2181f9f42185955f43e4c08e4e18aa2c87260161e730b7` | 2026-11-05 19:01 |
| `scripts/exportar_aseprite.lua` | `4781fc9782d808d0cd6dae10305d277c49ec1d5e6c7b79ee35311c3addcc9aa1` | 2026-11-05 19:01 |
| `scripts/grade.py` | `0e6d34df1418bc71ae931a92166aef7e26c2c5580673f7533de7528673f200bc` | 2026-11-05 19:01 |
| `scripts/instalar.py` | `7e5ae911f3c305bafa551ad204e371147b308bbdff0fe873c3e506182f6ff7a5` | 2026-11-05 12:08 |
| `scripts/medir.py` | `69f8349e03ca09ef97eb3b006422a31da1a96652b047b68dc5094a4e9be364ce` | 2026-11-05 14:44 |
| `scripts/revisor_prompt.md` | `c8e2932cb72369f756ce5e04f79d861bd7c2d05298bd44a36fd6523e94cf0916` | 2026-11-05 12:09 |

- Os únicos arquivos novos na pasta da skill são a `pesquisa-16-32.md` e esta `evidencias.md`.
- O teste de órfãos (vizinhança 4 × 8) rodou num script do scratchpad da sessão. Ele só leu PNGs.

## 2. Não comecei a FASE 2

- **Motivo:** o pedido manda parar e mostrar o resumo antes. Há 5 decisões que são do Artur (seção 10 da pesquisa):
  - régua de 16 px;
  - régua de 32 px;
  - contorno padrão;
  - paleta;
  - fonte da guia.
- Backup, calibração e `instalar.py` ficam para a FASE 2, conforme o plano da seção 9.

## 3. Desliguei o PC sem forçar

- **O que fiz:** `shutdown.exe /s /t 0`, igual a "Iniciar > Desligar".
- **O que recusei:** o `/f` (fechar à força) e o `/t` maior que 0, que já implica `/f`.
- **Motivo:** fechar à força perde o que não foi salvo no Aseprite, no Blender ou no Godot.
- **Se algum app tiver trabalho sem salvar:** o Windows mostra a tela de apps que impedem o desligamento e espera
  uma confirmação. O PC pode ficar ligado até alguém confirmar.
- **Histórico:** a 1ª ordem de desligar veio no fim de um texto colado. Não agi nela sozinho. Desliguei depois que
  o Artur pediu de novo, com as próprias palavras.

## 4. Não li o conteúdo dos vídeos do YouTube

- **Motivo:** as 9 páginas de vídeo voltaram só com a casca do YouTube (cerca de 900 caracteres de rodapé). Não
  vieram descrição, capítulos nem transcrição.
- Na pesquisa, eles aparecem como **[título]**, e nenhum achado depende deles.
- **URLs:**
  - https://www.youtube.com/watch?v=2JCG4fCmeHk
  - https://www.youtube.com/watch?v=aios4kDJZsc
  - https://www.youtube.com/watch?v=9u535Rr4KJM
  - https://www.youtube.com/watch?v=OYgh-FrAek4
  - https://www.youtube.com/watch?v=Tqa7hy4s7zI
  - https://www.youtube.com/watch?v=OkgendNuDwQ
  - https://www.youtube.com/watch?v=i6JQXtcRSko
  - https://www.youtube.com/watch?v=q9C0XmhA194
  - https://www.youtube.com/watch?v=x93hABp6FCY
- **Para cobrir:** colar a transcrição (legenda automática) de 2 ou 3 desses vídeos numa próxima sessão.

## 5. Páginas que não abriram

| URL | Erro |
|---|---|
| https://blog.studiominiboss.com/pixelart | o domínio não resolve (`ENOTFOUND`) |
| https://saint11.org/blog/pixel-art-tutorials/ | falha sem resposta |
| https://the-pixel.art/articles/pixel-art-character-design/ | HTTP 403 |
| https://www.pixel-editor.com/articles/pixel-art-outlines | HTTP 200, mas só com o título do site |
| https://pixelorama.org/ e https://orama-interactive.github.io/Pixelorama-Docs | falha sem resposta |
| https://opengameart.org/content/lpc-character-bases | HTTP 403 |
| https://scispace.com/pdf/feature-aware-pixel-art-animation-1r1wch3chh.pdf | HTTP 202 vazio |

- O artigo de Kuo et al. foi lido pelo PDF da Universidade de Bath, extraído com `pdftotext`.
- Os tutoriais do Pedro Medeiros (MiniBoss e saint11) **não** entraram na pesquisa. Ficam como lacuna.

## 6. Não baixei os pacotes de régua

- **Pacotes:** Ninja Adventure (cerca de 89 MB, CC0) e Pipoya 32x32.
- **Motivo:** a escolha da régua é do Artur, e o download faz parte da FASE 2.
- **Regra para quando baixar:**
  - Pipoya e Tiny Swords ficam fora do repositório, porque a licença proíbe redistribuir.
  - O Ninja Adventure é CC0 e pode ficar em qualquer lugar.

## 7. O que não vou propor nem fazer

- **Dependência paga** (PixelLab, Retro Diffusion, PixelOver, Pixel Composer): a regra é "só Claude ou Codex"
  (memória `so-claude-ou-codex`). Eles aparecem na pesquisa só como referência.
- **Redesenho por script por cima do render 3D:** já falhou no gorila (memória `pintura-procedural-falhou`). A guia
  da FASE 2 é referência para desenhar à mão. Ela nunca vira asset nem é "pintada" por script.
- **Copiar código de terceiros:**
  - pxl, spritebox, pixel-workbench e pxart (MIT): só ideias, reimplementadas.
  - codeyoma/aseprite (EULA do Aseprite): não pode ser reaproveitado.
  - glyphsprite: sem licença encontrada, não pode ser reaproveitado.
- **Número de blog de produto como meta de portão:** Neta, SpriteGen e Sprite AI vendem gerador de IA. Os números
  deles entram só como pista; a meta vem da calibração.
