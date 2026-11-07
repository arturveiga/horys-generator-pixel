# Estilos: cada pessoa cria o seu

O repo não traz "o estilo do Artur" embutido. Ele traz o **motor** e uma **base universal** de boas práticas de pixel
art; o estilo é um **pacote** que cada pessoa cria, ajusta e treina. O Horys Pixel Liso é o primeiro pacote.

## O que é um pacote de estilo

```
estilos/<nome>/
  estilo.md           a bíblia: escala, proporção, rosto, cor, contorno, luz, animação, cenário, efeitos, UI
  paleta.gpl/.hex/.json  rampas travadas
  regras/             técnicas próprias do estilo (por assunto), por cima da base universal
  regua.json          caminhos dos sprites-régua (podem ficar fora do repo; ver Licenças)
  metas.json          metas do portão calibradas na régua
  gosto/              memória de aprovações e recusas            (fora do git)
  conjunto/           imagens de treino com legenda             (fora do git)
  lora/               versões treinadas + avaliação de cada uma  (fora do git)
  estilo.json         nome, autor, licença, versão, motor padrão, fonte de referência padrão
```

Um pacote pode também **apontar para uma pasta externa** em vez de copiar (ex.: o Horys aponta para a base do
Obsidian, que continua sendo a fonte da verdade do Artur).

## Criar meu estilo (assistente no Aseprite)
**Horys › Estilos › Novo estilo.** O motor conduz, pelo painel de conversa:
1. **Nome e imagens:** você manda de 10 a 100 imagens do estilo que quer ("gosto disso").
2. **Leitura das imagens:** o motor mede (cores, tamanho de cluster, contorno, tons por material, proporção, grade) e
   propõe o rascunho do `estilo.md`, uma resposta por item do guia de estilo (contorno, paleta, tons, vista,
   saturação, fundo, textura, quadros, proporções...). Você confirma ou ajusta item por item.
3. **Paleta:** extraída das imagens e organizada em rampas com hue shift; você aprova.
4. **Régua:** escolhe quais sprites medem a qualidade. As metas do portão são calibradas neles (`calibrar`): os bons
   têm que passar e versões estragadas automaticamente têm que reprovar.
5. **Primeiro asset de teste:** um personagem simples passa por todo o fluxo, para validar o pacote.
6. **Treino (opcional):** se as imagens permitirem, propõe treinar o primeiro LoRA ([treino](treino.md)).

## Usar e evoluir
- Cada pedido escolhe o estilo (o projeto tem um padrão: Hunvix → Horys Pixel Liso).
- Aprovações e recusas alimentam `gosto/`; regras repetidas viram proposta de mudança no `estilo.md`.
- Mudou o estilo? Nova versão do pacote, recalibra as metas e, se houver LoRA, avalia de novo.

## Licenças (porque o repo vai ser distribuído)
- **O repo nunca traz arte de terceiros.** Sprites de pacotes comprados ou de outros jogos (ex.: Tiny Swords) entram só
  por caminho local em `regua.json`, na máquina de quem tem a licença.
- **Conjunto de treino:** a arte da própria pessoa, ou arte cuja licença permita treino. O assistente pergunta a
  origem de cada lote e registra no `estilo.json`.
- **Modelos-base** (SD 1.5, SDXL) são baixados por quem usa, aceitando a licença deles. O repo não distribui pesos.
- **Base universal:** escrita com as nossas palavras, só conceito, com créditos às fontes.
