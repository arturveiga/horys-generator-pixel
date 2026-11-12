# Experimento: animação de boss por modelo 3D

Pipeline: modelo 3D low-poly → câmera ortográfica 3/4 fixa → render em pixel art → motor de sequência
do Horys (`horys_pixel.sequencia`, loader `render3d`) → spritesheet do Godot 4.

Custo zero obrigatório: só ferramentas livres e locais. Nenhum serviço pago de geração 3D.
Código GPL de terceiros (Blender, add-ons, Blockbench) fica **fora** do repositório; aqui só há scripts nossos.

Nesta etapa não há modelo nem animação: só regras e código.

## Pastas

| Pasta | Conteúdo |
|---|---|
| `blender/` | `render_pixel.py` (caminho nativo A3) e `config_exemplo.json` |
| `blockbench/` | Experimento B (BlockBenchMCP externo), ver o README de lá |
| `renders/<acao>/` | PNGs `0000.png…` + `manifest.json` (gerados) |
| `spritesheets/` | Folhas exportadas para o Godot (geradas) |
| `previews/` | GIFs e folhas de contato para revisão (geradas) |
| `auditoria.md` | Versões instaladas, licenças e riscos |

## Render (Blender, headless)

```
blender -b cena.blend -P blender/render_pixel.py -- --config blender/config_exemplo.json
```

O script não salva o `.blend` e não mexe nas preferências. A câmera é enquadrada uma vez pelo bbox da ação
inteira, nunca por quadro, para o personagem não "respirar" de tamanho.

## Contrato do manifest (versão 1)

Toda fonte (Blender, Blockbench ou outra) escreve `renders/<acao>/manifest.json` exatamente assim:

```json
{
  "versao": 1,
  "fonte": "blender",
  "acao": "idle",
  "fps": 12,
  "canvas": [256, 256],
  "pivo": [128, 200],
  "camera": {"pitch": 32.0, "yaw": 0.0, "ortho_scale": 3.2},
  "loop": true,
  "quadros": ["0000.png", "0001.png"]
}
```

| Campo | Tipo | Regra |
|---|---|---|
| `versao` | int | sempre `1` neste contrato |
| `fonte` | str | `"blender"` ou `"blockbench"` |
| `acao` | str | nome da pasta da ação |
| `fps` | número | quadros por segundo já considerando o passo |
| `canvas` | [W, H] | tamanho em px de todos os PNGs (iguais) |
| `pivo` | [x, y] | px, origem no canto de cima à esquerda; origem da raiz/armature projetada no chão |
| `camera` | obj | `pitch` e `yaw` em graus, `ortho_scale` em unidades de mundo |
| `loop` | bool | `true`: o último quadro não repete o primeiro |
| `quadros` | [str] | nomes relativos à pasta do manifest, em ordem |

Pitch, yaw e escala são os mesmos para todos os assets do jogo.
