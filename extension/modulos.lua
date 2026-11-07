-- Carrega os módulos da extensão a partir da pasta dela, sem usar require:
-- o cache de require (package.loaded) é compartilhado com outras extensões, e nomes como
-- "handlers" ou "sha256" colidiriam. Cada arquivo recebe a tabela M com os módulos já carregados.

local pasta, versao = ...

local function juntar(a, b)
  if app and app.fs then return app.fs.joinPath(a, b) end
  return a .. "/" .. b
end

local M = { VERSAO = versao or "0.1.0", pasta = pasta }

function M.carregar(nome)
  local caminho = juntar(pasta, nome .. ".lua")
  local fn, erro = loadfile(caminho)
  if not fn then error("não consegui carregar " .. caminho .. ": " .. tostring(erro), 0) end
  local mod = fn(M)
  M[nome] = mod
  return mod
end

-- ordem importa: cada um usa os anteriores
for _, nome in ipairs({ "jsonx", "base64", "sha256", "logica", "arquivos", "handlers", "cliente" }) do
  M.carregar(nome)
end

return M
