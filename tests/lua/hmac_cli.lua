-- Imprime o HMAC-SHA256 da extensão para os parâmetros dados (usado por tests/test_extensao_lua.py):
--   aseprite -b --script-param ext=<pasta extension> --script-param token=<t> --script-param nonce=<n> --script hmac_cli.lua
-- Saída: "HMAC <hex>", "TOKEN_ARQUIVO <token lido do arquivo_token ou nil>" e "OLA <json do ola>" (o mesmo cálculo que o cliente faz no aperto de mão).
local ext = app.params.ext
local M = assert(loadfile(app.fs.joinPath(ext, "modulos.lua")))(ext, "0.1.0")
local token, nonce = app.params.token or "", app.params.nonce or ""
print("HMAC " .. M.sha256.hmacHex(token, nonce))
if app.params.arquivo_token then
  print("TOKEN_ARQUIVO " .. tostring(M.arquivos.lerTokenDoArquivo(app.params.arquivo_token)))
end

-- o mesmo pelo cliente: responde ao desafio com o "ola"
local enviado
local c = M.cliente.novo{
  enviar = function(t) enviado = t end,
  fechar = function() end,
  token = function() return M.logica.limparToken(token) end,
  handlers = M.handlers,
  versao = "0.1.0",
}
c:aoAbrir()
c:aoTexto(M.jsonx.codificar({ t = "desafio", nonce = nonce, protocolo = 1 }))
print("OLA " .. tostring(enviado))
