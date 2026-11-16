# Ferramentas MCP

Gerado por `scripts/gerar_docs_ferramentas.py` a partir do código — não edite à mão.

Coordenadas 0-based, (0,0) no canto de cima à esquerda; quadros e camadas 0-based.

## Desenho (ponte com o Aseprite)

### `horys_status`

Conexão com o Aseprite e o sprite ativo (tamanho, camadas de baixo para cima, quadros, tags). Coordenadas 0-based, (0,0) no canto de cima à esquerda; quadros e camadas 0-based.

Parâmetros: — (`*` = obrigatório)

### `horys_sprite_novo`

Cria um sprite RGB transparente. Para asset do estilo prefira horys_asset_novo (quadro, pivô, camadas por parte, paleta e tags de uma vez).

Parâmetros: `largura`*, `altura`*, `nome` (`*` = obrigatório)

### `horys_abrir`

Abre um arquivo (.aseprite, .png...) no Aseprite.

Parâmetros: `arquivo`* (`*` = obrigatório)

### `horys_sprites`

Lista os sprites abertos no Aseprite; com 'indice' ou 'arquivo', ativa um deles.

Parâmetros: `indice`, `arquivo` (`*` = obrigatório)

### `horys_salvar`

Salva o sprite. 'copia': salva uma cópia e o sprite continua com o nome atual. Só salva dentro das pastas permitidas e nunca sobrescreve sem 'sobrescrever': true.

Parâmetros: `arquivo`, `copia`, `sobrescrever` (`*` = obrigatório)

### `horys_camada`

Camadas: acao criar|remover|renomear|propriedades|ordem|ativar. Ex.: {acao:'criar', nome:'cabeca', acima_de:'corpo'}, {acao:'ordem', nomes:[de baixo para cima]}, {acao:'propriedades', nome:'sombra', opacidade:77, visivel:true}.

Parâmetros: `acao`*, `nome`, `novo`, `acima_de`, `abaixo_de`, `visivel`, `opacidade`, `nomes` (`*` = obrigatório)

### `horys_quadro`

Quadros (0-based): acao criar|remover|duracao|ativar|garantir. Ex.: {acao:'criar', depois_de:2, copiar:true}, {acao:'duracao', todos:true, ms:100}, {acao:'garantir', total:8}.

Parâmetros: `acao`*, `indice`, `depois_de`, `copiar`, `ms`, `todos`, `total` (`*` = obrigatório)

### `horys_tag`

Tags de animação: {acao:'criar', nome:'idle', de:0, ate:7} ou {acao:'remover', nome}.

Parâmetros: `acao`*, `nome`*, `de`, `ate` (`*` = obrigatório)

### `horys_pixel_map`

Desenha pixels exatos: 'paleta' {letra: '#rrggbb'} + 'linhas' (uma string por linha).
'.' e espaço não mexem; uma letra mapeada para '#00000000' apaga. x/y deslocam o bloco. Carimbos: 'stamps'
{nome:{rows:[...], palette?}} + 'place' [[nome, x, y, 'h'|'v'|'hv'?], ...]. Dado grande: 'arquivo' = um .json com
esses mesmos campos. 'camada' (criada se faltar) e 'quadro' (0-based) usam os ativos se omitidos.
'trava': lista de '#hex' (a paleta do asset) ou 'oficio:<nome>' (paleta da base): cada cor é puxada para a mais
próxima (CIELAB) e a resposta diz o que mudou; ΔE > 12 = a paleta não tem esse tom. Vale para o sprite até
'trava': [] desligar.

Parâmetros: `paleta`, `linhas`, `x`, `y`, `camada`, `quadro`, `stamps`, `place`, `arquivo`, `trava` (`*` = obrigatório)

### `horys_set_pixels`

Poucos pixels soltos: 'pixels' [[x, y, '#rrggbb'], ...].

Parâmetros: `pixels`*, `camada`, `quadro` (`*` = obrigatório)

### `horys_ler_pixels`

Lê pixels no mesmo formato do horys_pixel_map (paleta + linhas). Sem 'camada' lê a imagem composta visível. 'rect' {x,y,w,h} ou 'selecao'. Passe a sua 'paleta' para reaproveitar as letras.

Parâmetros: `camada`, `quadro`, `rect`, `paleta`, `composto` (`*` = obrigatório)

### `horys_ver`

Mostra o sprite como imagem. Sem 'modo': 'critica' true = cor | cinza (valores) | silhueta | 1× e 2× numa imagem pequena (o melhor jeito de julgar); 'rect' amplia um detalhe. 'modo': 'comparar' (camada de referência à esquerda, arte sem ela à direita; 'referencia' = nome da camada, padrão a que começa com refer/guia), 'filmstrip' (todos os quadros numa imagem: o jeito certo de revisar animação), 'onion' (quadro opaco sobre vizinhos fantasmas; 'antes', 'depois', 'opacidade'), 'diff' (texto do que mudou entre 'de' e 'ate'). Sem camada = composto.

Parâmetros: `quadro`, `camada`, `rect`, `critica`, `escala`, `modo`, `referencia`, `antes`, `depois`, `opacidade`, `de`, `ate` (`*` = obrigatório)

### `horys_mudancas`

O que o usuário mudou no Aseprite desde a última vez (1ª chamada só marca o ponto de partida). Devolve, por camada e quadro, a área mudada e as linhas dela.

Parâmetros: `quadros` (`*` = obrigatório)

### `horys_selecao`

A seleção atual do usuário no Aseprite ('isto', 'aqui'): {x,y,w,h} ou vazia.

Parâmetros: — (`*` = obrigatório)

### `horys_limpar_camada`

Apaga o conteúdo de uma camada num quadro (ou em todos).

Parâmetros: `camada`*, `quadro`, `todos` (`*` = obrigatório)

### `horys_desfazer`

Desfaz (ou refaz, com 'refazer': true) passos no Aseprite. Cada chamada de ferramenta que muda pixels é um passo.

Parâmetros: `passos`, `refazer` (`*` = obrigatório)

### `horys_copiar`

Copia (e espelha) uma região: 'rect' origem, destino x/y, 'flip' h|v|hv, de/para camada e quadro. Útil para simetria: desenhe metade e espelhe.

Parâmetros: `rect`*, `x`*, `y`*, `flip`, `camada`, `quadro`, `para_camada`, `para_quadro` (`*` = obrigatório)

### `horys_lote`

Várias ferramentas em sequência numa chamada: 'passos' [{ferramenta, args}, ...]. Para no primeiro erro.

Parâmetros: `passos`* (`*` = obrigatório)

## Conversa (painel do Aseprite)

### `horys_perguntar`

Faz até 4 perguntas ao usuário no painel do Aseprite (como o AskUserQuestion).
Cada pergunta: {pergunta, cabecalho (até 12 letras), opcoes:[{rotulo, descricao}] (2–4, a recomendada primeiro e com
'(recomendado)'), multipla?}. O painel sempre oferece 'Outro'. Devolve um id NA HORA; chame horys_aguardar(id) para
receber as respostas. Se não houver painel, devolve 'sem_painel' e você pergunta no chat (ou segue a recomendada,
se estiver rodando sem terminal).

Parâmetros: `titulo`, `perguntas`*, `pedido` (`*` = obrigatório)

### `horys_aprovar`

