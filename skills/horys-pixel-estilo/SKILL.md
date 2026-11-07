---
name: horys-pixel-estilo
description: Cria e evolui um PACOTE DE ESTILO de pixel art a partir de imagens que a pessoa gosta ("quero criar meu estilo") — mede as imagens, propõe a bíblia (os 15 itens do guia de estilo), a paleta em rampas e a régua, calibra o portão de medidas, testa com um asset e, se a pessoa quiser, treina um modelo de imagem (LoRA) local no estilo. Use quando pedirem para criar um estilo novo, ajustar um estilo existente, recalibrar o portão ou treinar/avaliar o modelo do estilo.
---

# horys-pixel-estilo

Ferramentas MCP `horys_*`. Um estilo é um pacote em `~/.horys-pixel/estilos/<nome>/` (ver `docs/estilos.md` do repo
horys-pixel): `estilo.json`, `estilo.md` (a bíblia), paleta, régua, metas, e os dados (gosto, conjunto, LoRA).

## Criar um estilo
1. **Imagens e licença.** Peça de 10 a 100 imagens do estilo (`horys_perguntar`; caminhos em "Outro", ou já vieram
   no pedido). Pergunte a ORIGEM/licença de cada lote: arte da própria pessoa, comprada com licença, ou só
   referência (serve para medir, NÃO para treinar).
2. **Medir.** `horys_estilo_novo(nome, imagens, autor, licenca)`: escala do pixel, paleta em rampas, contorno,
   clusters, tons por material, proporções, AA/dithering → rascunho do `estilo.md`.
3. **Confirmar item por item** (até 4 por rodada no painel), recomendando o que a medida sugere:
   contorno; paleta e número de cores; tons por material; estilo de pintura; vista; tema; saturação e temperatura;
   fundo; textura; coerência; referências; quadros; estilo de animação; proporções; densidade de assets.
   Edite o `estilo.md` e o `estilo.json` do pacote com as respostas (os itens "a confirmar" somem).
4. **Paleta.** Mostre as rampas (`horys_aprovar` com a imagem da paleta, se houver) e ajuste: passos de L ~0,10,
   sombra girando o matiz, sem buraco de valor entre o contorno e os médios.
5. **Régua.** Quais sprites medem a qualidade (da própria pessoa ou com licença). Grave em `regua.pasta` e
   `regua.por_categoria` no `estilo.json` (caminhos locais; nada de arte de terceiros no repo).
   `horys_estilo_calibrar`: os bons têm que passar todos e os estragados reprovar todos. Se não fechar, mostre os
   números e ajuste com a pessoa antes de confiar no portão.
6. **Teste.** Um asset simples pelo fluxo completo (skill horys-pixel) para validar o pacote. O que a pessoa
   recusar vira ajuste no estilo.
7. **Treino (opcional).** `horys_treino_status` (GPU e perfil). Se houver imagens com licença para treino ou
   aprovados suficientes, proponha treinar — e PEÇA O SIM antes de cada passo pesado:
   `horys_treino(comando: 'instalar', executar: true)` (3–5 GB, uma vez), a pessoa baixa o modelo-base (licença
   dele), `preparar` → `configurar` → `treinar(executar)` → `avaliar(executar)` → o revisor dá nota às duas
   versões → `notas` → `promover` só com nota maior **e** o sim. Detalhes: `docs/treino-uso.md` do repo.

## Evoluir um estilo
- `horys_gosto_consultar(estilo)`: defeitos que voltam viram **proposta** de regra no `estilo.md` — nunca mude o
  estilo sem o sim da pessoa. Registre a data e o motivo.
- Mudou paleta, contorno ou proporção: recalibre (`horys_estilo_calibrar`) e, se houver LoRA, avalie de novo.
