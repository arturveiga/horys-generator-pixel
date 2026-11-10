# Pesquisa: geradores de pixel art para o horys

Data: 2026-11-09. Pedido: `prompt-pesquisa-geradores.md`. Só pesquisa: nada foi instalado, baixado, assinado ou gasto.
Todas as páginas foram acessadas em 2026-11-09; a data de publicação aparece quando a página traz uma.

Legenda de evidência:
- **[V]** verificado na página oficial citada;
- **[R]** relatado por usuário, blog, revendedor ou agregador;
- **[I]** inferência nossa.

Os nomes e preços de modelos comerciais mudam rápido (vários foram trocados em 2026). Conferir na página oficial antes
de gastar.

## Restrição do projeto (decidida pelo Artur em 2026-11-09)

**O horys tem que funcionar para quem tem só um Claude ou um Codex.**
- O gerador de imagem é o do Codex (gpt-image dentro do plano ChatGPT).
- O Claude não gera imagem: ele dirige, mede, corrige e revisa.
- Modelo aberto local fica como **extra opcional**, para quem tem GPU.
- Serviços pagos de terceiros (PixelLab, Retro Diffusion, Gemini API, BFL e outros) **ficam fora** do caminho do
  produto. A pesquisa sobre eles continua abaixo só como referência: mostram o que "gerar nativo" consegue e servem
  de régua.

## Resposta curta

**Atualização (2026-11-09, mesma data):** a melhor aposta passou a ser o **Blender pelo Claude** (seção 1.0 e teste B): render direto em 96 px, esqueleto mantendo escala e chão, loop sem o Artur e sem gerar imagem. O caminho do Codex em grade nativa (abaixo) fica em paralelo, como comparação e fonte de decalque.

**Dentro da restrição, o ganho está em mudar o que pedimos ao Codex e como reduzimos, não em trocar de gerador.**

1. **Pedir pixel art numa grade inteira, não uma ilustração.**
   - Hoje o conceito sai com ~1400 px e a moda reduz 14,6× até 96 px (golem-caveira, `entrada_checagem.txt`). O
     modelo desenha runas e dentes de 3 px que não sobrevivem.
   - O pedido passa a ser "pixel art em blocos de 4×4, figura com 384 px de altura (96 blocos)". Assim o orçamento de
     detalhe cai na escala certa.
   - Os serviços nativos (PixelLab, Retro Diffusion) fazem exatamente isso por dentro.