Portão do usuário: mostra no painel o que aprovar (texto e, se 'imagem' = caminho de
PNG ou 'sprite' = true, a imagem) com os botões Aprovar / Refazer e um comentário. Devolve um id na hora; use
horys_aguardar(id). Passe 'estilo', 'etapa', 'tipo' e 'descricao' para a resposta virar memória de gosto.

Parâmetros: `titulo`*, `texto`, `imagem`, `sprite`, `quadro`, `estilo`, `etapa`, `tipo`, `descricao`, `pedido` (`*` = obrigatório)

### `horys_esperar_imagem`

Entrega do prompt e espera da imagem gerada FORA (ChatGPT, Gemini, Codex, vídeo...).
Mostra no painel do Aseprite o prompt (texto em 'prompt' ou o arquivo 'arquivo_prompt', ex.: traducao/prompt.md do
horys_prompt_traducao) com o botão Copiar e cria a pasta <pasta>/entrada/. A espera destrava quando o usuário salva
uma imagem nessa pasta (o horysd vigia) ou escolhe o arquivo no painel. Devolve um id na hora; chame
horys_aguardar(id): a resposta traz 'imagem' (caminho), que vai direto para o horys_portao_entrada. 'pasta' padrão:
a do 'pedido', senão a pasta acima de traducao/. Sem painel, a vigia da pasta continua: mostre o prompt no chat.

Parâmetros: `prompt`, `arquivo_prompt`, `pasta`, `titulo`, `pedido` (`*` = obrigatório)

### `horys_aguardar`

Espera a resposta de uma pergunta, aprovação, imagem (horys_esperar_imagem),
acabamento (horys_entrega), revisão ou tarefa (id). Espera no
máximo 'segundos' (padrão 45, máx. 55) e devolve o estado: 'respondido' com a resposta, ou 'pendente' — então chame
de novo. O usuário pode demorar: continue chamando enquanto estiver pendente.

Parâmetros: `id`*, `segundos` (`*` = obrigatório)

### `horys_painel`

Mostra uma mensagem de andamento no painel do Aseprite (sem pedido associado).

Parâmetros: `etapa`, `texto`*, `nota` (`*` = obrigatório)

## Estilo

### `horys_estilos`

Lista os pacotes de estilo e mostra o resumo de um ('nome'): paleta, régua, KB e notas que a skill deve ler.

Parâmetros: `nome` (`*` = obrigatório)

### `horys_ficha`

Lê ou ajusta a ficha do sprite ativo (estilo, tipo, partes de baixo para cima, contorno auto|suave|nenhum, cor_contorno, sombra, sem_contorno [hex], sem_borda [hex], limite_cores, ritmo, pasta de saída; asset modular: modular, preset_partes, juncoes [{nome, inferior, superior, movel}], partes_oculto). Sem campos, só mostra.

Parâmetros: `estilo`, `nome`, `tipo`, `partes`, `contorno`, `cor_contorno`, `sombra`, `sem_contorno`, `sem_borda`, `limite_cores`, `ritmo`, `pasta`, `estado`, `pedido`, `descricao`, `modular`, `preset_partes`, `juncoes`, `partes_oculto`, `componentes_max`, `espessura_fina`, `motivo`, `referencia`, `angulo` (`*` = obrigatório)

### `horys_asset_novo`

OBRIGATÓRIOS: 'referencia' = caminho de uma imagem de referência EM PIXEL ART (nativa
ou ampliada; ilustração lisa, foto ou render são recusados) e 'angulo' = top-down | 3/4 top-down | lateral | frontal |
3/4 frontal | isometrico. Sem os dois, pergunte ao usuário. Cria o sprite de um asset pela ficha, de uma vez: quadro QxQ (padrão 192; pé no
pivô (Q/2, Q·127/192) = (96,127)), camadas 'sombra' (opacidade 77) e 'contorno' embaixo, uma camada por PARTE de baixo
para cima (padrão ['desenho']) e 'revisao' (oculta) em cima, quadros e tags por estado
(estados [{nome, quadros, ms}]), paleta do estilo travada. Desenhe só nas partes: contorno e sombra são gerados por
horys_contorno, como o portão espera. Com 'preset_partes' (ex.: 'humanoide-ferreiro') cria o asset MODULAR: as partes
do preset, a camada 'referencia' (oculta, para o desenho completo) e a ficha com modular, preset_partes, juncoes
(contratos de junção) e partes_oculto; o portão passa a exigir as partes sem erro (horys_partes_checar).

Parâmetros: `estilo`, `nome`, `tipo`, `partes`, `contorno`, `cor_contorno`, `sombra`, `sem_contorno`, `sem_borda`, `limite_cores`, `ritmo`, `pasta`, `estado`, `pedido`, `descricao`, `modular`, `preset_partes`, `juncoes`, `partes_oculto`, `componentes_max`, `espessura_fina`, `motivo`, `referencia`*, `angulo`*, `quadro`, `estados` (`*` = obrigatório)

### `horys_paleta_estilo`

Põe a paleta do estilo no Aseprite e devolve as letras; com 'verificar': true conta os pixels das partes fora da paleta (por cor e camada).

Parâmetros: `estilo`, `verificar` (`*` = obrigatório)

### `horys_contorno`

Gera o CONTORNO e a SOMBRA do estilo (como o grade.py: anel externo de 2 px 'auto',
1 px 'suave' ou nenhum; elipse do chão) a partir das partes, nas camadas 'contorno' e 'sombra', em todos os quadros
(ou só 'quadros'). Rode depois de mexer na silhueta; o portão recompõe do mesmo jeito.

Parâmetros: `quadros` (`*` = obrigatório)

### `horys_converter`

Converte uma imagem de referência/conceito em pixel art do estilo, direto numa
camada: reduz pela MODA (cor mais frequente por bloco, sem borrar contornos internos) para a 'altura' pedida (com
contorno), trava a paleta do estilo e põe o pé no pivô. 'tirar_contorno': anéis do contorno do conceito a descascar
(1 para conceito com contorno grosso). É só o PONTO DE PARTIDA: depois limpe (horys_limpar, horys_afinar) e redesenhe
à mão rosto e detalhes.

Parâmetros: `imagem`*, `altura`*, `camada`, `quadro`, `modo`, `tirar_contorno`, `fundo`, `nativo`, `forcar`, `motivo` (`*` = obrigatório)

### `horys_limpar`

Limpeza MECÂNICA de uma camada (não cria forma): funde manchas menores que 'min' px na cor vizinha. 'proteger': hex das cores que ficam (olho, brilho); 'proteger_area': [[x0,y0,x1,y1]] em coordenadas do recorte.

Parâmetros: `camada`, `quadro`, `min`, `proteger`, `proteger_area` (`*` = obrigatório)

### `horys_afinar`

Limpeza MECÂNICA: afina linhas internas para 1 px e tira cor de contorno encostada no vazio (o contorno externo vem do horys_contorno).

Parâmetros: `camada`, `quadro`, `proteger_area` (`*` = obrigatório)

### `horys_portao_entrada`

