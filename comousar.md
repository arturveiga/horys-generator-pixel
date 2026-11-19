# Como usar, passo a passo

A ideia: você aprova a **arte parada** (frente, lado e costas) como ela saiu. Depois o **Blender** anima o modelo 3D
ajustado a essa arte, e a ferramenta só entrega se tudo bater.

```
imagem do gerador ─► arte parada 1x ─► você aprova ─► modelo 3D no Blender ─► gabarito (3D = arte?)
                                                                                    │ passou
                                    folhas para o jogo ◄─ portões ◄─ pós ◄─ animação nas 8 direções
```

## 0. Instalar (uma vez)

Requisitos: Python 3.10+, `uv` e Blender 4 ou mais novo. O Aseprite é opcional: com ele sai também um `.aseprite`
com tags.

```powershell
cd C:\Users\artur\workspace\repos\horys\horys-generator-pixel
uv sync --extra dev
.venv\Scripts\horys --help
```

Antes do `uv sync`, feche o Estúdio antigo (`horys estudio`) se ele ainda estiver aberto: ele trava o `horys.exe`.

Se o `uv sync` reclamar de "Acesso negado", dá para usar sem instalar:
`$env:PYTHONPATH="src"; python -m horys_pixel --help`.

Nos passos abaixo, `horys` é `.venv\Scripts\horys`, ou `python -m horys_pixel` com `PYTHONPATH=src`.

## 1. Conferir o contrato do jogo (uma vez por jogo)

Abra `jogo.json`. Ele vale para TODOS os assets:

- `altura_humano_px` (hoje 44): altura de um humano na tela.
- `px_por_metro` (hoje 26,6): escala do mundo 3D para pixel. Com ela, o bonequinho de 1,69 m sai com 44 px.
- `angulo` (43°), `quadro` (96 px), `direcoes` (8), `luz`, `contorno` (1 px por fora), `max_cores` (20).
- `portoes`: os limites que bloqueiam a entrega.

Mudar um número aqui muda o jogo inteiro. Nenhum asset sobrescreve o contrato.

## 2. Criar o asset

```powershell
horys novo goblin --descricao "goblin verde, colete de couro marrom, lança de madeira; sem capacete" --altura 36
```

Sem `--altura`, vale a altura do humano. O comando cria `assets/goblin/` com `asset.json`, `arte/`, `blender/` e
`saida/`.

## 3. Pedir a imagem ao gerador

```powershell
horys prompt goblin
```

Cole o texto no ChatGPT ou no Codex. O formato e o porquê de cada item estão em `prompt.md`. Salve a melhor de 3
tentativas como `assets/goblin/gerada.png`.

## 4. Ler a arte parada

```powershell
horys ler goblin
```

O comando lê a imagem na grade dela e grava `arte/frente.png`, `arte/lado.png`, `arte/costas.png` (1x), mais
`arte/folha.png` e a prévia `arte/folha_8x.png`.

Se der **ERRO** de altura, a imagem não respeitou o pedido: gere de novo. Não conserte à mão.

## 5. Abrir o visor (deixe aberto)

```powershell
horys visor
```

O navegador abre `http://127.0.0.1:8770`. Ali dá para **ver**:

- a imagem do gerador;
- a arte parada;
- a paleta;
- o gabarito;
- as animações tocando em cada direção, com zoom.

A página se atualiza sozinha quando um arquivo muda. Nada se edita por ela.

## 6. Paleta

```powershell
horys paleta goblin --materiais 4
```

O comando grava `paleta.json` e `paleta.png`: uma família de material por linha, 2–3 tons, mais a tinta do contorno.
Pode renomear as famílias no `paleta.json`, por exemplo `material1` para `pele`.

## 7. Você aprova a arte e a paleta

Olhe no visor. Se gostar:

```powershell
horys aprovar goblin arte --comentario "gostei, só a lança mais curta depois"
horys aprovar goblin paleta
```

A aprovação fica presa ao conteúdo do arquivo. Se a arte mudar, a aprovação cai e precisa ser feita de novo.

Com a paleta aprovada, um novo `horys ler` trava a arte nessas cores.

