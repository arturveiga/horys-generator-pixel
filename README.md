# horys-pixel

Gerador de pixel art no estilo de cada pessoa, que desenha **ao vivo no Aseprite**, conversa com você dentro dele e
funciona com **Claude ou Codex** como motor.

> **Plano atual:** animação por modelo 3D low-poly renderizado com câmera fixa, tratado pelo motor de sequência.
> Ver [docs/plano.md](docs/plano.md).

## Em uma frase
No Aseprite você abre **Arquivo › Horys › Novo asset…**, escreve "um viking", anexa uma referência se quiser, escolhe
o motor (Claude ou Codex) e clica em Gerar. O motor faz as perguntas da skill numa janela do Aseprite, desenha passo a
passo, passa no portão de medidas e no revisor do outro motor, e para você aprovar silhueta, cor e animação. Cada
aprovação ensina o seu gosto e, com o tempo, treina um modelo de imagem local no seu estilo.

## Como funciona
```
Aseprite + extensão Horys ──WebSocket (token HMAC)──► horysd (Python, sempre ligado) ◄── horys-mcp ◄── Claude Code / Codex
   painel: perguntas, aprovações, andamento            ferramentas horys_* · pedidos · motor de estilo · gosto · treino
```
- **`horysd`** é o único que fala com o Aseprite; vários clientes MCP ao mesmo tempo, sem trocar porta (9140).
- **Ferramentas MCP `horys_*`**: desenho (pixel_map, ler, ver crítica, mudanças, camadas, quadros, tags), conversa
  (perguntar, aprovar, aguardar), estilo (asset_novo, contorno, converter, limpar, afinar, portão, régua, marcar,
  exportar, medir_arquivo, revisar), pedidos, gosto, estilos e treino. Lista completa: `horys ferramenta ...` ou
  [docs/ferramentas.md](docs/ferramentas.md).
- **Skills:** `horys-pixel` (gerar), `horys-pixel-review` (revisar), `horys-pixel-estilo` (criar/treinar estilo).
- **Estilos são pacotes** ([docs/estilos.md](docs/estilos.md)); o repo traz `exemplo`. O seu fica em
  `~/.horys-pixel/estilos/`.

## Instalar
Requisitos: Python 3.10+, Aseprite 1.3+, Claude Code. O Codex CLI é opcional; o `ffmpeg` só é preciso para animar a partir de vídeo.
```bash
pip install -e .                       # dependências + comandos horys, horysd, horys-mcp
horys instalar --tudo --simular        # mostra o que vai fazer
horys instalar --tudo                  # extensão no Aseprite, plugin do Claude Code e MCP (sem o Codex)
horys instalar --tudo --codex          # também o MCP e as skills do Codex (opcional)
```
Opções: `--confiar` pré-autoriza a extensão no `aseprite.ini` (com o Aseprite fechado; senão o Aseprite pergunta uma
vez); `--inicializacao` sobe o `horysd` com o Windows (para o botão Gerar funcionar sem terminal aberto).

Pelo Claude Code, o plugin também instala direto do repositório:
```
/plugin install horys-pixel --marketplace <owner>/<repo>
```

Depois: reabra o Aseprite. A extensão lê o token de `~/.horys-pixel/token` e conecta sozinha (status em
**Arquivo › Horys › Conexão e painel…**).

## Fluxo (referência primeiro)
Ficha do tipo (`src/horys_pixel/padroes/`) → `horys_prompt_traducao` (você gera a imagem no gerador que quiser: ChatGPT,
Gemini, Codex, vídeo) → `horys_portao_entrada` → `horys_converter` → limpeza → portão de medidas → revisor. Animação:
`horys_sequencia` (motor de sequência) no lugar da conversão. A entrega vem com o acabamento marcado para você
finalizar no Aseprite, e o seu retoque volta como gosto. Detalhes em [arquitetura](docs/arquitetura.md) e
[plano](docs/plano.md).

## Usar
- **No Aseprite:** Arquivo › Horys › Novo asset… / Revisar este sprite / Novo estilo….
- **No terminal (Claude Code ou Codex):** peça normalmente ("faz o idle do ferreiro do Hunvix"); a skill usa as
  ferramentas e o Aseprite mostra tudo.
- **CLI:** `horys status`, `horys estilos`, `horys pedido "um viking" --motor codex`, `horys ferramenta horys_ver '{"critica":true}'`,
  `horys treino gpu`.

## Desenvolver
```bash
python -m pytest -q                    # 126 testes (HORYS_PULAR_LENTOS=1 pula a calibração de ~1,5 min)
python scripts/build_extension.py      # dist/horys-pixel.aseprite-extension
python scripts/gerar_agente.py         # agents/revisor.md a partir do revisor_prompt.md
```
Documentos: [plano](docs/plano.md) · [arquitetura](docs/arquitetura.md) · [protocolo](docs/protocolo.md) · [ferramentas](docs/ferramentas.md) ·
[estilos](docs/estilos.md) · [treino](docs/treino.md) e [uso do treino](docs/treino-uso.md) ·
[decisões](docs/decisoes.md).

## Créditos
- Ponte com o Aseprite inspirada no `aseprite-mcp` do sloplink (MIT); `extension/sha256.lua` vem dele.
- Motor de estilo (grade, medir, conceito, calibrar) e revisão (`pixel_review`) portados das skills
  `horys-pixel-liso` e `pixelart-review` do autor.
- Treino: [kohya-ss/sd-scripts](https://github.com/kohya-ss/sd-scripts) (instalado à parte, Apache-2.0).
