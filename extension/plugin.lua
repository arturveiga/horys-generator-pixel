-- Horys Pixel: extensão do Aseprite.
-- Conecta o Aseprite ao servidor horysd (docs/protocolo.md) para desenhar ao vivo e conversar
-- dentro do Aseprite. Menu: Arquivo › Horys.
--
-- Organização:
--   plugin.lua    conexão (WebSocket + Timer), menu e preferências
--   cliente.lua   protocolo: desafio HMAC, req → res, eventos (testável sem WebSocket)
--   handlers.lua  comandos do servidor sobre o sprite (testável no modo batch)
--   logica.lua    regras das janelas (testável)    ui.lua  só desenha as janelas
--   arquivos.lua  leitura do token e imagens temporárias (todo io.open fica lá)

local PORTA_PADRAO = 9140
local ESPERA_RECONEXAO = 5      -- segundos entre tentativas enquanto desconectado
local ESPERA_APOS_RECUSA = 30   -- token recusado: espera mais antes de tentar de novo

local M, H, C, L, A, UI
local prefs
local ws, cliente
local timer
local parado = false            -- a pessoa clicou em Desconectar
local esperarAte = 0
local caiu = false             -- o socket fechou ou deu erro: o tique troca por um novo (handshake limpo)
local ultimoSinal = 0           -- os.time() da última mensagem/evento do socket (o horysd manda ping a cada 10 s)
local SEM_SINAL_CONECTADO = 35  -- sem nada nesse tempo, a conexão morreu (o Aseprite nem sempre avisa o CLOSE)
local SEM_SINAL_HANDSHAKE = 12  -- preso no aperto de mão
local statusTexto = "Desconectado"
local listas = { estilos = {}, tipos = {}, motores = {} }

local function setStatus(texto)
  if texto and texto ~= "" then statusTexto = texto end
  if UI then pcall(UI.atualizarConexao) end
end

local function porta()
  local p = math.floor(tonumber(prefs.porta) or PORTA_PADRAO)
  if p < 1 or p > 65535 then p = PORTA_PADRAO end
  return p
end

-- Token: primeiro o arquivo ~/.horys-pixel/token; senão, o colado em Configurações
local function obterToken()
  local t = A.lerTokenDoArquivo()
  if t then return t end
  local colado = L.limparToken(prefs.token or "")
  if colado ~= "" then return colado end
  return nil
end

local function conectado()
  return cliente ~= nil and cliente.autenticado == true
end

local function fecharSocket()
  if cliente then cliente.autenticado = false end
  if ws then
    local velho = ws
    ws = nil
    pcall(function() velho:close() end)
  end
  cliente = nil
end

local conectar -- definida abaixo

-- O cliente pediu para fechar (token recusado, prova errada, protocolo diferente, sem token)
local function aoFalhaAutenticacao(motivo)
  fecharSocket()
  if motivo == "protocolo" then
    esperarAte = os.time() + 300
  elseif motivo == "token" then
    esperarAte = os.time() + ESPERA_RECONEXAO
  else
    esperarAte = os.time() + ESPERA_APOS_RECUSA
  end
  setStatus()
end

conectar = function()
  fecharSocket()
  caiu = false
  ultimoSinal = os.time()
  parado = false
  esperarAte = 0
  if not obterToken() then
    setStatus("Sem token: ligue o horysd ou cole o token em Configurações")
    return false
  end
  local p = porta()
  local sock, c
  c = C.novo{
    enviar = function(texto) sock:sendText(texto) end,
    fechar = aoFalhaAutenticacao,
    token = obterToken,
    handlers = H,
    versao = M.VERSAO,
    aoMudar = function(_, texto) setStatus(texto) end,
    aoConfig = function(cl)
      listas = { estilos = cl.estilos, tipos = cl.tipos, motores = cl.motores }
    end,
  }
  local ok, erro = pcall(function()
    sock = WebSocket{
      url = "ws://127.0.0.1:" .. p .. "/",
      deflate = false,
      minreconnectwait = 600, -- a reconexão é nossa (tique): a interna fica fora do caminho
      maxreconnectwait = 600,
      onreceive = function(tipo, dados, err)
        if sock == nil or sock ~= ws then return end -- conexão antiga
        ultimoSinal = os.time()
        local okR, e = pcall(function()
          if tipo == WebSocketMessageType.OPEN then
            c:aoAbrir()
          elseif tipo == WebSocketMessageType.CLOSE then
            c:aoFechar()
            caiu = true
            setStatus("Aguardando o horysd na porta " .. p .. "…")
          elseif tipo == WebSocketMessageType.ERROR then
            if not c.autenticado then caiu = true end
            if not c.autenticado then setStatus("Aguardando o horysd na porta " .. p .. "…") end
          elseif tipo == WebSocketMessageType.TEXT then
            local res = c:aoTexto(dados)
            if res then pcall(app.refresh) end
          end
        end)
        if not okR then print("Horys: erro na conexão: " .. tostring(e)) end
      end,
    }
  end)
  if not ok or not sock then
    -- sem permissão para abrir a conexão: não insiste sozinho
    parado = true
    setStatus("Não consegui abrir a conexão: " .. tostring(erro))
    return false
  end
  ws, cliente = sock, c
  setStatus("Conectando na porta " .. p .. "…")
  sock:connect()
  return true
