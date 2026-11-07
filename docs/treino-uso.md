# Treinar o LoRA do seu estilo: guia de uso

Guia prático do módulo `horys_pixel.treino`. O porquê das escolhas está em [treino.md](treino.md).

> **Regra de ouro:** todo comando que baixa, treina ou gera imagem só faz isso com `--executar`.
> Sem `--executar`, ele mostra o que faria: comandos, caminhos e arquivos de configuração. Rode sempre
> uma vez sem `--executar` para conferir.

Todos os comandos começam com `python -m horys_pixel.treino` (abreviado como `treino` abaixo), rodados da
raiz do repo com o pacote instalado (`pip install -e .`).

## 1. Requisitos
- **GPU NVIDIA** com driver recente (`nvidia-smi` funcionando). Sem GPU NVIDIA dá para usar só a memória de
  gosto, ou treinar numa GPU alugada (veja o fim deste guia).
- **Windows 10/11** (Linux deve funcionar, mas ainda não foi testado), **git**, **Python 3.10** (recomendado
  pelo sd-scripts; 3.11 funciona, mas o sd-scripts não testa nessa versão).
- **Disco:** ~6 GB para o kohya (torch com CUDA + dependências) e 2 a 7 GB por modelo-base.
- **RAM:** 16 GB ou mais (32 GB é confortável).

Confira a placa e o perfil escolhido:
```
treino gpu
treino perfil            # ou: treino perfil --todos
```

| VRAM | Perfil | Modelo-base | Resolução |
|---|---|---|---|
| ~6 GB | `sd15-6gb` | SD 1.5 | 512 |
| 8 a 10 GB | `sdxl-8gb` | SDXL | 768 |
| 10 a 15 GB | `sdxl-12gb` | SDXL | 1024 |
| 16 GB ou mais | `sdxl-16gb` | SDXL | 1024 |

Use `--perfil <nome>` em qualquer comando para forçar outro perfil.