PORTÃO DE ENTRADA: mede a imagem gerada (ilustração chapada) ANTES do
horys_converter. Confere fundo liso e ausente da figura, figura inteira com margem (margem_min, padrão 0.01), linha dos
pés sem sombra nem chão, escala (figura >= 3× a 'altura' alvo), grade [linhas, colunas] (uma pose por célula, alturas
±3% e chão comum) e se é chapado (grupos de cor OKLab, áreas lisas, degradê). Grava entrada_checagem.txt
(APROVADO/REPROVADO) e a prévia no tamanho final ao lado da imagem. Cada falha vem como correção citando o item do
prompt de tradução: peça a correção no mesmo chat do gerador.

Parâmetros: `imagem`*, `altura`*, `grade`, `margem_min` (`*` = obrigatório)

### `horys_portao`

PORTÃO DE MEDIDAS do sprite aberto: exporta as partes de cada estado (tag) para .grade
em <pasta>/vNN, roda o motor (horys_pixel.motor.grade gerar, o mesmo da skill horys-pixel-liso: perfis 16/32/64
pela altura, contorno selout, D01–D05 entre direções, G01 contra a guia; folha, _8x, silhueta, _regua = prancha boas
práticas + aprovados do Artur, gif, _checagem.txt, medidas/ e o .aseprite fatiado) e devolve APROVADO/REPROVADO com
as falhas. Reprovado: corrija e rode de novo; não
chame o revisor com o portão reprovado.

Parâmetros: `estados`, `pasta`, `versao` (`*` = obrigatório)

### `horys_exportar`

Entrega: gera a versão (como o portão: PNG da folha, GIF, .grade fonte e .aseprite
fatiado) e, com 'destino', copia os arquivos finais para lá (ex.: assets/generated/<asset>-vN do jogo). Com o portão
REPROVADO nada é copiado, a não ser com 'forcar': true + 'motivo' (o usuário pediu), que fica em entrega.json.

Parâmetros: `estados`, `pasta`, `versao`, `destino`, `forcar`, `motivo` (`*` = obrigatório)

### `horys_regua`

Mostra a régua do estilo ao lado do sprite, na mesma escala (por categoria: idle, andar, ataque, tile, arvore, efeito...).

Parâmetros: `categoria`, `quadro` (`*` = obrigatório)

### `horys_marcar`

Marca problemas na camada 'revisao' (e a mostra): 'pontos' [[x,y]] viram cruzes, 'retangulos' [[x,y,w,h]] viram molduras. 'limpar': true apaga as marcas antes.

Parâmetros: `quadro`, `pontos`, `retangulos`, `cor`, `limpar` (`*` = obrigatório)

### `horys_medir_arquivo`

Medição técnica da revisão avulsa (horys-pixel-review) em PNGs: cores e alfa,
fora da paleta, pixels órfãos, contorno dobrado, degraus irregulares, simetria, pés/altura entre quadros e entre vistas,
quadros parados; 'mockup': true mede tela/conceito ('IA slop'). Sem 'caminhos', mede o sprite ativo (composto).
Devolve erros/avisos, marcas com coordenadas (para horys_marcar) e a primeira folha de overlay.

Parâmetros: `caminhos`, `estilo`, `paleta`, `fundo`, `quadros`, `vista`, `mockup` (`*` = obrigatório)

### `horys_prompt_traducao`

Monta o PROMPT DE TRADUÇÃO (11 itens do cofre) para o usuário levar a qualquer
gerador de imagem (Codex, ChatGPT, Gemini, vídeo...): 'tipo' (personagem, criatura-pequena, criatura-grande, boss,
prop, arvore, predio, tile, icone, retrato, efeito), 'descricao' do design, 'estilo' (a paleta vira os hex e os
papéis), 'altura' alvo em px, 'modo' parado | poses (com 'poses', a lista), 'referencia' (caminho; só vai anexada se
'referencia_propria'), e opcionais foco, pecas, cortes, nao_fazer, vista, base_aprovada, guia_pose e 'rampas' (subpaleta:
nomes das rampas do estilo que o design usa; sem ela vai a paleta inteira). Grava
<pasta>/traducao/prompt.md e traducao/paleta-<estilo>.png (amostra com os hex) e devolve o prompt.

Parâmetros: `tipo`*, `descricao`*, `estilo`, `nome`, `altura`, `modo`, `poses`, `referencia`, `referencia_propria`, `foco`, `pecas`, `cortes`, `nao_fazer`, `vista`, `base_aprovada`, `guia_pose`, `pasta`, `rampas` (`*` = obrigatório)

### `horys_referencia_gerar`

Gera imagem de referência quando o usuário não tem uma: 'fonte' manual (PADRÃO: monta o prompt
de tradução via horys_prompt_traducao para o usuário gerar onde quiser; passe 'tipo'), codex (opcional, só se o Codex
estiver instalado) ou lora (o modelo treinado do estilo, se houver).
'prompt' descreve o asset com a paleta e os princípios do estilo (nunca anexe arte de terceiros). Pode levar minutos;
devolve os caminhos das imagens.

Parâmetros: `fonte`, `prompt`*, `pasta`, `n`, `estilo`, `imagens`, `tipo`, `altura`, `modo`, `poses` (`*` = obrigatório)

### `horys_revisar`

Chama o REVISOR exigente (sem terminal; por padrão o Claude revisa). Com a
preferência revisor 'cruzado' (opcional, exige o Codex instalado), o outro motor revisa: se o Claude desenhou, o
Codex revisa. O Codex só é chamado se estiver no PATH e a preferência pedir ('cruzado' ou 'codex'). Passe a pasta vNN do portão, os estados, a ficha.md e a praticas.md, a etapa, a rodada e,
em asset fiel, a referência. Devolve um id na hora; use horys_aguardar(id) — a revisão leva alguns minutos. A
resposta traz o JSON do revisor (PASSA/NAO_PASSA, notas, aceitação, correções).

Parâmetros: `pasta`*, `estados`, `ficha`, `praticas`, `etapa`, `rodada`, `referencia`, `motor`, `quem_desenhou` (`*` = obrigatório)

### `horys_estilo_novo`

Cria um PACOTE DE ESTILO a partir de imagens do estilo que a pessoa gosta: mede
escala do pixel, paleta em rampas, contorno, tamanho de cluster, tons por material, proporções e AA/dithering, e grava
em ~/.horys-pixel/estilos/<nome>/ (estilo.json, paleta, analise.json e estilo.md rascunho com os 15 itens do guia
de estilo; o que não deu para medir fica 'a confirmar'). 'licenca': origem/licença das imagens (obrigatória para
treinar depois). Depois confirme item por item com a pessoa (skill horys-pixel-estilo).

Parâmetros: `nome`*, `imagens`*, `autor`, `licenca` (`*` = obrigatório)

### `horys_estilo_calibrar`

Confere se o portão de medidas (perfil 32) está calibrado no corpus de teste
da config do motor ("corpus_teste"; não é régua de estilo): gera as mutações (versões estragadas do corpus) e mede bons
e estragados. Os bons têm que passar todos e os estragados têm que reprovar todos. Leva alguns minutos.

Parâmetros: `estilo` (`*` = obrigatório)

## Partes (fatiamento modular)

### `horys_partes_checar`

