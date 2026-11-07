-- Testes da extensão Horys dentro de um Aseprite de verdade, sem interface:
--   aseprite -b --script-param ext=<pasta extension> --script tests/lua/test_handlers.lua
-- Imprime "OK <n> testes" ou "FALHA ..." (uma linha por teste que falhou) e sai com erro em falha.

local ext = app.params.ext
if not ext or ext == "" then
  -- tests/lua/test_handlers.lua -> <repo>/extension
  local aqui = debug.getinfo(1, "S").source:gsub("^@", "")
  ext = app.fs.joinPath(app.fs.filePath(app.fs.filePath(app.fs.filePath(app.fs.normalizePath(aqui)))), "extension")
end

local M = assert(loadfile(app.fs.joinPath(ext, "modulos.lua")))(ext, "0.1.0-teste")
local J, B64, S, L, A, H, C = M.jsonx, M.base64, M.sha256, M.logica, M.arquivos, M.handlers, M.cliente

local tmp = app.fs.joinPath(app.fs.tempPath, "horys-teste-" .. os.time() .. "-" .. math.random(1000000))
app.fs.makeAllDirectories(tmp)

local total, falhas = 0, {}

local function fecharTudo()
  while app.sprite do app.sprite:close() end
end

local function teste(nome, fn)
  fecharTudo()
  total = total + 1
  local ok, erro = xpcall(fn, function(e) return tostring(e) .. "\n" .. debug.traceback("", 2) end)
  if not ok then falhas[#falhas + 1] = nome .. ": " .. erro end
end

local function igual(atual, esperado, oque)
  if atual ~= esperado then
    error((oque or "valor") .. ": esperava " .. tostring(esperado) .. ", veio " .. tostring(atual), 2)
  end
end

local function verdade(v, oque)
  if not v then error((oque or "condição") .. " falhou", 2) end
end

-- executa pelo despacho (como o servidor faria) e exige sucesso
local function cmd(nome, args)
  local ok, res = H.executar(nome, args or {})
  if not ok then error("comando " .. nome .. " falhou: " .. tostring(res), 2) end
  return res
end

local function cmdFalha(nome, args, padrao)
  local ok, res = H.executar(nome, args or {})
  if ok then error("comando " .. nome .. " deveria falhar", 2) end
  if padrao and not tostring(res):find(padrao) then
    error("erro inesperado de " .. nome .. ": " .. tostring(res), 2)
  end
  return res
end

-- pixels RGBA como string a partir de uma lista {r,g,b,a}
local function px(lista)
  local t = {}
  for i, c in ipairs(lista) do t[i] = string.char(c[1], c[2], c[3], c[4]) end
  return table.concat(t)
end

-- pixel (x,y) de um resultado de `ler`
local function pixel(res, x, y)
  local bytes = B64.decodificar(res.rgba)
  local k = ((y - res.y) * res.w + (x - res.x)) * 4 + 1
  return { bytes:byte(k, k + 3) }
end

local function cor(c) return string.format("%d,%d,%d,%d", c[1], c[2], c[3], c[4]) end

local function nomesCamadas(st)
  local t = {}
  for i, c in ipairs(st.sprite.camadas) do t[i] = c.nome end
  return table.concat(t, ",")
end


-- ---------------------------------------------------------------------------
-- Base64, SHA-256, HMAC, JSON
-- ---------------------------------------------------------------------------
teste("base64 vetores do RFC 4648", function()
  local v = { [""] = "", f = "Zg==", fo = "Zm8=", foo = "Zm9v", foob = "Zm9vYg==", fooba = "Zm9vYmE=", foobar = "Zm9vYmFy" }
  for claro, cod in pairs(v) do
    igual(B64.codificar(claro), cod, "codificar '" .. claro .. "'")
    igual(B64.decodificar(cod), claro, "decodificar '" .. cod .. "'")
  end
end)

teste("base64 ida e volta com bytes aleatórios", function()
  for n = 0, 40 do
    local t = {}
    for i = 1, n do t[i] = string.char(math.random(0, 255)) end
    local s = table.concat(t)
    igual(B64.decodificar(B64.codificar(s)), s, "tamanho " .. n)
  end
  local t = {}
  for i = 1, 100003 do t[i] = string.char(math.random(0, 255)) end
  local grande = table.concat(t)
  igual(B64.decodificar(B64.codificar(grande)) == grande, true, "100 KB")
  local ok = pcall(B64.decodificar, "ab$d")
  igual(ok, false, "base64 inválido dá erro")
end)

teste("sha256 de 'abc' e da string vazia", function()
  igual(S.sha256Hex("abc"), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
  igual(S.sha256Hex(""), "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
end)

teste("HMAC-SHA256: RFC 4231 casos 1 e 2", function()
  igual(S.hmacHex(string.rep("\x0b", 20), "Hi There"),
    "b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7", "caso 1")
  igual(S.hmacHex("Jefe", "what do ya want for nothing?"),
    "5bdcc146bf60754e6a042426089575c75a003f089d2739839dec58b964ec3843", "caso 2")
  -- caso 6: chave maior que o bloco (131 bytes)
  igual(S.hmacHex(string.rep("\xaa", 131), "Test Using Larger Than Block-Size Key - Hash Key First"),
    "60e431591ee0b67f0d8a26aacbf5b77f8e0bc6213728c5140546040f0ee37f54", "caso 6")
  igual(S.iguais("abc", "abc"), true)
  igual(S.iguais("abc", "abd"), false)
  igual(S.iguais("abc", nil), false)
end)

teste("JSON: objetos vazios, listas, null e escapes", function()
  igual(J.codificar({}), "{}")
  igual(J.codificar(J.lista({})), "[]")
  igual(J.codificar({ a = J.null }), '{"a":null}')
  igual(J.codificar({ 1, 2, 3 }), "[1,2,3]")
  igual(J.codificar({ b = 1.5, a = true, c = "x\"\n\\" }), '{"a":true,"b":1.5,"c":"x\\"\\n\\\\"}')
  igual(J.codificar({ n = 3.0 }), '{"n":3}')
  igual(J.codificar("ação"), '"ação"')
  local d = J.decodificar('{"id":17,"cmd":"x","args":{"l":[1,2],"f":0.5,"s":"ã","o":{}}}')
  igual(math.type(d.id), "integer")
  igual(d.args.l[2], 2)
  igual(d.args.f, 0.5)
  igual(d.args.s, "ã")
  igual(type(d.args.o), "table")
  igual(pcall(J.decodificar, "{oops"), false, "JSON inválido dá erro")
end)

-- ---------------------------------------------------------------------------
-- Sprites, camadas, quadros, tags, paleta
-- ---------------------------------------------------------------------------
teste("status sem sprite", function()
  local st = cmd("status")
  igual(st.sprite, J.null, "sprite")
  verdade(st.versao_aseprite:find("1%."), "versão do Aseprite")
  igual(#st.sprites, 0)
  verdade(J.codificar(st):find('"sprite":null', 1, true), "sprite:null no JSON")
end)

teste("sprite_novo", function()
  local st = cmd("sprite_novo", { largura = 8, altura = 6, nome = "teste" })
  local sp = st.sprite
  igual(sp.largura, 8); igual(sp.altura, 6); igual(sp.modo, "rgb")
  igual(#sp.camadas, 1); igual(sp.camadas[1].nome, "desenho"); igual(sp.camadas[1].indice, 0)
  igual(sp.camadas[1].visivel, true); igual(sp.camadas[1].opacidade, 255)
  igual(#sp.quadros, 1); igual(sp.quadros[1].ms, 100)
  igual(#sp.tags, 0); igual(sp.camada_ativa, "desenho"); igual(sp.quadro_ativo, 0)
  igual(app.sprite.layers[1].isBackground, false, "fundo transparente")
  igual(#st.sprites, 1); igual(st.sprites[1].indice, 0)
  verdade(J.codificar(st):find('"tags":[]', 1, true), "tags vazia vira []")
  cmdFalha("sprite_novo", { largura = 0, altura = 4 }, "tamanho")
  cmdFalha("sprite_novo", { altura = 4 }, "largura")
end)

teste("camada: criar, renomear, ordem, propriedades, ativar, remover", function()
  cmd("sprite_novo", { largura = 4, altura = 4 })
  local st = cmd("camada", { acao = "criar", nome = "contorno" })
  igual(nomesCamadas(st), "desenho,contorno")
  igual(st.sprite.camada_ativa, "contorno")
  st = cmd("camada", { acao = "criar", nome = "fundo", abaixo_de = "desenho" })
  igual(nomesCamadas(st), "fundo,desenho,contorno", "abaixo_de")
  st = cmd("camada", { acao = "criar", nome = "meio", acima_de = "desenho" })
  igual(nomesCamadas(st), "fundo,desenho,meio,contorno", "acima_de")
  cmdFalha("camada", { acao = "criar", nome = "meio" }, "já existe")
  st = cmd("camada", { acao = "renomear", nome = "meio", novo = "sombra" })
  igual(nomesCamadas(st), "fundo,desenho,sombra,contorno")
  st = cmd("camada", { acao = "ordem", nomes = { "contorno", "fundo", "sombra", "desenho" } })
  igual(nomesCamadas(st), "contorno,fundo,sombra,desenho", "ordem")
  igual(st.sprite.camadas[4].indice, 3)
  st = cmd("camada", { acao = "propriedades", nome = "sombra", visivel = false, opacidade = 128 })
  igual(st.sprite.camadas[3].visivel, false); igual(st.sprite.camadas[3].opacidade, 128)
  cmdFalha("camada", { acao = "propriedades", nome = "sombra", opacidade = 300 }, "0 a 255")
  st = cmd("camada", { acao = "ativar", nome = "fundo" })
  igual(st.sprite.camada_ativa, "fundo")
  st = cmd("camada", { acao = "remover", nome = "contorno" })
  igual(nomesCamadas(st), "fundo,sombra,desenho")
  cmdFalha("camada", { acao = "remover", nome = "nada" }, "não existe")
  cmdFalha("camada", { acao = "voar", nome = "fundo" }, "desconhecida")
end)

teste("camada: cada mudança é um passo de desfazer", function()
  cmd("sprite_novo", { largura = 4, altura = 4 })
  cmd("camada", { acao = "criar", nome = "b" })
  cmd("camada", { acao = "criar", nome = "c" })
  cmd("camada", { acao = "ordem", nomes = { "c", "b", "desenho" } })
  igual(nomesCamadas(cmd("status")), "c,b,desenho")
  cmd("desfazer", { passos = 1 })
  igual(nomesCamadas(cmd("status")), "desenho,b,c", "desfez a ordem num passo só")
  cmd("refazer", {})
  igual(nomesCamadas(cmd("status")), "c,b,desenho", "refez")
end)

teste("quadro: criar, duração, garantir, ativar, remover", function()
  cmd("sprite_novo", { largura = 2, altura = 2 })
  local r, g = { 255, 0, 0, 255 }, { 0, 255, 0, 255 }
  cmd("escrever", { camada = "desenho", quadro = 0, x = 0, y = 0, w = 1, h = 1, rgba = B64.codificar(px({ r })) })
  local st = cmd("quadro", { acao = "criar", copiar = true })
  igual(#st.sprite.quadros, 2); igual(st.sprite.quadro_ativo, 1)
  igual(cor(pixel(cmd("ler", { camada = "desenho", quadro = 1 }), 0, 0)), cor(r), "cópia do quadro 0")
  st = cmd("quadro", { acao = "criar", depois_de = 0, copiar = false })
  igual(#st.sprite.quadros, 3); igual(st.sprite.quadro_ativo, 1)
  igual(cor(pixel(cmd("ler", { camada = "desenho", quadro = 1 }), 0, 0)), "0,0,0,0", "quadro vazio no meio")
  igual(cor(pixel(cmd("ler", { camada = "desenho", quadro = 2 }), 0, 0)), cor(r), "cópia foi para o fim")
  cmd("escrever", { camada = "desenho", quadro = 2, x = 1, y = 1, w = 1, h = 1, rgba = B64.codificar(px({ g })) })
  st = cmd("quadro", { acao = "duracao", indice = 1, ms = 250 })
  igual(st.sprite.quadros[2].ms, 250); igual(st.sprite.quadros[1].ms, 100)
  st = cmd("quadro", { acao = "duracao", todos = true, ms = 80 })
  for i = 1, 3 do igual(st.sprite.quadros[i].ms, 80) end
  st = cmd("quadro", { acao = "garantir", total = 6 })
  igual(#st.sprite.quadros, 6)
  st = cmd("quadro", { acao = "garantir", total = 2 })
  igual(#st.sprite.quadros, 6, "garantir não remove")
  st = cmd("quadro", { acao = "ativar", indice = 4 })
  igual(st.sprite.quadro_ativo, 4)
  st = cmd("quadro", { acao = "remover", indice = 1 })
  igual(#st.sprite.quadros, 5)
  igual(cor(pixel(cmd("ler", { camada = "desenho", quadro = 1 }), 1, 1)), cor(g), "quadros andaram")
  cmdFalha("quadro", { acao = "remover", indice = 9 }, "não existe")
  cmdFalha("quadro", { acao = "duracao", indice = 0, ms = 0 }, "ms")
end)

teste("tag: criar e remover", function()
  cmd("sprite_novo", { largura = 2, altura = 2 })
  cmd("quadro", { acao = "garantir", total = 4 })
  local st = cmd("tag", { acao = "criar", nome = "andar", de = 1, ate = 3 })
  igual(#st.sprite.tags, 1)
  igual(st.sprite.tags[1].nome, "andar"); igual(st.sprite.tags[1].de, 1); igual(st.sprite.tags[1].ate, 3)
  cmdFalha("tag", { acao = "criar", nome = "andar", de = 0, ate = 0 }, "já existe")
  cmdFalha("tag", { acao = "criar", nome = "x", de = 2, ate = 1 }, "antes")
  cmdFalha("tag", { acao = "criar", nome = "x", de = 0, ate = 9 }, "não existe")
  st = cmd("tag", { acao = "remover", nome = "andar" })
  igual(#st.sprite.tags, 0)
end)

teste("paleta: definir e ler", function()
  cmd("sprite_novo", { largura = 2, altura = 2 })
  local r = cmd("paleta", { acao = "definir", cores = { "#000000", "#FF0000", "#00ff0080" } })
  igual(#r.cores, 3)
  igual(r.cores[1], "#000000"); igual(r.cores[2], "#ff0000"); igual(r.cores[3], "#00ff0080")
  r = cmd("paleta", { acao = "ler" })
  igual(#r.cores, 3)
  cmdFalha("paleta", { acao = "definir", cores = { "vermelho" } }, "cor inválida")
end)

-- ---------------------------------------------------------------------------
-- Pixels
-- ---------------------------------------------------------------------------
teste("escrever + ler: ida e volta", function()
  cmd("sprite_novo", { largura = 5, altura = 4 })
  local t = {}
  for i = 1, 3 * 2 do t[i] = { i * 10, 255 - i, i * 3, (i % 2 == 0) and 255 or 77 } end
  local r = cmd("escrever", { camada = "desenho", quadro = 0, x = 1, y = 1, w = 3, h = 2,
    rgba = B64.codificar(px(t)), mascara = B64.codificar(string.rep("\1", 6)) })
  igual(r.escritos, 6)
  local lido = cmd("ler", { camada = "desenho", quadro = 0, x = 1, y = 1, w = 3, h = 2 })
  igual(lido.w, 3); igual(lido.h, 2)
  igual(B64.decodificar(lido.rgba), px(t), "mesmos bytes")
  local tudo = cmd("ler", { camada = "desenho", quadro = 0 })
  igual(tudo.w, 5); igual(tudo.h, 4)
  igual(#B64.decodificar(tudo.rgba), 5 * 4 * 4)
  igual(cor(pixel(tudo, 0, 0)), "0,0,0,0", "fora da região")
  igual(cor(pixel(tudo, 3, 2)), cor(t[6]), "canto")
  -- a célula cobre o sprite inteiro
  local cel = app.sprite.layers[1]:cel(1)
  igual(cel.bounds.width, 5); igual(cel.bounds.height, 4)
end)

teste("escrever: máscara parcial e pixel transparente escrito", function()
  cmd("sprite_novo", { largura = 3, altura = 1 })
  local verm = { 200, 10, 10, 255 }
  cmd("escrever", { camada = "desenho", quadro = 0, x = 0, y = 0, w = 3, h = 1,
    rgba = B64.codificar(px({ verm, verm, verm })), mascara = B64.codificar("\1\1\1") })
  local azul, transp = { 0, 0, 255, 255 }, { 0, 0, 0, 0 }
  local r = cmd("escrever", { camada = "desenho", quadro = 0, x = 0, y = 0, w = 3, h = 1,
    rgba = B64.codificar(px({ azul, azul, transp })), mascara = B64.codificar("\0\1\1") })
  igual(r.escritos, 2)
  local lido = cmd("ler", { camada = "desenho", quadro = 0 })
  igual(cor(pixel(lido, 0, 0)), cor(verm), "máscara 0 não toca")
  igual(cor(pixel(lido, 1, 1 - 1)), cor(azul), "máscara 1 escreve")
  igual(cor(pixel(lido, 2, 0)), "0,0,0,0", "transparente foi escrito")
end)

teste("escrever: fora do sprite e tamanhos errados", function()
  cmd("sprite_novo", { largura = 2, altura = 2 })
  local c = { 1, 2, 3, 255 }
  local r = cmd("escrever", { camada = "desenho", quadro = 0, x = -1, y = 1, w = 2, h = 2,
    rgba = B64.codificar(px({ c, c, c, c })) })
  igual(r.escritos, 1, "só o pixel dentro do sprite")
  igual(cor(pixel(cmd("ler", { camada = "desenho", quadro = 0 }), 0, 1)), cor(c))
  cmdFalha("escrever", { camada = "desenho", quadro = 0, x = 0, y = 0, w = 2, h = 2, rgba = B64.codificar("abc") }, "bytes")
  cmdFalha("escrever", { camada = "desenho", quadro = 0, x = 0, y = 0, w = 1, h = 1,
    rgba = B64.codificar(px({ c })), mascara = B64.codificar("\1\1") }, "mascara")
  cmdFalha("escrever", { camada = "nada", quadro = 0, x = 0, y = 0, w = 1, h = 1, rgba = B64.codificar(px({ c })) }, "não existe")
  cmdFalha("escrever", { camada = "desenho", quadro = 3, x = 0, y = 0, w = 1, h = 1, rgba = B64.codificar(px({ c })) }, "quadro 3")
end)

teste("escrever: célula menor que o sprite é expandida sem mover o desenho", function()
  cmd("sprite_novo", { largura = 6, altura = 6 })
  local s = app.sprite
  local pequena = Image(2, 2, ColorMode.RGB)
  pequena:clear(app.pixelColor.rgba(9, 8, 7, 255))
  s:newCel(s.layers[1], 1, pequena, Point(3, 2))
  local c = { 50, 60, 70, 255 }
  cmd("escrever", { camada = "desenho", quadro = 0, x = 0, y = 0, w = 1, h = 1, rgba = B64.codificar(px({ c })) })
  local cel = s.layers[1]:cel(1)
  igual(cel.bounds.x, 0); igual(cel.bounds.y, 0); igual(cel.bounds.width, 6); igual(cel.bounds.height, 6)
  local lido = cmd("ler", { camada = "desenho", quadro = 0 })
  igual(cor(pixel(lido, 0, 0)), cor(c), "pixel novo")
  igual(cor(pixel(lido, 3, 2)), "9,8,7,255", "desenho antigo no lugar")
  igual(cor(pixel(lido, 4, 3)), "9,8,7,255", "desenho antigo no lugar (canto)")
  igual(cor(pixel(lido, 5, 3)), "0,0,0,0", "fora da célula antiga")
  -- célula que sai do sprite: o que está fora é preservado
  local larga = Image(3, 1, ColorMode.RGB)
  larga:clear(app.pixelColor.rgba(1, 1, 1, 255))
  s:newCel(s.layers[1], 1, larga, Point(-1, 5))
  cmd("escrever", { camada = "desenho", quadro = 0, x = 5, y = 0, w = 1, h = 1, rgba = B64.codificar(px({ c })) })
  cel = s.layers[1]:cel(1)
  igual(cel.bounds.x, -1, "manteve o pedaço fora do sprite")
  igual(cel.bounds.width, 7)
  lido = cmd("ler", { camada = "desenho", quadro = 0 })
  igual(cor(pixel(lido, 0, 5)), "1,1,1,255")
  igual(cor(pixel(lido, 5, 0)), cor(c))
end)

teste("ler: camada sem célula é toda transparente; retângulo recortado", function()
  cmd("sprite_novo", { largura = 4, altura = 4 })
  cmd("camada", { acao = "criar", nome = "vazia" })
  local lido = cmd("ler", { camada = "vazia", quadro = 0 })
  igual(B64.decodificar(lido.rgba), string.rep("\0", 4 * 4 * 4))
  lido = cmd("ler", { camada = "vazia", quadro = 0, x = 2, y = 3, w = 10, h = 10 })
  igual(lido.w, 2); igual(lido.h, 1); igual(lido.x, 2); igual(lido.y, 3)
  cmdFalha("ler", { quadro = 0, x = 9, y = 9, w = 2, h = 2 }, "fora do sprite")
end)

teste("ler composto: camadas visíveis, de cima para baixo", function()
  cmd("sprite_novo", { largura = 3, altura = 1 })
  local azul, verm, verde = { 0, 0, 255, 255 }, { 255, 0, 0, 255 }, { 0, 255, 0, 255 }
  cmd("escrever", { camada = "desenho", quadro = 0, x = 0, y = 0, w = 3, h = 1, rgba = B64.codificar(px({ azul, azul, azul })) })
  cmd("camada", { acao = "criar", nome = "topo" })
  cmd("escrever", { camada = "topo", quadro = 0, x = 1, y = 0, w = 1, h = 1, rgba = B64.codificar(px({ verm })) })
  cmd("camada", { acao = "criar", nome = "oculta" })
  cmd("escrever", { camada = "oculta", quadro = 0, x = 2, y = 0, w = 1, h = 1, rgba = B64.codificar(px({ verde })) })
  cmd("camada", { acao = "propriedades", nome = "oculta", visivel = false })
  local lido = cmd("ler", { quadro = 0 })
  igual(cor(pixel(lido, 0, 0)), cor(azul))
  igual(cor(pixel(lido, 1, 0)), cor(verm), "camada de cima por cima")
  igual(cor(pixel(lido, 2, 0)), cor(azul), "camada oculta não entra")
  lido = cmd("ler", { quadro = 0, x = 1, y = 0, w = 1, h = 1 })
  igual(lido.w, 1); igual(cor(pixel(lido, 1, 0)), cor(verm), "recorte do composto")
end)

teste("sprite indexado: escrever e ler pela paleta", function()
  local s = Sprite(2, 1, ColorMode.INDEXED)
  local pal = Palette(3)
  pal:setColor(0, Color{ r = 0, g = 0, b = 0, a = 0 })
  pal:setColor(1, Color{ r = 255, g = 0, b = 0 })
  pal:setColor(2, Color{ r = 0, g = 0, b = 255 })
  s:setPalette(pal)
  cmd("escrever", { camada = s.layers[1].name, quadro = 0, x = 0, y = 0, w = 2, h = 1,
    rgba = B64.codificar(px({ { 250, 5, 5, 255 }, { 0, 0, 0, 0 } })) })
  local lido = cmd("ler", { camada = 0, quadro = 0 })
  igual(cor(pixel(lido, 0, 0)), "255,0,0,255", "cor mais próxima da paleta")
  igual(cor(pixel(lido, 1, 0)), "0,0,0,0", "transparente")
end)

teste("limpar_camada: um quadro e todos", function()
  cmd("sprite_novo", { largura = 2, altura = 2 })
  local c = { 9, 9, 9, 255 }
  cmd("escrever", { camada = "desenho", quadro = 0, x = 0, y = 0, w = 1, h = 1, rgba = B64.codificar(px({ c })) })
  cmd("quadro", { acao = "criar", copiar = true })
  cmd("quadro", { acao = "criar", copiar = true })
  local r = cmd("limpar_camada", { camada = "desenho", quadro = 1 })
  igual(J.codificar(r), "{}", "data {}")
  igual(cor(pixel(cmd("ler", { camada = "desenho", quadro = 1 }), 0, 0)), "0,0,0,0")
  igual(cor(pixel(cmd("ler", { camada = "desenho", quadro = 2 }), 0, 0)), cor(c), "outro quadro intacto")
  cmd("limpar_camada", { camada = "desenho", todos = true })
  for q = 0, 2 do igual(cor(pixel(cmd("ler", { camada = "desenho", quadro = q }), 0, 0)), "0,0,0,0") end
  cmd("desfazer", {})
  for q = 0, 2, 2 do igual(cor(pixel(cmd("ler", { camada = "desenho", quadro = q }), 0, 0)), cor(c), "desfez o limpar todos") end
end)

teste("desfazer e refazer: escrever é um passo só", function()
  cmd("sprite_novo", { largura = 3, altura = 3 })
  local a, b = { 10, 20, 30, 255 }, { 40, 50, 60, 255 }
  cmd("escrever", { camada = "desenho", quadro = 0, x = 0, y = 0, w = 1, h = 1, rgba = B64.codificar(px({ a })) })
  cmd("escrever", { camada = "desenho", quadro = 0, x = 0, y = 0, w = 3, h = 3, rgba = B64.codificar(px({ b, b, b, b, b, b, b, b, b })) })
  igual(cor(pixel(cmd("ler", { camada = "desenho", quadro = 0 }), 2, 2)), cor(b))
  igual(J.codificar(cmd("desfazer", { passos = 1 })), "{}")
  local lido = cmd("ler", { camada = "desenho", quadro = 0 })
  igual(cor(pixel(lido, 0, 0)), cor(a), "voltou ao primeiro escrever")
  igual(cor(pixel(lido, 2, 2)), "0,0,0,0")
  cmd("refazer", { passos = 1 })
  igual(cor(pixel(cmd("ler", { camada = "desenho", quadro = 0 }), 2, 2)), cor(b), "refez")
  cmd("desfazer", { passos = 2 })
  igual(cor(pixel(cmd("ler", { camada = "desenho", quadro = 0 }), 0, 0)), "0,0,0,0", "dois passos")
end)

teste("salvar cópia, salvar como, abrir e selecionar_sprite", function()
  cmd("sprite_novo", { largura = 4, altura = 3 })
  local c = { 1, 2, 3, 255 }
  cmd("escrever", { camada = "desenho", quadro = 0, x = 2, y = 1, w = 1, h = 1, rgba = B64.codificar(px({ c })) })
  local original = app.sprite.filename
  cmdFalha("salvar", { copia = false }, "ainda não tem arquivo")
  cmdFalha("salvar", { copia = true }, "informe 'arquivo'")
  local copia = app.fs.joinPath(app.fs.joinPath(tmp, "sub"), "copia.aseprite")
  local r = cmd("salvar", { arquivo = copia, copia = true })
  igual(r.arquivo, copia)
  verdade(app.fs.isFile(copia), "arquivo da cópia existe")
  igual(app.sprite.filename, original, "cópia não muda o nome do sprite")
  local st = cmd("abrir", { arquivo = copia })
  igual(#st.sprites, 2)
  igual(app.fs.fileName(st.sprite.arquivo), "copia.aseprite")
  igual(cor(pixel(cmd("ler", { camada = "desenho", quadro = 0 }), 2, 1)), cor(c), "pixels gravados")
  -- os índices seguem a lista "sprites" do status (o Aseprite lista o mais recente primeiro)
  local idxOriginal
  for _, it in ipairs(st.sprites) do if it.arquivo == original then idxOriginal = it.indice end end
  verdade(idxOriginal ~= nil, "sprite original na lista")
  st = cmd("selecionar_sprite", { indice = idxOriginal })
  igual(st.sprite.arquivo, original)
  st = cmd("selecionar_sprite", { arquivo = copia })
  igual(app.fs.fileName(st.sprite.arquivo), "copia.aseprite")
  cmdFalha("selecionar_sprite", { indice = 5 }, "não existe")
  cmdFalha("abrir", { arquivo = app.fs.joinPath(tmp, "nao-existe.aseprite") }, "não encontrado")
  -- salvar como: o sprite passa a ter o arquivo novo; depois salvar sem arquivo usa ele
  cmd("selecionar_sprite", { indice = idxOriginal })
  local como = app.fs.joinPath(tmp, "como.aseprite")
  cmd("salvar", { arquivo = como, copia = false })
  igual(app.sprite.filename, como)
  r = cmd("salvar", {})
  igual(r.arquivo, como)
  -- PNG
  local png = app.fs.joinPath(tmp, "folha.png")
  cmd("salvar", { arquivo = png, copia = true })
  verdade(app.fs.isFile(png), "png gravado")
end)

teste("selecao", function()
  cmd("sprite_novo", { largura = 8, altura = 8 })
  local r = cmd("selecao")
  igual(r.vazia, true)
  app.sprite.selection = Selection(Rectangle(1, 2, 3, 4))
  r = cmd("selecao")
  igual(r.vazia, false); igual(r.x, 1); igual(r.y, 2); igual(r.w, 3); igual(r.h, 4)
end)

teste("despacho: comando desconhecido e erros sem caminho de arquivo", function()
  local ok, erro = H.executar("voar", {})
  igual(ok, false); verdade(erro:find("desconhecido"), "mensagem")
  ok, erro = H.executar("escrever", { camada = "x" })
  igual(ok, false)
  verdade(not erro:find("%.lua:%d+"), "sem caminho de arquivo: " .. erro)
  verdade(erro:find("nenhum sprite"), "mensagem em português: " .. erro)
end)

-- ---------------------------------------------------------------------------
-- Painel (ui_*) com uma interface falsa
-- ---------------------------------------------------------------------------
teste("ui_*: validam e chamam o painel", function()
  local chamadas = {}
  H.ui = {
    perguntar = function(a) chamadas[#chamadas + 1] = { "perguntar", a } end,
    aprovar = function(a) chamadas[#chamadas + 1] = { "aprovar", a } end,
    progresso = function(a) chamadas[#chamadas + 1] = { "progresso", a } end,
    fechar = function(id) chamadas[#chamadas + 1] = { "fechar", id } end,
  }
  local ok, err = pcall(function()
    local r = cmd("ui_perguntar", { id = "p1", titulo = "Briefing", perguntas = {
      { pergunta = "Qual a pose?", cabecalho = "Pose", multipla = false,
        opcoes = { { rotulo = "Frente", descricao = "vista frontal" }, { rotulo = "Lado" } } } } })
    igual(r.mostrado, true)
    igual(chamadas[1][1], "perguntar")
    igual(chamadas[1][2].perguntas[1].opcoes[2].descricao, "")
    cmdFalha("ui_perguntar", { id = "p2", perguntas = {} }, "ao menos uma")
    cmdFalha("ui_perguntar", { perguntas = { { pergunta = "x" } } }, "id")
    r = cmd("ui_aprovar", { id = "a1", titulo = "Silhueta", texto = "Aprova?" })
    igual(r.mostrado, true); igual(chamadas[2][2].imagem, nil)
    cmdFalha("ui_aprovar", { titulo = "x" }, "id")
    cmd("ui_progresso", { pedido = "7", etapa = "limpeza", texto = "contorno", nota = 61 })
    igual(chamadas[3][2].nota, 61)
    cmd("ui_fechar", { id = "p1" })
    igual(chamadas[4][2], "p1")
  end)
  H.ui = nil
  if not ok then error(err, 0) end
  cmdFalha("ui_progresso", { texto = "x" }, "painel")
end)

-- ---------------------------------------------------------------------------
-- Lógica das janelas
-- ---------------------------------------------------------------------------
teste("logica: respostas das perguntas", function()
  local ps = L.normalizarPerguntas({ id = 1, perguntas = {
    { pergunta = "Pose?", cabecalho = "Pose", opcoes = { { rotulo = "Frente" }, { rotulo = "Lado" } } },
    { pergunta = "Cores?", cabecalho = "Cores", multipla = true,
      opcoes = { { rotulo = "Quentes" }, { rotulo = "Frias" }, { rotulo = "Neutras" } } },
    { pergunta = "Nome?", opcoes = {} },
  } })
  local r, faltando = L.montarRespostas(ps, {
    { selecionados = { 2 } },
    { selecionados = { 3, 1 } },
    { outro = "  Bjorn " },
  })
  igual(#faltando, 0)
  igual(r["Pose?"], "Lado"); igual(r["Cores?"], "Quentes, Neutras"); igual(r["Nome?"], "Bjorn")
  -- "Outro" vence a opção marcada
  r = L.montarRespostas(ps, { { selecionados = { 1 }, outro = "De costas" }, { selecionados = { 1 } }, { outro = "x" } })
  igual(r["Pose?"], "De costas")
  r, faltando = L.montarRespostas(ps, { {}, { selecionados = {} }, { outro = " " } })
  igual(#faltando, 3); igual(faltando[1], "Pose"); igual(faltando[3], "Nome?")
  verdade(J.codificar(L.montarRespostas(ps, {})) == "{}", "respostas vazias viram {}")
end)

teste("logica: pedido, estilo, estados, tamanho, linhas, token", function()
  local e = L.lerEstados(" idle, andar;atacar ,, idle ")
  igual(table.concat(e, "|"), "idle|andar|atacar")
  igual(J.codificar(L.lerEstados("")), "[]")
  igual(L.normalizarTamanho("32"), "32x32"); igual(L.normalizarTamanho(" 32 x 48 "), "32x48")
  igual(L.normalizarTamanho(""), nil)
  igual(select(2, L.normalizarTamanho("grande")) ~= nil, true)
  local p, erro = L.montarPedido({ descricao = " um viking ", referencia = "", tipo = "personagem",
    estilo = "horys-pixel-liso", motor = "claude", estados = "idle, andar", tamanho = "" })
  igual(erro, nil)
  igual(p.descricao, "um viking"); igual(p.referencia, nil); igual(p.tamanho, nil); igual(#p.estados, 2)
  local semRef = L.montarPedido({ descricao = "baú", referencia = "C:/pasta/", tipo = "prop",
    estilo = "exemplo", motor = "codex", estados = "idle", tamanho = "" })
  igual(semRef.referencia, nil, "Dialog:file vazio retorna o diretório com separador final")
  igual(J.codificar(p), '{"descricao":"um viking","estado' .. 's":["idle","andar"],"estilo":"horys-pixel-liso","motor":"claude","tipo":"personagem"}')
  p = L.montarPedido({ descricao = "x", referencia = "C:/ref.png", tipo = "t", estilo = "e", motor = "codex", estados = "", tamanho = "24" })
  igual(p.referencia, "C:/ref.png"); igual(p.tamanho, "24x24")
  igual(select(2, L.montarPedido({ descricao = "", tipo = "t", estilo = "e", motor = "m" })), "Descreva o que criar.")
  local est = L.montarEstilo({ nome = "meu", imagens = { "a.png", " a.png", "b.png" }, motor = "codex" })
  igual(#est.imagens, 2)
  igual(select(2, L.montarEstilo({ nome = "meu", imagens = {}, motor = "codex" })), "Adicione ao menos uma imagem.")
  verdade(L.ehImagem("x/Y.PNG") and not L.ehImagem("a.txt"), "ehImagem")
  local linhas = L.quebrarLinhas("uma frase bem comprida para quebrar\n\nfim", 12)
  igual(linhas[1], "uma frase"); igual(linhas[2], "bem comprida"); igual(linhas[#linhas], "fim")
  igual(L.limparToken(" ab12\r\n cd \n"), "ab12cd")
  local env = { USERPROFILE = "C:\\Users\\x" }
  igual(L.caminhoToken(function(k) return env[k] end, function(a, b) return a .. "/" .. b end), "C:\\Users\\x/.horys-pixel/token")
  env = { HOME = "/home/x" }
  igual(L.caminhoToken(function(k) return env[k] end, function(a, b) return a .. "/" .. b end), "/home/x/.horys-pixel/token")
  igual(L.linhaProgresso({ pedido = 3, etapa = "portão", texto = "medindo", nota = "61%" }), "Pedido 3 · portão: medindo (nota 61%)")
end)

teste("arquivos: PNG em base64 vira Image", function()
  local img = Image(3, 2, ColorMode.RGB)
  img:clear(app.pixelColor.rgba(0, 0, 0, 0))
  img:drawPixel(1, 1, app.pixelColor.rgba(10, 200, 30, 255))
  local caminho = app.fs.joinPath(tmp, "aprovar.png")
  img:saveAs(caminho)
  local b64 = B64.codificar(A.lerArquivo(caminho, true))
  local volta = A.imagemDePngBase64(b64, "a1")
  igual(volta.width, 3); igual(volta.height, 2)
  local v = volta:getPixel(1, 1)
  igual(app.pixelColor.rgbaG(v), 200)
  igual(pcall(A.imagemDePngBase64, B64.codificar("não é png")), false, "recusa o que não é PNG")
  verdade(A.caminhoToken():find("%.horys%-pixel"), "caminho do token")
end)

-- ---------------------------------------------------------------------------
-- Cliente: aperto de mão e pedidos (sem WebSocket)
-- ---------------------------------------------------------------------------
local function novoCliente(token)
  local saida, fechado = {}, {}
  local c = C.novo({
    enviar = function(t) saida[#saida + 1] = J.decodificar(t); saida[#saida].bruto = t end,
    fechar = function(m) fechado[#fechado + 1] = m end,
    token = function() return token end,
    handlers = H,
    versao = "0.1.0",
    nonce = function() return "c0ffee00c0ffee00c0ffee00c0ffee00" end,
  })
  return c, saida, fechado
end

teste("cliente: desafio, prova dos dois lados, listas e pedidos", function()
  local token = "0123456789abcdef0123456789abcdef0123456789abcdef"
  local c, saida, fechado = novoCliente(token)
  c:aoAbrir()
  -- pedido antes de autenticar: ignorado
  c:aoTexto('{"t":"req","id":1,"cmd":"status","args":{}}')
  igual(#saida, 0, "nada antes de autenticar")
  c:aoTexto('{"t":"desafio","nonce":"00112233445566778899aabbccddeeff","protocolo":1}')
  igual(#saida, 1)
  local ola = saida[1]
  igual(ola.t, "ola"); igual(ola.papel, "aseprite"); igual(ola.versao, "0.1.0")
  igual(ola.nonce, "c0ffee00c0ffee00c0ffee00c0ffee00")
  igual(ola.prova, S.hmacHex(token, "00112233445566778899aabbccddeeff"))
  igual(c.autenticado, false)
  c:aoTexto(J.codificar({ t = "bem_vindo", prova = S.hmacHex(token, ola.nonce), versao = "0.1",
    estilos = { "horys-pixel-liso" }, tipos = { "personagem", "tile" }, motores = { "claude", "codex" } }))
  igual(c.autenticado, true); igual(c.estado, "conectado")
  igual(#c.tipos, 2); igual(c.estilos[1], "horys-pixel-liso"); igual(c.motores[2], "codex")
  c:aoTexto('{"t":"req","id":17,"cmd":"status","args":{}}')
  local res = saida[#saida]
  igual(res.t, "res"); igual(res.id, 17); igual(res.ok, true)
  verdade(res.bruto:find('"sprite":null', 1, true), "data.sprite null")
  c:aoTexto('{"t":"req","id":18,"cmd":"voar"}')
  res = saida[#saida]
  igual(res.id, 18); igual(res.ok, false); verdade(res.erro:find("desconhecido"), "erro")
  c:aoTexto('{"t":"req","id":19,"cmd":"limpar_camada","args":{"camada":"x","quadro":0}}')
  igual(saida[#saida].ok, false)
  c:aoTexto('{"t":"config","tipos":["prop"]}')
  igual(#c.tipos, 1); igual(c.tipos[1], "prop"); igual(#c.estilos, 1, "o resto fica")
  igual(c:evento("revisar_sprite", { arquivo = "a.aseprite" }), true)
  local evt = saida[#saida]
  igual(evt.t, "evt"); igual(evt.tipo, "revisar_sprite"); igual(evt.arquivo, "a.aseprite")
  igual(#fechado, 0)
  c:aoFechar()
  igual(c.autenticado, false)
  igual(c:evento("cancelar", { pedido = "1" }), false, "sem conexão não envia")
end)

teste("cliente: servidor com prova errada, recusa e protocolo diferente", function()
  local token = "aa"
  local c, saida, fechado = novoCliente(token)
  c:aoAbrir()
  c:aoTexto('{"t":"desafio","nonce":"00112233445566778899aabbccddeeff","protocolo":1}')
  c:aoTexto(J.codificar({ t = "bem_vindo", prova = S.hmacHex("outro", saida[1].nonce) }))
  igual(c.autenticado, false); igual(fechado[1], "prova")
  c:aoTexto('{"t":"req","id":1,"cmd":"status"}')
  igual(#saida, 1, "ignora tudo depois")

  c, saida, fechado = novoCliente(token)
  c:aoAbrir()
  c:aoTexto('{"t":"desafio","nonce":"00112233445566778899aabbccddeeff","protocolo":1}')
  c:aoTexto('{"t":"recusado","motivo":"token"}')
  igual(fechado[1], "recusado"); igual(c.estado, "recusado")

  c, saida, fechado = novoCliente(token)
  c:aoAbrir()
  c:aoTexto('{"t":"desafio","nonce":"00112233445566778899aabbccddeeff","protocolo":2}')
  igual(fechado[1], "protocolo"); igual(#saida, 0)

  c, saida, fechado = novoCliente(nil)
  c:aoAbrir()
  c:aoTexto('{"t":"desafio","nonce":"00112233445566778899aabbccddeeff","protocolo":1}')
  igual(fechado[1], "token"); igual(#saida, 0)

  -- bem_vindo sem desafio antes: ignorado
  c, saida, fechado = novoCliente(token)
  c:aoAbrir()
  c:aoTexto(J.codificar({ t = "bem_vindo", prova = "x" }))
  igual(c.autenticado, false); igual(#fechado, 0)
  c:aoTexto("lixo que não é JSON")
  igual(#saida, 0)
end)

teste("plugin.lua e ui.lua carregam no modo batch e registram o menu Horys", function()
  local UIm = M.carregar("ui")
  verdade(type(UIm.perguntar) == "function" and type(UIm.novoAsset) == "function", "ui.lua")
  local comandos, grupos = {}, {}
  local prefsFalsas = {}
  local pluginFalso = {
    path = ext, version = "0.1.0", preferences = prefsFalsas,
    newMenuGroup = function(_, t) grupos[#grupos + 1] = t end,
    newCommand = function(_, t) comandos[#comandos + 1] = t end,
  }
  local antesInit, antesExit = init, exit
  assert(loadfile(app.fs.joinPath(ext, "plugin.lua")))()
  init(pluginFalso)
  igual(#grupos, 1); igual(grupos[1].title, "Horys"); igual(grupos[1].group, "file_scripts")
  igual(#comandos, 5)
  local titulos = {}
  for i, c in ipairs(comandos) do titulos[i] = c.title; igual(c.group, grupos[1].id) end
  igual(table.concat(titulos, "|"), "Conexão e painel…|Novo asset…|Revisar este sprite|Novo estilo…|Configurações…")
  igual(prefsFalsas.porta, 9140); igual(prefsFalsas.autoconectar, true)
  exit(pluginFalso)
  init, exit = antesInit, antesExit
end)

-- ---------------------------------------------------------------------------
fecharTudo()
if #falhas == 0 then
  print("OK " .. total .. " testes")
else
  for _, f in ipairs(falhas) do print("FALHA " .. f) end
  print("FALHA " .. #falhas .. " de " .. total .. " testes")
  error("testes falharam", 0)
end
