# Validação do horys-pixel pelo Codex

Data: 06/11/2026, horário de Fortaleza. Python 3.11.0; Codex CLI 0.164.0; Aseprite 1.3.16.1-dev.

## Dá para o Artur usar hoje?

**Sim, como ferramenta experimental acompanhada para desenhar, converter e medir no Aseprite. Ainda não como gerador autônomo confiável de assets aprovados.** O núcleo técnico funciona; os testes não demonstram que o botão Gerar entrega arte boa sozinho. O pedido Codex desta validação ficou bloqueado na leitura da skill e foi cancelado. O cancelamento deixou processos filhos vivos no Windows, exigindo encerramento da árvore do teste.

Antes do uso cotidiano: carregar a extensão corrigida, instalar o MCP/skills no perfil desejado, corrigir encerramento de processos, garantir leitura de arquivos pelo motor e serializar operações sobre o sprite. Antes de distribuir: completar as proteções de escrita, isolamento e testes de instalação fora do checkout. Não é necessário instalar torch/kohya para usar referência importada.

Nenhum commit/push, treino ou instalação de torch/kohya foi feito. Não alterei `src/horys_pixel/motor/`.

## 1. Testes executados

| Execução | Resultado |
|---|---|
| `python -m pytest -q`, antes das correções, sem `HORYS_PULAR_LENTOS` | **127 passed**, 129,79 s; nenhum skip |
| Regressões novas, antes das respectivas correções | Falhas reproduzidas para caminho relativo, salvar implícito, espera de conexão, pasta de asset, referência vazia na UI, execução por argumento de treino e ferramenta inexistente nas instruções MCP |
| `python -m pytest -q`, depois das correções, sem `HORYS_PULAR_LENTOS` | **136 passed**, 127,64 s; nenhum skip |

As duas execuções completas incluem `tests/test_motor_equivalencia.py`: comparação com a skill original, folhas PNG pixel a pixel e calibração **46/46 bons e 19/19 estragados**. Os testes Lua rodam no Aseprite real em modo batch, incluindo 31 casos internos no script de handlers. Testes novos em `tests/test_validacao_codex.py` e extensão de um caso em `tests/lua/test_handlers.lua`.

## 2. O que rodei de verdade

### Codex como motor

O daemon estava disponível quando consultei `python -m horys_pixel status`; inicialmente não havia Aseprite conectado.

1. Rodei a chamada solicitada com `Path('tmp-codex')`. Falhou imediatamente: código 1, `os error 2`.
2. Rodei a mesma chamada com caminho absoluto. Código 0, chamada real a `horys_status`, sem pedido de aprovação e sem falha de sandbox.
3. Corrigi `rodar()` para resolver a pasta antes de montar os caminhos e repeti a chamada com pasta relativa. Funcionou. A resposta final foi `Aseprite conectado, nenhum sprite aberto.`

Evidências: `tmp-codex/motor.log`, `tmp-codex/motor_ultima.txt`, `tmp-codex-absoluto/motor.log`. O primeiro log foi substituído pela repetição bem-sucedida; a falha original também está reproduzida no teste de regressão.

`comando()` já usa `approval_policy="never"`, `workspace-write`, prompt por stdin e aprovações por ferramenta. **Não houve motivo comprovado para afrouxar o sandbox ou substituir essas opções.** A correção foi na resolução de caminhos em `rodar()`.

O subprocesso herda MCPs/plugins pessoais: iniciou servidores alheios ao Horys, produziu avisos de autenticação/conexão e consumiu contexto desnecessário. A chamada simples de status registrou 44.307 tokens no resumo do CLI. Isso é evidência de custo/contexto, não medição de cobrança.

### Registro do MCP no Codex

Não havia `[mcp_servers.horys]` no `C:/Users/artur/.codex/config.toml`. Não alterei esse arquivo pessoal. Testei `instalar.registrar_codex()` com home temporário: TOML válido, executável existente, todas as **47 ferramentas** registradas com `approval_mode="approve"` e timeout de 600 s. O motor funcionou porque injeta esse registro via `-c`.