Valida o fatiamento em PARTES do sprite modular (ficha com modular/preset_partes):
parte vazia ou desconexa, partes que não se tocam, inferior ao menos 1 px sob a superior (erro; aviso se < 2 px),
buraco ao deslocar a parte móvel 1 px (erro) ou 2 px (aviso) nas 8 direções, linha interna entre as partes e cobertura
mínima de 90% da anatomia oculta e da camada 'referencia'. Camada faltando é erro. Devolve o diagnóstico e a VISTA
EXPLODIDA (cada parte numa célula, pixels ocultos em MAGENTA). 'quadros' (padrão: todos); 'quadro' escolhe o da
vista; 'salvar': pasta onde gravar partes_checagem.txt, medidas/partes.json e <nome>_partes.png.

Parâmetros: `quadros`, `quadro`, `salvar` (`*` = obrigatório)

### `horys_partes_recortar`

Copia uma 'regiao' {x,y,w,h} da camada OCULTA 'referencia' para uma 'parte', no
'quadro' (padrão o ativo; 'quadro_ref' se a referência estiver em outro). Só escreve onde a imagem composta final NÃO
muda (pixel coberto por parte de cima ou da mesma cor que a composição já mostra); o resto é recusado e contado.
Recusa sprite com mais de 128 px de altura (boss: anime por render 3D), salvo 'forcar' + 'motivo'.
Confere a composição depois e desfaz se mudou. 'sobrescrever': troca também pixels já existentes na parte.

Parâmetros: `parte`*, `regiao`*, `quadro`, `quadro_ref`, `sobrescrever`, `forcar`, `motivo` (`*` = obrigatório)

### `horys_partes_estender`

Estende a parte INFERIOR de 1 a 2 px por baixo da SUPERIOR (anatomia oculta,
com a cor do vizinho mais próximo), pela 'juncao' (nome do contrato) ou por 'inferior'+'superior'. 'px' 1–2 (padrão 2);
'quadros' (padrão: o ativo; 'todos': true para todos). Só toca pixels cobertos pela superior; se a imagem composta
mudasse, ABORTA e REVERTE.

Parâmetros: `juncao`, `inferior`, `superior`, `px`, `quadro`, `quadros`, `todos` (`*` = obrigatório)

## Pedidos

### `horys_pedido_novo`

Cria um pedido de asset e inicia um motor sem terminal (o mesmo que o botão Gerar
do Aseprite). 'motor': claude|codex. Use quando o usuário pedir pelo terminal para o outro motor desenhar, ou para
testar o fluxo completo. 'autonomo_s': se ninguém responder uma pergunta ou aprovação do painel nesse tempo, segue
a recomendada (a aprovação fica marcada 'pendente_usuario').

Parâmetros: `descricao`*, `tipo`, `estilo`, `motor`, `estados`, `referencia`, `tamanho`, `iniciar`, `autonomo_s` (`*` = obrigatório)

### `horys_pedido`

Estado de um pedido (ou a lista dos últimos, sem 'id').

Parâmetros: `id` (`*` = obrigatório)

### `horys_pedido_atualizar`

Registra o andamento do pedido e mostra no painel do Aseprite: 'etapa'
(briefing, pesquisa, praticas, ficha, referencia, conversao, limpeza, partes, portao, revisor, aprovacao, animacao,
entrega, concluido), 'texto' curto e 'nota' (aceitação do revisor, 0–100). Também guarda decisões e pendências
('pendencia'). Em asset modular, 'animacao' só é aceita depois de horys_partes_checar sem erros (etapa 'partes').

Parâmetros: `id`*, `etapa`, `texto`, `nota`, `pendencia` (`*` = obrigatório)

### `horys_pedido_cancelar`

Cancela um pedido e encerra o motor dele.

Parâmetros: `id`* (`*` = obrigatório)

## Memória de gosto

### `horys_gosto_registrar`

Guarda uma aprovação ou recusa do usuário na memória de gosto do estilo.
'capturar': true salva a imagem composta do quadro ativo (aprovados viram exemplo e conjunto de treino).
(Respostas do horys_aprovar com 'estilo' já são registradas sozinhas.)

Parâmetros: `estilo`*, `etapa`, `aprovado`*, `comentario`, `defeitos`, `tipo`, `descricao`, `capturar` (`*` = obrigatório)

### `horys_gosto_consultar`

O que o usuário já aprovou e recusou neste estilo: comentários recentes,
defeitos que mais se repetem (candidatos a regra) e exemplos aprovados do mesmo tipo para usar como referência.

Parâmetros: `estilo`*, `tipo` (`*` = obrigatório)

## Treino

### `horys_treino_status`

Treino do estilo: GPU detectada, perfil (SD 1.5 / SDXL) e se o kohya está instalado. Só lê; não baixa nem treina.

Parâmetros: `estilo` (`*` = obrigatório)

### `horys_treino`

Roda um passo do treino do estilo (CLI python -m horys_pixel.treino): 'comando' em
gpu, perfil, instalar, preparar, configurar, treinar, avaliar, notas, promover, gerar e 'args' (lista de argumentos da CLI, ex. ["--estilo", "horys-pixel-liso"]). Tudo que baixa,
treina ou gera imagem só acontece com 'executar': true — PEÇA O SIM DO USUÁRIO antes (horys_perguntar): instalar
baixa de 3 a 5 GB e treinar ocupa a GPU por quase uma hora.

Parâmetros: `comando`*, `args`, `executar` (`*` = obrigatório)

## SpriteKiln (base 3D animada)

### `horys_paleta_kiln`

Grava a paleta do estilo no formato de rampas do SpriteKiln (índice 0 = contorno,
depois sombra -> base -> luz), para o spec apontar 'palette:' para ela. 'estilo' (padrão: o da ficha ou o padrão),
'destino' (caminho .yaml).

Parâmetros: `estilo`, `destino`* (`*` = obrigatório)

### `horys_importar_kiln`

Importa um render do SpriteKiln (o JSON que `spritekiln render` grava em
out/<nome>/<nome>.json, com o atlas ao lado) para o sprite ativo: um quadro por quadro do render, na camada
'camada' (padrão 'referencia'), com as durações e as tags (estado sem o sufixo de direção). 'tags': só esses
estados; 'direcao': a vista (padrão a primeira do atlas); 'limpar_min': funde manchas menores que N px em todos os
quadros sem criar boil (sugerido 3). Asset MODULAR: passe 'spec' (o .yaml) e 'grupos' {parte_do_horys: [partes do
spec]} (ou deixe 'grupos' na ficha, chave kiln_grupos) para distribuir cada pixel visível na camada da sua parte;
'anatomia_oculta' (padrão true) renderiza cada grupo isolado e completa somente pixels cobertos por partes de cima;
'max_oculto_px' limita a profundidade (padrão 4). 'resto' recebe o que não cair em grupo nenhum. O sprite tem o mesmo tamanho de
quadro do render (crie com horys_asset_novo quadro=<w>).

Parâmetros: `json`*, `tags`, `direcao`, `camada`, `limpar_min`, `spec`, `grupos`, `resto`, `substituir`, `anatomia_oculta`, `max_oculto_px` (`*` = obrigatório)

## Sequência (animação de qualquer fonte)

### `horys_sequencia`

