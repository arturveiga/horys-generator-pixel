-- JSON da extensão.
-- Codificar: escrito aqui porque o json.encode do Aseprite transforma {} em [] e não tem null.
-- Decodificar: usa o json.decode do Aseprite (C++) e converte o resultado (userdata, números
-- sempre float) em tabelas Lua comuns, com inteiros onde o número é inteiro.

local J = {}

local MT_ARRAY = { __jsontipo = "array" }
local MT_OBJETO = { __jsontipo = "objeto" }

-- Valor que vira "null" no JSON
J.null = setmetatable({}, { __jsontipo = "null", __tostring = function() return "null" end })

-- Marca uma tabela como lista (vazia vira [])
function J.lista(t) return setmetatable(t or {}, MT_ARRAY) end
-- Marca uma tabela como objeto (vazia vira {})
function J.objeto(t) return setmetatable(t or {}, MT_OBJETO) end

local ESCAPES = {
  ['"'] = '\\"', ["\\"] = "\\\\", ["\b"] = "\\b", ["\f"] = "\\f",
  ["\n"] = "\\n", ["\r"] = "\\r", ["\t"] = "\\t",
}

local function escapar(s)
  return '"' .. s:gsub('[%c"\\]', function(c)
    return ESCAPES[c] or string.format("\\u%04x", c:byte())
  end) .. '"'
end

local function ehLista(t)
  local mt = getmetatable(t)
  if mt and mt.__jsontipo == "array" then return true end
  if mt and mt.__jsontipo == "objeto" then return false end
  local n = #t
  if n == 0 then return false end -- tabela vazia sem marca: objeto
  local conta = 0
  for k in pairs(t) do
    if math.type(k) ~= "integer" or k < 1 or k > n then return false end
    conta = conta + 1
  end
  return conta == n
end

local function codificar(v, saida, prof)
  if prof > 64 then error("JSON profundo demais", 0) end
  local tv = type(v)
  if v == nil or v == J.null then
    saida[#saida + 1] = "null"
  elseif tv == "boolean" then
    saida[#saida + 1] = v and "true" or "false"
  elseif tv == "number" then
    if v ~= v or v == math.huge or v == -math.huge then
      saida[#saida + 1] = "null"
    elseif math.type(v) == "integer" then
      saida[#saida + 1] = string.format("%d", v)
    elseif v == math.floor(v) and math.abs(v) < 2^53 then
      saida[#saida + 1] = string.format("%d", math.floor(v))
    else
      saida[#saida + 1] = string.format("%.14g", v)
    end
  elseif tv == "string" then
    saida[#saida + 1] = escapar(v)
  elseif tv == "table" then
    if ehLista(v) then
      saida[#saida + 1] = "["
      for i = 1, #v do
        if i > 1 then saida[#saida + 1] = "," end
        codificar(v[i], saida, prof + 1)
      end
      saida[#saida + 1] = "]"
    else
      -- chaves em ordem: saída estável (facilita testes e logs)
      local chaves = {}
      for k in pairs(v) do chaves[#chaves + 1] = tostring(k) end
      table.sort(chaves)
      saida[#saida + 1] = "{"
      local primeiro = true
      for _, k in ipairs(chaves) do
        local val = v[k]
        if val == nil then val = v[tonumber(k)] end
        if not primeiro then saida[#saida + 1] = "," end
        primeiro = false
        saida[#saida + 1] = escapar(k)
        saida[#saida + 1] = ":"
        codificar(val, saida, prof + 1)
      end
      saida[#saida + 1] = "}"
    end
  else
    error("valor sem JSON: " .. tv, 0)
  end
end

function J.codificar(v)
  local saida = {}
  codificar(v, saida, 0)
  return table.concat(saida)
end

-- userdata/tabela do json.decode do Aseprite -> tabela Lua comum
local function simples(v, prof)
  local t = type(v)
  if t == "number" then
    if v == math.floor(v) and v >= math.mininteger and v <= math.maxinteger then
      return math.floor(v)
    end
    return v
  end
  if (t == "table" or t == "userdata") and prof < 32 then
    local o = {}
    if v[1] ~= nil then
      for i = 1, #v do o[i] = simples(v[i], prof + 1) end
    else
      for k, val in pairs(v) do o[k] = simples(val, prof + 1) end
    end
    return o
  end
  return v
end

function J.decodificar(texto)
  if type(json) == "nil" or not json.decode then
    error("esta versão do Aseprite não tem json.decode", 0)
  end
  local ok, v = pcall(json.decode, texto)
  if not ok then error("JSON inválido", 0) end
  return simples(v, 0)
end

J.simples = function(v) return simples(v, 0) end

return J
