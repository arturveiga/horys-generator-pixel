---
name: horys-pixel-liso-animacao
description: Planeja, produz e revisa animação de sprites Horys Pixel Liso a partir de um personagem ou conceito já escolhido. Use para ciclos, fluidez, franja/cabelo, roupa, apoio dos pés, timing e fidelidade entre quadros; criação de um personagem novo começa na skill de arte.
---

# Horys Pixel Liso — Animação

Transforme a intenção do movimento em poses e evidências. Mais quadros, mais cores ou um arquivo Aseprite não comprovam qualidade. Preserve o personagem escolhido pelo usuário.

## Aseprite MCP no Hunvix

Use primeiro o servidor MCP `aseprite` (sloplink) já configurado no Codex. Comece cada sessão com `aseprite_help` e confirme a Bridge com `aseprite_status`. O Codex usa a porta 9124; não altere a instalação, dependências, token ou porta do Claude. Nunca habilite `aseprite_run_lua`/`ASEPRITE_MCP_ALLOW_LUA`.

- Antes de editar, use `aseprite_changes`: o artista pode estar desenhando no mesmo arquivo.
- Abra a base convertida, ponha a referência em camada-guia e corrija por cima. Leia a região com `aseprite_read_pixels` e envie mudanças locais por `aseprite_pixel_map` com coordenadas. Para dados grandes, grave JSON no diretório temporário do sistema e use o parâmetro `file`.
- Use `aseprite_view` com `critique:true` para conferir cinza, silhueta e 1x. Separe as camadas que realmente serão animadas.
- Quando o usuário indicar uma seleção, limite a leitura/edição com `rect:"selection"`.
- Não salve por cima de arquivo do artista sem pedido explícito. Use `aseprite_save` com caminho novo dentro da pasta `vNN` do asset.

## Fontes e precedência

KB: `C:/Users/artur/Dropbox/obsidian/Notes/Desenvolvimento de games/pixel-liso`.
Leia `tecnicas/animacao.md`, `tecnicas/animacao-producao-fiel.md` e as seções relevantes de `tecnicas/checklist.md`. Para franja e acessórios, leia também `analise/o-poder-do-pixel/personagens-carismaticos.md`, especialmente raiz presa, onda, luz e fechamento do loop.
Leia a ficha e a direção de arte do projeto. No Hunvix: `C:/Users/artur/Dropbox/obsidian/Notes/Desenvolvimento de games/Hunvix/arte/`.

Pedido atual > ficha aprovada > regras do projeto > padrões da KB. Não reaplique 10 cores, 10 fps, 70 px ou mãos soltas a uma referência que o usuário pediu preservar. Registre exceções; não altere a identidade para passar numa régua inadequada. Tiny Swords mede acabamento e movimento, não substitui o design escolhido.

## Antes de desenhar

1. Abra a referência e a última animação; confira o arquivo-fonte e a duração real. Identifique quais estados o pedido abrange. Reutilize decisões já autorizadas; pergunte apenas o que muda essencialmente o resultado e não pode ser inferido.
2. Registre um contrato curto na documentação canônica: identidade e cores a preservar, resolução, pivô, estado, duração total e por quadro, poses-chave, arco dos pés/mãos, parte que lidera e atraso de cada parte solta **em ms**. Compartilhe a intenção com o usuário, sem exigir um novo sim para trabalho já autorizado.
3. Desenhe/prepare as poses-chave antes dos intermediários. Confira silhueta, identidade e mecânica. **Pose-chave reprovada em identidade ou mecânica bloqueia os intermediários.** Corrija a base antes de multiplicar o erro.
4. Marque por pose quadril, joelhos, tornozelos, pé de apoio, ombros, mãos, raiz e ponta da franja. Confira correspondência entre pose planejada e produzida: oito hashes diferentes podem conter a mesma passada repetida. Registre grade e pivô reais da fonte antes de converter; o gerador pode ignorar dimensões pedidas.

Se só existe um conceito grande, estabilize primeiro o sprite-base na resolução escolhida. Não trate uma folha nova de corpo inteiro como conversão fiel: compare a base com o conceito, fixe os marcos do rosto e as mechas, e só depois anime. Se tentativas de geração repetem a mesma falha anatômica, mude para construção/revisão explícita das poses na fonte editável em vez de insistir em prompts da folha inteira.

