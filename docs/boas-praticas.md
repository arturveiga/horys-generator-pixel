# Boas práticas de pixel art (horys)

> Gerado de `src/horys_pixel/boas_praticas.json` por `scripts/gerar_boas_praticas.py`. Não edite à mão.
> Versão 1 (2026-11-14).

Um livro de regras só, sem repetição, juntando as notas do Obsidian (`pixelart/`), o ofício portado do
aseprite-ai-artist (`oficio_dados/regras/`), as lições do sprite-forge e do agent-sprite-forge (MIT), o portão do
motor (`motor/medir.py`, `sequencia/validar.py`), a skill pixelart-review e as lições do próprio Artur.
**Não há régua externa: a régua é o Artur** (a ficha e os sprites em `_aprovados`). Quando a ficha registrar
outra decisão, a ficha vence.

## Envelope (perfeicao.md §5)
- Humanoide chibi 32 px (quadro 48×48, cabeça 40–45%); monstro 48 px (até 64) com 3–5 massas.
- ≤ 20 cores; contorno escuro de 1 px (selout aceito); 2–3 tons por material; luz de cima-esquerda.
- Nada menor que 2×2 px, salvo olho e brilho (cores protegidas). Nada existe em 1 px num quadro e some no outro.
- Linha dos pés estável. idle 2–4 · andar 4 (≤ 6) · ataque 3–5 · dano 2 · morte 3–4; 100–160 ms por quadro.
- Mudança de 15–40% dos pixels por quadro de andar é **diretriz, não portão**: num render 3D o bob do corpo mexe
  tudo, então BP40 e BP41 só informam com `render3d`.

## Como usar
- Código: `horys_pixel.boas_praticas` — `checar_quadro(rgba, contexto)`, `checar_animacao(quadros, contexto)`,
  `checar_direcoes(vistas, contexto)`, `overlay(rgba, resultados)`, `checar_caminho(arquivo, contexto, saida)`.
- MCP: `horys_boas_praticas` (PNG, pasta de quadros ou folha PNG+JSON) grava `<x>_praticas.json` e o overlay
  `<x>_praticas.png` (vermelho = grave, amarelo = leve).
- Revisor: cita os ids BP; as regras de **olho** são dele, as automáticas vêm do JSON (não conte pixel a olho).
- Severidade: **grave** aparece em 1× ou quebra o envelope (reprova); **leve** só ampliado (vira ajuste).
- Contexto: `protegidas` (olho, brilho, emissivo), `contorno`, `paleta`, `chao`, `acao`, `loop`, `render3d`,
  `altura_alvo`, `perfil` (16/32/64), `limites` (`{"BP12": 24}`).

Regras: 53 (35 automáticas, 18 de olho).


## Forma e silhueta

| id | regra | por quê | medida (limite) | sev. | fonte |
|---|---|---|---|---|---|
| BP01 | A silhueta lê numa cor só, a 1× e em miniatura | Se a forma chapada não diz o que é, nenhum sombreado salva. | olho do revisor — _silhueta / 1× | grave | OBS-pv, OF-14, OF-03 |
| BP02 | Espaço negativo onde o corpo tem vão; sem tangência (partes que só se encostam) | Tangência funde partes e mata a leitura da pose. | olho do revisor | grave | OBS-pv, OF-03, OF-14 |
| BP03 | Forma orgânica, não montada com primitivas (caixa, elipse cortada) | Borda em trechos retos longos denuncia figura de primitivas (gorila v01–v08). | `retas_silhueta`: fração da borda da silhueta em trechos retos ≥ reta_min do perfil (M17) (16: 1.0, 32: 0.7, 64: 0.25) | grave | MED, ART |
| BP04 | Figura inteira dentro do quadro, com folga | Pixel na borda do quadro = corte no jogo (ataque, chifre). | `toca_borda`: pixels opacos na moldura de 1 px do quadro (0) | grave | OBS-val, SF-17 |
| BP05 | Uma peça só: sem fragmento solto fora do corpo | Pedaço solto é resto de recorte ou de redução, não desenho. | `pedacos_soltos`: componentes opacos 8-conexos fora do maior com ≥ 3 px (cores protegidas não contam) (0) | leve | ASF, SF-10 |
| BP06 | Hierarquia de massas e proporção do envelope | Chibi 32 px com cabeça 40–45%; monstro 48 px com 3–5 massas. Detalhe pequeno some. | olho do revisor | grave | PERF5, OBS-pers |

## Contorno