Fragilidade: se o bloco já existir, o instalador apenas mantém tudo; não atualiza caminhos antigos nem aprovações de ferramentas novas (`instalar.py:182`). Instalação persistente completa no perfil normal continua pendente.

### Revisor cruzado real

Chamei `ferramentas.estilo.revisar()` na pasta real:

`C:/Users/artur/.horys-pixel/pedidos/20261105-223425-43c9/v10`

Passei ficha, práticas e `quem_desenhou='claude'`. Usei rodada 91 apenas para não sobrescrever os logs das rodadas anteriores. O Codex terminou com código 0, **NAO_PASSA, aceitação 62**, JSON completo extraído por `motores.extrair_json`. Sem fallback para Claude.

Resultado preservado em `tmp-codex-absoluto/revisao-validacao.json`; logs `revisor_r91.*` na v10. A rodada artificial não deve ser interpretada como 91 revisões realizadas. Um teste adicional verifica extração de JSON com objetos aninhados; não foi necessário mudar o extrator.

### Aseprite e ferramentas

Instalei a extensão apenas no perfil isolado `C:/Users/artur/AppData/Local/Temp/aseprite-horys-validacao-codex`, com as permissões previstas no procedimento de teste fornecido. Abri o executável já existente. A extensão conectou automaticamente.

Executei via ponte real:

- `horys_asset_novo`: sprite 192×192, camadas sombra/contorno/desenho/revisao, tag idle e paleta do estilo exemplo.
- `horys_pixel_map`: 64 pixels de controle em 8×8.
- `horys_contorno`: contorno/sombra calculados sem erro.
- `horys_portao`: v01 reprovou a cor deliberadamente fora da paleta; após recolorir com uma cor válida, v02 passou.
- O exportador reabriu o `.aseprite` e confirmou igualdade pixel a pixel com a folha. Artefatos em `tmp-validacao-live/v01` e `v02`.

**Esse quadrado técnico passar no portão não significa qualidade artística.** O estilo exemplo não tem régua. A prova cobre escrita, paleta, contorno, exportação e medição, não produção de um baú convincente.

| Interface | Resultado observado |
|---|---|
| Novo asset | Abriu, recebeu texto e seleção Codex. Gerar com referência vazia falhou antes de enviar evento, por converter vazio em diretório atual. Corrigido e coberto por teste Lua; a UI instalada não foi recarregada para repetir o botão corrigido. |
| Perguntas | Abriu; clique Enviar retornou ao daemon `O evento de resposta chegou?: Sim`. |
| Aprovação com imagem | Imagem crítica exibida; clique Refazer retornou `aprovado: false`. |
| Painel de andamento | Exibiu conexão, id do pedido e início do motor Codex. |
| Novo estilo | Janela abriu com campos, lista e botões. Não submeti criação de pacote, portanto o evento desse botão não foi validado ao vivo. |
| Configurações | Ação do menu acionada, mas não obtive observação confiável da janela final; permanece não validada. Não alterei token/porta pela UI. |

### Pedido completo pelo Codex

Como o botão original bloqueou sem referência, usei a alternativa CLI solicitada, com descrição de baú de madeira, estilo exemplo, tipo prop e restrições de um quadro, sem animação nem geração externa de imagens.

Pedido: `20261106-080657-200e`, em `C:/Users/artur/.horys-pixel/pedidos/20261106-080657-200e`.

O painel recebeu o início e o briefing. O motor tentou listar recursos MCP (não implementados pela ponte) e utilizar outras ferramentas herdadas. Depois abriu uma pergunta dizendo não conseguir ler a skill local e pedindo que fosse disponibilizada. **Não gerou o baú nem completou o pipeline.** Cancelei o pedido; apesar de `estado=cancelado`, o processo filho continuou ativo. Encerrei explicitamente a árvore Node/Codex desse teste. Não confundir o sprite técnico criado por mim com resultado desse pedido.