end

local function desconectar()
  parado = true
  fecharSocket()
  setStatus("Desconectado")
end

-- A cada 5 s: se estiver desconectado (e a pessoa não pediu para parar), tenta de novo.
-- Enquanto o socket existe, o próprio WebSocket tenta reconectar a cada 5 s.
local function tique()
  if parado or prefs.autoconectar == false then return end
  if ws and not caiu then
    local limite = (cliente and cliente.autenticado) and SEM_SINAL_CONECTADO or SEM_SINAL_HANDSHAKE
    if os.time() - ultimoSinal > limite then caiu = true end
  end
  if ws and caiu then
    -- não confia na reconexão interna do WebSocket (reabre com estado velho): descarta e cria outro
    caiu = false
    fecharSocket()
    if esperarAte < os.time() + ESPERA_RECONEXAO then esperarAte = os.time() + ESPERA_RECONEXAO end
  end
  if ws then return end
  if os.time() < esperarAte then return end
  conectar()
end

local function enviarEvento(tipo, campos)
  if not conectado() then return false end
  return cliente:evento(tipo, campos)
end

local function criarMenu(plugin)
  local grupo = "horys_menu"
  local okGrupo = pcall(function()
    plugin:newMenuGroup{ id = grupo, title = "Horys", group = "file_scripts" }
  end)
  local prefixo = ""
  if not okGrupo then
    grupo = "file_scripts"
    prefixo = "Horys: "
  end
  local itens = {
    { id = "HorysPainel", title = "Conexão e painel…", onclick = function() UI.abrirPainel() end },
    { id = "HorysNovoAsset", title = "Novo asset…", onclick = function() UI.novoAsset() end },
    { id = "HorysRevisar", title = "Revisar este sprite", onclick = function() UI.revisar() end,
      onenabled = function() return app.sprite ~= nil end },
    { id = "HorysNovoEstilo", title = "Novo estilo…", onclick = function() UI.novoEstilo() end },
    { id = "HorysConfiguracoes", title = "Configurações…", onclick = function() UI.configuracoes() end },
  }
  for _, it in ipairs(itens) do
    plugin:newCommand{
      id = it.id,
      title = prefixo .. it.title,
      group = grupo,
      onclick = function()
        local ok, e = pcall(it.onclick)
        if not ok then app.alert{ title = "Horys", text = { "Erro:", tostring(e) } } end
      end,
      onenabled = it.onenabled,
    }
  end
end

function init(plugin)
  prefs = plugin.preferences
  if prefs.porta == nil then prefs.porta = PORTA_PADRAO end
  if prefs.autoconectar == nil then prefs.autoconectar = true end

  M = assert(loadfile(app.fs.joinPath(plugin.path, "modulos.lua")))(plugin.path, plugin.version and tostring(plugin.version) or nil)
  H, C, L, A = M.handlers, M.cliente, M.logica, M.arquivos
  UI = M.carregar("ui")

  UI.iniciar{
    prefs = prefs,
    conectado = conectado,
    statusTexto = function() return statusTexto end,
    listas = function() return listas end,
    enviarEvento = enviarEvento,
    conectar = conectar,
    desconectar = desconectar,
    config = function()
      return {
        token = prefs.token or "",
        porta = porta(),
        autoconectar = prefs.autoconectar ~= false,
        caminhoToken = A.caminhoToken(),
        tokenDoArquivo = A.lerTokenDoArquivo() ~= nil,
      }
    end,
    salvarConfig = function(c)
      prefs.token = c.token
      prefs.porta = c.porta
      prefs.autoconectar = c.autoconectar
      A.leituraNegada = nil -- pergunta de novo pela permissão de ler o arquivo do token
    end,
  }

  H.ui = {
    perguntar = UI.perguntar,
    aprovar = UI.aprovar,
    progresso = UI.progresso,
    fechar = UI.fechar,
  }

  criarMenu(plugin)

  -- Sem interface (aseprite -b), não conecta: só registra os comandos.
  if app.isUIAvailable == false then return end

  -- primeira tentativa logo depois de abrir (1 s), depois a cada 5 s
  timer = Timer{
    interval = 1.0,
    ontick = function()
      if timer and timer.interval ~= ESPERA_RECONEXAO then
        timer:stop()
        timer.interval = ESPERA_RECONEXAO
        timer:start()
      end
      local ok, e = pcall(tique)
      if not ok then print("Horys: " .. tostring(e)) end
    end,
  }
  timer:start()
end

function exit(plugin)
  if timer then
    pcall(function() timer:stop() end)
    timer = nil
  end
  fecharSocket()
  if UI then pcall(UI.fecharTudo) end
  if H then H.ui = nil end
end
