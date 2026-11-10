-- Janelas da extensão. Só desenha: a lógica (montar respostas, pedidos, estilos) fica em
-- logica.lua e a conexão em plugin.lua/cliente.lua. Não roda no modo batch (sem Dialog).

local M = ...
local L = M.logica
local A = M.arquivos

local UI = {}

local ctx -- preenchido por UI.iniciar (plugin.lua)

local janelas = {}           -- id (texto) -> Dialog de pergunta/aprovação aberta
local painel                 -- Dialog do painel da conversa
local painelReconstruindo = false
local painelFechadoPeloUsuario = false
local andamento = { pedido = nil, linhas = {} }
local acabamentoPendente      -- último ui_acabamento sem resposta (o painel reabre a lista)

local LARGURA_TEXTO = 64
local LINHAS_ANDAMENTO = 6
local MOTORES_PADRAO = { "claude", "codex" }
local NOMES_MOTOR = { claude = "Claude", codex = "Codex" }
local EXTENSOES = { "png", "jpg", "jpeg", "gif", "webp", "bmp", "aseprite", "ase" }

--[[
ctx:
  conectado()                 -> bool
  statusTexto()               -> texto do estado da conexão
  listas()                    -> {estilos=, tipos=, motores=}
  enviarEvento(tipo, campos)  -> bool (false = sem conexão)
  conectar(), desconectar()
  config()                    -> {token=, porta=, autoconectar=, caminhoToken=, tokenDoArquivo=bool}
  salvarConfig{token=, porta=, autoconectar=}
  prefs                       -> plugin.preferences (lembra as últimas escolhas)
]]
function UI.iniciar(c) ctx = c end

local function chave(id) return tostring(id) end

local function avisar(texto)
  app.alert{ title = "Horys", text = texto }
end

local function semConexao()
  avisar({ "Sem conexão com o horysd.", "Ligue o servidor (horysd) e veja Arquivo › Horys › Conexão e painel…" })
end

-- várias linhas de texto, uma por label
local function textoLongo(dlg, texto, largura)
  for _, linha in ipairs(L.quebrarLinhas(texto, largura or LARGURA_TEXTO)) do
    dlg:label{ text = linha ~= "" and linha or " " }
  end
end

local function fecharJanela(k)
  local d = janelas[k]
  if d then
    janelas[k] = nil
    pcall(function() d:close() end)
  end
end

local function opcoesMotor(dlg, prefixo, escolhido)
  local motores = ctx.listas().motores
  if not motores or #motores == 0 then motores = MOTORES_PADRAO end
  local achou = false
  for _, m in ipairs(motores) do if m == escolhido then achou = true end end
  if not achou then escolhido = motores[1] end
  for i, m in ipairs(motores) do
    dlg:radio{
      id = prefixo .. m,
      label = (i == 1) and "Motor:" or nil,
      text = NOMES_MOTOR[m] or m,
      selected = (m == escolhido),
    }
  end
  return motores
end

local function motorEscolhido(dlg, prefixo, motores)
  local d = dlg.data
  for _, m in ipairs(motores) do
    if d[prefixo .. m] then return m end
  end
  return ""
end

local function comPadrao(lista, padrao)
  if lista and #lista > 0 then return lista end
  return padrao
end