A skill é detalhada para um agente que disponha de leitura/escrita local. O prompt apenas aponta para seu caminho; não entrega seu conteúdo nem garante essas capacidades. Proposta: perfil de execução dedicado, conteúdo da skill disponível desde o início e leitura/escrita de arquivos claramente suportada, com teste real até a entrega. Não presumir que o problema seja sandbox: o status e o revisor funcionaram.

## 3. Bugs corrigidos

Referências abaixo são do estado final dos arquivos. P1 = alto impacto; P2 = impacto moderado.

| Gravidade | Local | Cenário e correção |
|---|---|---|
| P1 | `src/horys_pixel/ferramentas/desenho.py:128` | `horys_salvar({})` enviava salvar sem verificar permissão/sobrescrita do arquivo atual. Agora obtém o caminho do sprite e aplica as verificações existentes. Teste confirma recusa antes de enviar comando ao editor. |
| P1 | `src/horys_pixel/ferramentas/treino.py:47` | `executar=false` podia ser contornado colocando `--executar` em `args`. Agora rejeita essa opção e abreviações aceitas pelo argparse; exige o campo próprio. Testado com runner falso: nada foi instalado/treinado. |
| P1 | `src/horys_pixel/ferramentas/estilo.py:111` e `:397` | Pasta do asset/versão era criada sem consultar `caminho_permitido`. Acrescentada verificação antes de criar. Teste prova que pasta negada não é criada. Isso NÃO conclui a proteção de todos os caminhos: ver pendências abaixo. |
| P2 | `src/horys_pixel/daemon/motores.py:78` | Pasta relativa era reutilizada em `cwd`, `-C` e arquivo de saída; resultava em pasta duplicada/inexistente. Agora normalizada com `resolve()` antes de montar caminhos. Teste com subprocesso e repetição real do Codex. |
| P2 | `src/horys_pixel/daemon/ponte.py:75` | Falha em `ws.send` ou cancelamento deixava Future em `_espera`. Envio agora fica no try e limpeza em finally. Regressão simula desconexão durante envio. |
| P2 | `extension/logica.lua:196` | `Dialog:file` vazio devolveu diretório com separador final; Novo asset tratava como imagem obrigatória inexistente. Normalização descarta esse valor sem nome de arquivo. Teste executado no Aseprite batch. |
| P2 | `src/horys_pixel/mcp_ponte.py:31` | Instruções MCP anunciavam `horys_sombra`, inexistente. Removida a citação: sombra já é gerada por `horys_contorno`. Teste confere todos os nomes das instruções contra o registro. |

## 4. Problemas restantes e fragilidades

### Prioridade antes de geração autônoma

1. **P1 — cancelamento/timeout não encerra a árvore Windows.** `daemon/pedidos.py:158` e `daemon/motores.py:99` usam `proc.kill()` sobre o lançador `.CMD`; o filho continuou vivo no teste. Em timeout também falta aguardar o término. Proposta: gerenciar a árvore com Job Object ou mecanismo equivalente, aguardar encerramento e cancelar tarefas/pendências associadas. Validar com filho e neto reais, inclusive cancelamento antes de `ao_iniciar`.
2. **P1 — não há fila/isolamento de sprite entre pedidos.** `daemon/pedidos.py:128` inicia tarefas concorrentes; `daemon/servidor.py:72` despacha chamadas simultâneas. Uma operação composta faz vários awaits e todas dependem de `app.sprite`. Outro pedido ou o usuário pode trocar o ativo entre ler e escrever. Proposta: fila por documento, identidade estável de sprite nas requisições e seção crítica por operação composta. Não implementei uma mudança arquitetural durante a revisão.
3. **P1 — acesso a arquivos da skill não garantido.** `daemon/pedidos.py:27` apenas manda ler caminho absoluto. O pedido real abriu pergunta de bloqueio em vez de executar. Garantir capacidade de leitura/escrita e retirar dependência acidental dos MCPs pessoais.
4. **P1 — escrita ainda não centralmente protegida.** `ferramentas/estilo.py:585` cria pasta de referência sem validar; `gosto.py:18` usa nome de estilo no fallback de caminho; `daemon/pedidos.py:69` concatena id sem validar. O portão ainda usa nome de tag em `saida / f'{nome}.grade'` (`estilo.py:412`), permitindo separadores/escape; `exportar` usa `copy2` sem confirmação de sobrescrita (`:467`). Proposta: validar componentes e destino final de CADA arquivo, reservar versões atomicamente e nunca sobrescrever sem autorização explícita. Não declarar o sistema seguro apenas pela correção da pasta-base.

