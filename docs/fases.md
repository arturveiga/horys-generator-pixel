# Fases

Cada fase termina testável sozinha. A `horys-pixel-liso` e a `pixelart-review` continuam funcionando até a fase 5.

> **Estado em 2026-11-06:** fases 1 a 5 implementadas e testadas (126 testes; ponta a ponta com o Aseprite real
> e o Claude sem terminal). Fase 6 implementada sem rodar (instalar o kohya e o modelo-base é decisão do Artur).
> Falta validar o Codex como motor (estava sem cota) — ver `PENDENCIAS.md` e `CODEX_VALIDAR.md`.

## Fase 0: base conceitual (feita em 2026-11-05)
- KB do Obsidian só com conceito, por assunto; notas de vídeo e prints arquivados fora do cofre.
- **Pronto:** nenhuma referência de vídeo na KB; skill aponta para as técnicas.

## Fase 1: servidor e ponte
- `horysd` em Python, extensão mínima no Aseprite, ponte `horys-mcp`.
- Ferramentas de desenho (status, sprite, camada, quadro, pixel_map, ler, ver, mudanças, seleção, desfazer, salvar).
- **Pronto:** Claude Code e Codex conectados ao mesmo tempo desenham no mesmo sprite, sem trocar porta.

## Fase 2: conversa e memória de gosto
- Painel no Aseprite; `perguntar`, `aguardar`, `aprovar`, `progresso`.
- `gosto_registrar` e `gosto_consultar`.
- **Pronto:** um briefing completo respondido só pelo painel; cada resposta registrada.

## Fase 3: estilos, medidor único e ferramentas de estilo
- Formato do pacote de estilo; o Horys Pixel Liso vira o primeiro pacote (apontando para o Obsidian).
- `grade`, `medir`, `pixel_review`, `conceito` e `calibrar` viram módulos do servidor; **um medidor só**.
- `asset_novo`, `paleta`, `contorno`, `sombra`, `referencia`, `converter`, `limpar`, `afinar`, `portao`, `regua`,
  `medir_arquivo`, `exportar`.
- **Pronto:** ida e volta do `construtor` v04 idêntica pixel a pixel; o portão no sprite aberto dá o mesmo resultado
  que o `grade.py` de hoje; calibração 46/46 e 19/19 mantida; `medir_arquivo` reproduz os achados da
  `pixelart-review` num sprite já revisado.

## Fase 4: botão Gerar e revisor cruzado
- Janela "Novo asset" completa; motor por pedido (`claude -p` / `codex exec`); fila com estado salvo.
- Revisor como execução separada, cruzado por padrão; **Horys › Revisar este sprite**.
- **Pronto:** "um viking" sai do clique até a v01 revisada sem tocar no terminal, com os dois motores.

## Fase 5: skills únicas, assistente de estilo e pacote
- Skills `horys-pixel` (gerar) e `horys-pixel-review` (revisar), agnósticas de motor.
- Assistente **Novo estilo** no Aseprite.
- Plugin do Claude Code, configuração do Codex, instalador; licença do repo.
- **Pronto:** instalação limpa numa máquina sem nada do Artur cria um estilo novo a partir de imagens e gera um
  asset nele; a `horys-pixel-liso` e a `pixelart-review` passam a apontar para cá.

## Fase 6: modelo treinado (kohya-ss/sd-scripts)
- Instalação do kohya em ambiente próprio, perfis por VRAM, conjunto com legendas e origem, avaliação pelo revisor,
  promoção com o sim de quem usa.
- **Pronto:** no PC do Artur (6 GB, SD 1.5) a vN+1 ganha da vN no mesmo lote de teste e vira o gerador de referência
  padrão do Horys Pixel Liso.

## Fase 7: referência primeiro, gerador trocável e sequência (2026-11-09)
Plano em [new-task.md](../new-task.md): padrões de entrada em dados, prompt de tradução, portão de entrada, motor de
sequência, fontes de movimento (grade, vídeo, Kiln), revisor estrutural × acabamento e gosto pelo retoque. O `TODO.md`
antigo ficou em [historico/TODO.md](historico/TODO.md).
