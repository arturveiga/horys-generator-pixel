# Prompt para o Codex validar o horys-pixel

Cole o bloco abaixo no Codex, com este repositório como pasta de trabalho
(`C:\Users\artur\workspace\repos\horys\horys-generator-pixel`).

---

Você vai VALIDAR o repositório horys-pixel, escrito numa noite pelo Claude. O Artur quer saber, de manhã, se o que
foi feito funciona, onde está frágil e o que corrigir. Seja um revisor exigente e concreto. Trabalhe em pt-BR.

## Contexto (leia primeiro)
- `README.md`, `docs/arquitetura.md`, `docs/protocolo.md`, `docs/ferramentas.md`, `docs/estilos.md`,
  `docs/treino.md`, `docs/treino-uso.md`, `docs/decisoes.md`, `PENDENCIAS.md`.
- Peças: `src/horys_pixel/` (daemon/, ferramentas/, motor/, treino/, estilos.py, analise_estilo.py, grade_io.py,
  pixels.py, mcp_ponte.py, cli.py, instalar.py), `extension/` (Lua do Aseprite), `skills/` (3 skills), `agents/`,
  `.claude-plugin/`, `.mcp.json`, `tests/`.
- O motor (`src/horys_pixel/motor/`) foi PORTADO da skill `C:\Users\artur\.agents\skills\horys-pixel-liso\scripts`
  e do `pixelart-review`, e provado equivalente (46/46 e 19/19 na calibração; PNG idênticos). Não "melhore" o motor
  sem provar que a equivalência continua.

## O que validar (nesta ordem; anote tudo num relatório)
1. **Testes:** `python -m pytest -q` (Python 3.11). Todos devem passar. A calibração lenta roda sem
   `HORYS_PULAR_LENTOS`; rode pelo menos uma vez.
2. **Coerência entre peças:**
   - Todo comando de `docs/protocolo.md` existe em `extension/handlers.lua` e é usado do jeito certo pelo Python
     (`src/horys_pixel/ferramentas/*.py`); campos e índices 0-based batem dos dois lados.
   - Toda ferramenta `horys_*` citada nas três `skills/*/SKILL.md` e nos prompts de `daemon/pedidos.py` existe no
     registro (`python -m horys_pixel ferramenta` com um nome errado lista o erro; ou leia
     `ferramentas/registro.py` + módulos). Liste as que faltam ou têm parâmetro errado.
   - `docs/ferramentas.md` está desatualizado em relação ao código? Liste diferenças.
3. **Codex como motor (o mais importante para você):** confira `daemon/motores.py::comando` para o Codex. Rode de
   verdade, com o `horysd` ligado (`python -m horys_pixel daemon` em outro terminal, PYTHONPATH=src):
   `python -c "import asyncio,sys;sys.path.insert(0,'src');from pathlib import Path;from horys_pixel.daemon import motores;print(asyncio.run(motores.rodar('codex','Chame a ferramenta MCP horys_status uma vez e responda só a primeira linha.',Path('tmp-codex'),timeout=300)))"`
   Ele precisa chamar a ferramenta sem pedir aprovação (approval_policy never) e sem erro de sandbox. Se falhar,
   descubra a configuração certa do `codex exec` (versão instalada: `codex --version`) e corrija `comando()`.
   Confira também o registro do MCP no `~/.codex/config.toml` que `instalar.py::registrar_codex` escreve.
4. **Revisor cruzado:** `ferramentas/estilo.py::revisar` chama o outro motor com `motor/revisor_prompt.md`. O texto
   final precisa terminar num JSON que `motores.extrair_json` pegue. Teste com uma pasta vNN real (ex.: a última
   versão em `~/.horys-pixel/pedidos/*/` ou `~/AppData/Local/Temp/horys-teste-ao-vivo/v01`).
5. **Ponta a ponta com o Aseprite (se ele estiver disponível):** veja `PENDENCIAS.md` › "Como testar ao vivo".
   Abra o Aseprite com a extensão, rode `python -m horys_pixel status`, crie um asset (`horys_asset_novo`),
   desenhe com `horys_pixel_map`, `horys_contorno`, `horys_portao`. Confira as janelas: Novo asset, perguntas,
   aprovação (com imagem), painel de andamento, Novo estilo, Configurações. Anote o que não abre ou não manda o
   evento.
6. **Pedido pelo botão Gerar com o Codex:** no Aseprite, Novo asset… com motor Codex (ou
   `python -m horys_pixel pedido "um baú de madeira" --motor codex --estilo exemplo --tipo prop`). Acompanhe
   `~/.horys-pixel/pedidos/<id>/motor.log` e o painel. A skill `skills/horys-pixel/SKILL.md` está clara o bastante
   para você seguir sem terminal? Onde você travou?
7. **Revisão de código:** procure bugs reais (concorrência no daemon, conexões que não fecham, caminhos no Windows,
   encoding UTF-8, permissões de salvar em `config.caminho_permitido`, uso de `asyncio` em ferramentas longas,
   vazamento do token em log/saída, Lua que pode derrubar a extensão). Cite arquivo:linha e o cenário que quebra.
8. **Segurança:** o token nunca deve aparecer em log, chat, `pedido.json` ou saída de ferramenta. A extensão não
   executa código vindo do servidor. Salvar só em pastas permitidas.

## Regras
- Corrija só o que for bug claro E que você conseguir provar com teste (escreva o teste). Para o resto, proponha.
- Não mude o motor sem rodar `tests/test_motor_equivalencia.py` sem pular nada.
- Não instale torch/kohya e não treine (é pesado; está em PENDENCIAS).
- Não faça commit nem push sem o Artur pedir.

## Entrega
Grave `VALIDACAO-CODEX.md` na raiz com: resultado dos testes; o que você rodou de verdade e o que deu; bugs
(gravidade, arquivo:linha, cenário, correção feita ou proposta); incoerências entre docs/skills/código; o que achou
frágil; e a sua resposta curta: "dá para o Artur usar hoje? o que ele precisa fazer antes?".
