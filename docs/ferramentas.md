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

Parâmetros: `paleta`, `linhas`, `x`, `y`, `camada`, `quadro`, `stamps`, `place`, `arquivo` (`*` = obrigatório)

### `horys_set_pixels`

Poucos pixels soltos: 'pixels' [[x, y, '#rrggbb'], ...].

Parâmetros: `pixels`*, `camada`, `quadro` (`*` = obrigatório)

### `horys_ler_pixels`

Lê pixels no mesmo formato do horys_pixel_map (paleta + linhas). Sem 'camada' lê a imagem composta visível. 'rect' {x,y,w,h} ou 'selecao'. Passe a sua 'paleta' para reaproveitar as letras.

Parâmetros: `camada`, `quadro`, `rect`, `paleta`, `composto` (`*` = obrigatório)

### `horys_ver`

Mostra o sprite como imagem. 'critica': true = cor | cinza (valores) | silhueta | 1× e 2× numa imagem pequena (o melhor jeito de julgar). 'rect' amplia um detalhe. Sem camada = composto.

Parâmetros: `quadro`, `camada`, `rect`, `critica`, `escala` (`*` = obrigatório)

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

### `horys_aguardar`

Espera a resposta de uma pergunta, aprovação, revisão ou tarefa (id). Espera no
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

Parâmetros: `estilo`, `nome`, `tipo`, `partes`, `contorno`, `cor_contorno`, `sombra`, `sem_contorno`, `sem_borda`, `limite_cores`, `ritmo`, `pasta`, `estado`, `pedido`, `descricao`, `modular`, `preset_partes`, `juncoes`, `partes_oculto`, `componentes_max`, `espessura_fina`, `motivo` (`*` = obrigatório)

### `horys_asset_novo`

Cria o sprite de um asset pela ficha, de uma vez: quadro QxQ (padrão 192; pé no
pivô (Q/2, Q·127/192) = (96,127)), camadas 'sombra' (opacidade 77) e 'contorno' embaixo, uma camada por PARTE de baixo
para cima (padrão ['desenho']) e 'revisao' (oculta) em cima, quadros e tags por estado
(estados [{nome, quadros, ms}]), paleta do estilo travada. Desenhe só nas partes: contorno e sombra são gerados por
horys_contorno, como o portão espera. Com 'preset_partes' (ex.: 'humanoide-ferreiro') cria o asset MODULAR: as partes
do preset, a camada 'referencia' (oculta, para o desenho completo) e a ficha com modular, preset_partes, juncoes
(contratos de junção) e partes_oculto; o portão passa a exigir as partes sem erro (horys_partes_checar).

Parâmetros: `estilo`, `nome`, `tipo`, `partes`, `contorno`, `cor_contorno`, `sombra`, `sem_contorno`, `sem_borda`, `limite_cores`, `ritmo`, `pasta`, `estado`, `pedido`, `descricao`, `modular`, `preset_partes`, `juncoes`, `partes_oculto`, `componentes_max`, `espessura_fina`, `motivo`, `quadro`, `estados` (`*` = obrigatório)

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

Parâmetros: `imagem`*, `altura`*, `camada`, `quadro`, `modo`, `tirar_contorno`, `fundo`, `nativo` (`*` = obrigatório)

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
em <pasta>/vNN, roda o motor (grade.py gerar: folha, _8x, silhueta, _regua, _regua_anim, gif, _checagem.txt,
medidas/ e o .aseprite fatiado) e devolve APROVADO/REPROVADO com as falhas. Reprovado: corrija e rode de novo; não
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

### `horys_referencia_gerar`

Gera imagem de referência quando o usuário não tem uma: 'fonte' codex
(geração de imagem embutida do Codex; o Claude não gera imagem) ou lora (o modelo treinado do estilo, se houver).
'prompt' descreve o asset com a paleta e os princípios do estilo (nunca anexe arte de terceiros). Pode levar minutos;
devolve os caminhos das imagens.

Parâmetros: `fonte`*, `prompt`*, `pasta`, `n`, `estilo`, `imagens` (`*` = obrigatório)

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

Confere se o portão de medidas está calibrado na régua do estilo: gera as
mutações (versões estragadas da régua) e mede bons e estragados. Os bons têm que passar todos e os estragados têm que
reprovar todos. Leva alguns minutos.

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
Confere a composição depois e desfaz se mudou. 'sobrescrever': troca também pixels já existentes na parte.

Parâmetros: `parte`*, `regiao`*, `quadro`, `quadro_ref`, `sobrescrever` (`*` = obrigatório)

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