| id | regra | por quê | medida (limite) | sev. | fonte |
|---|---|---|---|---|---|
| BP07 | Contorno escuro fechado de 1 px (selout aceito) | Envelope do Artur; separa a figura de qualquer chão. | `contorno_fechado`: fração da 1ª camada da borda que é a cor do contorno ou escura (OKLab L < 0,56) (0.55) | grave | PERF5, OF-92, MED |
| BP08 | Contorno de 1 px, não duplo | Contorno de 2 px come o sprite pequeno (12% de 16 px). | `contorno_duplo`: fração da 2ª camada da borda na cor do contorno (0.3) | grave | OF-10, OBS-fund, PR |
| BP09 | Pixel duplo só em quina (sem cotovelo em L na diagonal) | O cotovelo engrossa a diagonal e parece borrão. | `cotovelos`: cotovelos no contorno / pixels do contorno (0.04) | leve | OBS-fund, OF-10, PR |
| BP10 | Contorno não é preto puro | Preto puro picota o sprite pequeno; use o tom mais escuro da rampa ou anil. | `preto_puro`: pixels #000000 (0) | leve | OBS-fund, OBS-est, OBS-val |
| BP11 | Um estilo de contorno no sprite inteiro | Contorno que muda de regra por parte parece colagem. | olho do revisor | leve | OF-04, OF-07 |

## Cor e paleta

| id | regra | por quê | medida (limite) | sev. | fonte |
|---|---|---|---|---|---|
| BP12 | No máximo 20 cores por personagem (e na sequência) | Envelope do Artur; acima disso é ruído de render ou de redução. | `cores`: cores opacas distintas (quadro e sequência) (20) | grave | PERF5, OF-92 |
| BP13 | Toda cor dentro da paleta aprovada | Paleta aprovada pelo Artur é contrato (passo 0 da rota Blender). | `fora_paleta`: pixels fora da paleta do contexto (só se houver paleta) (0) | grave | OBS-val, OF-92, PERF5 |
| BP14 | Sem cores quase iguais | Dois tons com ΔE < 3 não se leem como degrau; desperdiçam a paleta. | `quase_iguais`: pares com ΔE < 3 (paleta_ops.analisar) (0) | leve | OF-92, OBS-pv |
| BP15 | Alfa binário (0 ou 255) | Alfa parcial é AA de filtro: borra e muda com o fundo. | `alfa_parcial`: pixels com 0 < alfa < 255 (0) | grave | OF-92, OF-12, ASF |
| BP16 | 2–3 tons por material (4º só como brilho) | Envelope; mais tons vira gradiente e ruído. | `tons_por_rampa`: maior rampa detectada (paleta_ops.detectar_rampas) (4) | leve | PERF5, OBS-est, OBS-pers |
| BP17 | Rampa com giro de matiz (sombra mais fria, luz mais quente) | Rampa que só escurece tem cara de máquina. | `rampas_sem_giro`: rampas não neutras com giro < 5° (0) | leve | OF-01, OF-92, OBS-est |
| BP18 | Acento saturado com parcimônia; um traço marcante | O acento guia o olho; espalhado, não guia nada. | olho do revisor | leve | OBS-pv, OBS-pers, OBS-est |

## Luz e sombra

| id | regra | por quê | medida (limite) | sev. | fonte |
|---|---|---|---|---|---|
| BP19 | Luz de cima-esquerda, a mesma em todo asset | Envelope; luz trocada entre peças quebra o volume. | `luz`: correlação de L (OKLab) com y e com x no preenchimento: y < 0 (claro em cima) e x ≤ 0,10 (y_max: 0.0, x_max: 0.1) | leve | PERF5, OBS-est, OBS-pv |
| BP20 | Valor separa a figura do chão do jogo | Teste do cinza: sem ΔL a figura some no chão. | `contraste_chao`: fração da borda externa com |ΔL| ≥ 0,12 contra o chão do contexto (0.8) | grave | OBS-val, OBS-fund, MED |
| BP21 | Faixa de valor ampla (do escuro ao claro) | Valor antes de matiz: forma lê pelo valor. | `faixa_valor`: L_max − L_min das cores usadas (0.45) | leve | OF-14, OBS-fund |
| BP22 | Sombra em massas; sem pillow shading nem banding | Anel de sombra que segue o contorno ignora a luz. | olho do revisor | grave | OF-11, OF-02, OBS-est |
| BP23 | Partes de trás um tom mais escuras | Profundidade sem perspectiva: perna e braço de trás recuam. | olho do revisor | leve | OBS-fund, OBS-est, SF-12 |

## Clusters e ruído