### Comportamento e manutenção

- **P2 — sucesso de processo não é sucesso de asset:** `pedidos.py:145` marca estado concluído por exit code 0, mesmo se a etapa/arte continuar pendente. Persistir resultado artístico, técnico e aprovação separadamente.
- **P2 — reinício não retoma trabalho:** `Pedidos.__init__` não reconstitui processos/fila a partir dos pedidos persistidos. A promessa da arquitetura de continuar de onde parou não está implementada.
- **P2 — aprovação automática contamina gosto:** `conversa.py` agenda `aprovado=true, pendente_usuario=true`; `gosto.registrar_aprovacao` ignora esse marcador. Ausência de resposta pode virar preferência positiva. Além disso a aprovação pelo painel grava metadados, não captura automaticamente PNG para o conjunto, apesar da promessa documental.
- **P2 — tarefas MCP sobrevivem ao cliente:** `_cliente_mcp` cria tarefas sem guardá-las/cancelá-las na desconexão. Há limite de 64 MiB por mensagem, mas não limite de tarefas concorrentes. Falhas de handshake durante `_abrir` também merecem finally para fechar socket; o principal stdio não chama `Daemon.fechar()` em finally.
- **P2 — operações longas/timeouts:** subprocessos de conversão/treino matam sem aguardar; `medir_arquivo` deixa diretório `mkdtemp` para trás; contorno faz processamento síncrono dentro do event loop. Revisão pode levar 1800 s, mas a conexão MCP usa 600 s para chamadas diretas longas. Revisão já usa id/aguardar; conversão/calibração/treino não seguem uniformemente esse padrão.
- **P2 — backups prometidos não encontrados:** a arquitetura promete backup antes de cada etapa, mas não há implementação correspondente no daemon/ferramentas. Transações Lua permitem Undo por comando, não necessariamente por ferramenta composta inteira.
- **P2 — portão pode recompor diferente do documento arbitrariamente editado:** partes são lidas e contorno/sombra regenerados; opacidades/visibilidade das partes e edição manual das camadas geradas não são uma matriz canônica geral. A equivalência comprovada é do fluxo/formato suportado, não de todo documento possível do Aseprite.
- **P2 — distribuição:** caminhos `RAIZ/extension`, `RAIZ/skills` e `RAIZ/estilos` pressupõem checkout. `pyproject.toml` inclui dados dentro do pacote Python, mas essas pastas vivem fora dele. Validar wheel em ambiente limpo antes de anunciar instalação sem checkout; dependência `websockets>=12` também merece teste com versão mínima, pois o código usa `websockets.asyncio`.
- **P3 — UTF-8:** arquivos e subprocessos principais usam UTF-8 explicitamente. Saídas de scripts enviados via pipe PowerShell exibiram acentos substituídos no terminal; isso não prova corrupção dos arquivos, que foram lidos corretamente. Fixar `PYTHONIOENCODING=utf-8` nos comandos de diagnóstico facilita reproduções.

## 5. Coerência entre código, protocolo e skills

