# Pendências (para o Artur ver de manhã)

Noite de 2026-11-05 → 06. O que ficou esperando você, o que não deu para testar e como testar.

## 1. Decisões suas
| # | Decisão | O que eu fiz enquanto isso |
|---|---|---|
| 1 | **Commit.** O repo tem `git init`, mas nenhum commit (só commito quando você pedir). | Tudo está no working tree. Sugestão: o Codex valida, você olha e pede o commit. |
| 2 | **Trocar o token do sloplink** que eu imprimi no chat no começo da conversa. | Não mexi. Rode `node C:/Users/artur/Documents/aseprite-mcp/server.mjs token --new` se ainda for usar o sloplink. O token do horys é outro (`~/.horys-pixel/token`) e nunca foi impresso. |
| 3 | **Aposentar o MCP `aseprite` do sloplink** e as skills `horys-pixel-liso` / `pixelart-review` antigas? | Mantidos. Os dois MCPs convivem (portas 9123 e 9140). Quando você aprovar o horys-pixel, dá para remover o `aseprite` do `~/.claude.json` e apontar as skills antigas para cá. |
| 4 | **`horysd` subir com o Windows** (para o botão Gerar funcionar sem nenhum terminal aberto)? | Não ativei. Hoje ele sobe sozinho quando um Claude/Codex abre o MCP. Para ativar: `horys instalar --inicializacao`. |
| 5 | **Pacote do Horys Pixel Liso** (`~/.horys-pixel/estilos/horys-pixel-liso/estilo.json`): confira versão `0.2`, trigger do LoRA `horysliso`, licença "pessoal, não redistribuir". | Valores escolhidos pelo agente que montou os pacotes. |
| 6 | **Licença do repo:** MIT (padrão em `pyproject.toml` e no plugin)? | Deixei MIT. Confirme antes de publicar. |
| 7 | **Revisor cruzado** (o Codex revisa o que o Claude desenhou e vice-versa) é o padrão. | `~/.horys-pixel/preferencias.json` → `"revisor": "cruzado" | "claude" | "codex"`. |
| 8 | **Grama base do `terreno.md`** (KB): textura dentro do tile vs. variação só por tiles variantes. | Ficou como estava (os dois convivem). |

## 2. Instalação: falta você rodar (eu não instalei)
O sistema de permissões do Claude Code bloqueou a instalação, com razão: ela mexe na configuração do próprio Claude.
Então **nada foi instalado** no seu Claude Code, no seu Codex nem no seu Aseprite. Os testes ao vivo rodaram num
Aseprite isolado (perfil temporário). Para instalar, num terminal seu:
```powershell
cd C:\Users\artur\workspace\repos\horys\horys-generator-pixel
pip install -e .
horys instalar --tudo --simular     # confira
horys instalar --tudo               # extensão no Aseprite, plugin do Claude, MCP + aprovações + skills do Codex
```
Feche o Aseprite antes e acrescente `--confiar` se não quiser o pedido de permissão na primeira conexão. Tudo é
reversível:
- extensão: apague `%APPDATA%\Aseprite\extensions\horys-pixel`;
- plugin: `claude plugin uninstall horys-pixel`;
- Codex: há uma cópia de antes em `config.toml.horys-bak`;
- skills do Codex: apague as junções `~/.codex/skills/horys-pixel*`.

O que já existe fora do repo: `~/.horys-pixel/` (token, estilos — inclusive o seu `horys-pixel-liso` —, pedidos,
logs, fichas). No Codex, o instalador registra `approval_mode = "approve"` para cada ferramenta `horys_*`; sem isso o
`codex exec` pode parar pedindo aprovação.

## 3. Não deu para testar (ou testar inteiro)
- **Codex como motor:** às 22h19 a conta bateu no limite de uso ("try again at 22h52"). As opções `-c` do MCP foram
  aceitas sem erro; falta ver o Codex chamar as ferramentas sem pedir aprovação. Está no `CODEX_VALIDAR.md` (item 3).
- **Janelas da extensão:** testei de verdade, com clique, a janela de perguntas e a de aprovação com imagem, e vi
  o painel de andamento. Não testei as janelas Novo asset (o botão Gerar), Novo estilo e Configurações: precisam
  digitar texto. O mesmo evento `pedido_novo` foi testado pelo `horys_pedido_novo`.
- **Treino (kohya):** só o código e os testes sem GPU. Instalar baixa 3–5 GB:
  `horys treino instalar --executar`, depois baixe o SD 1.5 (`v1-5-pruned-emaonly-fp16.safetensors`, licença
  CreativeML OpenRAIL-M) e siga `docs/treino-uso.md`. O sd-scripts recomenda Python 3.10; aqui só há 3.11
  ("funciona, não testado").
- **Calibração do estilo `exemplo`:** ele não tem régua, então o portão usa as metas do Tiny.