No Hunvix, a conversão fiel começa por uma ilustração chapada feita para conversão, com a paleta vigente e fundo liso. Reduza a partir da resolução cheia em OKLab escolhendo a cor **mais frequente de cada bloco**; média de área mistura contornos e borra. Depois descasque o anel externo que o `grade.py` recompõe, funda manchas soltas, afine linhas internas para 1 px e redesenhe o rosto manualmente nas posições medidas. Use `art-src/pixel-liso/paleta-hunvix-v2.json`; não invente cores fora dela.

O portão M05 é diagnóstico, não licença para destruir leitura. Se a mancha média reprovar e simplificar piorar o personagem, preserve as duas opções e peça a decisão do usuário.

## Produção

- Use o meio de edição adequado disponível (Aseprite/grade; geração de imagem quando aplicável). Uma folha gerada é candidata: não equivale a animação pronta. Preserve a fonte e numere versões.
- Faça o movimento principal primeiro, secundário depois. Raiz do cabelo acompanha o crânio; meio flexiona; ponta continua e retorna em arco. Não mova todo o cabelo como placa rígida. Mechas, bolsa e roupa não precisam atingir os extremos juntas.
- Construa contato, absorção de peso, passagem e alto para os dois pés. Confira o apoio em relação ao chão; não converta uma caminhada em corrida para ganhar amplitude.
- Faça intermediários que conservem volume, articulações e clusters. Não infle o número repetindo desenhos, usando ping-pong de uma passada ou interpolação óptica. Holds intencionais são duração, não quadros fingidos.
- Recortes, rigs e transformações podem apoiar o rascunho. A entrega exige articulações fechadas, oclusões resolvidas e mudanças de forma que funcionem visualmente; deslocar membros recortados não basta.
- Use um canvas, uma escala e um pivô para o ciclo todo. Nunca autoajuste cada pose à própria bounding box. Não realinhe cada quadro pelo pé mais baixo: isso apaga o quique. Se a geração variar o tamanho do crânio, redesenhe, não normalize a altura do corpo inteiro.
- Use uma única paleta explícita para toda a animação. Se o usuário autoriza expansão, registre novas cores e proveniência. Não quantize independentemente cada quadro. Uma amostragem ou redução não é identidade RGB perfeita com a imagem grande; informe essa diferença.
- Defina duração pelo movimento. 12–16 desenhos podem ser um ponto de partida para um andar detalhado, não uma regra para toda animação. Ao mudar fps, preserve atrasos físicos em ms e reveja o espaçamento.

## Verificação com evidência

Confira o ciclo em 1×, ampliado com nearest, na velocidade final e lenta. Assista vários loops; folha estática não prova fluidez. Compare lado a lado com a referência com escala de apresentação declarada.

Faça duas avaliações separadas:

1. **Estrutural:** quantidade e duração reais, hashes de quadros, alpha, paleta, canvas, cortes, duplicatas e diferenças no fechamento. Use `scripts/auditar_animacao.py` com um GIF ou JSON-array do Aseprite. As métricas são triagem; não certificam beleza, pé plantado, inércia ou redesenho.
2. **Visual:** identidade (rosto/proporção/franja), limpeza, apoio/peso, arcos, overlap, timing e costura. Confira o atraso da ponta relativamente à cabeça; deslocamento absoluto da ponta não demonstra flexão.

Para revisão de produção, peça um subagente independente com referência, contrato, folha, prévia, fonte e relatório. Peça inventário completo, critérios 0–100, falhas graves e localização por quadro. Diga quais métricas são aplicáveis: não use silenciosamente limites calibrados para outra escala/paleta. O veredito se refere ao hash dos arquivos avaliados. Uma revisão baseada apenas em quadros estáticos deve declarar que não assistiu ao loop.

Aceitação interna: nenhuma falha grave e média >= 80, com cada critério principal >= 75; isso não substitui aprovação do usuário. No máximo três rodadas por etapa. Se persistirem falhas, entregue o melhor **estudo reprovado**, diagnóstico e próximo trabalho específico; não o chame de pronto e não o integre.

## Entrega

Entregue Aseprite editável, PNG, JSON com durações/tags e GIF de prévia. Declare se as partes estão separadas ou se há uma única camada por quadro. Inclua preview inline e links dos arquivos. Registre decisões e avaliação no Obsidian, sem espelhar documentação no repositório. Arte-fonte, scripts e resultados de medição ficam junto do asset.
Integração no jogo somente quando estiver no escopo. Não altere relógio de simulação para mudar fps visual.