## 8. Modelo 3D no Blender

Faça o modelo em `assets/goblin/blender/goblin.blend`. Ele pode ser modelado à mão ou por script, como no
`assets/bonequinho/blender/modelar.py`.

Regras:
- **Peças rígidas em coleções por parte**: Tronco, Cabeça, Braço Esquerdo/Direito, Perna Esquerda/Direita.
- **Um empty "âncora"** na base.
- O personagem olha para **-Y**, com o **chão em z = 0**.
- Materiais com a cor base de cada família da paleta.

Depois:

```powershell
horys inspecionar goblin
```

O comando mostra as coleções, a caixa de cada uma, a altura em metros e os **pivôs sugeridos**. Copie o `rig`
(segmentos com pivô), os `papeis` e as `acoes` para o `asset.json`. O `assets/bonequinho/asset.json` é o exemplo
completo.

**Ações:**

| Tipo | Uso |
|---|---|
| `parado` | pose de repouso |
| `idle` | respiração |
| `andar`, `correr` | locomoção |
| `flutuar` | corpo sem pernas |
| `ataque`, `soco` | golpes |
| `dano`, `morte` | reação e queda |
| `timeline` | a animação que já está no .blend |

Cada ação leva `quadros`, `fps` e `amplitude`.

## 9. Gabarito: o 3D bate com a arte?

```powershell
horys gabarito goblin
```

O comando renderiza o modelo parado em frente, lado e costas, na câmera e na escala do jogo, e compara com a arte
aprovada:

- **silhueta**: mínimo de 85% igual;
- **materiais no lugar certo**: mínimo de 75%;
- **altura**: diferença de no máximo 8%.

O resultado sai em `saida/gabarito/gabarito.png` e no visor: arte, render e diferença lado a lado. Vermelho é só a
arte; azul é só o render.

Se não passar, ajuste o **modelo** e rode de novo. Altura errada se corrige mudando o tamanho do modelo em metros,
nunca a escala do jogo. Sem gabarito aprovado, a animação recusa rodar.

## 10. Animar

```powershell
horys animar goblin --previa     # rápido: 4 quadros por ação, para conferir no visor
horys animar goblin              # completo: todas as ações × 8 direções
```

O pós-render trava a paleta, limpa pixel solto, corta a cintilação entre quadros e põe o contorno de 1 px.

Depois vêm os **portões**. Eles bloqueiam a entrega quando:
- a figura não cabe no quadro;
- uma junta está fora da peça;
- mais de 2% dos pixels piscam (3% nos golpes);
- no idle, a altura ou o pé muda;
- o andar só desliza.

Saem uma folha (PNG, JSON no formato do Aseprite e GIF) por ação × direção, mais `prancha.png` e
`personagem.aseprite`.

## 11. Exportar para o jogo

```powershell
horys exportar goblin D:\godot\games\vila_monstros\art\personagens
```

Só funciona com os portões ok e o .blend igual ao que foi animado.

## Ver o que falta

```powershell
horys estado
```

Mostra, para cada asset, o que está feito e o que falta.

## Problemas comuns

| Mensagem | O que fazer |
|---|---|
| `a figura tem N px de altura ... Gere a imagem de novo` | A imagem não respeitou a altura. Peça de novo com o número certo (`prompt.md`). |
| `falta aprovar 'arte'` | `horys aprovar <asset> arte`, depois que você disser sim. |
| `... mudou depois da aprovação` | O arquivo mudou: olhe de novo e aprove. |
| `o .blend mudou depois do gabarito` | Rode `horys gabarito` de novo. |
| `NAO_CABE` | Aumente `quadro` no `jogo.json`. Isso vale para o jogo todo. |
| `JUNTA_FORA` | O pivô daquele segmento está no ar: corrija em `asset.json` (`horys inspecionar` sugere). |
| `Blender não encontrado` | Instale o Blender ou defina a variável `BLENDER` com o caminho do `blender.exe`. |

## Testes

```powershell
uv run --extra dev pytest -q
```

Sem o `uv`: `$env:PYTHONPATH="src"; python -m pytest -q`.
