-- O lado Aseprite do protocolo (docs/protocolo.md): desafio HMAC, pedidos (req → res) e eventos.
-- Não sabe nada de WebSocket nem de janelas: recebe funções para enviar texto e fechar a conexão.
-- Assim dá para testar o aperto de mão inteiro no modo batch.

local M = ...
local J = M.jsonx
local S = M.sha256
local L = M.logica

local C = {}

C.PROTOCOLO = 1

local function nonceAleatorio()
  local t = {}
  for i = 1, 16 do t[i] = string.format("%02x", math.random(0, 255)) end
  return table.concat(t)
end

--[[
opcoes:
  enviar(texto)        manda uma mensagem de texto pelo WebSocket
  fechar(motivo)       fecha a conexão (motivo: "recusado", "prova", "protocolo")
  token()              devolve o token atual (string) ou nil
  handlers             tabela com executar(cmd, args) -> ok, data|erro
  versao               versão da extensão
  aoMudar(estado, texto)  avisa a interface (opcional)
  aoConfig(cliente)    listas estilos/tipos/motores mudaram (opcional)
  nonce()              gera o nonce do cliente (opcional; para testes)
]]
function C.novo(op)
  local c = {
    estado = "desconectado", -- desconectado | aguardando | autenticando | conectado | recusado
    autenticado = false,
    estilos = {}, tipos = {}, motores = {},
    versaoServidor = nil,
  }
  local nonceCliente, tokenUsado

  local function mudar(estado, texto)
    c.estado = estado
    if op.aoMudar then pcall(op.aoMudar, estado, texto) end
  end

  local function enviar(t)
    local ok, erro = pcall(function() op.enviar(J.codificar(t)) end)
    return ok, erro
  end

  local function guardarListas(msg)
    if msg.estilos ~= nil then c.estilos = L.listaDeTextos(msg.estilos) end
    if msg.tipos ~= nil then c.tipos = L.listaDeTextos(msg.tipos) end
    if msg.motores ~= nil then c.motores = L.listaDeTextos(msg.motores) end
    if op.aoConfig then pcall(op.aoConfig, c) end
  end

  function c:aoAbrir()
    self.autenticado = false
    nonceCliente, tokenUsado = nil, nil
    mudar("aguardando", "Conectado; esperando o desafio do servidor…")
  end

  function c:aoFechar()
    local estava = self.autenticado
    self.autenticado = false
    nonceCliente, tokenUsado = nil, nil
    if self.estado ~= "recusado" then mudar("desconectado", estava and "Conexão perdida" or nil) end
  end

  local function tratarAutenticacao(msg)
    if msg.t == "desafio" then
      if msg.protocolo ~= C.PROTOCOLO then
        mudar("recusado", "Versão de protocolo diferente: atualize a extensão ou o horysd")
        op.fechar("protocolo")
        return
      end
      if type(msg.nonce) ~= "string" or #msg.nonce < 16 or #msg.nonce > 128 then return end
      local token = op.token()
      if not token or token == "" then
        mudar("recusado", "Sem token: rode o horysd (ou cole o token em Configurações)")
        op.fechar("token")
        return
      end
      tokenUsado = token
      nonceCliente = (op.nonce or nonceAleatorio)()
      enviar({
        t = "ola",
        papel = "aseprite",
        versao = op.versao or "0",
        nonce = nonceCliente,
        prova = S.hmacHex(token, msg.nonce),
      })
      mudar("autenticando", "Autenticando…")
    elseif msg.t == "bem_vindo" then
      if not nonceCliente or not tokenUsado then return end
      local esperado = S.hmacHex(tokenUsado, nonceCliente)
      if S.iguais(msg.prova, esperado) then
        c.autenticado = true
        c.versaoServidor = msg.versao
        guardarListas(msg)
        mudar("conectado", "Conectado ao horysd" .. (msg.versao and (" " .. tostring(msg.versao)) or ""))
      else
        mudar("recusado", "O servidor não provou que conhece o token; desconectado")
        op.fechar("prova")
      end
    elseif msg.t == "recusado" then
      mudar("recusado", "Token recusado pelo servidor (" .. tostring(msg.motivo or "?") .. ")")
      op.fechar("recusado")
    end
    -- qualquer outra coisa antes de autenticar é ignorada
  end

  local function tratarPedido(msg)
    local ok, res = op.handlers.executar(msg.cmd, msg.args)
    local resposta
    if ok then
      resposta = { t = "res", id = msg.id, ok = true, data = res }
    else
      resposta = { t = "res", id = msg.id, ok = false, erro = tostring(res) }
    end
    local enviado, erro = enviar(resposta)
    if not enviado then
      enviar({ t = "res", id = msg.id, ok = false, erro = "não consegui montar a resposta: " .. tostring(erro) })
    end
    return resposta
  end

  -- Uma mensagem de texto chegou do servidor. Devolve a resposta montada (para testes) ou nil.
  function c:aoTexto(texto)
    local ok, msg = pcall(J.decodificar, texto)
    if not ok or type(msg) ~= "table" then return nil end
    if not self.autenticado then
      tratarAutenticacao(msg)
      return nil
    end
    if msg.t == "req" then
      return tratarPedido(msg)
    elseif msg.t == "config" then
      guardarListas(msg)
    end
    return nil
  end

  -- Manda um evento {t="evt", tipo=..., ...campos}. Devolve false se não estiver conectado.
  function c:evento(tipo, campos)
    if not self.autenticado then return false end
    local t = { t = "evt", tipo = tipo }
    for k, v in pairs(campos or {}) do t[k] = v end
    local ok = enviar(t)
    return ok
  end

  return c
end

return C
