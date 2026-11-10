Repo: C:\Users\artur\workspace\repos\horys\horys-generator-pixel (horys-pixel: MCP que desenha pixel art ao vivo no Aseprite). Leia antes: new-task.md, docs/hd.md, docs/aprendizados-boss.md e resumo.md.

## Pergunta

Existe um jeito melhor de gerar pixel art de qualidade (~80% de aceitação no revisor) para os jogos do Artur, em vez de
"ilustração gerada → redução por moda → limpeza"? Pesquise a fundo e traga opções comparadas, com evidência.

## Por que pesquisar

O fluxo atual bate num teto:
- parado: 84% no melhor caso (17 versões) e 65% pelo fluxo novo;
- animação: 46–55% em todas as abordagens (Kiln, rig de partes, pele ComfyUI + decalque, grade de poses do gerador).

Causas medidas:
- reduzir de ~450 para ~96 px apaga rosto e detalhes;
- o gerador externo não mantém escala, chão nem passada entre quadros;
- o desenho do agente do zero sai geométrico;
- o loop gerar → portão → corrigir passa pelo Artur à mão (Claude Code não gera imagem).

Alvo: boss top-down (3/4 de cima) de ~96 px, máximo 16 cores, parado e andar de frente e de lado.

## O que pesquisar (use WebSearch/WebFetch; cite fontes e datas)

0. **PRIORIDADE: 3D → pixel art (Blender pelo Claude, boas práticas do Noct 3D).** Relato de terceiro: "gerar os
   modelos com o Claude usando o Blender, extraindo as boas práticas do Noct 3D" deu pixel art muito boa. Pesquise e
   desenhe o fluxo: Blender MCP (qual servidor, como instala, o que ele permite), modelagem low-poly feita pelo agente,
   shader toon de 2–3 tons, contorno (Freestyle ou casca invertida), câmera ortográfica 3/4 top-down, render sem
   antialiasing no tamanho final ou em 2× + redução por moda, rig e animação (andar de frente, lado e costas), e o
   pós-processo do horys (paleta travada, contorno, limpeza, portão, revisor). Procure no repo e em
   `~/.horys-pixel/` o que já existe do Noct 3D (o `new-task.md` cita "guia de pose do Kiln/Noct 3D") e extraia as
   boas práticas dele. Proponha o teste com o golem-caveira (blocos de pedra: caso ideal para low-poly).
1. **PixelLab** (pixellab.ai): o que gera (personagem, rotação em 4/8 direções, animação, tiles, inpainting), qualidade
   em 64–128 px, API oficial, servidor MCP oficial, preço e limites, licença de uso comercial dos assets, plugin de
   Aseprite. Como plugar no horys como "fonte" (igual ao `fonte: codex` do `horys_referencia_gerar`).
2. **Retro Diffusion** (extensão do Aseprite e API): modelos, roda local ou nuvem, qualidade, preço, licença.
3. **Modelos abertos locais** no ComfyUI que o Artur já usa: LoRAs e checkpoints de pixel art para SDXL, Flux e outros,
   ControlNet/IP-Adapter para manter o personagem, geração já na grade de pixels (sem redução). Verificar o que cabe numa
   **RTX 3060 de 6 GB**.
4. **Geradores dentro do loop do agente:** Codex/gpt-image, Gemini/Imagen, outros com API, para o loop gerar → portão de
   entrada → correção rodar sozinho.
5. **Animação de pixel art com IA:** PixelLab animate, ferramentas de interpolação para pixel art, esqueleto → pixel
   (renderizar o rig em resolução alta e reduzir), vídeo → quadros. O que existe de fato e com que qualidade.
6. **App próprio:** o que seria um "PixelLab do Artur": modelo aberto local (item 3) + pós-processo do horys
   (paleta, contorno, portão, revisor) + UI no Aseprite. Esforço, peças existentes e riscos.
7. **Pixel art "de verdade" no fluxo:** técnicas que estúdios usam com IA (gerar no tamanho final, gerar em 2× e reduzir
   por moda, pintar por cima de 3D renderizado em baixa resolução, como o Dead Cells).

## Entrega

`docs/pesquisa-geradores.md` com:
- uma tabela comparando as opções: qualidade esperada no alvo, consistência entre quadros, animação, roda local ou paga,
  custo mensal, licença, esforço para integrar no horys, dependência de terceiros;
- para as 2 ou 3 melhores, um **teste concreto** proposto com o golem-caveira
  (`C:\Users\artur\.horys-pixel\experimentos\golem-caveira\conceito.png`), medido pelo portão de entrada, pelo portão de
  medidas e pelo revisor do horys, para comparar com os 65–84% de hoje;
- recomendação com justificativa e o que fica em aberto.

## Regras

- **Só pesquisa e relatório.** Não instalar, baixar modelo, criar conta, assinar serviço nem gastar crédito sem
  autorização do Artur.
- Não fazer engenharia reversa de serviço de terceiros (PixelLab ou outro). Usar só API, documentação e termos públicos.
- Não anexar arte de terceiros em prompts de geração.
- Diferencie o que foi verificado em fonte do que é inferência.