| id | regra | por quê | medida (limite) | sev. | fonte |
|---|---|---|---|---|---|
| BP24 | Sem pixel solto (sem vizinho opaco) | Pixel desligado do corpo é sujeira de redução. | `soltos`: pixels opacos sem vizinho opaco nos 4 lados (0) | grave | OF-11, OBS-val |
| BP25 | Sem ruído (órfão de baixo contraste) | Órfão de baixo contraste é ruído; o de alto contraste é acento. | `ruido`: isolados-8 de baixo contraste / área (comum.isolados8; cores protegidas e contorno fora) (0.01) | grave | MED, OF-11, OF-92, PR |
| BP26 | Nada menor que 2×2 px (salvo olho e brilho protegidos) | Detalhe de 1–2 px some no jogo (lenhadora, gorila). | `detalhe_fino`: manchas de cor de até 4 px onde não cabe um bloco 2×2, fora da borda / área (0.006) | grave | PERF5, ART, OF-14 |
| BP27 | Poucas manchas grandes por tom | Cluster coerente descreve volume; confete não. | olho do revisor — ≤ ~3 manchas por tom por parte a 32 px | leve | OF-11, OBS-pv |
| BP28 | Dithering e AA só quando pedidos | No estilo do Artur o dithering é raro; AA de filtro é proibido. | olho do revisor | leve | OBS-est, OF-12, OF-13 |

## Linhas e curvas

| id | regra | por quê | medida (limite) | sev. | fonte |
|---|---|---|---|---|---|
| BP29 | Degraus regulares na silhueta (sem jaggy) | Degrau irregular (2-1-2) parece erro; curva muda o degrau em ordem. | `degraus`: degraus irregulares na borda externa (comum.degraus_irregulares) (16: 8, 32: 14, 64: 20) | leve | OBS-fund, OF-10, MED |
| BP30 | Uma espessura de linha; linha interna só onde dois planos se fundiriam | Linha interna escura em sprite pequeno pesa e suja. | olho do revisor | leve | OF-10, OF-14 |

## Animação

| id | regra | por quê | medida (limite) | sev. | fonte |
|---|---|---|---|---|---|
| BP31 | Mesmo canvas e alfa binário em todos os quadros | Câmera fixa; motor do jogo recorta pelo canvas. | `canvas_alfa`: SEQ V01 + V02 (0) | grave | SEQ, SF-17 |
| BP32 | Linha dos pés estável em idle e andar | Pé que sobe e desce sem motivo = personagem flutuando. | `pes_var`: variação (px) da linha mais baixa da figura entre quadros (1) | grave | OBS-val, OBS-anim, PERF5 |
| BP33 | Altura estável (salvo squash pedido) | Cabeça que cresce é proporção quebrada, não animação. | `altura_var`: SEQ V05 (variação / altura mediana) (0.06) | grave | SEQ, OF-07 |
| BP34 | Sem deriva horizontal | Ciclo no lugar não anda pelo quadro. | `deriva_x`: SEQ V06 (max(2 px, 2% da largura)) | grave | SEQ |
| BP35 | Sem cintilação (pixel solto que pisca A→B→A) | Boil de 1 px é o defeito mais visível em loop. | `pisca`: SEQ V09 (pisca_isolado) (0.02) | grave | SEQ, ASF, OF-11 |
| BP36 | Nenhum quadro parado num movimento contínuo | Quadro esquecido parado quebra o loop. | `quadros_iguais`: SEQ V10 (quadros vizinhos idênticos) (0) | grave | OBS-anim, OBS-val, SEQ |
| BP37 | O loop fecha (último → primeiro como um passo normal) | Salto no fecho aparece a cada ciclo. | `loop`: SEQ V11 (fecho / mediana dos passos) (2.0) | grave | SEQ, OBS-ef |
| BP38 | Identidade: silhueta e cabeça do quadro 0 em todos (cabeça travada) | Rosto que ferve e tronco redesenhado (robô 14/11). | `identidade`: SEQ V12/V12b (IoU alinhado pelos pés) (silhueta: 0.55, cabeca: 0.5) | grave | SEQ, ASF, ART |
| BP39 | Nenhum detalhe some num quadro e volta no outro | Olho ou runa que pisca é defeito, não animação. | `elemento_some`: SEQ V13 (cor com ≥ 6 px no quadro 0 presente em todos) (0) | grave | PERF5, SEQ |
| BP40 | Andar muda 15–40% dos pixels por quadro (diretriz) | Menos = marcha no lugar; mais = redesenho que ferve. Em render 3D o bob do corpo mexe tudo: só informa. | `mudanca_andar`: fração da união das silhuetas que muda entre quadros vizinhos (só andar/correr; nunca reprova render 3D) (0.15–0.4) | leve | SF, ART, PERF5 |
| BP41 | Quadros e tempo no envelope | idle 2–4, andar 4 (≤ 6), ataque 3–5, dano 2, morte 3–4; 100–160 ms por quadro. Render 3D (andar de 16) é exceção. | `envelope_quadros`: número de quadros pela ação do contexto; durações se dadas (idle: [2, 4], andar: [4, 6], correr: [4, 6], ataque: [3, 5], dano: [2, 2], morte: [3, 4], ms: [100, 160]) | leve | PERF5 |
| BP42 | O que não mexe fica idêntico; restaure, não adivinhe | Redesenhar o resto cria boil; vão aberto se preenche com o pixel de referência. | olho do revisor | grave | SF-2, SF-10, ASF |
| BP43 | Pé de apoio não desliza (slip 1,0); passada que lê | Andar 'só desliza' (médico v16); lado ±5–6 px nos contatos. | olho do revisor | grave | SF-7, ART, ASF |
| BP44 | Secundário 1 quadro atrasado; antecipação e overlap; ataque gira só braço/arma | Inércia vende peso; tronco girando inteiro parece vídeo. | olho do revisor | leve | SF-13, OBS-anim, ART |

