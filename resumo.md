# Resumo da sessão: gargalo de animação do Horys Pixel (boss macaco-golem)

Data: 2026-11-09. Repo: `C:\Users\artur\workspace\repos\horys\horys-generator-pixel`. Nada foi commitado nesta sessão; o trabalho novo está em `~/.horys-pixel/experimentos/golem-kiln/` (não versionado) e em `resumo.md`.

## Objetivo

Resolver o gargalo de **animação** de pixel art dos jogos do Artur e **reduzir a dependência do Codex** (cota estourada até **2026-11-12 12:15**). Alvo de teste: `walk` de frente do boss **macaco-golem** (quadro 320×320, pivô 160,212, altura 198–200 com contorno, contorno `#18122c` de 1 px, subpaleta `macaco-golem-16`). Base aprovada de identidade: `~/.horys-pixel/pedidos/20261108-193955-0b8b/poses/base_v19_8x.png` (84% no revisor).

## Ideia testada

**Kiln faz a base e o movimento** (modelo 3D procedural, YAML) e outra coisa faz a pele/acabamento. O Kiln já estava integrado ao Horys (`horys_importar_kiln`, `horys_paleta_kiln`, TODO fases 0–3).

## Resultados do revisor (`horys-pixel-liso-revisor`), walk de frente

| Rodada | Fluxo | Aceitação |
|---|---|---|
| 1 | Kiln 3D, caixas | 34% |
| 2 | Kiln 3D, crânio/runa/espinhos | 44% |
| 3 | Kiln 3D puro, junta de ombro, pelo, pernas em A | 46% (L3=40, critério de parada atingido) |
| 4 | Kiln + pele ComfyUI, sem decalque | 40% (olhos sumiram, runa cintilava) |
| 5 | Kiln + pele ComfyUI + **decalque do crânio e da placa da v19** + pé plantado (`golem-final` v02) | **50%** (melhor; `redesenhar_forma: false`) |
| 6 | pose nova (pernas em A bem abertas), pelo do Kiln restaurado | montado em `~/.horys-pixel/experimentos/golem-kiln/out-final4/`, **ainda não importado, medido nem revisado** |

Notas da r5: L1 60, L2 55, L3 35, L4 68, L5 40, L6 45, L7 50. Faltava: linhas internas, pelo, punhos de pedra, sombra fixa, M10 (51 degraus vs ~11), quique 10,6 px.

## Conclusões

- **Kiln puro tem teto** (~46%): placas, juntas, pelo e espiral de 1 px não saem de shading 3D. O Kiln serve como **motor de movimento e pose** (ciclo estável, volume constante).
- **Pele local (ComfyUI)** funciona se os 8 quadros forem gerados **numa grade única** (mesmo desenho nos 8). Quadro a quadro ou em duas grades cintila.
- **Prompt mais longo quase não muda a imagem** (IPAdapter e pose mandam). Não vale gastar rodada nisso.
- **Peças rígidas por decalque** (crânio, placa do peito com espiral), coladas nos sockets do Kiln, resolvem consistência e L4.
- Mão por cima no Aseprite **não escala** (testado em 1 quadro: M17 37→36%). Trocar caixas por polígonos irregulares no modelo atuou nos 8 quadros (37→26%).
- Dataset `Angais/pixel-art-atlas-1.4m` (16×16, objetos soltos, sem animação, sintético): **não ajuda** este gargalo.
- PixelDoll (`C:\Users\artur\workspace\repos\PixelDoll`): usa PixelLab/IA; travou nos mesmos pontos (arma na mão, apoio do pé). Úteis: medir deslize dos pés no portão, cadência ligada à velocidade, empunhadura em pixel opaco, espelhar direções.

## Bugs que eu mesmo introduzi (já corrigidos, mas vale saber)

- Posição do ombro virou 0,70 por substituição global de números (braços soltos).
- Canais dos pés na caminhada estavam entre aspas e a substituição nunca casava (pernas nunca abriram até a r6).
- Fundo da v19 é `#68a057` (104,160,87), não `#649958`; o decalque saiu como retângulo verde.
- Índice de banda fora da rampa quebrou o render (`rock` com 3 cores precisa `bands: [0, 2]`).

## Arquivos e ferramentas (tudo em `~/.horys-pixel/experimentos/golem-kiln/`)