- **47 ferramentas registradas.** Todas as ferramentas `horys_*` citadas nas três skills e nos prompts de `daemon/pedidos.py` existem. Nenhum parâmetro escrito como exemplo nas skills foi identificado como nome incompatível; muitas chamadas são pseudocódigo, não JSON executável. Por exemplo, `horys_pedido_atualizar` requer `id`, omitido em abreviações da skill: convém mostrar um exemplo completo.
- `docs/ferramentas.md` foi regenerado com o script oficial: **bytes idênticos ao arquivo anterior**. Não estava desatualizado quanto ao registro, parâmetros ou descrições. Descrições herdadas podem prometer mais do que o código: `horys_treino_status` diz informar instalação kohya, mas só chama `gpu` e `perfil`; `rect` descreve aceitar string `selecao`, enquanto o schema só aceita objeto; `composto` aparece no schema mas não governa a leitura como parâmetro separado.
- Todos os **19 comandos** documentados estão no despacho explícito `COMANDOS` de `extension/handlers.lua`. Chamadas Python usam esses nomes; `refazer` é selecionado dinamicamente. Conversões de quadro/tag usam +1/-1 no Lua; não encontrei incompatibilidade 0-based nos fluxos testados.
- `ui_aprovar` no protocolo documenta apenas PNG base64. O Python atual envia `imagem_rgba`, `imagem_w`, `imagem_h`; Lua suporta esse caminho e a UI real funcionou. Documentar esses campos e o ping/reconexão para evitar clientes incompatíveis.
- `mcp_ponte.INSTRUCOES` tinha a única ferramenta fantasma encontrada, `horys_sombra`; corrigida.
- Estilo exemplo não tem KB/régua completas, mas a skill exige uma sequência de documentos típica do Horys Pixel Liso. Deixar explícito fallback para `estilo.md` e regras universais, sem exigir arquivos inexistentes.
- `README`/pendências falam em 126 testes; havia 127 antes desta revisão, 136 depois. “v0.1 funcionando de ponta a ponta” deve ser qualificado: o resultado Claude anterior já era não aprovado, e o pedido Codex atual não completou.
- `agents/revisor.md` e `motor/revisor_prompt.md` continuam orientados ao Horys Pixel Liso/Tiny mesmo com pacotes genéricos. Não confundir calibração Tiny com qualidade de qualquer estilo.

## 6. Segurança verificada e limites

- Servidor ligado a `127.0.0.1`, desafio HMAC nos dois sentidos. Testes Python/Lua de autenticação passaram.
- Extensão despacha comandos conhecidos, protegidos por `pcall`; não encontrei execução de Lua recebida do servidor. `loadfile` carrega os módulos locais da extensão, não conteúdo da mensagem.
- Examinei **17 arquivos** de logs/JSON/textos dos testes, pedido e logs do daemon procurando os bytes exatos do token local: **zero ocorrências**. Não imprimi o valor. Essa checagem não prova inexistência de vazamento em todos os caminhos possíveis.
- O comando CLI `horys token` imprime o token por design; não o executei. Isso precisa ser distinguido da regra de nunca expor segredo em chat/log/ferramenta. Mensagens arbitrárias de prompt/erro ainda são registradas sem redator central.
- `config.pastas_permitidas()` permite todo o home e TEMP, além das pastas configuradas. É mais amplo do que “apenas pastas de projeto” descrito na arquitetura.
- Há bypasses de escrita restantes listados acima. **A validação de segurança não está aprovada para distribuição.**

## 7. Avaliação do segundo prompt: faz sentido aqui?

**Sim como direção de produto e backlog incremental. Não deve ser aplicado literalmente como uma reescrita nem misturado à correção de bugs desta auditoria.** Ele acerta ao priorizar referência importada, preview, preservação do original e distinção entre fidelidade técnica e qualidade artística.

