-- Base64 (RFC 4648, alfabeto padrão, com "=") em Lua pura.
-- Feito para strings grandes (pixels RGBA): trabalha em blocos e junta com table.concat.

local ALFABETO = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

local PARA_CHAR = {}
local DE_CHAR = {}
for i = 1, 64 do
  local c = ALFABETO:sub(i, i)
  PARA_CHAR[i - 1] = c
  DE_CHAR[c:byte()] = i - 1
end

-- tabela de 4096 pares: 12 bits -> 2 caracteres
local PAR = {}
for i = 0, 4095 do PAR[i] = PARA_CHAR[i >> 6] .. PARA_CHAR[i & 63] end

local function codificar(s)
  local n = #s
  local partes, k = {}, 0
  local byte = string.byte
  local completo = n - n % 3
  local i = 1
  while i <= completo do
    -- 12 bytes por volta quando dá (menos chamadas de string.byte)
    if i + 11 <= completo then
      local a1, b1, c1, a2, b2, c2, a3, b3, c3, a4, b4, c4 = byte(s, i, i + 11)
      local v1 = (a1 << 16) | (b1 << 8) | c1
      local v2 = (a2 << 16) | (b2 << 8) | c2
      local v3 = (a3 << 16) | (b3 << 8) | c3
      local v4 = (a4 << 16) | (b4 << 8) | c4
      k = k + 1
      partes[k] = PAR[v1 >> 12] .. PAR[v1 & 4095] .. PAR[v2 >> 12] .. PAR[v2 & 4095]
        .. PAR[v3 >> 12] .. PAR[v3 & 4095] .. PAR[v4 >> 12] .. PAR[v4 & 4095]
      i = i + 12
    else
      local a, b, c = byte(s, i, i + 2)
      local v = (a << 16) | (b << 8) | c
      k = k + 1
      partes[k] = PAR[v >> 12] .. PAR[v & 4095]
      i = i + 3
    end
  end
  local resto = n - completo
  if resto == 1 then
    local a = byte(s, n)
    local v = a << 16
    k = k + 1
    partes[k] = PARA_CHAR[v >> 18] .. PARA_CHAR[(v >> 12) & 63] .. "=="
  elseif resto == 2 then
    local a, b = byte(s, n - 1, n)
    local v = (a << 16) | (b << 8)
    k = k + 1
    partes[k] = PARA_CHAR[v >> 18] .. PARA_CHAR[(v >> 12) & 63] .. PARA_CHAR[(v >> 6) & 63] .. "="
  end
  return table.concat(partes)
end

local function decodificar(s)
  if type(s) ~= "string" then error("base64 inválido: esperava texto", 0) end
  s = s:gsub("[%s]", "")
  if #s % 4 ~= 0 then
    -- aceita sem "=" no fim
    s = s .. string.rep("=", (4 - #s % 4) % 4)
  end
  local n = #s
  local partes, k = {}, 0
  local byte, char = string.byte, string.char
  for i = 1, n, 4 do
    local c1, c2, c3, c4 = byte(s, i, i + 3)
    local v1, v2 = DE_CHAR[c1], DE_CHAR[c2]
    if v1 == nil or v2 == nil then error("base64 inválido na posição " .. i, 0) end
    if c4 == 61 then -- "="
      if c3 == 61 then
        k = k + 1
        partes[k] = char((v1 << 2) | (v2 >> 4))
      else
        local v3 = DE_CHAR[c3]
        if v3 == nil then error("base64 inválido na posição " .. (i + 2), 0) end
        local v = (v1 << 18) | (v2 << 12) | (v3 << 6)
        k = k + 1
        partes[k] = char(v >> 16, (v >> 8) & 255)
      end
      if i + 4 <= n then error("base64 inválido: '=' antes do fim", 0) end
    else
      local v3, v4 = DE_CHAR[c3], DE_CHAR[c4]
      if v3 == nil or v4 == nil then error("base64 inválido na posição " .. i, 0) end
      local v = (v1 << 18) | (v2 << 12) | (v3 << 6) | v4
      k = k + 1
      partes[k] = char(v >> 16, (v >> 8) & 255, v & 255)
    end
  end
  return table.concat(partes)
end

return { codificar = codificar, decodificar = decodificar }