2. **Reduzir pela grade detectada, não por moda num fator arbitrário.**
   - Os geradores gerais desenham "pictures of pixels" e escolhem uma grade diferente a cada imagem
     [V] (https://www.spritecook.ai/blog/why-ai-cant-match-pixel-art-resolution, 26/08/2026).
   - Detectar o tamanho do bloco e a fase da grade em cada imagem, como o `unfake` (MIT) faz
     [V] (https://pypi.org/project/unfake/), e reduzir 1 bloco → 1 pixel.
   - Depois, o registro do motor de sequência iguala a altura entre quadros.
   - Para o detalhe que mesmo assim some na redução, o PixelOE (seção 1.8) engrossa contornos finos antes de reduzir.
3. **Animação: uma pose por chamada, com a base aprovada e a silhueta do guia anexadas.**
   - Os relatos de 2026 dizem que pedir a folha inteira de uma vez é instável e que uma pose por chamada com a
     referência fixa funciona melhor [R].
   - O motor de sequência que já existe (registro, trava de identidade, anticintilação) faz o resto.
4. **Loop sem o Artur.**
   - O horys já chama o Codex CLI (`fonte: codex`).
   - Falta fechar o ciclo gerar → portão de entrada → reprompt com as falhas → gerar, com teto de tentativas.
   - O limite é a cota do plano: uma imagem gasta 3–5× um turno de texto [V-busca] (https://learn.chatgpt.com/codex/pricing).
   - Login no Codex por chave de API tira o limite, mas é pago à parte: fica como escolha de quem usa.

Nada disso tem prova a 96 px ainda. Os testes da seção 3 medem, com o portão e o revisor do horys, se a grade nativa
no Codex supera os 65–84% do parado e os 46–55% da animação.


## 1. O que foi achado, por item do pedido

### 1.0 PRIORIDADE: 3D → pixel art com o Blender pelo Claude (boas práticas do Noct 3D)

**Origem:** relato de terceiro ("gerar os modelos com o Claude usando o Blender, extraindo as boas práticas do Noct 3D
deu pixel art bem bacana").

**Por que é a aposta mais forte dentro da restrição [I]:**
- Precisa só do Claude e do Blender, que é grátis e já está instalado: `C:\Program Files\Blender Foundation\Blender 5.2`.
- Ataca três das quatro causas do teto:
  - renderiza direto em 96 px, sem redução;
  - o modelo e o esqueleto mantêm escala, chão e passada em todos os quadros e vistas;
  - o Claude fecha o loop sozinho (modela, renderiza, mede, corrige), sem gerar imagem.

**O que a pesquisa achou:**
- **Nenhum relato público com prova** de "Claude modelou no Blender e virou pixel art boa" para personagem ou criatura.
  O relato do terceiro continua sem confirmação. Fizemos várias buscas, inclusive em japonês.
- **Relatos sobre Blender MCP [R]:**
  - funciona bem: cena, materiais, câmera, scripts e hard-surface;
  - falha: formas orgânicas, curvas de animação livres, rig com pesos e "anything requiring visual judgment"
    (MindStudio, 06/05/2026, https://www.mindstudio.ai/blog/claude-blender-mcp-real-world-performance);
  - humanoide de primitivas parece "mannequin";
  - r/aigamedev (05/2026): Claude "can handle simplistic shapes on blender".
- **[I]** O golem é quase todo hard-surface (blocos, placas, punhos, pedras), o que pesa a favor. O crânio e o
  detalhe fino continuam sendo o risco: foi onde o Kiln parou (46%).
- **A técnica de 3D → pixel no Blender está bem documentada** (detalhes abaixo). O caso Dead Cells mostra que ela
  funciona em personagem de ~50 px, com detalhe baixo e cintilação aceita.

**Servidores MCP do Blender:**

| Servidor | Licença | Blender | O que expõe | Risco |
|---|---|---|---|---|
| **Oficial, Blender Lab** (https://www.blender.org/lab/mcp-server/) | GPL-3.0+ [R] | **5.1+** [V] | leitura da cena, `bpy`, screenshot do viewport [R] | roda o código do LLM "without any guards" [V]: a página recomenda VM ou máquina sem dados sensíveis |
| **ahujasid "MCP for Blender"** (https://github.com/ahujasid/blender-mcp) | MIT [V] | 3.0+ | `execute_blender_code`, `look` (viewport, câmera, render), `get_scene_info`, assets do Poly Haven/Sketchfab, geradores 3D pagos | socket sem autenticação, telemetria ligada por padrão, 4 CVEs em 2026 [R] |

- **Instalação do comunitário [V]:** `claude mcp add blender uvx mcp-for-blender`.
- **[I] Não precisamos de MCP para começar.** O Claude Code roda o Blender sem interface:
  `blender --background --python receita.py -- <args>`.
- **Vantagens do modo sem interface:**
  - é determinístico, como o Noct 3D pede (receita salva, não Python inline);
  - não abre socket nenhum;
  - não instala nada;
  - o Claude "vê" o resultado pelo PNG renderizado e pelo portão do horys.
- O MCP oficial fica como extra, para ajustes interativos no viewport. Instalá-lo é download e pede autorização.

**Técnica de render [V/R]:**
- **Resolução:** final pequena (ex.: 192×192 com a figura em 96 px).
  - EEVEE com Render Samples = 1 e View Transform = **Standard**, para a cor sair exata
    (https://bnpr.gitbook.io/bnpr/pixel-art/pixel-art-basics) [V].
  - No Cycles, Filter Size ~0 [R].
  - O nó Pixelate do compositor ainda faz antialias (https://studio.blender.org/blog/3d-pixel-art-in-blender,
    06/06/2024) [V]: renderizar no tamanho final, não pixelar depois.
- **Câmera:** ortográfica.
  - O `blender-sprite-render` (MIT, sem interface) usa inclinação de 55–60° e yaw por direção N/S/E/W
    (https://github.com/coreway-labs/blender-sprite-render) [V].
  - [I] Calibrar a inclinação com a ficha boss do horys (vista 3/4 de cima, topo da cabeça e dos ombros visível).
- **Toon:** Diffuse → Shader to RGB → Color Ramp **Constant**, com as paradas nas cores da subpaleta. Só no EEVEE
  (https://blog.gskinner.com/archives/2020/05/shader-rgb-node.html) [R].
  - [I] A alternativa do Noct 3D é a sombra pintada na textura, com material emission (sem luz de cena). Elimina a
    cintilação que a luz cria ao mover o corpo.
- **Contorno:** [I] em pós, pelo `horys_contorno`, sobre a silhueta já no tamanho final.
  - O Freestyle e a casca invertida em baixa resolução são instáveis [R].
  - O Noct 3D faz linha pixel-perfect sem pixel em L e com vizinhança 4, que é a mesma regra do horys.
- **Cintilação (pixel creep):** câmera ortográfica + posição do root presa ao tamanho do texel
  (https://propixelizer.github.io/docs/usage/eliminate-pixel-creep) [R].
  - [I] Num handler de quadro, arredondar o root para `ortho_scale / altura_px`.
  - Usar poucos tons no ramp.
  - O motor de sequência (anticintilação, A13) mede o que sobrar.
- **Addons grátis:**
  - Pixel Art Rendering (Lucas Roedel, atualizado para o 5.0): https://lucasroedel.gumroad.com/l/pixel_art
  - Lospec Blender Toolkit: https://lospec.com/blender-toolkit
  - Sprite Sheet Generator (GPL): https://extensions.blender.org/add-ons/sprite-sheet-generator/
  - [I] Não são necessários: tudo acima cabe numa receita `bpy` própria.

**Rig e animação [V/I]:**
- O Rigify pode ser gerado por script (`bpy.ops.pose.rigify_generate`) [V]
  (https://docs.blender.org/manual/en/4.0/addons/rigging/rigify/basics.html).
- **Para o golem não precisa:** peças rígidas, cada uma filha de um osso, sem pesos. É o "transform group" do Noct 3D,
  sem deformação nem costura [I].
- O andar é uma função `bpy` com **4–6 poses-chave** pedidas em números (ângulos e alturas, não curvas livres),
  interpolação CONSTANT ou LINEAR e pose a pose, como o Dead Cells.
- Os relatos dizem que o LLM erra curvas livres [R].
- O Mixamo exige conta Adobe e é para humanoide: fere a restrição.

**Boas práticas do Noct 3D**
- Pacote local: `C:\Users\artur\Downloads\noct-asset-forge-3d-bb-v2\noct-asset-forge-3d-bb-v2`.
- Ele **não usa Blender**: é Python puro, gera `.bbmodel` e GLB, e faz a prévia em Three.js.
- Licença proprietária: uso interno livre, redistribuir é proibido (`LICENSE:20-31`). **Copiar as regras, não o
  código.**

Práticas, por prioridade:
1. **Receita salva, determinística e com seed fixa; nunca Python inline.** Um script por etapa: modelo, materiais,
   rig, animação, render. Re-rodar só a etapa pedida (`AGENTS.md:3`, `docs/pipeline.md:20-21`).
2. **Convenções fixas:** chão em 0, frente fixa, `_L`/`_R` no fim do nome; construir um lado e espelhar
   (`.agents/skills/forge-3d-model/SKILL.md:17-34`).
3. **Escala ligada ao pixel final.** Fixar unidades por pixel e derivar a menor peça permitida. No Noct, "polygon
   collapses at UV density 1" (`forge-3d-model/references/errors.md:39`). Para 96 px: runa, dente e olho com ≥ 2 px.
4. **Peças rígidas por grupo de transformação**, não armadura com pesos (`forge-3d-model/references/rigging.md:6-11`):
   - pivô exatamente no plano da junta;
   - seções diferentes dos dois lados da junta;
   - folga entre peças, sem faces coplanares
     (`forge-3d-model/references/box-modeling.md:29-36`, `lib/geometry_validation.py:125-182`).
   - Isso evita as frestas e degraus que derrubaram o rig de partes 2D (55%).
5. **Sombra pintada e quantizada em vez de luz de cena:** uma luz fixa, ambient e bandas duras com a paleta fechada
   (`Tools/TexturePainter/fields.py:400-427`, `forge-3d-texture/references/procedural-fields.md:53,73`). Render
   unlit ou emission.
6. **Textura a 1 texel = 1 px final**, contínua entre faces e pensada no espaço do modelo (`lineart.md:5-12`):
   - rachaduras por `cells` sobre `fbm` (receita de pedra pronta, `procedural-fields.md:90`);
   - escurecer dobras e contatos entre blocos (`texture-painter-api.md:101-102`).
   - É aqui que entram as placas, juntas e runas que faltaram ao Kiln.
7. **Linha pixel-perfect:** sem pixel em L, espessura exata, vizinhança 4 (`lineart.md:37-45`).
8. **Pé plantado por IK com `pin`, joelho com direção explícita**, quadril animado antes das pernas; fechar o loop e
   conferir o contato depois de suavizar (`forge-3d-animation/references/animation-api.md:23,29-49,73`).
9. **Portão numérico de movimento antes do visual** (`lib/ik.py:498-511`):
   - cut: > 150°/s;
   - tip jolt: > 3 comprimentos de cadeia por segundo;
   - snap: alcance > 99,8% com o joelho ainda a 90°/s;
   - pop: > 720°/s.
10. **Conformidade:** primeiro os números (bbox, pés no chão, pivôs); depois o render clay ao lado da referência, com
    correção por parte (`forge-3d-visual-conformance/SKILL.md:10-28`).
11. **Lint de silhueta:** evitar tubo reto uniforme e face esticada (`errors.md:31-33`). É o antídoto para o "cara de
    robô".
12. **Golden bit a bit** dos sprites aprovados, para pegar regressão quando a receita muda (`tests/test_pixel_golden.py`).
13. **Tokens de estilo num lugar só** (paleta de 16, linhas) e um `STYLE.md` para o resto (`theme.md:14-20`).

O Noct 3D não tem nada de vista 3/4 top-down, amostragem de quadros para sprite ou redução. Essa parte é nova.

**Onde o detalhe fino entra (decisão do teste) [I]:**
- (a) **Textura UV pintada a 1 texel = 1 px**, com filtro Closest, pela receita (prática 6). Fica tudo no 3D e
  consistente em todas as vistas e quadros.
- (b) **Render só da massa, da sombra e da silhueta**, e o crânio, o medalhão e as runas como decalque fixo por vista,
  pela trava de identidade do motor de sequência (`sequencia/identidade.py`), recortado de um parado aprovado.
- Testar (a) primeiro. A (b) é o plano B, porque já funcionou na r5 (o decalque subiu o L4).

**Diferença em relação ao Kiln, que é a mesma ideia e deu 46% [I]:**

| | Kiln | Blender pelo Claude |
|---|---|---|
| Forma | primitivas em YAML | malha de verdade: bisel, extrusão, polígonos irregulares, modificadores |
| Detalhe | shading 3D, sem superfície | textura na densidade do pixel (placas, juntas, runas) |
| Vista | o render `e` falhou por corte no topo | câmera livre, 3/4 top-down calibrada |
| Loop | sem conformidade visual | clay ao lado do `conceito.png`, correção por parte |

Se a forma e a textura não ficarem melhores que as do Kiln, o teto vai ser o mesmo. É isso que o teste B mede
primeiro.

### 1.1 PixelLab (pixellab.ai)

**O que gera [V]** (https://api.pixellab.ai/v2/llms.txt, https://api.pixellab.ai/mcp/docs):
- **Personagem:** `create-character-v3`, em 8 rotações por padrão (também 4 ou 8 direções explícitas), além de `-pro` e `-pro-flash`.
- **Animação:**
  - `animate-character`: por template (`walking`, `breathing-idle`, `taking-punch`…), por texto (v3) ou por esqueleto (`animate-with-skeleton-v3`, `estimate-skeleton`);
  - `edit_animation` e `transfer_outfit`.
- **Tiles:** tileset top-down e sidescroller, tile isométrico, `map-objects`.
- **Edição e estilo:** `inpaint-v3` e `generate-with-style-v2` (estilo por 1–4 imagens de referência).
- **No MCP, também:** `image_to_pixelart(_pro)`, `reduce_colors`, `correct_pixelart` e `unzoom_image`.

**Tamanhos, no nosso alvo [V]:**
- **Personagem:**
  - v3: 32–256 px, em múltiplos de 4;
  - pro: 32–168 px, custa 10–25 gerações;
  - standard: até 128 px, guardado num quadro ~40% maior (64 → 92×92), então é preciso recortar e alinhar o chão.
- **Animação:**
  - v3: 4–16 quadros pares, com `w×h×quadros ≤ 8×256×256` (96×96 cabe com folga);
  - esqueleto: 3–15 quadros, quadro de 16 a 256, opção "fixed head: always";
  - "Animate with text (Pro)" de 65–128 px: **só 4 quadros** (grade 2×2);
  - **interpolação só a 64×64**;
  - "animation to animation" até 128, com o aviso "expect manual cleanup" (https://www.pixellab.ai/docs/tools/skeleton-animation).
- **Vista [V]:** `view` = `"low top-down"` (~20°, "classic 3/4 RPG", padrão), `"high top-down"` (~35°), `"side"` ou `"oblique"` (beta).
- **Paleta [V]:**
  - `palette`: 2–256 cores hex ("Every pixel the tool draws is one of them");
  - `max_colors`: 2–64;
  - em `create_character` e `animate_object`, as duas opções **exigem `mode='pro'`**;
  - contorno, sombra e detalhe são só dica.
- **Custo por chamada [V]:**
  - template: 1 geração por direção até ~92 px, mais acima disso;
  - v3: `ceil(w*h*quadros/65536)` por direção (96–128 px = 2–3);
  - esqueleto: 2–4;
  - pro: 10–25.

**Integração [V]:**
- **API v2:** `https://api.pixellab.ai/v2`, `Authorization: Bearer`.
- **SDK Python `pixellab`:** aponta para a **v1** e não tem release (https://github.com/pixellab-code/pixellab-python). Para a v2, chamar o REST direto.
- **MCP oficial:**
  - remoto, em `https://api.pixellab.ai/mcp` (stdio via `npx mcp-remote@latest`);
  - exige assinatura;
  - jobs assíncronos de 2–5 min (https://github.com/pixellab-code/pixellab-mcp).
- **Extensão de Aseprite:** baixada pela conta; exige Aseprite 1.3+.
- **Termos §2.2 [V]:** "Programmatic usage is only allowed through our official API". Automatizar o site ou a extensão viola os termos.

**Preço:**
- **[R]** Sem página oficial legível (`/pricing` dá 404; a home mostra "Loading subscription plans…"). Valores de terceiros (https://app.cinevva.com/guides/ai-pixel-art-generators, https://ai.g2.com/marketplace/tools/pixellab):
  - Tier 1: US$ 12/mês, ~2.000 gerações;
  - Tier 2: US$ 24/mês;
  - Tier 3: US$ 50/mês, 10.000 gerações;
  - trial de 40 gerações.
- **[V]** Ferramentas Pro e o esqueleto exigem Tier 1+ (https://www.pixellab.ai/llms.txt). Limite de taxa não publicado.

**Licença [V]** (https://www.pixellab.ai/termsofservice, "Last Updated: 2026-10-30"):
- §1.3: "You own the copyrights to your creations", com uso comercial.
- §4.1: o uso segue a licença Open RAIL-M.
- **§1.2 e §3.3: é proibido treinar modelos com as saídas sem permissão.** Isso conflita com o `horys treino` (LoRA treinado com os aprovados do estilo): asset que nasceu no PixelLab não pode entrar no conjunto de treino.

**Qualidade [R]:**
- r/aigamedev: "every sprite needs some love", "consistency wasn't there for generating sprite animations", "AI is generally pretty bad at pixel art but [PixelLab] is ok" (snapshots de 2025–2026: https://reddit.sentinel-team.org/posts/1r8owqw/snapshots/2026-02-21T05%3A50%3A01.663559Z, https://reddit.sentinel-team.org/posts/1rjnp3r/snapshots/2026-03-06T19%3A43%3A57.140654Z).
- Não achamos teste público a 96 ou 128 px.
- O PixelDoll (`C:\Users\artur\workspace\repos\PixelDoll`) já usou o PixelLab e travou em arma na mão e apoio do pé (`resumo.md`). Isso é sinal de que a animação precisa do motor de sequência e do portão depois.

**Como plugar no horys [I]:**
- `horys_referencia_gerar(fonte: "pixellab")` chama o REST v2 com `view`, tamanho, `palette` (a subpaleta do estilo) e a base aprovada como referência.
- Grava o PNG em `entrada/`, como o painel já faz (1.3).
- Para a animação, `fonte` do `horys_sequencia` vira a tira devolvida.
- Preferir o **REST, não o MCP deles**: o loop gerar → portão → corrigir fica dentro do horys, com polling e sem um segundo servidor.

### 1.2 Retro Diffusion

**Modelos e preços da API [V]** (https://github.com/Retro-Diffusion/api-examples, https://www.retrodiffusion.ai/):

| Modelo | Tamanho | US$/imagem | Útil para nós |
|---|---|---|---|
| RD Pro (`rd_pro__topdown`, `_spritesheet`, `_edit`, `_pixelate`) | 12–256 px (sheet e edit: 64–256) | 0,18 | parado nativo a 96 px, até 9 `reference_images` |
| RD Plus (`_topdown_asset`, `_character_turnaround`) | 64–384 px | 0,06 | turnaround (frente, lado) |
| RD Fast | 64–384 px | 0,03 | rascunho barato |
| `rd_advanced_animation__walking/idle/attack` (de uma imagem parada) | entrada 32–256 px, 4–16 quadros | 0,14 | **andar a partir da base aprovada** |
| `rd_advanced_animation__custom_action`, `subtle_motion` | idem | 0,25 | golpe, morte |
| `rd_animation__four_angle_walking` (só texto) | **só 48 px** | — | não serve |
| `rd_animation__big_animation` (só texto) | 128 px | 0,25 | talvez |

- **Paleta [V]:** `input_palette` (base64) restringe as cores; `return_pre_palette` devolve também a imagem antes da quantização.
- **API [V]:**
  - `POST https://api.retrodiffusion.ai/v2/inferences`, cabeçalho `X-RD-Token`;
  - `check_cost: true` consulta o preço sem cobrar;
  - também está no Replicate desde 19/11/2025 (https://replicate.com/blog/retro-diffusions-pixel-art-models-are-now-on-replicate).
- **Preço [V]:**
  - saldo pré-pago a partir de US$ 5, sem assinatura, que não expira;
  - conta nova ganha US$ 0,50;
  - ferramentas grátis: K-Centroid Downscale, Color Reducer, Palette Converter e Pixel Art Fixer.

**Extensão de Aseprite local [V]** (https://astropulse.itch.io/retrodiffusion):
- US$ 65, compra única, roda na GPU local (64×64 em ~5 s numa RTX 3060).
- O desenvolvedor informa 4 GB de VRAM como mínimo [R].
- **Não anima** ("The extension can't handle any kind of animation, but the website can").
- O devlog de **24/08/2026** anuncia que a extensão está sendo descontinuada em favor de um editor próprio.
- Conclusão [I]: não vale comprar agora.

**Licença [V]:** "You own your outputs and can use them in personal and commercial projects alike" (site). A página
`/terms` não carregou: **lacuna**.

**Qualidade [R]:**
- Ferramentas desse tipo são "mainly tuned for bipedal humans and usually only give you idle/walk cycles" (r/aigamedev, 03/2026).
- O golem é bípede, o que ajuda [I].
- Não achamos avaliação independente a 64–128 px.

### 1.3 Modelos abertos no ComfyUI (RTX 3060 Laptop, 6 GB)

**O que cabe em 6 GB:**

| Modelo | VRAM / tempo | Licença | Para nós |
|---|---|---|---|
| **FLUX.2 [klein] 4B** (GGUF) | 3060 Laptop 6 GB + 32 GB de RAM: 20–30 s por edição [R] (https://reddit.sentinel-team.org/posts/1rttjxg/snapshots/2026-03-17T00%3A19%3A08.427431Z); bf16 oficial ~13 GB [V] | **Apache 2.0** [V] (https://huggingface.co/black-forest-labs/FLUX.2-klein-4B) | texto→imagem e **edição com várias referências**; o melhor candidato local |
| FLUX.2 klein 9B | grande demais | não comercial | descartar |
| Flux.1 dev GGUF Q4 | ~1,5–2,5 min por imagem [I, a partir de relatos em 3050/3060 Ti] | não comercial (pesos) | lento |
| Kontext dev NF4/GGUF | ~7 GB [R]; sem confirmação em 6 GB | pesos não comerciais | incerto |
| Qwen-Image-Edit-2511 | Q4 = 13,1 GB [V]; Nunchaku 4-bit ~8 GB [R] | Apache 2.0 | só com offload pesado |
| SDXL + IPAdapter + ControlNet (o que existe hoje) | apertado; cada ControlNet SDXL ~1,4 GB [R] | OpenRAIL-M | já testado (r4/r5) |
| Wan 2.2 TI2V-5B GGUF | Q4 3,2 GiB [V]; "~6 GB" para 81 quadros [R] | Apache 2.0 | vídeo; lento e fora da grade |
| AnimateDiff SDXL | ~12–13 GB [R] | — | não cabe |

**LoRAs de pixel art:**
- **SDXL `nerijs/pixel-art-xl`** [V] (https://huggingface.co/nerijs/pixel-art-xl):
  - escala fixa: "Downscale 8 times… (use Nearest Neighbors)";
  - OpenRAIL-M;
  - não gera sprite sheet.
- **FLUX.2 klein 4B-base "Pixel Art Spritesheet – 4-Walk Small"** [V] (https://huggingface.co/svntax-dev/pixel_spritesheet_4walk_small_lora_v1):
  - andar em 4 direções;
  - **personagem de 32 px**, gerado a 512 e reduzido 4× com k-centroid;
  - há uma versão "mais criativa para não humanoides em modo edição";
  - licença do LoRA não declarada.
- **Qwen-Image-Edit-2511:** SpriteForge (troca o personagem de um template de sprite sheet 4×4) e `Leon1000/pixel_spritesheet_4walk_combat_32x48_v1` [R]. Licenças não verificadas, e não cabem bem em 6 GB.
- **SD1.5 `Onodofthenorth/SD_PixelArt_SpriteSheet_Generator`** [V]: Apache 2.0, 4 vistas, mas sem 3/4 e fraco.

**Gerar já na grade [V/I]:**
- **O princípio:** um LoRA treinado com fator fixo (8× no pixel-art-xl, 4× no 4-Walk) desenha blocos N×N, e a redução fica exata.
- Para 96 px, gerar a figura com 384 px (4×) ou 768 px (8×) de altura, não com 1400 px arbitrários.
- **Ferramentas de redução exata:**
  - `unfake`, Python/Rust, MIT [V] (https://pypi.org/project/unfake/): detecta a escala por Sobel, alinha a grade, reduz pela cor dominante e quantiza por Wu;
  - ComfyUI-Unfake-Pixels [V] (https://github.com/tauraloke/ComfyUI-Unfake-Pixels);
  - Pixel Snapper (Sprite Fusion), MIT [V] (https://github.com/Hugo-Dz/spritefusion-pixel-snapper);
  - ComfyUI-PixelArt-Detector [V] (https://github.com/dimtoneff/ComfyUI-PixelArt-Detector);
  - K-Centroid, extensão de Aseprite da Astropulse [V] (https://astropulse.itch.io/k-centroid).
- [I] O `unfake` é a peça que falta no `horys_converter`: detectar a grade em vez de assumir moda num fator não inteiro.

**Consistência:**
- Edição por referência (klein 4B, Qwen-Edit, Kontext) é o caminho atual para "mesmo personagem, nova pose" [V: o klein aceita várias referências].
- O PuLID é para rosto humano: descartar.
- O ControlNet de pose animal só existe em SD1.5 [R].
- O openpose xinsir que já está instalado serve para boss bípede [I].

**Treinar LoRA em 6 GB:**
- SD1.5 funciona: ~1–2 h para 100 imagens [R] (https://lilting.ch/en/articles/rtx3060-lora-training-guide, 11/12/2025).
- O treino do klein 4B pede no mínimo 12 GB de VRAM [V] (https://docs.bfl.ai/flux_2/flux2_klein_training).
- SDXL e Flux em 6 GB não estão comprovados.
- Conclusão [I]: um LoRA do estilo Horys só em SD1.5 local ou em GPU alugada, como `docs/treino.md` já prevê.

### 1.4 Geradores dentro do loop do agente (API)

| Gerador | Modelo atual (nov/2026) | Referências | Fundo transparente | US$/imagem 1K | Fonte |
|---|---|---|---|---|---|
| Google Gemini API | Nano Banana 2.1 (`gemini-nano-banana-2.1`) | até 14 (10 de objeto + 4 de personagem); "melhorado para consistência multi-turn" | não (chroma) | 0,0336; batch 0,0168 | [V] https://aistudio.google.com/docs/pricing, https://aistudio.google.com/docs/image-generation |
| Google Gemini API | Nano Banana Pro (`gemini-3-pro-image`) | 6 de objeto + 5 de personagem + 3 de estilo | não | 0,134 | [V] idem |
| OpenAI Images API | `gpt-image-2.5` Flare/Sunburst (`gpt-image-1` desligado em 2026-10-23) | várias em `/v1/images/edits`, máscara | **sim**, `background: "transparent"` | ~0,013 (medium) a ~0,053 (high) | [V] https://developers.openai.com/api/docs/guides/image-generation; preço por imagem [R] |
| BFL | FLUX 3 / FLUX.2 pro | até 10 | não documentado | 0,048 (FLUX 3); FLUX.2 pro 0,03 + 0,015 por referência | [V] https://bfl.ai/pricing |
| Recraft | V3, estilo `Pixel art` | só estilo, não conteúdo | remoção à parte | 0,04 | [V] https://www.recraft.ai/docs/api-reference/styles |
| fal.ai / Replicate | agregadores (Qwen-Edit, Nano Banana, RD…) | depende | depende | por uso | [R] |
| Midjourney | sem API oficial; termos proíbem automação | — | — | — | [R] |

Pontos que mudam o fluxo:
- **Codex:**
  - **[V-busca]** Com login por chave de API, a imagem do Codex é cobrada no preço da API, fora da cota do plano (https://learn.chatgpt.com/codex/pricing).
  - Isso resolve a cota sem trocar de ferramenta: o `fonte: codex` atual continua servindo.
  - Na cota do plano, uma imagem gasta 3–5× mais que um turno de texto.
- **Gemini:**
  - **[V]** A API não tem tier grátis para imagem.
  - O SynthID (marca d'água invisível) vai em todas as imagens.
- **MCP de geradores:**
  - **[V]** A BFL tem MCP oficial: `claude mcp add --transport http FLUX https://mcp.bfl.ai` (https://docs.bfl.ml/api_integration/mcp_integration).
  - OpenAI e Google não têm MCP oficial de imagem.
  - Os comunitários existem (shinpr/mcp-image) [R].
  - [I] Chamar o SDK direto de dentro do horys é mais simples e mantém o portão no loop.
- **Relatos de sprites:**
  - Funcionou quando: mesmo chat, uma pose por chamada, base aprovada sempre anexada, linha do chão fixa e fundo liso (https://geekvibesnation.com/nano-banana-pro-sprite-sheets-make-the-walk-cycle-work/, 05/10/2026; https://dev.to/kenjidev9662/practical-workflow-for-ai-pixel-art-gemini-2d-animation-experiment-21le, mar/2026).
  - Falhas comuns: pé deslizando, cabeça mudando de tamanho, acessório trocando de lado e fundo xadrez falso [R].
- **[V] Por que a escala varia entre poses** (https://www.spritecook.ai/blog/why-ai-cant-match-pixel-art-resolution, 26/08/2026):
  - esses modelos desenham "pictures of pixels" em ~1024 px e, a cada pose, escolhem outra grade;
  - um personagem de 158 px voltou com cara de 80 px;
  - repetir raramente ajuda.
  - Isso explica as três grades reprovadas no portão de entrada em 09/11.

**Resumo [I]:** os geradores gerais resolvem o "Artur à mão" (o loop fecha sozinho), mas **não** resolvem a redução, que
continua apagando rosto e detalhe. Servem como fonte do conceito e das poses quando a fonte nativa falhar.

### 1.5 Animação de pixel art com IA

| Ferramenta | O que faz a 96 px | Evidência |
|---|---|---|
| PixelLab, esqueleto | quadro até 256, 3–15 quadros, "fixed head", poses por esqueleto; recomendado pela própria doc para personagem | [V] https://www.pixellab.ai/docs/tools/skeleton-animation |
| PixelLab, texto v3 / template `walking` | 4–16 quadros a 96 px, 2–3 gerações por direção | [V] |
| PixelLab, interpolação | só 64×64 | [V] |
| Retro Diffusion `rd_advanced_animation__walking` | entrada até 256, 4–16 quadros, a partir da imagem parada | [V] |
| Retro Diffusion, andar só por texto | 48 px fixo | [V] |
| God Mode AI | rig Spine automático a partir de uma imagem | [R]; é o nosso rig de partes (55%) [I] |
| Ludo.ai, SEELE, AutoSprite, Sorceress | marketing, números conflitantes; a Sorceress usa vídeo de IA por baixo | [R] |
| **"Neural Controlled Directional Frame Generation for Sprite Animation"** (Alonso e Patow, Girona) | interpolação RGBA a **128×128**, sem difusão; código aberto (`NethamGH/deepinterframes_neural_sprite_inbetweening`) | [V] https://arxiv.org/html/2610.27253 (19/10/2026) |
| ToonCrafter | interpolação de desenho animado a 512×320; nenhum teste em pixel | [V] https://arxiv.org/abs/2405.17933 |

- **Interpolação de Girona, números [V]:**
  - FLIP de 0,258 no quadro do meio, contra 0,313 do RIFE;
  - falha em rotação acima de 45°, em oclusão e em partículas;
  - só 280 trios de treino, com dados fechados;
  - 8–10 s por quadro numa T4.
- **Vídeo → quadros:**
  - [R] O Veo foi "unusable for sprite animation" (https://blog.makko.ai/how-to-make-ai-sprite-animations-that-match-the-rest-of-your-game/).
  - [R] O Wan 2.1 cintila em pixel art (thread do r/StableDiffusion).
  - Ferramentas como mp4tosprite e Sorceress True Pixel aplicam paleta única e mediana temporal [R]. A mediana temporal tira a cintilação, mas também o impacto do movimento [I].
  - Para nós, o vídeo ficou **abaixo do 3D** (sem controle de chão e com mais cintilação) [I].
- **Esqueleto e 3D → pixel:** ver 1.7 (Dead Cells). O horys já testou: Kiln 46%, rig 55%.

### 1.6 "PixelLab do Artur" (app próprio)

**O que seria:**
1. Gerador local: FLUX.2 klein 4B GGUF com edição por referência, gerando na escala 4× do alvo.
2. Redução exata (`unfake` ou Pixel Snapper) e a subpaleta do estilo.
3. Pós-processo do horys: motor de sequência, limpeza, contorno, portão e revisor.
4. UI: o painel do Aseprite, que já existe.
5. Para animar: Kiln ou esqueleto como guia de pose, passado ao klein por edição (pose + base aprovada), e o motor de sequência para travar a identidade.

**Peças que já existem no repo [V, código]:**
- `sequencia/` (registro, quantização conjunta, trava de identidade, anticintilação, limpeza);
- `entrada.py`;
- `traducao.py`;
- `horys_guia_poses`;
- o painel e os pedidos;
- `treino/` (kohya, perfis por GPU).

**Falta:**
- o fluxo ComfyUI do klein (workflow JSON chamado pela API do ComfyUI, como o `mix_cn_full.py` da r5);
- a redução por grade detectada no `horys_converter`;
- um modo "nativo" no portão de entrada (escala 1×).

**Esforço [I]:**
- 1–2 semanas para um protótipo que roda.
- O risco está na qualidade, não no código.

**Riscos [I]:**
1. O klein 4B a 6 GB ainda não foi medido aqui (só um relato de 20–30 s).
2. Os LoRAs de sprite sheet são de 32 px; um boss de 96 px provavelmente sai pose por pose, e aí volta o problema da escala variando entre poses.
3. Não há LoRA do estilo Horys: o SD1.5 é o único treinável local, e é fraco.
4. Cada modelo novo exige baixar pesos de terceiros (autorização do Artur).

**Em resumo [I]:** é o caminho sem dependência, mas é o mais incerto. Vale **depois** de saber, pelos testes A e B, se
gerar nativo resolve. Se resolver, o app próprio passa a ter uma meta concreta: igualar o PixelLab.

### 1.7 Pixel art "de verdade" com IA: o que estúdios fazem

- **Dead Cells** [V] (Thomas Vasseur, Game Developer, 25/01/2018, https://www.gamedeveloper.com/production/art-design-deep-dive-using-a-3d-pipeline-for-2d-animation-in-i-dead-cells-i-):
  - modelo 3D simples com esqueleto, renderizado **bem pequeno e sem antialias**, com toon shader pelo normal, numa ferramenta caseira;
  - personagem de **~50 px**;
  - animação pose a pose, com quadros extras só antes ou depois das chaves;
  - **a cintilação de pixels "nunca foi resolvida"**: eles aceitaram e abriram mão de detalhe.
  - [I] A 96 px e 16 cores a cintilação aparece mais. Isso explica o teto do Kiln (46%).
- **Ferramentas de 3D → pixel [V]:**
  - PixelOver, Godot, importa GLB/FBX, tem IK 3D, ossos 2D e indexação de paleta (https://store.steampowered.com/app/1762550/PixelOver/);
  - Pixel Renderer (BUKKBEEK), Godot 4.4, código aberto, 2–32 cores, contorno Sobel (https://80.lv/articles/free-open-source-3d-to-pixel-art-toolkit-for-godot, 23/07/2025).
  - Mesmo método do Kiln: mesmo teto [I].
- **Gerar grande e reduzir é o padrão do mercado** [V]: SpriteCook, unfake.js (https://dev.to/jenissimo/how-to-tame-your-ai-pixel-art-3pk5, 30/07/2025), K-Centroid. Nenhum deles trata consistência entre quadros; isso é o que o motor de sequência do horys faz.
- **Retoque manual em todo asset é a norma** [R]:
  - a Relish Games orça limpeza em todo asset e diz que a IA rende mais em cenário do que em sprite (https://relishgames.com/journal/generative-ai-for-2d-game-art-tools-and-techniques/);
  - Pixel Parmesan (08/11/2022) [V]: ~50% de ganho em peça grande e quase nada em sprite (https://pixelparmesan.com/ai-and-the-future-of-pixel-art/).
- **Não achamos entrevista formal** de estúdio (2024–2026) descrevendo IA na animação de pixel art em produção.

### 1.8 Bibliotecas de código (Python, Rust, Go, JS/TS), sem IA de imagem

Levantamento de memória, **não verificado na web nesta rodada** [I]. Conferir repo, licença e manutenção antes de usar.

**1. Geradores procedurais.** Montam sprite por regra: máscara, espelho e ruído.
- Exemplos:
  - o algoritmo de Dave Bollinger e o `pixel-sprite-generator` (JS);
  - geradores de naves, monstros e planetas (Deep-Fold "PixelPlanets", Godot).
- O que fazem: sprites de 8–32 px aleatórios, sem anatomia nem identidade.
- **Não fazem um boss de 96 px** com design definido.

**2. Conversores de imagem para pixel art.** Atacam a causa nº 1, a redução.
- **PixelOE** (Python): "detail-oriented pixelization" com expansão de contorno por contraste. Engrossa linhas finas
  *antes* de reduzir, para não sumirem. Tem modos de redução (k-centroid, contraste, mediana).
  É o mais próximo do nosso problema do rosto e das runas apagados.
- **unfake** (Python e Rust, MIT) e **Pixel Snapper** (Rust, MIT) [V, seção 1.3]: detectam a grade de "pixel falso"
  e reduzem exato.
- **pyxelate** (Python): redução com mistura gaussiana e dither.
- **Pixelization neural** ("Make Your Own Sprites: Aliasing-Aware and Cell-Controllable Pixelization", SIGGRAPH Asia
  2022; código em PyTorch): rede pequena, roda em GPU modesta. Licença a conferir.

**3. 3D/esqueleto renderizado em pixel.**
- O Kiln (já integrado), o Pixel Renderer do Godot e o PixelOver.
- Mesmo teto medido (~46%): ver 1.7.

**Conclusão [I]:**
- Nenhuma biblioteca **desenha** um boss orgânico de 96 px com qualidade só por código. A forma tem que vir de um
  gerador (Codex) ou de um artista.
- O que o código resolve é a **conversão**: PixelOE e a detecção de grade entram no `horys_converter` como modos de
  redução, testados no teste 1 contra a moda.

## 2. Tabela comparativa

**Com a restrição "só Claude ou Codex":** valem **0 (Blender)**, E (Codex), F, H, I e C/G só como extra local. A, B e D ficam como referência (serviços pagos de terceiros).


Alvo: boss top-down 3/4, ~96 px, 16 cores, parado e andar de frente e de lado.

| Opção | Qualidade esperada no alvo | Consistência entre quadros | Animação | Local ou pago | Custo mensal | Licença | Esforço no horys | Dependência |
|---|---|---|---|---|---|---|---|---|
| **Hoje:** conceito (Codex/manual) → moda → limpeza | 65–84% parado [medido] | — | 46–55% [medido] | pago (cota do Codex) ou manual | cota do ChatGPT | sua | feito | Codex/Artur |
| **0. Blender pelo Claude** (receitas bpy, regras do Noct 3D) | média–alta [I]: nativo 96 px; sem relato público com prova | alta: mesmo modelo e esqueleto em todos os quadros e vistas | sim, rig rígido + IK, pose a pose | local | 0 | sua; Blender GPL (só a ferramenta) | médio: receitas + `horys_converter` fator 1 | baixa |
| **A. PixelLab** (REST v2) | alta [I]: nativo 96 px, vista 3/4, paleta forçada; sem prova a 96 px | média [R]: queixa recorrente | esqueleto/template a 96 px, 4–16 quadros [V] | nuvem | US$ 12 (Tier 1) [R] | sua, comercial [V]; **proíbe treinar com as saídas** | baixo–médio: `fonte`, polling, portão "nativo" | alta (serviço fechado, preço instável) |
| **B. Retro Diffusion** (REST v2) | média–alta [I]: `rd_pro__topdown` nativo 96 px, `input_palette` | desconhecida | `rd_advanced_animation__walking` da imagem parada, até 256 [V] | nuvem | por uso: ~US$ 0,30–0,50 por pose + andar; teste < US$ 5 [I a partir dos preços V] | sua, comercial [V]; termos completos não lidos | baixo–médio | média (pré-pago, sem assinatura) |
| **C. FLUX.2 klein 4B local** + grade 4× + `unfake` | média [I]; não medido em 6 GB | média com edição por referência [I] | pose por pose + motor de sequência | local | 0 (energia) | Apache 2.0 [V] | médio–alto: workflow ComfyUI, download ~3–8 GB | baixa |
| **D. Gemini Nano Banana 2.1** no loop | igual a hoje no parado (ainda reduz) [I] | média com base anexada [R] | grade ou pose por pose; escala varia [V SpriteCook] | nuvem | ~US$ 3 por boss (10 tentativas × 8 poses) [I] | sua [V-busca] | baixo: SDK `google-genai` | média |
| **E. gpt-image-2.5** via API ou Codex com chave de API | igual a hoje (é o motor atual) | média | idem D | nuvem | ~US$ 0,01–0,05 por imagem [R] | sua [V-busca] | mínimo: `fonte: codex` já existe | média |
| **F. 3D/esqueleto → pixel** (Kiln, PixelOver, Dead Cells) | ~46% [medido] | alta na forma; cintila na pele | sim | local | 0 | sua | feito (Kiln) | baixa |
| **G. Vídeo → quadros** (Wan local, Veo/Kling/Omni) | baixa [R] | baixa: cintila, câmera e chão andam [R] | sim | local lento ou ~US$ 0,05–0,30 por ciclo | baixo | depende | médio (o motor de sequência já lê MP4) | média |
| **H. Interpolação de Girona** (entre poses-chave) | sem medida em pixel de 16 cores; FLIP 0,258 a 128 px [V] | a ver | só os quadros do meio | local (~618 MB) | 0 | código aberto [V]; checar licença | médio | baixa |
| **I. App próprio** (C + horys + painel) | igual a C, depois de afinado | igual a C | igual a C + H | local | 0 | sua | alto (1–2 semanas de protótipo) [I] | baixa |

## 3. Testes propostos com o golem-caveira (dentro da restrição)

**Linha de base medida hoje** (`~/.horys-pixel/experimentos/golem-caveira/`):
- O conceito passou no portão de entrada (14,6×, 22 grupos de cor).
- Das 7 versões do parado a 96 px, **só a v04 passou no portão de medidas**. As outras reprovaram em M05: as manchas
  de cor ficaram em média com 18 a 44 px, maiores do que o limite.
- O **M10 ficou em 19 degraus em todas** (régua ~11).
- Referências: o macaco-golem a 198 px deu 84% (v19) e 65% (fluxo 1.7); a animação ficou em 46–55%.

**Regras comuns:**
- **Entrada:**
  - a mesma subpaleta de 16 cores (`traducao/paleta-horys-pixel-liso.png`);
  - `conceito.png` como referência de identidade (arte do próprio Artur);
  - nada de arte de terceiros: o `Golem-Skeleton Walking Animation Sprite Sheet.png` da pasta **não** entra.
- **Saída medida** pelo `horys_portao_entrada`, pelo `horys_sequencia`, pelo `horys_portao` e pelo revisor
  `horys-pixel-liso-revisor`.
- **Registrar por rodada:**
  - nota L1–L7 e aceitação;
  - M05, M10 e A13 (pisca);
  - quique, pé deslizando e altura entre quadros;
  - versões até passar;
  - imagens gastas da cota do Codex.
- **Critério de parada:** 3 rodadas sem ganho de 5 pontos, ou ≥ 80% sem falha grave.
- **Quando:** a cota do Codex volta em 2026-11-12, 12h15. A preparação no código e o teste 0 podem ser feitos antes.

**Preparação no código** (não feita aqui; pede o ok do Artur):
1. `horys_converter` com `reducao: grade`: detecta o bloco e a fase da grade e reduz 1 bloco → 1 pixel pela cor
   dominante. Cai para moda se a detecção não for confiável. Teste com imagens sintéticas em blocos de 3, 4 e 8 com
   deslocamento.
2. Portão de entrada: nova medida "grade detectada" (tamanho do bloco, confiança, altura em blocos) e prévia com a
   redução por grade.
3. `horys_prompt_traducao` com modo `grade`: pede blocos de N×N e a altura em blocos, mantendo os 11 itens.

### Teste B: golem-caveira no Blender pelo Claude (PRIORIDADE 1)

**Custo:** zero. Usa o Blender 5.2 já instalado, sem interface, e não baixa nada.

**Onde:** `~/.horys-pixel/experimentos/golem-blender/`, com `receitas/` (um script por etapa) e `out/`.

**Etapas e marcos:**
1. **B1, modelo parado de frente:**
   - `receitas/modelo.py` modela o golem com peças nomeadas (`cranio`, `tronco`, `ombreira_L`, `punho_L`, `coxa_L`,
     `pedra_1`…).
   - Usa as regras do Noct: chão em 0, espelhar um lado, folga nas juntas, pivô no plano da junta, nenhuma peça abaixo
     de 2 px na projeção.
   - Referência de proporção: o `conceito.png` (arte do Artur).
   - Conformidade: render clay de frente ao lado do conceito, correção por parte, até 3 rodadas.
2. **B2, material e textura:**
   - `receitas/materiais.py`: toon Constant com as 16 cores da subpaleta (ou emission com sombra pintada).
   - Textura UV a 1 texel = 1 px para placas, juntas, espiral do crânio, olhos, medalhão e runas.
3. **B3, render:**
   - `receitas/render.py`: EEVEE, 1 amostra, Standard, fundo transparente, ortográfica 3/4 de cima.
   - Figura com 96 px num quadro de 192, pivô e chão da ficha.
   - Saídas: frente (S), lado (E) e costas (N).
4. **B4, horys:**
   - `horys_converter` com fator 1 (só trava de paleta e pivô) → `horys_contorno` (1 px `#18122c`) → limpeza →
     portão → revisor.
   - **Marco: parado de frente ≥ 75%**, comparado com a v04 da linha de base.
5. **B5, andar:**
   - `receitas/rig.py`: ossos, com cada peça filha de um osso.
   - `receitas/anim.py`: 8 quadros, 4 poses-chave em números (contato, passagem), IK com o pé preso, quique de 2–4 px,
     crânio e pedras com 1–2 quadros de atraso, root preso ao texel.
   - Portão de movimento (cut, jolt, snap, pop) antes de renderizar.
   - Depois, `horys_sequencia` (fator 1, anticintilação) → portão → revisor nas três vistas.
   - **Marco: andar de frente ≥ 65%**, acima do teto de 46–55%.

**Critério de parada:**
- Se B4 ficar abaixo de 60% depois de 3 rodadas, ir para o plano (b): render da massa + decalque do parado aprovado
  pelo teste 1.
- Se B5 não passar de 55%, o problema está na pose e no timing, não na fonte. Revisar as poses-chave com o Artur.

**O que precisa de ok:**
- Nada para B1–B4: só roda o Blender local.
- Instalar um MCP do Blender só se o modo sem interface travar algo (download).

### Teste 0: só a redução, sem gastar cota (prioridade 3)

**Precisa de autorização** para instalar o PixelOE (pip).

**Passos:**
1. Reduzir o `conceito_margem.png` atual para 96 px por três caminhos:
   - moda, que é o de hoje (v01);
   - PixelOE com expansão de contorno;
   - PixelOE com k-centroid.
2. Mesma subpaleta, mesma limpeza, portão e revisor.

**Hipótese:** o rosto e as runas sobrevivem melhor com a expansão de contorno, e o M05 cai.

### Teste 1: parado no Codex em grade nativa (prioridade 2)

**Custo:** 3–6 imagens da cota do Codex.

**Passos:**
1. `horys_prompt_traducao` em modo `grade`:
   - blocos de 4×4, golem com 96 blocos de altura;
   - vista 3/4 de cima, 16 cores da subpaleta, fundo liso;
   - `conceito.png` anexado.
2. O Codex gera 3 candidatos (`fonte: codex`).
3. Portão de entrada → redução por grade → limpeza → portão → revisor.
4. **Controle:** o mesmo candidato reduzido por moda e pelo vencedor do teste 0. Isso separa o efeito da redução do
   efeito do prompt.

**Hipótese:** M05 e M10 caem e o rosto do crânio sobrevive. Parado ≥ 75% na v01–v03. A hipótese cai se o Codex não
respeitar a grade (blocos de tamanhos misturados) ou se a detecção errar.

### Teste 2: andar de frente e de lado, uma pose por chamada

**Custo:** 8–16 imagens (4 poses-chave × 2 vistas, mais refazer).

**Passos:**
1. `horys_guia_poses` gera as silhuetas das 4 poses-chave a partir do Kiln, no mesmo enquadramento: contato E,
   passagem, contato D, passagem.
2. Cada pose é uma chamada ao Codex com 2 anexos: o parado aprovado do teste 1 e a silhueta da pose. O prompt pede a
   mesma grade, a mesma altura e o mesmo chão.
3. Redução por grade em cada pose → `horys_sequencia` (registro, trava de identidade do crânio e do peito,
   anticintilação) → portão → revisor.
4. **Controle:** as 4 poses numa grade única (o que reprovou em 09/11), medida igual.
5. Lado: repetir com a vista de lado como parado de referência.

**Hipótese:** pose por chamada + redução por grade acima de 55%, que é o teto atual. Os quadros do meio ficam para
depois.

### Teste 3 (opcional, local): FLUX.2 klein 4B + grade 4×

Só para quem tem GPU, como extra.

**Precisa de autorização** para baixar o klein 4B GGUF e o encoder (~3–8 GB, medir antes). Licença Apache 2.0.

**Passos:**
1. Mesmos prompts do teste 1 e do teste 2, em edição com referência no ComfyUI.
2. Mesma redução por grade.
3. Medir também o tempo por imagem na 3060.

**Por que vale:** se empatar com o Codex, quem tem GPU gera sem gastar cota.

### Teste extra: quadros do meio

Se as poses-chave passarem e os quadros do meio forem o problema, testar a interpolação de Girona (local, código
aberto, 128 px) [V] (https://arxiv.org/html/2610.27253). Checar a licença antes.

## 4. Recomendação

1. **Teste B primeiro: Blender pelo Claude, sem interface, com as regras do Noct 3D.**
   - Custo zero e nenhuma dependência nova.
   - É a única opção que ataca de uma vez a redução, a consistência entre quadros e vistas e o loop sem o Artur.
   - O risco conhecido é o mesmo do Kiln (forma em bloco e falta de detalhe). As respostas são malha de verdade,
     textura a 1 texel = 1 px e conformidade contra o `conceito.png`.
2. **Teste 1 em paralelo: Codex ou ChatGPT na web em grade nativa.**
   - Os prompts estão prontos em `~/.horys-pixel/experimentos/golem-caveira/teste1/prompts.md`.
   - Serve de comparação no parado e é a fonte do decalque, se o B precisar do plano (b).
3. **Teste 0 (PixelOE × moda)** só se o teste 1 mostrar que a redução ainda pesa.
4. **Se o B passar no andar:** o Blender vira a fonte padrão de boss e criatura. O Kiln e o rig de partes saem do
   caminho, e o Codex fica para conceito e decalque.
5. **Não fazer:**
   - serviço pago de terceiros como dependência;
   - os geradores 3D pagos do MCP comunitário (Rodin, Tripo, Meshy);
   - vídeo → quadros;
   - treinar LoRA SDXL/Flux em 6 GB;
   - app próprio antes de medir B e 1.
6. **Se nada passar de ~65% na animação,** aceitar poses-chave retocadas à mão (o acabamento marcado no Aseprite,
   Fase 4). É o que a evidência de mercado mostra (Dead Cells, Relish, Pixel Parmesan).

## 5. Em aberto

- **Qualidade real a 96 px:** nenhuma fonte pública mostra boss a 96–128 px em PixelLab ou Retro Diffusion. Só os testes A e B respondem.
- **Preço oficial do PixelLab e limites de taxa** dos dois serviços (página fora do ar ou não publicada).
- **Termos completos do Retro Diffusion** (`/terms` não carregou) e o anúncio de 24/08/2026.
- **PixelLab e o `horys treino`:** os termos proíbem treinar com as saídas. Decidir se assets vindos do PixelLab ficam marcados com a origem e fora do conjunto de treino; o `treino/conjunto.py` já registra origem e licença.
- **Klein 4B na 3060 Laptop:** só há um relato (20–30 s). Medir antes de apostar no teste C.
- **Vista de lado:** o PixelLab gera a direção E na mesma chamada. No RD, a vista de lado depende do turnaround ou de uma 2ª geração, e a consistência entre as duas vistas não foi testada.
- **Interpolação de Girona:** licença do código e o comportamento em paleta de 16 cores não foram verificados.
- **Nomes de modelos comerciais** (gpt-image-2.5, Nano Banana 2.1, FLUX 3) mudaram em 2026; conferir antes de integrar.
- **Fluxo Blender do terceiro:** não há relato público com prova. Vale pedir a ele um exemplo (sprite, tamanho, quantas
  cores) e como extraiu as regras do Noct 3D: textura pintada ou só forma? Contorno no 3D ou em pós?
- **Inclinação da câmera 3/4:** calibrar no teste B contra a ficha boss e a régua do projeto.
- **Noct 3D:** licença proprietária (uso interno livre). Reaproveitar as regras, não o código, num fluxo que vá para
  outras pessoas.


## 6. Resultado do teste B: golem-caveira no Blender pelo Claude (2026-11-09, noite)

Tudo em `~/.horys-pixel/experimentos/golem-blender/`; o estado detalhado está no `STATUS.md` de lá.

**Fluxo que funcionou ponta a ponta, sem o Artur e sem gerar imagem:**
1. receitas `bpy` (modelo, materiais, render, animação), sem interface, no Blender 5.2;
2. toon Constant com as 16 cores exatas (0 px fora da paleta), câmera ortográfica a 15°, EEVEE com 1 amostra;
3. pós mecânica (`pos.py`): linhas internas por salto de profundidade entre peças (passes de ID e profundidade),
   limpeza de manchas pequenas e contorno de 1 px;
4. horys: `horys_converter` 1:1 (`modo media`, `altura` = corpo + 4) → `horys_contorno` (suave) → `horys_portao`
   → revisor.

**Números:**

| Medida | Linha de base (conceito → moda) | Blender r07 (horys v04) | Blender r11 (horys v07) |
|---|---|---|---|
| Portão de medidas | só a v04 de 7 passou | aprovado na 1ª importação | aprovado |
| M10 (degraus irregulares; régua ~11) | 19 | sem aviso | 22 (espinhos finos) |
| M05 (mancha média) | 18–44 | 30,9 | > 30 |
| Revisor | (não medido nesta pasta) | **44%** | **50%** |

- **Andar de frente e de lado, 8 quadros** (a03):
  - mesma escala e mesmo chão em todos os quadros, por construção;
  - quique físico de 0 a −2,5 px, com o pé de apoio sempre no chão;
  - crânio, fumaça e pedras com 1 quadro de atraso.
- **A vista de lado ainda é fraca:** pilha de blocos e pé de trás solto na passagem. O andar não foi ao revisor.

**O que o revisor diz (rodada 2):**
- melhor que a linha de base na técnica: contorno e linhas de 1 px, paleta, sem borrão, simetria, contraste na
  grama de 48%;
- pior na identidade: corpo de caixas com faixas horizontais, cabeça que lê como "pessoa de chapéu" (calota creme e
  fumaça roxa colada), sem punhos, pelo invisível, espinhos finos, um "pilar" entre os pés.
- Pede `redesenhar_forma` **no modelo 3D, não no pixel**: "o fluxo Blender é a base melhor para corrigir, porque os
  defeitos estão no modelo 3D e não no pixel".

**Leitura [I]:**
- A hipótese "Blender resolve consistência e técnica" se confirmou.
- A hipótese "o Claude modela forma orgânica boa no 3D" ainda não: são os mesmos limites relatados na pesquisa (1.0).
- O que falta é modelagem: punhos, pelo em mechas, crânio com maxilar, shading por normal em cacho em vez de faixa.
- Pelo critério do teste B (abaixo de 60% depois de 3 rodadas → plano (b), decalque), falta 1 rodada para decidir.