## 2. Instalar o kohya (sd-scripts)
O horys instala o [kohya-ss/sd-scripts](https://github.com/kohya-ss/sd-scripts) (Apache-2.0) **fora do repo**,
em `~/.horys-pixel/kohya/`, com ambiente Python próprio:
```
treino instalar             # mostra os passos
treino instalar --executar  # baixa ~3–5 GB e instala (10 a 30 min, conforme a internet)
```
Os passos: `git clone`, `venv`, torch 2.6.0 com CUDA (índice oficial do PyTorch, `cu124` se o driver for ≥ 525),
`pip install -r requirements.txt` e `accelerate config default` (sem perguntas). O log fica em
`~/.horys-pixel/kohya/instalar.log`. Opções: `--ref <tag ou commit>` para fixar uma versão do sd-scripts,
`--python <caminho>` para escolher o Python do venv, `--cuda cu118|cu124|cu126`.

## 3. Baixar o modelo-base (você baixa; o repo não distribui pesos)
Baixe **um arquivo `.safetensors`** e guarde onde quiser (sugestão: `~/.horys-pixel/modelos/`).

- **Perfil `sd15-6gb` → Stable Diffusion 1.5.** O repositório original (runwayml) saiu do ar; a cópia oficial está
  em `huggingface.co/stable-diffusion-v1-5/stable-diffusion-v1-5` (arquivo `v1-5-pruned-emaonly-fp16.safetensors`,
  ~2 GB). Licença **CreativeML OpenRAIL-M**.
- **Perfis SDXL → SDXL base 1.0**: `huggingface.co/stabilityai/stable-diffusion-xl-base-1.0`
  (`sd_xl_base_1.0.safetensors`, ~7 GB). Licença **CreativeML Open RAIL++-M**.
- Modelos da comunidade (Civitai etc.) também servem, desde que sejam da mesma família (SD 1.5 ou SDXL)
  **e a licença permita o seu uso** — algumas proíbem uso comercial ou exigem crédito. Leia antes.

Ao baixar, você aceita a licença do modelo. Ela vale também para o que você gerar e distribuir com ele.

## 4. Preparar o conjunto
O conjunto junta os **aprovados da memória de gosto** (`estilos/<nome>/gosto/aprovados/`) e, se quiser,
**imagens suas**, sempre com a licença declarada:
```
treino preparar --estilo-dados estilos/meu-estilo --trigger meuestilo
treino preparar --estilo-dados estilos/meu-estilo --imagens C:\arte\lote1 --licenca "minha arte" --tipo personagem
```
- **Trigger:** palavra rara, minúscula, sem espaço (ex.: `hpxliso`). Ela ativa o estilo no prompt.
- **Licença:** só entra arte sua ou cuja licença permita treino. Cada imagem fica registrada com origem e licença
  em `conjunto/manifesto.json`. Os lotes ficam guardados e entram de novo nos próximos preparos.
- O horys tira duplicatas (inclusive cópias ampliadas), recorta o transparente com margem, põe fundo liso
  (`--fundo ffffff`; o `#` é opcional e no PowerShell precisa de aspas), deixa quadrado e amplia **por vizinho mais próximo** até a resolução do perfil. Nenhuma
  cor nova é criada.
- Legenda de cada imagem: `<trigger>, pixel art, <tipo>, <descrição>`. O modelo entende inglês: descrições em
  inglês dão resultado melhor. Os tipos comuns (personagem, item, tile...) já são traduzidos.
- **Quantidade:** 15 a 100 imagens variadas. Com menos de 10 o horys avisa.

Resultado: `conjunto/img/<repetições>_<trigger>/` com `.png` + `.txt`, no formato do sd-scripts.

## 5. Configurar e treinar
```
treino configurar --estilo-dados estilos/meu-estilo --modelo C:\modelos\v1-5-pruned-emaonly-fp16.safetensors
treino treinar --estilo-dados estilos/meu-estilo              # mostra o comando
treino treinar --estilo-dados estilos/meu-estilo --executar   # treina
```
`configurar` cria a próxima versão (`lora/v1/`, `lora/v2/`...) com `dataset.toml`, `treino.toml` e `plano.json`
(os TOML podem ser editados à mão antes de treinar). `treinar --executar` roda `accelerate launch` com
`train_network.py` (SD 1.5) ou `sdxl_train_network.py` (SDXL), grava o log em `lora/vN/treino.log` e o
resumo em `lora/vN/info.json` (perfil, conjunto, hash do modelo-base, duração). O LoRA sai em
`lora/vN/<trigger>_vN.safetensors`.

### Quanto tempo leva (perfil de 6 GB, ex.: RTX 3060 Laptop)
Estimativa honesta, que varia com a temperatura do notebook e o que mais estiver aberto:
- ~2.000 passos (ex.: 30 imagens × 7 repetições × 10 épocas) a **0,6–1,5 s por passo** → **25 a 60 min**,
  mais alguns minutos para carregar o modelo e montar o cache.
- Ligue o notebook na tomada, em modo desempenho; feche jogos e vídeos. Se faltar memória ("CUDA out of
  memory"), feche outros programas que usam a GPU e tente de novo.
- SDXL em 6 GB (forçando `--perfil sdxl-8gb`) é **várias vezes mais lento** e pode não caber. Não recomendado.

## 6. Avaliar
```
treino avaliar --estilo-dados estilos/meu-estilo --executar
```
Gera o **mesmo lote de teste** (8 prompts fixos, um por tipo de asset, com seeds fixos) com a versão nova e com
a de comparação: a ativa, ou a anterior, ou o modelo sem LoRA (`--contra base`). Monta uma prancha lado a lado
em `lora/vN/avaliacao/` e grava `lora/vN/avaliacao.json`. Imagens já geradas de uma versão são reaproveitadas.

O revisor (Claude ou Codex) dá nota às duas; registre:
```
treino notas --estilo-dados estilos/meu-estilo --versao v2 --nota 82 --revisor codex
treino notas --estilo-dados estilos/meu-estilo --versao v2 --notas-json notas.json   # {critério: nota}
```

## 7. Promover
```
treino promover --estilo-dados estilos/meu-estilo --versao v2 --aprovado
```
A versão só vira a ativa (`lora/ativo.json`) se a nota dela for **maior** que a da ativa **e** você der o sim
(`--aprovado`). Sem isso, o comando explica o que faltou e nada muda.

## 8. Gerar referências
```
treino gerar --estilo-dados estilos/meu-estilo --prompt "knight with a spear" --tipo personagem -n 3 --executar
```
Usa a versão ativa e salva em `lora/referencias/<data>/`. A imagem é só **referência**: passa pela conversão
com a paleta travada, limpeza, portão e revisor, e nunca vira asset direto.

## Sem GPU NVIDIA (ou com pouca VRAM)
Rode `preparar` e `configurar` com `--perfil <nome>` e leve o conjunto e os TOML para uma GPU alugada com o
sd-scripts instalado (ajuste os caminhos dentro dos TOML). Traga o `.safetensors` para `lora/vN/` com o nome
que está em `plano.json` e siga com `avaliar`, `notas` e `promover`.

## Onde fica cada coisa
```
~/.horys-pixel/kohya/        sd-scripts, venv, accelerate.yaml, instalar.log
estilos/<nome>/conjunto/     img/<rep>_<trigger>/, manifesto.json, lotes.json
estilos/<nome>/lora/vN/      dataset.toml, treino.toml, plano.json, treino.log, info.json, *.safetensors,
                             teste/ (lote de teste), avaliacao/ (prancha), avaliacao.json, notas.json
estilos/<nome>/lora/ativo.json   versão ativa e histórico
```
`gosto/`, `conjunto/` e `lora/` ficam fora do git.
