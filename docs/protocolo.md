# Protocolo horysd ↔ Aseprite (v1)

Transporte: WebSocket de texto, JSON por mensagem, em `ws://127.0.0.1:<porta>/` (porta padrão **9140**).
O mesmo servidor atende a extensão do Aseprite (papel `aseprite`) e as pontes MCP (papel `mcp`).

## Autenticação (os dois lados provam que conhecem o token; o token nunca trafega)
Token: 48 hex em `~/.horys-pixel/token` (criado pelo `horysd`; `horys token` mostra; `horys token --novo` troca).

1. Servidor → `{"t":"desafio","nonce":"<32 hex>","protocolo":1}`
2. Cliente → `{"t":"ola","papel":"aseprite","versao":"<versão da extensão>","nonce":"<32 hex do cliente>",
   "prova":"<hmac_sha256_hex(token, nonce_do_servidor)>"}`
3. Servidor → `{"t":"bem_vindo","prova":"<hmac_sha256_hex(token, nonce_do_cliente)>","versao":"<servidor>",
   "estilos":["horys-pixel-liso",...],"tipos":["personagem",...],"motores":["claude","codex"]}`
   (as listas alimentam as janelas da extensão; o servidor reenvia `{"t":"config", ...mesmos campos}` quando mudam)
   ou `{"t":"recusado","motivo":"token"}` e fecha.
4. O cliente confere a prova do servidor; se não bater, fecha e ignora tudo.

`hmac_sha256_hex(chave, msg)`: HMAC-SHA256 padrão (RFC 2104), chave = os bytes ASCII do token, msg = os bytes ASCII do
nonce, saída em hex minúsculo.

## Pedido servidor → Aseprite
```json
{"t":"req","id":17,"cmd":"escrever","args":{...}}
```
Resposta:
```json
{"t":"res","id":17,"ok":true,"data":{...}}
{"t":"res","id":17,"ok":false,"erro":"texto curto em português"}
```
Cada comando que muda o sprite roda dentro de **uma** `app.transaction` (um passo de desfazer).
Índices: **quadros e camadas são 0-based** no protocolo (a extensão converte para o 1-based do Aseprite).
Cores: `"#rrggbb"` ou `"#rrggbbaa"`. Pixels: RGBA 8 bits, linha a linha, em **base64**.

### Comandos
| cmd | args | data |
|---|---|---|
| `status` | — | `{"versao_aseprite","sprite":null \| {"arquivo","largura","altura","modo","camadas":[{"nome","visivel","opacidade","indice"}],"quadros":[{"ms"}],"tags":[{"nome","de","ate"}],"camada_ativa","quadro_ativo"},"sprites":[{"indice","arquivo"}]}` |
| `sprite_novo` | `{"largura","altura","nome"?}` (RGB, fundo transparente, 1 camada "desenho") | igual a `status` |
| `abrir` | `{"arquivo"}` | `status` |
| `selecionar_sprite` | `{"indice"}` ou `{"arquivo"}` | `status` |
| `salvar` | `{"arquivo"?, "copia":bool}` (copia = Save Copy As, o sprite continua com o nome antigo) | `{"arquivo"}` |
| `camada` | `{"acao":"criar","nome","abaixo_de"?\|"acima_de"?}` · `{"acao":"remover","nome"}` · `{"acao":"renomear","nome","novo"}` · `{"acao":"propriedades","nome","visivel"?,"opacidade"?(0–255)}` · `{"acao":"ordem","nomes":[de baixo para cima]}` · `{"acao":"ativar","nome"}` | `status` |
| `quadro` | `{"acao":"criar","depois_de"?,"copiar":bool}` · `{"acao":"remover","indice"}` · `{"acao":"duracao","indice"\|"todos":true,"ms"}` · `{"acao":"ativar","indice"}` · `{"acao":"garantir","total"}` (cria quadros vazios até ter `total`) | `status` |
| `tag` | `{"acao":"criar","nome","de","ate"}` · `{"acao":"remover","nome"}` | `status` |
| `paleta` | `{"acao":"definir","cores":[...]}` · `{"acao":"ler"}` | `{"cores":[...]}` |
| `escrever` | `{"camada","quadro","x","y","w","h","rgba","mascara"}` — `mascara`: base64 de w·h bytes (1 = escreve o pixel do `rgba`, inclusive transparente; 0 = não toca). A célula é criada se faltar e cobre o sprite inteiro. | `{"escritos":n}` |
| `ler` | `{"camada"?(sem = imagem composta visível),"quadro","x"?,"y"?,"w"?,"h"?}` | `{"w","h","rgba"}` |
| `limpar_camada` | `{"camada","quadro"\|"todos":true}` | `{}` |
| `selecao` | — | `{"vazia":bool,"x","y","w","h"}` |
| `desfazer` / `refazer` | `{"passos":1}` | `{}` |
| `ui_perguntar` | `{"id","titulo","perguntas":[{"pergunta","cabecalho","multipla":bool,"opcoes":[{"rotulo","descricao"}]}]}` | `{"mostrado":true}` |
| `ui_aprovar` | `{"id","titulo","texto","imagem"?(base64 PNG)}` | `{"mostrado":true}` |
| `ui_progresso` | `{"pedido","etapa","texto","nota"?}` | `{}` |
| `ui_fechar` | `{"id"}` | `{}` |
| `ui_imagem` | `{"id","titulo","prompt","arquivo_prompt"?,"pasta"}` (mostra o prompt com Copiar e espera a imagem em `pasta`) | `{"mostrado":true}` |
| `ui_acabamento` | `{"id","titulo","itens":[{"id","onde","correcao"}]}` (lista do acabamento, com checkbox por item) | `{"mostrado":true}` |

## Eventos Aseprite → servidor (sem resposta)
```json
{"t":"evt","tipo":"resposta","id":"<id da pergunta>","respostas":{"<pergunta>":"<rótulo ou texto do 'outro'>"}}
{"t":"evt","tipo":"aprovacao","id":"<id>","aprovado":true,"comentario":"..."}
{"t":"evt","tipo":"pedido_novo","pedido":{"descricao","referencia"?,"tipo","estilo","motor":"claude|codex","estados":[...],"tamanho"?}}
{"t":"evt","tipo":"revisar_sprite","arquivo"?}
{"t":"evt","tipo":"estilo_novo","estilo":{"nome","imagens":[caminhos],"motor"}}
{"t":"evt","tipo":"cancelar","pedido"}
{"t":"evt","tipo":"imagem","id":"<id da espera>","caminho":"<arquivo escolhido>"}   // o horysd copia para entrada/
{"t":"evt","tipo":"abrir_pasta","id":"<id da espera>"}                              // abre entrada/ no sistema
{"t":"evt","tipo":"acabamento","id":"<id>","feitos":["L5",...],"total":3,"comentario":"..."}
```

## Pontes MCP (papel `mcp`)
Mesmo desafio; no `ola`, `"papel":"mcp"`. Depois:
```json
→ {"t":"chamar","id":3,"ferramenta":"horys_pixel_map","args":{...}}
← {"t":"resultado","id":3,"conteudo":[{"type":"text","text":"..."},{"type":"image","data":"<b64>","mimeType":"image/png"}],"erro":false}
→ {"t":"listar","id":4}
← {"t":"ferramentas","id":4,"ferramentas":[{"name","description","inputSchema"}]}
```