MOTOR DE SEQUÊNCIA: trata os quadros de uma animação como um todo. 'fonte' = o
manifest.json de um render 3D com câmera fixa (Blender/Blockbench; liga o preset render3d), pasta de PNGs, uma grade
(PNG + 'linhas' e 'colunas'), um vídeo (precisa do ffmpeg) ou o JSON do atlas do Kiln. 'preset' render3d | grade |
video. Etapas: fundo por célula → registro (altura alvo, pés e pivô da ficha; 'escala' fixa | comum | por_quadro —
fixa = uma transformação para a sequência inteira, preserva quique e agachamento) → escolha de quadros
('plano' andar | golpe com 'n') → quantização conjunta na paleta do estilo → redução por moda → anti-cintilação →
trava de identidade ('base' = PNG da base aprovada no tamanho final e 'decalques' [{nome, rect [x,y,w,h], busca}]) →
limpeza (órfãos e borda) → validação objetiva (canvas, alpha, paleta, proporção, deriva, cintilação, quadros
repetidos, loop, identidade). 'proteger' = cores (#hex) que podem mudar sem a forma mudar (brilho do olho).
'prancha' = PNG com poses soltas sem grade (achadas por componentes, em ordem de leitura); 'franja' (padrão true)
tira o anel quase-fundo colado no contorno. 'saida_folha' = pasta onde gravar a folha PNG + JSON (Aseprite hash, lido pela Godot 4) + GIF. Uma grade (imagem) só entra com o portão de entrada APROVADO, salvo 'forcar' + 'motivo'.
Escreve na camada (padrão: a de cima da ficha) a partir do quadro 'quadro_inicial', cria a
tag 'estado' e devolve o relatório (deriva, % de pixels que piscam antes e depois). Depois: horys_contorno →
horys_portao.

Parâmetros: `fonte`*, `altura`*, `linhas`, `colunas`, `fps`, `estado`, `camada`, `quadro_inicial`, `ms`, `plano`, `n`, `escala`, `fator`, `base`, `decalques`, `limpar_min`, `regularizar`, `cor_fundo`, `proteger`, `prancha`, `franja`, `forcar`, `motivo`, `preset`, `loop`, `saida_folha` (`*` = obrigatório)

### `horys_guia_poses`

GUIA DE POSE: as poses do plano em silhueta, em grade, com a mesma escala e o mesmo
chão, para anexar ao prompt de poses (horys_prompt_traducao modo poses, 'guia_pose'). 'fonte' = o JSON do atlas do
Kiln (ou do Noct 3D) ou uma pasta de PNGs já renderizados; 'linhas' × 'colunas' = poses (ex.: 2×4 = 8; o andar do
golem pede 4–8 silhuetas); 'plano' andar | golpe escolhe os quadros-chave. Grava o PNG em 'saida'.

Parâmetros: `fonte`*, `linhas`, `colunas`, `plano`, `saida`*, `celula_w`, `celula_h` (`*` = obrigatório)

### `horys_validar_sequencia`

VALIDAÇÃO OBJETIVA de uma animação pronta, sem Aseprite: 'fonte' = pasta de PNGs,
manifest.json de render 3D, grade (com 'linhas' e 'colunas') ou folha PNG em tira (com 'colunas'). Mede: mesmo canvas,
alpha só 0/255, cores na paleta ('paleta' #hex, ou a do 'estilo'), proporção (altura estável), deriva horizontal,
linha dos pés, pivô ('pivo' [x,y]), cintilação, quadros repetidos, loop último→primeiro, silhueta e cabeça
reconhecíveis, elementos que somem. Os números não substituem a revisão: sequência que desliza continua reprovada.

Parâmetros: `fonte`*, `linhas`, `colunas`, `paleta`, `estilo`, `pivo`, `loop` (`*` = obrigatório)

### `horys_colagem`

COLAGEM GUIADA: o gerador só diz ONDE cada peça vai; os pixels vêm da arte-mestra.
'mestre' = conceito aprovado em pixel art ampliada (lido na grade dele: pixel quadrado, fase pelo Sobel). 'guia' = os
quadros da animação gerados a partir desse conceito (PNG em prancha de poses soltas, ou grade com 'linhas' e
'colunas', ou pasta). Os guias vão para a grade do mestre (escala única, moda na paleta) e cada peça de 'pecas'
[{nome, rect [x,y,w,h] no mestre recortado, apagar: faixa|caixa|nada, busca, espelho, erro_max}] é achada em cada
quadro e colada exata por cima, na ordem dada. Cabeça/cabelo acima dos ombros: apagar 'faixa'. Deixe de fora o que
se mexe (braço, perna): fica como o guia desenhou e é o que se limpa à mão. Paleta: 'paleta' #hex, a do 'estilo',
ou 'cores' tiradas do conceito (padrão 16). Sem 'pecas', só devolve o mestre com régua de linhas/colunas para
escolher os rects. Grava em 'saida' os quadros, o mestre, a folha PNG + JSON + GIF e devolve a estabilidade (px de
cada peça diferentes do quadro 0). Não precisa do Aseprite. Depois: horys_validar_sequencia → horys_revisar.

Parâmetros: `mestre`*, `guia`, `pecas`, `saida`*, `linhas`, `colunas`, `paleta`, `estilo`, `cores`, `cor_fundo`, `busca`, `ms`, `estado`, `loop` (`*` = obrigatório)

## Entrega e retoque

### `horys_entrega`

Estado de ENTREGA a partir do JSON do revisor ('resultado'): pronto = zero defeito
estrutural E aceitação >= 'limite' (padrão 80). Os defeitos de ACABAMENTO viram marcas na camada 'revisao' (as
coordenadas que o revisor deu em 'onde') e uma lista guardada na ficha (acabamento_pendente) para o usuário
finalizar no Aseprite. Se estiver pronto, a lista também abre no painel (botão 'Terminei o retoque') e a resposta traz
um id: horys_aguardar(id) devolve o que o usuário marcou como feito; depois rode horys_gosto_do_retoque.
'marcar': false só avalia. TRAVA: 'pasta' (a pasta da versão) precisa ter o A/B do revisor registrado
(horys_ab_registrar); sem ele a entrega é recusada.

Parâmetros: `resultado`*, `limite`, `quadro`, `marcar`, `pasta`* (`*` = obrigatório)

### `horys_gosto_do_retoque`

Depois do retoque do usuário: compara a camada 'camada' do quadro 'quadro' com
o PNG 'antes' (a versão entregue) e resume o que ele mudou por categoria (rosto, brilho, contorno, cor, forma).
Grava o resumo na memória de gosto do estilo (horys_gosto_registrar) com as categorias mais mexidas como defeitos;
as que se repetem viram candidatas a regra da praticas.md do projeto (proponha ao usuário).

Parâmetros: `antes`*, `camada`, `quadro`, `estilo`, `etapa`, `tipo`, `registrar` (`*` = obrigatório)

## Ofício (base de pixel art)

### `horys_oficio`

Base de ofício de pixel art (62 regras, ~400 modelos de grade, 2006 paletas com autor). É ofício, não
régua de estilo: a régua é o Artur (ficha e aprovados). Ações:
• 'indice' — lista as regras (00 núcleo, 1x técnica, 2x cor/material, 3x personagem, 4x animação, 5x criaturas,
  6x cenário, 7x objetos/3D, 8x efeitos/UI, 9x estilo).
• 'regra' {regra:'34' ou 'hands-and-feet', secao?:'Rules'|'Mistakes'|'Review'..., sem_modelos?} — lê uma regra.
• 'buscar' {termo} — linhas das regras com todas as palavras (ex.: 'hand 32', 'walk contact').
• 'modelos' {filtro?} — lista modelos de grade (nome, regra, tamanho).
• 'modelo' {nome, cores?:{papel ou letra:'#hex'}, desenhar?:true, x, y, camada, quadro} — mostra o modelo
  (prévia + paleta e linhas prontas para horys_pixel_map). Troque as cores pela paleta do asset com 'cores'.
  'desenhar': true carimba no Aseprite (pontos '.' não mexem). Modelo é ponto de partida: adapte à pose.
• 'paletas' {termo?, tamanho?} — busca paletas (nome, autor, notas).
• 'paleta' {nome} — cores de uma paleta, com autor e fonte.

Parâmetros: `acao`*, `regra`, `secao`, `sem_modelos`, `termo`, `filtro`, `nome`, `cores`, `desenhar`, `x`, `y`, `camada`, `quadro`, `tamanho`, `limite` (`*` = obrigatório)

## Base + Pele (master, partes, vestir, animar, travas)

### `horys_base_ler`

Lê a imagem do Codex de um corpo-base (pixel art ampliada sobre cor-chave, vistas lado a lado) na grade nativa
dela e grava a folha 1x da base: base.png (vistas na mesma linha de chão, margem transparente para chapéu/capa),
vista_N.png, base_8x.png (prévia) e base.json (bloco, cores, alturas, avisos). Não cria forma.
Leitura pela GRADE PRÓPRIA (cortes irregulares ajustados às bordas + voto da maioria no miolo de cada célula; a
franja da chave não vira cor). 'paleta': encaixa na paleta da ficha; sem ela, 'cores' cores reais da imagem
(16 é bom para master; 4 para corpo-base liso). 'metodo': propria (padrão) | centro (o antigo).

Parâmetros: `imagem`*, `saida`*, `chave`, `cores`, `margem`, `paleta`, `metodo` (`*` = obrigatório)

### `horys_vestir`

Separa a pele de um personagem: relê a imagem do Codex (a base vestida, pedida com "A ÚNICA MUDANÇA: vista esta
figura como <ficha>") NA GRADE DA BASE e grava só as células que mudaram. Saída: pele.png (camada de pele),
vestido.png (base + pele), vestido_8x.png e pele.json (grade achada, % da base mantida, cores, avisos).
Aviso de grade fraca = gere de novo no Codex; não conserte à mão. TRAVA: a base precisa estar aprovada pelo Artur
(horys_aprovar_arquivo).

Parâmetros: `base`*, `imagem`*, `saida`*, `chave`, `paleta`, `max_cores`, `manter_isolados` (`*` = obrigatório)

### `horys_propagar_pele`

Leva a pele para cada quadro da animação da base. Recebe a pele (PNG, mesmo tamanho dos mapas), o mapa de partes
do quadro de referência e os mapas dos quadros alvo (PNG em que cada cor opaca é uma parte; a mesma cor = a mesma
parte em todos os quadros). Opcional: as bases de cada quadro, para gravar o composto. Saída: pele_NN.png,
composto_NN.png e propagar.json (deslocamento e IoU por parte; aviso = limpar à mão aquela parte).

Parâmetros: `pele`*, `partes_ref`*, `partes`*, `bases`, `saida`*, `raio` (`*` = obrigatório)

### `horys_partes_mapa`

MAPA DE PARTES de uma vista (cor por parte, contrato de art-src/motion-rigs: cabeça ciano, tronco laranja, braço
esq. verde, braço dir. roxo, perna esq. amarela, perna dir. vermelha, arma rosa, enfeite branco). Sem 'mapa': faz o
RASCUNHO automático (pescoço pelo perfil de largura, virilha pelo vão das pernas, braços fora do quadril) e grava
<saida>/partes.png para corrigir no Aseprite. Com 'mapa': só checa. Sempre checa a FORMA FECHADA por parte
(cobertura exata, 1 pedaço, sem buraco, junções encostadas) e grava partes.json + partes_8x.png.
'lado': vista de perfil (uma perna só). 'enfeite_topo': linhas do topo que são chifre/cabelo/antena.

Parâmetros: `vista`*, `saida`*, `mapa`, `lado`, `cabeca_frac`, `enfeite_topo` (`*` = obrigatório)

### `horys_animar_tabela`

ANIMA uma vista aprovada deslocando partes por uma TABELA (dx, dy por parte por quadro): 'tabela' = idle |
andar-frente | andar-lado, ou um objeto {n, ms, partes: {parte: [[dx,dy],...] | "atraso:cabeca"}}. Precisa do mapa de
partes checado (horys_partes_mapa ok). O que não mexe fica idêntico; a emenda de 1 px numa junção é fechada
esticando o vizinho; vão maior vira aviso (limpar à mão). Grava quadro_NN.png, folha PNG+JSON+GIF em 'saida'.

Parâmetros: `vista`*, `mapa`*, `tabela`*, `saida`*, `estado`, `espelhar` (`*` = obrigatório)

### `horys_pedido_codex`

PEDIDO PRONTO AO CODEX (image_gen), do jeito que funcionou: pixel art no tamanho final, simples, paleta fixa, fundo
chapado de cor-chave, todas as vistas numa imagem. 'modo': master (conceito -> folha de vistas; 'imagem' = conceito,
'ficha', 'altura', 'paleta', 'vistas', 'extras'), vestir (base 1x ampliada + "A ÚNICA MUDANÇA: vista como <ficha>"),
vista (a vista que falta ao lado do master) ou pose ("A ÚNICA MUDANÇA: <pose>"). Gera 'n' tentativas (padrão 3) em
<saida>/tentativa_NN.png; tentativa ruim se descarta, não se conserta. Com 'so_prompt' só grava prompt.md e o anexo.
Depois: master -> horys_base_ler; vestir -> horys_vestir; pose/vista -> horys_vestir com a imagem aprovada como base.
Leva minutos por tentativa (devolve um id; use horys_aguardar).

Parâmetros: `modo`*, `saida`*, `imagem`, `ficha`, `altura`, `paleta`, `chave`, `vistas`, `extras`, `vista`, `pose`, `n`, `escala`, `so_prompt` (`*` = obrigatório)

### `horys_aprovar_arquivo`

Registra a APROVAÇÃO de um arquivo (master, base, vista, quadro): grava <arquivo>.aprovado.json com o sha256 do
arquivo. Se o arquivo mudar, a aprovação cai. Use SÓ depois do sim do Artur: passe 'id' de um horys_aprovar já
respondido (confere que foi Aprovar e não automático) ou 'chat': true quando ele disse sim no chat (cite as palavras
dele em 'comentario'). 'quem': artur (padrão) | revisor. Vestir e animar recusam o que não foi aprovado pelo Artur.

Parâmetros: `arquivo`*, `id`, `chat`, `comentario`, `quem` (`*` = obrigatório)

### `horys_ab_registrar`

Registra uma rodada A/B CEGA do revisor em <pasta>/ab.json: 'a' = antes, 'b' = depois da correção, 'vencedor'
A | B | EMPATE e o 'motivo'. A correção só fica se B vencer (senão volte ao A). horys_entrega recusa pasta sem A/B.

Parâmetros: `pasta`*, `a`*, `b`*, `vencedor`*, `motivo`, `revisor` (`*` = obrigatório)

### `horys_pose_ler`

Lê uma POSE ou VISTA do Codex (horys_pedido_codex modo pose/vista) NA GRADE DO MASTER: bloco pela altura do master,
voto da maioria na 'paleta' (padrão: as cores do master), sem o halo claro de fora do contorno e com a CABEÇA
TRAVADA (as 'cabeca' linhas do topo do master coladas por cima, no melhor encaixe). Grava <saida>/<nome>.png e
<nome>_bruto.png. Aviso de altura ou de cabeça = descarte a tentativa e gere de novo.

Parâmetros: `imagem`*, `master`*, `saida`*, `nome`, `cabeca`, `paleta`, `chave` (`*` = obrigatório)

## Efeitos (pixelfx)

### `horys_vfx_listar`

Lista os efeitos do pixelfx (patch-gg, MIT; ~244 efeitos de pixel art em código: fogo, explosões, gelo, raio,
arcano, sagrado, sombra, status, natureza, clima, UI, coleta, transições, bichos). filtro: palavras que precisam
aparecer no id ou na descrição (ex.: "fire", "heal", "explosion"). Cada linha: id, loop/once, duração, tamanho
nativo e [boneco] quando o efeito desenha o boneco cinza do pixelfx junto (prefira os sem boneco para VFX solto).

Parâmetros: `filtro`, `categoria`, `sem_boneco` (`*` = obrigatório)

### `horys_vfx_gerar`

Gera um VFX do pixelfx recolorido pela rampa do personagem. efeito: id de horys_vfx_listar (ex.: fire/campfire).
rampa: lista de hex do escuro ao claro (a do personagem); o pixelfx recebe a rampa e depois cada pixel vira a cor
da rampa pela luminância (só cores da rampa, alfa binário: abaixo de alfa_minimo some). quadros: quantos quadros
(amostrados por igual; a duração total se mantém; vazio = todos). tamanho: lado do quadrado final em px (recorta na
caixa visível e centraliza; se não couber, reduz e avisa). Grava em saida: <nome>.png (tira horizontal),
<nome>.json (formato do Aseprite, durações em ms, pivô, crédito MIT) e <nome>_previa.png.

Parâmetros: `efeito`*, `rampa`*, `saida`*, `tamanho`, `quadros`, `seed`, `alfa_minimo`, `paleta_nativa`, `nome` (`*` = obrigatório)

## Tileset, paleta e guarda de correção (portado do ai-artist)

### `horys_tileset`

TileSet do Godot 4 (.tres, format=3) a partir de uma folha de tiles PNG. Não precisa do Aseprite.
• layout 'grid' (padrão): um tile por slot com pixel.
• layout 'blob47': 47 tiles de autotile em ordem canônica (máscaras de 8 vizinhos reduzidas, em ordem crescente,
  linha a linha) a partir do slot 'pular'; o .tres sai com terrain_set 0 (cantos e lados) e os peering bits.
  'mascaras' (47 inteiros) troca a ordem se a folha foi desenhada em outra.
• acao 'guia' {saida:.png, tile?, colunas?}: grava a prancha-guia do blob47 (molde para desenhar à mão na ordem
  que o 'blob47' espera).
'res' é o caminho da textura no projeto Godot (padrão res://<nome da folha>). Grava também <saida>.json.

Parâmetros: `acao`, `folha`, `saida`*, `tile`, `tile_w`, `tile_h`, `layout`, `res`, `margem`, `espaco`, `pular`, `mascaras`, `nome_terreno`, `cor_terreno`, `incluir_vazios`, `colunas` (`*` = obrigatório)

### `horys_paleta_rampa`

Rampa com giro de matiz, do escuro ao claro, com a base no meio: a sombra gira para o azul e perde um pouco de
saturação, a luz gira para o amarelo e satura (rampa que só muda o brilho é a marca de pixel art de máquina).
'passos' (5), 'abertura' (0,55: quanto vai à sombra e à luz), 'giro' (25 graus no extremo).
'adicionar': true acrescenta a rampa à paleta do sprite aberto no Aseprite.

Parâmetros: `base`*, `passos`, `abertura`, `giro`, `adicionar` (`*` = obrigatório)

### `horys_paleta_analisar`

Analisa uma paleta: pares quase iguais (ΔE76 < 'limiar', padrão 3), rampas achadas (matiz/croma OKLCH, escuro ->
claro) com o giro de matiz de cada uma, contraste (extremos e o par usado de menor contraste) e, com imagem, uso por
cor, cores da arte fora da paleta e entradas sem uso. Fonte: 'cores' e/ou 'imagem' (PNG); sem nenhuma das duas
(ou com 'ao_vivo': true) lê a paleta e o quadro 'quadro' do sprite aberto no Aseprite.

Parâmetros: `cores`, `imagem`, `limiar`, `ao_vivo`, `quadro` (`*` = obrigatório)

### `horys_guarda_correcao`

Guarda do loop de correção (fix, não redesenho). Por camada e quadro:
• 'marcar' — tira a foto da camada (recomeça a contagem de rodadas).
• 'aplicar' {passos:[{ferramenta,args}]} — tira a foto se não houver, roda os passos (ex.: horys_pixel_map) e
  confere: se mexeu em mais de 'limite' (1/4) dos pixels opacos, DESFAZ (repõe a foto) e recusa.
• 'conferir' — confere o que mudou desde a foto (correção feita por outras chamadas); recusada = repõe a foto.
• 'restaurar' — repõe a foto. • 'estado' — rodadas e limite.
No máximo 3 rodadas aceitas; depois disso toda correção é desfeita: mostre ao Artur e pergunte.

Parâmetros: `acao`*, `camada`*, `quadro`, `passos`, `limite`, `max_rodadas` (`*` = obrigatório)

### `horys_cel_tween`

Move uma camada ao longo dos quadros 'de'..'ate' (0-based), a partir do quadro 'de':
• modo 'tween' {dx, dy, curva: linear|ease_in|ease_out|ease_in_out|smoothstep} — chega em (dx,dy) no 'ate'.
• modo 'oscilar' {amp_x, amp_y, periodo?, fase?} — seno por quadro (balanço, flutuar, respirar).
• modo 'copiar' — repete o quadro 'de' nos outros (no lugar de "linkar": edição posterior NÃO se propaga).
A ponte não move célula: o tween é deslocamento de pixels, quadro a quadro; o que sai da tela se perde nos quadros
deslocados. Não faz tween de opacidade. Cria os quadros que faltarem.

Parâmetros: `camada`*, `de`*, `ate`*, `modo`, `dx`, `dy`, `curva`, `amp_x`, `amp_y`, `periodo`, `fase` (`*` = obrigatório)

## Guia de pose do SpriteKiln (cor por parte)

### `horys_guia_kiln`

Guia de pose de uma spec do SpriteKiln: renderiza cada ação × direção no tamanho final com UMA COR CHAPADA POR
PARTE (sem sombreado, contorno, linha interna, dither, brilho nem sombra) nas cores do contrato de partes
(cabeca ciano, tronco laranja, braco-esq verde, braco-dir roxo, perna-esq amarelo, perna-dir vermelho, arma rosa,
enfeite branco). Grava <saida>/<anim>_<dir>_NN.png e <saida>/guia.json (parte -> cor, motivos, durações, avisos).
Lados: esquerda/direita da IMAGEM na vista de frente (s): parte _L do spec = braco-dir/perna-dir; _R = -esq; a cor
fica presa à parte em todas as direções. Todas as direções são renderizadas de verdade (mirror desligado).
'mapeamento' ({parte: categoria}) corrige a classificação automática (mapeie a parte _L; a gêmea _R segue).
anims/dirs: listas (["idle", "walk"], ["s", "e"]); size: tamanho do quadro (padrão o da spec).
A spec original não é editada.

Parâmetros: `spec`*, `saida`*, `anims`, `dirs`, `size`, `mapeamento` (`*` = obrigatório)

## Pipeline Blender (paleta, render 3D para pixel, recolor)

### `horys_blender_paleta`

PASSO 0 do pipeline Blender: a PALETA da arte. Sem 'familias': propõe as cores-base do 'conceito' (k-médias OKLab
sem o fundo, 'n' cores, padrão 8) para você dar nome às famílias. Com 'familias' [{nome, base #hex, tons 2|3,
tipo toon|emissivo, rampa (opcional, pronta)}]: monta as rampas com giro de matiz (a base fica no meio; sombra
para o azul, luz para o amarelo), a 'tinta' do contorno, confere ≤ 20 cores e quase-iguais, grava
<saida>/paleta.json e paleta.png. Depois mostre ao Artur e registre o sim com horys_aprovar_arquivo(paleta.json):
o render final recusa paleta não aprovada.

Parâmetros: `saida`*, `conceito`, `n`, `familias`, `tinta` (`*` = obrigatório)

### `horys_blender_inspecionar`

Lista coleções (com as peças), empties, armatures, actions e materiais de um .blend, para montar a config do
personagem (rig por pivôs, regras de material). Roda o Blender headless; não altera o arquivo.

Parâmetros: `blend`* (`*` = obrigatório)

### `horys_blender_render`

RENDER do personagem pelo pipeline Blender do horys: 'config' = JSON do personagem (blend, paleta, rig por pivôs,
papeis, materiais, camera {quadro, altura_px, angulo}, luz, acoes {nome: {tipo andar|idle|timeline, quadros, fps,
amplitude}}, direcoes, contorno fora|dentro|nenhum, partes). No Blender: rig de empties, andar/idle procedural (pé
de apoio parado, IK de 2 segmentos), toon com a paleta e limiares calibrados pela área (a base domina), câmera do
jogo enquadrada por todas as poses, lote ações × direções e o passe de partes. No pós: paleta travada, pixel solto,
contorno 1 px, folha/JSON/GIF por ação_direção, prancha.png, personagem.aseprite (tags) e partes/. 'previa': 4
quadros por direção (não exige paleta aprovada). Leva de segundos a minutos (devolve id; horys_aguardar).

Parâmetros: `config`*, `saida`*, `previa` (`*` = obrigatório)

### `horys_blender_recolor`

RECOLOR depois do render (B7), sem rodar o Blender de novo: 'paleta' = o paleta.json novo (mesmas famílias, tons
trocados); cada cor antiga vira a nova da mesma família e posição na rampa. Refaz o pós (folhas, GIFs, prancha,
.aseprite) em 'saida'.

Parâmetros: `saida`*, `paleta`*, `config` (`*` = obrigatório)

## Horys Estúdio (interface)

### `horys_estudio_abrir`

Abre o HORYS ESTÚDIO (interface local estilo Noct): pastas agrupadas, grade, inspetor com zoom de pixel, player de
folha com onion, riscar na imagem e mandar o pedido ao chat, aprovar/reprovar (vira régua), paleta com recolor, boas
práticas e render do Blender. Sobe o servidor em 127.0.0.1 (uma vez) e devolve a URL com o token; 'navegador' abre
a janela ('app': janela sem barra, Edge/Chrome).

Parâmetros: `navegador`, `app`, `porta` (`*` = obrigatório)

### `horys_estudio_pedidos`

Lê os PEDIDOS que o Artur fez no Horys Estúdio (riscos + texto sobre uma imagem). Padrão: os pendentes, com a
imagem anotada de cada um, o arquivo do asset, o quadro e as marcas em pixels do sprite. Depois de atender, chame
horys_estudio_responder (o Artur vê a resposta na interface). 'estado': pendente | em_andamento | feito | todos.

Parâmetros: `estado`, `max` (`*` = obrigatório)

### `horys_estudio_responder`

Responde a um pedido do Horys Estúdio: 'texto' (o que foi feito), 'estado' (feito | em_andamento | pendente |
descartado) e opcional 'imagem' (caminho da versão nova, para o Artur comparar na interface).

Parâmetros: `id`*, `texto`*, `estado`, `imagem` (`*` = obrigatório)

## Boas práticas (checagem)

### `horys_boas_praticas`

Mede as BOAS PRÁTICAS automáticas (ids BP de docs/boas-praticas.md) de um sprite: 'arquivo' = PNG de um quadro,
pasta de quadros PNG, ou folha PNG+JSON (Aseprite/SpriteKiln; uma sequência por tag, ação pelo nome da tag).
Grava <x>_praticas.json (resultado por regra: passa, medida, limite, onde) e <x>_praticas.png (overlay ampliado:
vermelho = grave, amarelo = leve). Contexto opcional: 'protegidas' (cores de 1 px permitidas: olho, brilho,
emissivo), 'contorno', 'paleta', 'chao', 'acao' (idle|andar|correr|ataque|dano|morte), 'loop', 'render3d' (BP40/BP41
só informam), 'altura_alvo', 'perfil' (16|32|64), 'limites' {"BP12": 24}. As regras de olho ficam para o revisor.

Parâmetros: `arquivo`*, `saida`, `protegidas`, `contorno`, `paleta`, `chao`, `acao`, `loop`, `render3d`, `altura_alvo`, `perfil`, `limites`, `escala` (`*` = obrigatório)

## Corpo-base Eldiran

### `horys_base_eldiran`

Fatia o CORPO-BASE da Eldiran 32x32 (CC0; decisão do Artur 14/11: "usa a base do eldiran", só esqueleto, não régua)
em 'saida' (padrão art-src/base32/eldiran): quadros/<acao>_<dir>_NN.png (idle 1 + andar 4; s, n, e; w = e espelhado;
canvas 40x40, pés na mesma linha), base.png (3 vistas de descanso lado a lado, para horys_vestir), base.json
(layout, durações, origem, licença) e partes/<acao>_<dir>_NN.png (mapa de partes checado). As costas (n) são
derivadas da frente com o rosto apagado: a linha nua da folha não tem costas. 'folha': outra cópia da folha.

Parâmetros: `saida`, `folha` (`*` = obrigatório)

### `horys_pele_animar`

Anima uma PELE sobre a base Eldiran: 'pele' = pele.png de horys_vestir feita sobre <base_dir>/base.png. A pele é
cortada por vista, levada a cada quadro de cada ação/direção pelos mapas de partes (pele.propagar), composta sobre
o quadro da base e gravada em 'saida' como <acao>_<dir>.png/.json/.gif (w = e espelhado) + animar.json. Aviso =
parte que muda de forma no quadro: limpar à mão.

Parâmetros: `base_dir`*, `pele`*, `saida`*, `raio` (`*` = obrigatório)
