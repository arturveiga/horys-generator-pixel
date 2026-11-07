-- Acesso a arquivos da extensão, todo num lugar só: no Aseprite com interface, cada script que
-- usa io.open pede permissão uma vez; concentrando aqui, a pessoa autoriza um arquivo só.

local M = ...
local L = M.logica
local B64 = M.base64

local A = {}

local function juntar(a, b)
  if app and app.fs then return app.fs.joinPath(a, b) end
  return a .. "/" .. b
end

function A.lerArquivo(caminho, binario)
  local f = io.open(caminho, binario and "rb" or "r")
  if not f then return nil end
  local conteudo = f:read("a")
  f:close()
  return conteudo
end

function A.gravarArquivo(caminho, conteudo)
  local f, erro = io.open(caminho, "wb")
  if not f then error("não consegui gravar " .. tostring(caminho) .. ": " .. tostring(erro), 0) end
  f:write(conteudo)
  f:close()
end

function A.caminhoToken()
  return L.caminhoToken(os.getenv, juntar)
end

-- Token do arquivo ~/.horys-pixel/token (nil se não existir ou estiver vazio).
-- `caminho` só é passado nos testes.
function A.lerTokenDoArquivo(caminho)
  caminho = caminho or A.caminhoToken()
  if not caminho then return nil end
  if app and app.fs and not app.fs.isFile(caminho) then return nil end
  -- se a pessoa negou a leitura uma vez, não pergunta de novo a cada tentativa de conexão
  if A.leituraNegada then return nil end
  local ok, conteudo = pcall(A.lerArquivo, caminho, false)
  if not ok then
    A.leituraNegada = true
    return nil
  end
  if not conteudo then return nil end
  local token = L.limparToken(conteudo)
  if token == "" then return nil end
  return token
end

local contador = 0

-- PNG em base64 -> Image do Aseprite (via arquivo temporário, apagado em seguida)
function A.imagemDePngBase64(b64, nome)
  local bytes = B64.decodificar(b64)
  if bytes:sub(1, 8) ~= "\137PNG\r\n\26\n" then error("a imagem não é um PNG", 0) end
  contador = contador + 1
  local seguro = tostring(nome or "img"):gsub("[^%w_%-]", "_")
  local caminho = juntar(app.fs.tempPath, string.format("horys-%s-%d-%d.png", seguro, os.time(), contador))
  A.gravarArquivo(caminho, bytes)
  local ok, img = pcall(function() return Image{ fromFile = caminho } end)
  pcall(os.remove, caminho)
  if not ok or not img then error("não consegui abrir a imagem enviada", 0) end
  return img
end

-- Image a partir de RGBA cru em base64 (sem arquivo: nenhum pedido de permissão).
function A.imagemDeRgbaBase64(b64, w, h)
  local bytes = B64.decodificar(b64)
  if #bytes ~= w * h * 4 then error(string.format("RGBA com %d bytes, esperado %d", #bytes, w * h * 4), 0) end
  local img = Image(w, h, ColorMode.RGB)
  img.bytes = bytes
  return img
end

return A