## 4. Como testar ao vivo (sem mexer no seu Aseprite aberto)
```powershell
$env:PYTHONPATH = "C:\Users\artur\workspace\repos\horys\horys-generator-pixel\src"
python -m horys_pixel daemon            # terminal 1
# terminal 2: um Aseprite isolado, com perfil próprio
$env:ASEPRITE_USER_FOLDER = "$env:TEMP\aseprite-horys"
python -m horys_pixel instalar --extensao --confiar --pasta-aseprite $env:ASEPRITE_USER_FOLDER
& "C:\Users\artur\Documents\aseprite\aseprite.exe"
python -m horys_pixel status            # "Sprite: ..." ou "nenhum sprite aberto"
```

## 5. Diário da noite (o que foi feito e provado)
**Código:** servidor `horysd` + ponte MCP, extensão Lua, 47 ferramentas, 3 skills, plugin do Claude, motor portado,
pacotes de estilo, análise para "criar meu estilo", treino (kohya), instalador e CLI. **126 testes passando**
(`python -m pytest -q`; a calibração lenta foi rodada à parte: 46/46 bons e 19/19 estragados).

**Provas:**
- **Equivalência do portão:** a `.grade` real do construtor (v03, com camadas) entrou no Aseprite como camadas, o
  `horys_portao` reexportou e a folha saiu **idêntica pixel a pixel** ao `grade.py` original.
- **Aseprite real (perfil isolado):**
  - a extensão conecta sozinha pelo token;
  - desenho, contorno, portão e visão crítica funcionam;
  - janela de perguntas e janela de aprovação com imagem: os cliques chegaram ao `horysd`;
  - reconexão automática quando o `horysd` reinicia (~30 s).
- **Pedido de ponta a ponta com o Claude sem terminal** (aldeão ruivo, quadro base do idle, a partir do seu
  `conceito_101.png`, em modo autônomo de 45 s): **39 min, sozinho.**
  - **Etapas:** briefing → `praticas.md` (20 regras) e `ficha.md` → sprite 192×192 com 6 partes em camadas →
    conversão por moda → limpeza à mão → portão (v01–v04 reprovaram, a v05 passou: 10 cores, 69 px) → revisor em
    3 rodadas (54 → 57 → 55%, NÃO PASSA) → parou no limite, marcou os defeitos na camada `revisao` e entregou um
    relatório honesto.
  - **Resultado:** em `~/.horys-pixel/pedidos/20261105-223425-43c9/v10/` (PNG, `_regua`, `.aseprite` fatiado). Está
    fiel ao conceito e ao lado do peão do Tiny na mesma escala, mas **não aprovado**: falta o seu olho.
  - **Pendências que ele listou:** silhueta do cabelo com degraus, olho em "T", rubor, mão na bolsa, mangas, vão
    das botas, sombra do chão, e se libera 12 cores (âmbar e lilás).

**Bugs que o teste real achou e eu corrigi:**
1. A extensão não reconectava quando o `horysd` reiniciava (o Aseprite nem sempre entrega o CLOSE). Agora o
   `horysd` manda ping a cada 10 s e a extensão recria o socket.
2. A aprovação travava numa janela "Security" do Aseprite (o PNG temporário). Agora a imagem vai como RGBA cru, sem
   arquivo.
3. Abrir arquivo pedia permissão para o `handlers.lua`. O `--confiar` agora pré-autoriza todos os `.lua` da
   extensão, e o erro de tempo esgotado avisa para olhar a janela de permissão.
4. O revisor Codex falhava com "linha de comando muito longa" (o `codex.CMD` limita a ~8 mil caracteres). Agora o
   prompt vai pela entrada padrão, nos dois motores.
5. Revisor cruzado sem cota: agora cai no motor de reserva sozinho e avisa que a revisão não foi cruzada.
6. Pedido vindo com `motor: null` apagava o motor padrão.

**Observação visual:** a fonte do Aseprite não tem alguns acentos ("aprovação" aparece "aprovaşão"). É da fonte
pixel do tema do Aseprite, não do horys. Dá para trocar a fonte do tema ou evitar o til nos títulos.

## Execução da suíte — 2026-11-07 (TODO 0.1)
- `python -m pytest -q`: **176 passaram, 0 falhas** (2 min 34 s), incluindo os 29 testes de partes que nunca
  tinham rodado e os 10 novos de `tests/test_kiln.py`. `test_treino_args_nao_contorna_executar_false` agora passa.
- Reprodução 9.1 da `analise-perfect.md` (P0-1, fantasma): `rel.ok == True` → **confirmado**, o validador aprova a
  figura inteira duplicada na parte de baixo.
- Reprodução 9.2 (P0-2, recortar de partes vazias): `0 alterados, 136 recusados de 136` → **confirmado**.
- Na rota SpriteKiln com `spec` + `grupos`, a posse vem do render e os dois casos não se aplicam; na rota de
  desenho/conversão eles continuam abertos (Fase 3.2 do TODO).