-- ---------------------------------------------------------------------------
-- Painel da conversa
-- ---------------------------------------------------------------------------
local function linhasAndamento()
  local linhas = {}
  if andamento.atual then
    local p = andamento.atual
    local cab = {}
    if p.pedido ~= nil and tostring(p.pedido) ~= "" then cab[#cab + 1] = "Pedido " .. tostring(p.pedido) end
    if p.etapa ~= nil and tostring(p.etapa) ~= "" then cab[#cab + 1] = "etapa: " .. tostring(p.etapa) end
    if #cab > 0 then linhas[#linhas + 1] = table.concat(cab, " · ") end
    for _, l in ipairs(L.quebrarLinhas(p.texto or "", LARGURA_TEXTO)) do linhas[#linhas + 1] = l end
    if p.nota ~= nil and tostring(p.nota) ~= "" then linhas[#linhas + 1] = "Nota: " .. tostring(p.nota) end
  else
    linhas[1] = "Nenhum pedido em andamento."
  end
  while #linhas > LINHAS_ANDAMENTO do table.remove(linhas, #linhas - 1) end
  return linhas
end

local function contarPendentes()
  local n = 0
  for _ in pairs(janelas) do n = n + 1 end
  if n == 0 then return "Nada esperando você." end
  if n == 1 then return "1 janela esperando a sua resposta." end
  return n .. " janelas esperando a sua resposta."
end

local function atualizarPainel()
  if not painel then return end
  pcall(function()
    painel:modify{ id = "conexao", text = ctx.statusTexto() }
    painel:modify{ id = "botaoConexao", text = ctx.conectado() and "Desconectar" or "Conectar" }
    local linhas = linhasAndamento()
    for i = 1, LINHAS_ANDAMENTO do
      painel:modify{ id = "and" .. i, text = linhas[i] or "", visible = linhas[i] ~= nil }
    end
    painel:modify{ id = "pendentes", text = contarPendentes() }
    painel:modify{ id = "cancelar", enabled = andamento.atual ~= nil and andamento.atual.pedido ~= nil }
    painel:modify{ id = "acabamento", text = UI.textoBotaoAcabamento(), enabled = acabamentoPendente ~= nil }
  end)
end

function UI.textoBotaoAcabamento()
  if not acabamentoPendente then return "Acabamento" end
  return "Acabamento (" .. #acabamentoPendente.itens .. ")…"
end

local function construirPainel()
  local antes = painel and painel.bounds
  if painel then
    painelReconstruindo = true
    pcall(function() painel:close() end)
    painelReconstruindo = false
  end
  local dlg
  dlg = Dialog{
    title = "Horys",
    onclose = function()
      if painelReconstruindo then return end
      if painel == dlg then
        painel = nil
        painelFechadoPeloUsuario = true
      end
    end,
  }
  dlg:label{ id = "conexao", label = "Conexão:", text = ctx.statusTexto() }
  dlg:newrow()
  dlg:button{ id = "botaoConexao", text = ctx.conectado() and "Desconectar" or "Conectar", onclick = function()
    if ctx.conectado() then ctx.desconectar() else ctx.conectar() end
    atualizarPainel()
  end }
  dlg:button{ text = "Configurações…", onclick = function() UI.configuracoes() end }

  dlg:separator{ text = "Andamento" }
  dlg:newrow{ always = true }
  local linhas = linhasAndamento()
  for i = 1, LINHAS_ANDAMENTO do
    dlg:label{ id = "and" .. i, text = linhas[i] or "", visible = linhas[i] ~= nil }
  end
  dlg:label{ id = "pendentes", text = contarPendentes() }
  dlg:newrow()

  dlg:separator{}
  dlg:button{ text = "Novo asset…", onclick = function() UI.novoAsset() end }
  dlg:button{ text = "Revisar este sprite", onclick = function() UI.revisar() end }
  dlg:newrow()
  dlg:button{ id = "acabamento", text = UI.textoBotaoAcabamento(), enabled = acabamentoPendente ~= nil,
    onclick = function() if acabamentoPendente then UI.acabamento(acabamentoPendente) end end }
  dlg:button{ id = "cancelar", text = "Cancelar pedido",
    enabled = andamento.atual ~= nil and andamento.atual.pedido ~= nil,
    onclick = function()
      local p = andamento.atual and andamento.atual.pedido
      if p == nil then return end
      local r = app.alert{ title = "Horys", text = "Cancelar o pedido " .. tostring(p) .. "?", buttons = { "Cancelar pedido", "Voltar" } }
      if r ~= 1 then return end
      if not ctx.enviarEvento("cancelar", { pedido = p }) then semConexao() end
    end }
  dlg:button{ text = "Fechar", onclick = function() dlg:close() end }

  painel = dlg
  dlg:show{ wait = false }
  if antes then
    pcall(function() dlg.bounds = Rectangle(antes.x, antes.y, dlg.bounds.width, dlg.bounds.height) end)
  end
end

function UI.abrirPainel()
  painelFechadoPeloUsuario = false
  construirPainel()
end

-- Chamado pelo plugin quando a conexão muda
function UI.atualizarConexao()
  atualizarPainel()
end

-- ---------------------------------------------------------------------------
-- ui_progresso
-- ---------------------------------------------------------------------------
function UI.progresso(p)
  local novoPedido = p.pedido ~= nil and (not andamento.atual or andamento.atual.pedido ~= p.pedido)
  andamento.atual = {
    pedido = p.pedido,
    etapa = p.etapa,
    texto = p.texto and tostring(p.texto) or "",
    nota = p.nota,
  }
  if painel then
    atualizarPainel()
  elseif not painelFechadoPeloUsuario or novoPedido then
    painelFechadoPeloUsuario = false
    construirPainel()
  end
end

-- ---------------------------------------------------------------------------
-- ui_perguntar
-- ---------------------------------------------------------------------------
function UI.perguntar(a)
  local k = chave(a.id)
  fecharJanela(k)
  local perguntas = a.perguntas
  local dlg
  dlg = Dialog{
    title = (a.titulo and a.titulo ~= "") and a.titulo or "Horys: pergunta",
    onclose = function()
      -- fechou sem responder: nada é enviado, o servidor continua esperando
      if janelas[k] == dlg then janelas[k] = nil end
      atualizarPainel()
    end,
  }
  dlg:newrow{ always = true }
  for i, p in ipairs(perguntas) do
    dlg:separator{ text = (p.cabecalho ~= "" and p.cabecalho) or ("Pergunta " .. i) }
    textoLongo(dlg, p.pergunta)
    for j, o in ipairs(p.opcoes) do
      local id = "p" .. i .. "o" .. j
      if p.multipla then
        dlg:check{ id = id, text = o.rotulo, selected = false }
      else
        -- o primeiro radio de cada pergunta tem label: abre um grupo novo
        dlg:radio{ id = id, label = (j == 1) and "" or nil, text = o.rotulo, selected = (j == 1) }
      end
      if o.descricao ~= "" then
        for _, linha in ipairs(L.quebrarLinhas(o.descricao, LARGURA_TEXTO - 6)) do
          dlg:label{ text = "      " .. linha }
        end
      end
    end
    dlg:entry{ id = "p" .. i .. "outro", label = "Outro:", text = "" }
  end
  dlg:separator{}
  dlg:newrow()
  dlg:button{ text = "Enviar", focus = true, onclick = function()
    local d = dlg.data
    local escolhas = {}
    for i, p in ipairs(perguntas) do
      local sel = {}
      for j in ipairs(p.opcoes) do
        if d["p" .. i .. "o" .. j] then sel[#sel + 1] = j end
      end
      escolhas[i] = { selecionados = sel, outro = d["p" .. i .. "outro"] }
    end
    local respostas, faltando = L.montarRespostas(perguntas, escolhas)
    if #faltando > 0 then
      avisar({ "Falta responder:", table.concat(faltando, ", ") })
      return
    end
    if ctx.enviarEvento("resposta", { id = a.id, respostas = respostas }) then
      janelas[k] = nil
      dlg:close()
      atualizarPainel()
    else
      semConexao()
    end
  end }
  janelas[k] = dlg
  dlg:show{ wait = false }
  atualizarPainel()
end

-- ---------------------------------------------------------------------------
-- ui_aprovar
-- ---------------------------------------------------------------------------
local MAX_CANVAS = 384

local function prepararImagem(b64, id, rgba, w, h)
  local ok, img
  if rgba then
    ok, img = pcall(A.imagemDeRgbaBase64, rgba, w, h)
  else
    ok, img = pcall(A.imagemDePngBase64, b64, id)
  end
  if not ok then return nil, tostring(img) end
  local w, h = img.width, img.height
  local fator = math.min(MAX_CANVAS / w, MAX_CANVAS / h)
  if fator >= 1 then
    fator = math.floor(fator)
    local grande = img:clone()
    if fator > 1 then grande:resize(w * fator, h * fator) end -- vizinho mais próximo: sem suavizar
    return { img = grande, w = w * fator, h = h * fator, escala = true }
  end
  -- maior que o canvas: reduz na hora de desenhar
  return { img = img, w = math.max(1, math.floor(w * fator)), h = math.max(1, math.floor(h * fator)), escala = false }
end

function UI.aprovar(a)
  local k = chave(a.id)
  fecharJanela(k)
  local dlg
  dlg = Dialog{
    title = (a.titulo ~= "" and a.titulo) or "Horys: aprovação",
    onclose = function()
      if janelas[k] == dlg then janelas[k] = nil end
      atualizarPainel()
    end,
  }
  dlg:newrow{ always = true }
  textoLongo(dlg, a.texto)
  if a.imagem or a.imagem_rgba then
    local imagem, erro = prepararImagem(a.imagem, k, a.imagem_rgba, a.imagem_w, a.imagem_h)
    if imagem then
      dlg:canvas{
        id = "imagem", width = imagem.w, height = imagem.h, autoscaling = false,
        hexpand = false, vexpand = false,
        onpaint = function(ev)
          local gc = ev.context
          gc.antialias = false
          -- xadrez atrás da transparência
          local q = 8
          for y = 0, imagem.h - 1, q do
            for x = 0, imagem.w - 1, q do
              gc.color = (((x // q) + (y // q)) % 2 == 0) and Color{ r = 204, g = 204, b = 204 } or Color{ r = 255, g = 255, b = 255 }
              gc:fillRect(Rectangle(x, y, math.min(q, imagem.w - x), math.min(q, imagem.h - y)))
            end
          end
          if imagem.escala then
            gc:drawImage(imagem.img, 0, 0)
          else
            gc:drawImage(imagem.img, 0, 0, imagem.img.width, imagem.img.height, 0, 0, imagem.w, imagem.h)
          end
        end,
      }
    else
      dlg:label{ text = "(não consegui mostrar a imagem: " .. tostring(erro) .. ")" }
    end
  end
  dlg:entry{ id = "comentario", label = "Comentário:", text = "" }
  dlg:separator{}
  dlg:newrow()
  local function responder(aprovado)
    local ev = L.montarAprovacao(a.id, aprovado, dlg.data.comentario)
    ev.tipo = nil
    if ctx.enviarEvento("aprovacao", ev) then
      janelas[k] = nil
      dlg:close()
      atualizarPainel()
    else
      semConexao()
    end
  end
  dlg:button{ text = "Aprovar", focus = true, onclick = function() responder(true) end }
  dlg:button{ text = "Refazer", onclick = function() responder(false) end }
  janelas[k] = dlg
  dlg:show{ wait = false }
  atualizarPainel()
end

-- ---------------------------------------------------------------------------
-- ui_imagem: mostra o prompt de tradução e espera a imagem gerada fora
-- (o horysd também vigia a pasta entrada/: salvar lá já basta)
-- ---------------------------------------------------------------------------
local LINHAS_PROMPT = 24

local function copiar(textoCopiar)
  local ok = pcall(function() app.clipboard.text = textoCopiar end)
  return ok
end

function UI.imagem(a)
  local k = chave(a.id)
  fecharJanela(k)
  local dlg
  dlg = Dialog{
    title = (a.titulo ~= "" and a.titulo) or "Horys: gere a imagem",
    onclose = function()
      if janelas[k] == dlg then janelas[k] = nil end
      atualizarPainel()
    end,
  }
  dlg:newrow{ always = true }
  dlg:separator{ text = "Prompt" }
  local linhas = L.quebrarLinhas(a.prompt, LARGURA_TEXTO)
  for i = 1, math.min(#linhas, LINHAS_PROMPT) do
    dlg:label{ text = linhas[i] ~= "" and linhas[i] or " " }
  end
  if #linhas > LINHAS_PROMPT then
    dlg:label{ text = "(… " .. (#linhas - LINHAS_PROMPT) .. " linhas a mais: use Copiar prompt)" }
  end
  dlg:newrow()
  dlg:button{ text = "Copiar prompt", onclick = function()
    if copiar(a.prompt) then
      avisar("Prompt copiado. Cole no gerador de imagem que quiser.")
    else
      avisar({ "Este Aseprite não deixa copiar pelo script.", "Abra o arquivo: " .. (a.arquivo_prompt ~= "" and a.arquivo_prompt or "(sem arquivo)") })
    end
  end }
  dlg:button{ text = "Abrir pasta", onclick = function()
    if not ctx.enviarEvento("abrir_pasta", { id = a.id }) then semConexao() end
  end }
  dlg:separator{ text = "Imagem gerada" }
  textoLongo(dlg, "Salve a imagem nesta pasta (o Horys percebe sozinho) ou escolha o arquivo abaixo:")
  textoLongo(dlg, a.pasta)
  dlg:file{ id = "arquivo", label = "Arquivo:", title = "Imagem gerada", open = true, entry = true,
    filetypes = EXTENSOES, filename = "" }
  dlg:separator{}
  dlg:newrow()
  dlg:button{ text = "Enviar imagem", focus = true, onclick = function()
    local c = L.aparar(dlg.data.arquivo)
    if c == "" or not app.fs.isFile(c) then avisar("Escolha o arquivo da imagem.") return end
    if not L.ehImagem(c) then avisar("Esse arquivo não parece uma imagem.") return end
    if ctx.enviarEvento("imagem", { id = a.id, caminho = c }) then
      janelas[k] = nil
      dlg:close()
      atualizarPainel()
    else
      semConexao()
    end
  end }
  dlg:button{ text = "Depois", onclick = function() dlg:close() end }
  janelas[k] = dlg
  dlg:show{ wait = false }
  atualizarPainel()
end

-- ---------------------------------------------------------------------------
-- ui_acabamento: o que o usuário finaliza no Aseprite (as marcas da camada 'revisao')
-- ---------------------------------------------------------------------------
function UI.acabamento(a)
  acabamentoPendente = a
  local k = chave(a.id)
  fecharJanela(k)
  local dlg
  dlg = Dialog{
    title = (a.titulo ~= "" and a.titulo) or "Horys: acabamento",
    onclose = function()
      if janelas[k] == dlg then janelas[k] = nil end
      atualizarPainel()
    end,
  }
  dlg:newrow{ always = true }
  textoLongo(dlg, "Falta só acabamento. Os pontos estão marcados na camada 'revisao'. Marque o que já fez:")
  dlg:separator{}
  for i, it in ipairs(a.itens) do
    local cab = it.id ~= "" and ("[" .. it.id .. "] ") or ""
    local linhas = L.quebrarLinhas(cab .. it.correcao, LARGURA_TEXTO - 4)
    dlg:check{ id = "item" .. i, text = linhas[1] or "", selected = false }
    for j = 2, #linhas do dlg:label{ text = "      " .. linhas[j] } end
    if it.onde ~= "" then dlg:label{ text = "      onde: " .. it.onde } end
  end
  dlg:separator{}
  dlg:entry{ id = "comentario", label = "Comentário:", text = "" }
  dlg:newrow()
  dlg:button{ text = "Terminei o retoque", focus = true, onclick = function()
    local d = dlg.data
    local feitos = {}
    for i in ipairs(a.itens) do feitos[i] = d["item" .. i] == true end
    if ctx.enviarEvento("acabamento", L.montarAcabamento(a.id, a.itens, feitos, d.comentario)) then
      acabamentoPendente = nil
      janelas[k] = nil
      dlg:close()
      atualizarPainel()
    else
      semConexao()
    end
  end }
  dlg:button{ text = "Depois", onclick = function() dlg:close() end }
  janelas[k] = dlg
  dlg:show{ wait = false }
  atualizarPainel()
end

-- ---------------------------------------------------------------------------
-- ui_fechar
-- ---------------------------------------------------------------------------
function UI.fechar(id)
  if acabamentoPendente and chave(acabamentoPendente.id) == chave(id) then acabamentoPendente = nil end
  fecharJanela(chave(id))
  atualizarPainel()
end

-- ---------------------------------------------------------------------------
-- Novo asset…
-- ---------------------------------------------------------------------------
local TIPOS_PADRAO = { "personagem", "inimigo", "tile", "prop", "efeito", "ícone", "ui" }
local ESTILOS_PADRAO = { "horys-pixel-liso" }

local function indiceDe(lista, v)
  for i, x in ipairs(lista) do if x == v then return i end end
  return nil
end

function UI.novoAsset()
  local listas = ctx.listas()
  local tipos = comPadrao(listas.tipos, TIPOS_PADRAO)
  local estilos = comPadrao(listas.estilos, ESTILOS_PADRAO)
  local prefs = ctx.prefs
  local dlg = Dialog{ title = "Horys: novo asset" }
  dlg:newrow{ always = true }
  if not ctx.conectado() then
    dlg:label{ text = "Sem conexão com o horysd: o pedido só sai com o servidor ligado." }
  end
  dlg:entry{ id = "descricao", label = "O que criar:", text = "" }
  dlg:file{ id = "referencia", label = "Referência (opcional):", title = "Imagem de referência",
    open = true, entry = true, filetypes = EXTENSOES, filename = "" }
  dlg:combobox{ id = "tipo", label = "Tipo:", options = tipos,
    option = indiceDe(tipos, prefs.ultimoTipo) and prefs.ultimoTipo or tipos[1] }
  dlg:combobox{ id = "estilo", label = "Estilo:", options = estilos,
    option = indiceDe(estilos, prefs.ultimoEstilo) and prefs.ultimoEstilo or estilos[1] }
  local motores = opcoesMotor(dlg, "motor_", prefs.ultimoMotor or "claude")
  dlg:entry{ id = "estados", label = "Estados:", text = prefs.ultimosEstados or "idle" }
  dlg:label{ text = "separados por vírgula, ex.: idle, andar, atacar" }
  dlg:entry{ id = "tamanho", label = "Tamanho (opcional):", text = "" }
  dlg:label{ text = "ex.: 32 ou 32x48; vazio = padrão do estilo" }
  dlg:separator{}
  dlg:newrow()
  dlg:button{ text = "Gerar", focus = true, onclick = function()
    local d = dlg.data
    local pedido, erro = L.montarPedido({
      descricao = d.descricao, referencia = d.referencia, tipo = d.tipo, estilo = d.estilo,
      motor = motorEscolhido(dlg, "motor_", motores), estados = d.estados, tamanho = d.tamanho,
    })
    if not pedido then avisar(erro) return end
    if pedido.referencia and not app.fs.isFile(pedido.referencia) then
      avisar({ "Não achei a imagem de referência:", pedido.referencia })
      return
    end
    if not ctx.enviarEvento("pedido_novo", { pedido = pedido }) then semConexao() return end
    prefs.ultimoTipo, prefs.ultimoEstilo, prefs.ultimoMotor = pedido.tipo, pedido.estilo, pedido.motor
    prefs.ultimosEstados = d.estados
    dlg:close()
    if not painel then UI.abrirPainel() end
  end }
  dlg:button{ text = "Cancelar", onclick = function() dlg:close() end }
  dlg:show{ wait = false }
end

-- ---------------------------------------------------------------------------
-- Revisar este sprite
-- ---------------------------------------------------------------------------
function UI.revisar()
  local s = app.sprite
  if not s then avisar("Abra um sprite primeiro.") return end
  local campos = {}
  if s.filename and s.filename ~= "" and app.fs.isFile(s.filename) then
    campos.arquivo = s.filename
    if s.isModified then
      local r = app.alert{ title = "Horys",
        text = { "O sprite tem mudanças não salvas.", "A revisão usa o arquivo salvo e o que estiver aberto no Aseprite." },
        buttons = { "Revisar assim", "Cancelar" } }
      if r ~= 1 then return end
    end
  end
  if not ctx.enviarEvento("revisar_sprite", campos) then semConexao() return end
  if not painel then UI.abrirPainel() end
end

-- ---------------------------------------------------------------------------
-- Novo estilo…
-- ---------------------------------------------------------------------------
function UI.novoEstilo()
  local imagens = {}
  local prefs = ctx.prefs
  local dlg = Dialog{ title = "Horys: novo estilo" }
  dlg:newrow{ always = true }
  if not ctx.conectado() then
    dlg:label{ text = "Sem conexão com o horysd: o estilo só é criado com o servidor ligado." }
  end
  dlg:entry{ id = "nome", label = "Nome do estilo:", text = "" }
  dlg:separator{ text = "Imagens do que você gosta" }

  local function atualizarLista()
    local opcoes = #imagens > 0 and imagens or { "(nenhuma imagem)" }
    dlg:modify{ id = "lista", options = opcoes, option = opcoes[#opcoes] }
    dlg:modify{ id = "contagem", text = #imagens .. (#imagens == 1 and " imagem" or " imagens") }
  end

  local function adicionar(c)
    for _, x in ipairs(imagens) do if x == c then return end end
    imagens[#imagens + 1] = c
  end

  dlg:file{ id = "arquivo", label = "Imagem:", title = "Escolha uma imagem", open = true, entry = true,
    filetypes = EXTENSOES, filename = "" }
  dlg:newrow()
  dlg:button{ text = "Adicionar imagem", onclick = function()
    local c = L.aparar(dlg.data.arquivo)
    if c == "" or not app.fs.isFile(c) then avisar("Escolha um arquivo de imagem.") return end
    if not L.ehImagem(c) then avisar("Esse arquivo não parece uma imagem.") return end
    adicionar(c)
    atualizarLista()
  end }
  dlg:button{ text = "Adicionar a pasta toda", onclick = function()
    local c = L.aparar(dlg.data.arquivo)
    local pasta = c
    if c ~= "" and not app.fs.isDirectory(c) then pasta = app.fs.filePath(c) end
    if pasta == "" or not app.fs.isDirectory(pasta) then
      avisar("Escolha uma imagem dentro da pasta (ou digite o caminho da pasta).")
      return
    end
    local antes = #imagens
    local nomes = app.fs.listFiles(pasta)
    table.sort(nomes)
    for _, n in ipairs(nomes) do
      local caminho = app.fs.joinPath(pasta, n)
      if app.fs.isFile(caminho) and L.ehImagem(n) then adicionar(caminho) end
    end
    if #imagens == antes then avisar("Nenhuma imagem nova nessa pasta.") end
    atualizarLista()
  end }
  dlg:newrow{ always = true }
  dlg:combobox{ id = "lista", label = "Adicionadas:", options = { "(nenhuma imagem)" } }
  dlg:label{ id = "contagem", text = "0 imagens" }
  dlg:newrow()
  dlg:button{ text = "Remover a selecionada", onclick = function()
    local sel = dlg.data.lista
    for i, x in ipairs(imagens) do
      if x == sel then table.remove(imagens, i) break end
    end
    atualizarLista()
  end }
  dlg:newrow{ always = true }
  dlg:separator{}
  local motores = opcoesMotor(dlg, "motor_", prefs.ultimoMotor or "claude")
  dlg:separator{}
  dlg:newrow()
  dlg:button{ text = "Criar estilo", focus = true, onclick = function()
    local estilo, erro = L.montarEstilo({ nome = dlg.data.nome, imagens = imagens,
      motor = motorEscolhido(dlg, "motor_", motores) })
    if not estilo then avisar(erro) return end
    if not ctx.enviarEvento("estilo_novo", { estilo = estilo }) then semConexao() return end
    dlg:close()
    if not painel then UI.abrirPainel() end
  end }
  dlg:button{ text = "Cancelar", onclick = function() dlg:close() end }
  dlg:show{ wait = false }
end

-- ---------------------------------------------------------------------------
-- Configurações…
-- ---------------------------------------------------------------------------
function UI.configuracoes()
  local cfg = ctx.config()
  local dlg = Dialog{ title = "Horys: configurações" }
  dlg:newrow{ always = true }
  if cfg.tokenDoArquivo then
    dlg:label{ label = "Token:", text = "lido de " .. tostring(cfg.caminhoToken) }
    dlg:label{ text = "(o campo abaixo só é usado se esse arquivo não existir)" }
  else
    dlg:label{ label = "Token:", text = "arquivo não encontrado: " .. tostring(cfg.caminhoToken or "?") }
    dlg:label{ text = "Rode `horys token` no terminal e cole o token abaixo." }
  end
  dlg:entry{ id = "token", label = "Token colado:", text = cfg.token or "" }
  dlg:number{ id = "porta", label = "Porta:", text = tostring(cfg.porta), decimals = 0 }
  dlg:check{ id = "autoconectar", text = "Conectar sozinho ao abrir o Aseprite", selected = cfg.autoconectar }
  dlg:separator{}
  dlg:newrow()
  dlg:button{ text = "Salvar e conectar", focus = true, onclick = function()
    local d = dlg.data
    local porta = math.floor(tonumber(d.porta) or 0)
    if porta < 1 or porta > 65535 then avisar("Porta inválida.") return end
    ctx.salvarConfig{ token = L.limparToken(d.token), porta = porta, autoconectar = d.autoconectar == true }
    dlg:close()
    ctx.conectar()
    atualizarPainel()
  end }
  dlg:button{ text = "Cancelar", onclick = function() dlg:close() end }
  dlg:show{ wait = false }
end

-- Fecha tudo (ao desativar a extensão)
function UI.fecharTudo()
  for k in pairs(janelas) do fecharJanela(k) end
  if painel then
    local d = painel
    painel = nil
    painelReconstruindo = true
    pcall(function() d:close() end)
    painelReconstruindo = false
  end
end

return UI