| Proposta | Situação real / adaptação |
|---|---|
| Extensão Lua + serviço externo + MCP | Já existe; reutilizar daemon, ponte, handlers e UI. |
| Importação de referência e pixelização | `horys_converter` já faz moda, paleta e pivô. Falta a experiência curta de preview/confirmar. |
| Obsidian | Pacote `horys-pixel-liso` aponta para KB local existente; régua e notas de leitura foram verificadas no disco. Não há necessidade de novo serviço Obsidian. Não validei toda a interpretação artística dessas notas. |
| Matriz canônica | Arrays RGBA e `.grade` já existem. `.grade` é DADO textual: paleta/letras, partes, quadros e metadados; não é imagem com quadrícula. Definir snapshot versionado do documento sem manter JSON, Markdown e grade como fontes independentes. |
| 16×16, 48×64 e outros retângulos | Editor/desenho genéricos aceitam dimensões; `horys_asset_novo`, grade e portão esperam Q×Q, com pivô proporcional a 192. Introduzir canvas/tamanho visível/exportação separados; não mudar o motor para 48×64 sem nova equivalência. |
| Paleta automática e dimensão escolhida | Estilo atual trava paleta e orienta escala. Oferecer modo livre vs. estilo e registrar exceções; não apresentar saída fora da régua como aprovada pelo estilo. |
| Camadas semânticas | A ferramenta cria camadas, mas converter põe pixels em uma camada. Separar corpo/cabelo/ferramenta e reconstruir áreas ocultas exige decisões artísticas; não é capacidade já pronta. |
| Todos os derivados iguais | Bom requisito. Hoje o portão recompõe contorno/sombra: definir se a fonte é documento editado ou representação artística antes da composição, para evitar duas verdades. |
| Grade A1/AA1 e Markdown por célula | Novos formatos de inspeção, não essenciais para pessoa criar sprite. Recomendo opcionais; priorizar PNG, `.aseprite`, snapshot JSON e validação. Verde neon só no preview, nunca no alpha/pixels finais. |
| Geração por texto | Caminho existente em `motor/conceito.py`, separado de `daemon/motores.py`; captura imagens novas da pasta global do Codex. Não gerei imagens nesta auditoria. Não prometer disponibilidade universal nem isolamento entre gerações concorrentes. |
| Animação e treino depois do MVP | Faz sentido para a UX nova; preservar suporte existente e não expandir antes de referência → sprite funcionar bem. |

Sugestão de ordem: (1) corrigir bloqueios operacionais e de escrita; (2) fluxo referência → preview → confirmar com tamanho/paleta, sem depender de geração externa; (3) round-trip pixel a pixel para o snapshot suportado e preservação do original; (4) refinamento por prompt e partes; (5) geração textual/animação/treino como opções posteriores.

O MVP deve usar uma imagem controlada e depois uma referência de personagem, avaliando também legibilidade e fidelidade. “Poucos ajustes manuais” é meta de produto, não uma garantia comprovada pelo conversor atual.

## 8. Entrega e estado local

Modificados: `daemon/motores.py`, `daemon/ponte.py`, `ferramentas/desenho.py`, `ferramentas/estilo.py`, `ferramentas/treino.py`, `mcp_ponte.py`, `extension/logica.lua`, `tests/lua/test_handlers.lua`. Adicionados: `tests/test_validacao_codex.py` e este relatório.

Diretórios de evidência no checkout: `tmp-codex`, `tmp-codex-absoluto`, `tmp-validacao-live`. Não são produto nem devem entrar automaticamente em commit. O repositório estava integralmente sem arquivos rastreados no início; não havia baseline Git para um diff convencional.

A extensão isolada foi copiada antes da correção Lua; recarregar/reinstalar esse perfil é necessário para testar a correção visual. O daemon já em execução também não recarrega módulos Python automaticamente. As correções finais foram validadas pela suíte em processos novos; não alego que o daemon antigo tenha usado todas elas.

Para abrir manualmente o teste isolado: definir `ASEPRITE_USER_FOLDER` para a pasta temporária acima, reinstalar a extensão nesse perfil com o Aseprite fechado e abrir `C:/Users/artur/Documents/aseprite/aseprite.exe`. Para uso normal, seguir o instalador do README, preferindo conferir `--simular` primeiro. Isso não resolve por si só os bloqueios de autonomia documentados.