- **Spec do golem:** `art/specs/characters/golem/golem.yaml` (backups `golem_v1..v6_*.bak`), paleta `art/specs/palettes/golem.yaml`. Render: `spritekiln render art/specs/characters/golem/golem.yaml --anims walk --dirs s -o out-golem --force` (escala 0,0115, centro y 0,45; sockets `skull_c`, `chest_c`, `rock_*_c`).
- **Scripts (copiados para `~/.horys-pixel/experimentos/golem-kiln/scripts_mix/`):**
  - `mix_cn_full.py <quadros> <denoise> <semente> <saida> <peso_ip> <peso_canny>`: grade única 4×2 de 8 quadros no ComfyUI (SDXL + IPAdapter com a v19 + ControlNet canny), reduz 4× e trava na paleta de 16 cores.
  - `montar.py <pasta_snaps> <saida>`: monta o atlas final com decalque do crânio e da placa (recortados da v19 em `decal/v19_nat.png`), restaura o pelo violeta do Kiln e planta o pé (fundo do sprite fixo, `PE=217`). Gera `golem_final.png/.json` no formato do Kiln para `horys_importar_kiln`.
  - `mix_comfy*.py`, `mix_grade*.py`, `mix_cn.py`: versões anteriores.
  - `editor_tpl.html`: gerador do editor de retoque.
- **Resultados:** `out-final3/` (r5), `out-final4/` (r6: `golem_final.png`, `folha.png`). Sprites no Horys: `~/.horys-pixel/assets/golem-final/v02` (r5), `golem-mix/v03`, `golem-kiln3/v01`.
- **ComfyUI:** `D:\comfyui\ComfyUI` (venv em `D:\comfyui\venv`). Subir: `D:\comfyui\venv\Scripts\python.exe main.py --port 8188 --lowvram --disable-auto-launch`. Modelos: `sd_xl_base_1.0`, IPAdapter plus sdxl vit-h, CLIP vision ViT-H, controlnets openpose, **canny e depth (xinsir, ~2,5 GB cada, baixados do Hugging Face com autorização do Artur nesta sessão)**. GPU: RTX 3060 Laptop 6 GB. Sem LoRA de pixel art.
- **Editor de retoque (artifact):** https://claude.ai/artifact/FHDiuRKtHQ4Dwq4VjGUUZJ (canvas com paleta travada, onion skin, referência v19, carimbos, medidas ao vivo, guarda edições na coleção `retoque`). O único retoque salvo foi **teste de traço livre no quadro 1** (laços em `#918fa7`), **não foi importado** nem deve ser.

## Estado do Horys/Aseprite

O MCP `horys` conectou ao Aseprite durante a sessão. Fluxo usado: `horys_asset_novo` (quadro 320, `cor_contorno #18122c`, sombra) → `horys_importar_kiln` (`limpar_min` 3) → `horys_limpar` por quadro (zera órfãos, protege âmbar) → `horys_portao` → revisor. Sombra do portão continua com 7–22% da base (gerada pelo portão, não controlei).

## O que o Artur pediu por último

1. "Gerar um resumo.md para mandar ao Claude Desktop" (este arquivo).
2. Antes: "daria pra você desenhar de outro modo" (sem ele desenhar à mão, sem Codex).

Eu ia **derivar do mapa de normais do Kiln** (`out-golem/golem_normal.png`, RGBA 2560×320, 8 quadros) duas coisas iguais nos 8 quadros: (a) **linhas de junta de 1 px** onde a normal muda de repente (entre placas, ombreira/braço, coxa/joelho) e (b) **luz em 3 tons presa ao volume**, para acabar com as manchas diferentes por quadro. Foi interrompido antes de começar; nada foi alterado. Atenção: isso é derivação mecânica do modelo, em linha com a regra do repo de não inventar forma por script.

## Pendências sugeridas (ordem de impacto, segundo o revisor)

1. Importar `~/.horys-pixel/experimentos/golem-kiln/out-final4/golem_final.json` em um asset novo, limpar órfãos, rodar o portão e o revisor (rodada 6).
2. Linhas internas e luz por normal (acima).
3. Decalque da v19 para pelo do ventre, punhos de pedra e pés (mesmo método do crânio, sem rotação livre).
4. Quique até 6 px (hoje 10,6 por causa do plantio do pé), M10 abaixo de 15 (busca gulosa de borda), fumaça violeta com atraso de 2 quadros.
5. Quando o Codex voltar (12/11): usar só se o fluxo local não passar de ~65–70%; Kiln fica como guia de pose/timing.
6. Vistas de lado (`e`), ataque, idle e morte ainda não foram feitas neste fluxo. O render `e` do walk deu erro de corte no topo com o modelo antigo.

## Decisões e limites a manter

- Downloads de terceiros só com autorização explícita do Artur (só os 2 controlnets foram autorizados).
- Não commitar nada sem pedido. `~/.horys-pixel/experimentos/golem-kiln/` e `resumo.md` estão fora do que foi commitado.
- O revisor é a régua de aceitação (meta ≥ 80% sem falha grave); o portão só mede técnica.
