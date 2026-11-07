# Aprender o estilo

O Claude e o Codex **não são re-treinados**. Eles ficam como diretores: perguntam, convertem, limpam e revisam. O que
aprende o estilo são duas coisas, as duas por [pacote de estilo](estilos.md).

## 1. Memória de gosto (sem treino; desde a fase 2)
- Cada Aprovar / Refazer no Aseprite é guardado em `estilos/<nome>/gosto/`: sprite, etapa, comentário e defeito.
- Padrões repetidos viram **regra proposta** ("recusa olho de 1 px"), que só entra no estilo com o sim de quem usa.
- Os aprovados viram **exemplos** que entram como referência nos próximos pedidos do mesmo tipo.
- As metas do portão podem ser **recalibradas** com os sprites aprovados.

## 2. Modelo de imagem treinado (LoRA; fase 6)
Um ajuste pequeno sobre um modelo de imagem aberto, usado como **gerador de referência** quando a pessoa não tem
imagem. O que ele gera passa pelo mesmo pipeline: conversão por moda com a paleta travada, limpeza, portão e revisor.

### Ferramenta: kohya-ss/sd-scripts
Escolhida para que **qualquer pessoa com o repo** consiga treinar o próprio estilo:
- **Linha de comando e configuração em arquivo (TOML):** o agente gera, roda e versiona o treino sem interface gráfica.
- **Cobre o caminho todo:** SD 1.5, SDXL (e famílias mais novas), LoRA, legendas, latentes em cache.
- **Roda em GPU modesta:** gradient checkpointing, otimizador 8-bit, precisão mista e cache, o que viabiliza 6–8 GB.
- **A mais usada e documentada** para LoRA, licença Apache-2.0 (compatível com distribuir o repo).
- É instalada à parte pelo `horys` (ambiente Python próprio), não copiada para dentro do repo.
- Alternativas avaliadas: **OneTrainer** (boa em pouca VRAM, mas pensada para interface gráfica) e **ai-toolkit**
  (focada em modelos grandes e GPUs de 24 GB). Ficam como plano B.

### Perfis por placa (o `horys` detecta a GPU e escolhe)
| VRAM | Modelo-base | Observação |
|---|---|---|
| 6 GB (ex.: RTX 3060 Laptop do Artur) | SD 1.5 | SDXL só com otimização pesada e resolução menor; lento |
| 8–12 GB | SDXL | otimizações ligadas |
| 16 GB ou mais | SDXL ou mais novo | configuração padrão |
| sem GPU NVIDIA | — | só memória de gosto; treinar em GPU alugada e trazer o LoRA |

### Conjunto
- Fontes: os aprovados do estilo (automático) e as imagens que a pessoa mandar.
- O agente organiza: tira duplicata, recorta, padroniza fundo e tamanho (ampliação sem suavizar, vizinho mais
  próximo), escreve a legenda de cada imagem e registra a origem/licença de cada lote.

### Ciclo
```
aprovações → conjunto cresce → a cada N novas, o agente propõe treinar a vN+1
          → treina (kohya) → gera o mesmo lote de teste com vN e vN+1
          → o revisor dá nota às duas → a pessoa escolhe → a vencedora vira o gerador padrão do estilo
```
Nenhuma versão é promovida sem nota maior que a anterior **e** o sim de quem usa.
