# Fase 2 — Importação SpriteKiln → Horys (specs para o Codex)

Contexto: `TODO.md` (Fase 2) e `docs/decisoes.md` ("SpriteKiln como gerador de base", 1.3 e teste toon).
O SpriteKiln (MIT, `spritekiln` 0.3.0) é **dependência opcional**: nada do código dele entra no repo, e o Horys
continua funcionando sem ele instalado (`import spritekiln` só dentro das funções, com erro claro se faltar).

Regras para todas as tarefas:
- Código puro (sem Aseprite) num módulo novo `src/horys_pixel/kiln.py`; ferramentas MCP num módulo novo
  `src/horys_pixel/ferramentas/kiln.py`, registrado em `registro.carregar_todas()`.
- Ferramentas usam os helpers existentes: `desenho.escrever_rgba`, `desenho.ler_rgba`, `ctx.aseprite("quadro", ...)`,
  `ctx.aseprite("tag", ...)`, `ErroFerramenta`, `texto`/`imagem` de `registro.py`. Mensagens em português.
- Testes com o Aseprite falso (`tests/aseprite_falso.py`) e fixtures sintéticas pequenas (sem PNG do SpriteKiln no
  repo). Testes que precisam do `spritekiln` instalado usam `pytest.importorskip("spritekiln")`.
- Rodar `python -m pytest -q` no fim; regenerar `docs/ferramentas.md` com `scripts/gerar_docs_ferramentas.py`.

---

## 2.1 · `horys_importar_kiln` (atlas → quadros do Aseprite)

**Entrada:** caminho do JSON "hash" que o `spritekiln render` grava (`out/<nome>/<nome>.json`, formato em
`docs/format.md` do SpriteKiln): `frames{nome: {frame:{x,y,w,h}, duration}}`, `meta.frameTags[{name,from,to}]`,
`meta.image` (atlas PNG ao lado), bloco `spritekiln` (eventos, sockets, pivô).

**Puro (`kiln.py`):**
- `ler_atlas(caminho_json) -> Atlas` com `quadros: list[np.ndarray RGBA]`, `duracoes_ms`, `tags: list[(nome, de, ate)]`,
  `eventos: dict[int, list[str]]`, `pivo: (x, y)`, `tamanho: (w, h)`.
- `filtrar(atlas, tags=None, direcao=None)`: só as tags pedidas e só uma direção (`idle_e` → estado `idle`,
  direção `e`); renomeia a tag para o estado sem sufixo.

**Ferramenta `horys_importar_kiln`:** args `json` (obrigatório), `tags` (lista opcional), `direcao` (padrão: a
primeira), `camada` (padrão `referencia`).
1. Exige sprite ativo com o mesmo tamanho de quadro (senão erro dizendo o tamanho esperado e sugerindo
   `horys_asset_novo quadro=<w>`).
2. `quadro garantir total=N`, escreve cada quadro na `camada`, ajusta `duracao` de cada quadro e cria as tags.
3. Grava na ficha: `kiln = {json, sha256, direcao, tags, eventos, pivo}`.
4. Devolve resumo em texto + miniatura (escala inteira) dos quadros importados.

**Pronto quando:**
- `test_ler_atlas_sintetico`: atlas 3 quadros 8×8 com 2 tags reconstrói quadros, durações e tags exatos.
- `test_filtrar_direcao`: tags `idle_e/idle_w` → só `idle` da direção pedida.
- `test_importar_kiln_no_falso`: no falso, N quadros criados, pixels iguais ao atlas na `referencia`, durações e
  tags certas, ficha com `kiln.sha256`.
- `test_importar_kiln_tamanho_errado`: sprite 64×64 com atlas 96×96 → `ErroFerramenta` com "96".

## 2.2 · Importação por parte (posse por construção)

Base: `spritekiln.pipeline.parts_mask(spec, env, yaw, partes)` devolve a máscara dos pixels **visíveis** de cada parte
num quadro (`pipeline.py:181-190` do SpriteKiln 0.3.0). É função interna: fixar `spritekiln==0.3.*` no extra
opcional do `pyproject.toml` e cobrir com teste.

**Puro (`kiln.py`):** `mascaras_por_parte(spec_path, anim, quadro, direcao, grupos: dict[str, list[str]])
-> dict[str, np.ndarray bool]`, onde `grupos` mapeia cada parte do Horys para as partes do spec
(ex.: `"braco-frente": ["upper_arm_R", "forearm_R", "hand_R", "sword"]`). Pixels visíveis que não caem em grupo
nenhum vão para a parte declarada como `resto` (padrão: a de baixo de tudo).

**Ferramenta:** `horys_importar_kiln` ganha `spec` + `grupos` (ou `grupos` na ficha). Com eles, além da
`referencia`, distribui cada pixel visível para a camada da sua parte. Invariante: em cada quadro,
`compor(partes) == referencia` (igualdade exata) e cada pixel visível em exatamente uma parte.

**Fora do escopo agora:** anatomia oculta (render de parte isolada). Fica como 2.2b depois de medir.

**Pronto quando:**
- `test_mascaras_disjuntas_e_cobrem_tudo` (importorskip): no template `side_humanoid`, as máscaras são disjuntas e a
  união é igual ao alfa do quadro.
- `test_importar_por_parte_compoe_referencia` (falso, máscaras sintéticas): composição == referência em todo quadro.
- `horys_partes_checar` roda depois sem `parte-vazia`/`posse` errada nos grupos declarados.

## 2.3 · Paleta e limpeza na importação

O teste toon (decisoes.md) mostrou: com a paleta do estilo no spec, cor e valor passam; órfãos (M04 ~2,5%) e
cluster (M05 ~12 px) não.

**Puro (`kiln.py`):**
- `rampas_do_estilo(estilo) -> dict[str, list[str]]` gera rampas no formato do SpriteKiln a partir da paleta do
  estilo Horys (índice 0 = cor de contorno; depois sombra → base → luz).
- `escrever_paleta_kiln(estilo, destino.yaml)` para o spec apontar `palette:` para ele.
- `limpar_sequencia(quadros, min_px)`: aplica a limpeza mecânica do `horys_limpar` (fundir manchas menores que
  `min_px` na vizinha dominante) a todos os quadros **com a mesma decisão para pixels que não mudam entre quadros**
  (evitar boil: pixel igual em quadros vizinhos recebe a mesma cor).

**Ferramenta:** `horys_importar_kiln` ganha `limpar_min` (padrão 0 = desligado; sugerido 3).
Ferramenta nova `horys_paleta_kiln` (args `estilo`, `destino`) que grava o YAML de rampas.

**Pronto quando:**
- `test_rampas_do_estilo_padrao`: a paleta padrão gera rampas com o contorno no índice 0 e só cores da paleta.
- `test_limpar_sequencia_sem_boil`: sequência sintética com ruído igual em 3 quadros → mesma cor final nos 3; A08
  (boil) não piora.
- Manual (Claude Code terminal): aldeão `aldeao_horys` importado com `limpar_min=3` → M04 ≤ 1,5% e A01–A08 sem
  falha nova.