## Direções e consistência

| id | regra | por quê | medida (limite) | sev. | fonte |
|---|---|---|---|---|---|
| BP45 | Mesma altura e linha do pé entre direções | Personagem que muda de tamanho ao virar quebra a câmera fixa. | `direcoes_altura`: diferença (px) de altura e de linha do pé entre as vistas (1) | grave | MED, ASF |
| BP46 | Mesma paleta em todas as direções | Cor nova numa vista = material mudou. | `direcoes_paleta`: cores de uma vista que não existem na vista de referência (2) | leve | MED, ASF |
| BP47 | Vista de lado com 60–90% da área da frente | Lado do mesmo tamanho da frente = vista errada ou volume trocado. | `direcoes_area_lado`: área do lado / área da frente (0.6–0.9) | leve | MED |
| BP48 | Câmera top-down 3/4 fixa; oeste = leste espelhado | Topo da cabeça aparece; nada de perfil 2D de plataforma. | olho do revisor | grave | PERF5, OBS-est |

## Leitura no jogo

| id | regra | por quê | medida (limite) | sev. | fonte |
|---|---|---|---|---|---|
| BP49 | Lê em 1× sobre o chão do jogo | A prévia ampliada esconde o que some no jogo. | olho do revisor | grave | OBS-val, OF-14 |
| BP50 | Altura no envelope (humanoide 32 px, monstro 48 px) | Mesma densidade e escala para todo o elenco. | `altura_alvo`: |altura da figura − altura_alvo do contexto| (só com altura_alvo) (2) | leve | PERF5, OBS-est |
| BP51 | Densidade única: escala inteira e vizinho mais próximo, sem mixel | Pixel de tamanhos misturados denuncia redução ou IA. | olho do revisor | grave | OBS-est, OF-92 |
| BP52 | Rosto liso ou olhos de 1–2 px carimbados iguais em todos os quadros | Rosto é onde o olho cai; detalhe pequeno ferve. | olho do revisor | leve | PERF5, OBS-est, ASF |
| BP53 | Efeito fora do corpo; nunca esconde a silhueta por mais de 1–2 quadros | Leitura do golpe vem antes do brilho. | olho do revisor | leve | OBS-ef, OBS-est, PERF5 |

## Fontes

- **PERF5**: perfeicao.md §5 (envelope) e §14 (rota Blender)
- **ART**: lições do Artur (skills/horys-base-e-pele, memória)
- **OBS-pv**: Obsidian pixelart/padrao-visual.md
- **OBS-val**: Obsidian pixelart/skill/validacao.md
- **OBS-fund**: Obsidian pixelart/tecnicas/fundamentos.md
- **OBS-anim**: Obsidian pixelart/tecnicas/animacao.md
- **OBS-pers**: Obsidian pixelart/tecnicas/personagens.md
- **OBS-ef**: Obsidian pixelart/tecnicas/efeitos.md
- **OBS-est**: Obsidian pixelart/estilo/estilo-alvo.md
- **OF**: aseprite-ai-artist (MIT), src/horys_pixel/oficio_dados/regras/NN-*.md
- **SF**: sprite-forge (MIT) docs/LESSONS.md, lição n
- **ASF**: agent-sprite-forge (MIT) references/pixel-looks.md e docs/known-limitations.md
- **MED**: motor/medir.py + motor/comum.py (portão M/D)
- **SEQ**: sequencia/validar.py (V01–V13)
- **PR**: skill pixelart-review (pixel_review.py)
