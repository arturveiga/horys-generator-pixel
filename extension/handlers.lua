-- Comandos que o horysd pede ao Aseprite (docs/protocolo.md, "Pedido servidor → Aseprite").
-- Cada comando recebe a tabela `args` já convertida em tabela Lua comum e devolve a tabela `data`,
-- ou chama error() com um texto curto em português. Quem chama (H.executar) protege tudo com pcall.
--
-- Índices: quadros e camadas são 0-based no protocolo e 1-based no Aseprite.
-- Cada comando que muda o sprite roda dentro de UMA app.transaction (um passo de desfazer).

local M = ...
local J = M.jsonx
local B64 = M.base64
local L = M.logica

local H = {}

H.VERSAO = M.VERSAO or "0.1.0"

-- Funções do painel (ui_*); o plugin.lua preenche com as janelas de verdade.
-- Nos testes, um falso. Sem interface (modo batch), fica nil.
H.ui = nil

local pc = app.pixelColor

local function falha(msg) error(msg, 0) end

-- ---------------------------------------------------------------------------
-- Auxiliares
-- ---------------------------------------------------------------------------
local function precisaSprite()
  local s = app.sprite
  if not s then falha("nenhum sprite aberto no Aseprite") end
  return s
end

local function inteiro(v, nome, obrigatorio)
  if v == nil or v == J.null then
    if obrigatorio then falha("falta '" .. nome .. "'") end
    return nil
  end
  local n = tonumber(v)
  if not n or n ~= math.floor(n) then falha("'" .. nome .. "' precisa ser um número inteiro") end
  return math.floor(n)
end

local function textoObrigatorio(v, nome)
  if type(v) ~= "string" or v == "" then falha("falta '" .. nome .. "'") end
  return v
end

local function nomeModo(m)
  if m == ColorMode.RGB then return "rgb"
  elseif m == ColorMode.GRAY then return "cinza"
  elseif m == ColorMode.INDEXED then return "indexado"
  elseif ColorMode.TILEMAP and m == ColorMode.TILEMAP then return "tilemap" end
  return tostring(m)
end

-- Camadas de baixo para cima, entrando nos grupos (filhos antes do grupo)
local function camadasPlanas(camadas, saida)
  saida = saida or {}
  for _, l in ipairs(camadas) do
    if l.isGroup then camadasPlanas(l.layers, saida) end
    saida[#saida + 1] = l
  end
  return saida
end

local function acharCamadaPorNome(sprite, nome)
  for _, l in ipairs(camadasPlanas(sprite.layers)) do
    if l.name == nome then return l end
  end
  return nil
end

-- ref: nome (texto) ou índice 0-based na lista plana
local function acharCamada(sprite, ref, nomeArg)
  nomeArg = nomeArg or "camada"
  if ref == nil or ref == J.null then falha("falta '" .. nomeArg .. "'") end
  if type(ref) == "number" then
    local lista = camadasPlanas(sprite.layers)
    local l = lista[math.floor(ref) + 1]
    if not l then falha("camada " .. tostring(ref) .. " não existe (há " .. #lista .. ")") end
    return l
  end
  local l = acharCamadaPorNome(sprite, tostring(ref))
  if not l then falha("camada '" .. tostring(ref) .. "' não existe") end
  return l
end

local function camadaDeImagem(sprite, ref)
  local l = acharCamada(sprite, ref)
  if l.isGroup then falha("'" .. l.name .. "' é um grupo, não uma camada de imagem") end
  if l.isTilemap then falha("camadas de tilemap não são suportadas") end
  return l
end

-- índice 0-based do protocolo -> número de quadro 1-based (nil = quadro ativo)
local function numeroQuadro(sprite, q, nomeArg)
  local n
  if q == nil or q == J.null then
    n = (app.frame and app.frame.frameNumber) or 1
  else
    n = inteiro(q, nomeArg or "quadro") + 1
  end
  if n < 1 or n > #sprite.frames then
    falha("quadro " .. (n - 1) .. " não existe (o sprite tem " .. #sprite.frames .. ")")
  end
  return n
end

-- "#rrggbb" ou "#rrggbbaa" -> r, g, b, a
local function lerCor(s)
  local h = tostring(s or ""):gsub("^#", "")
  if not (#h == 6 or #h == 8) or h:find("[^%x]") then falha("cor inválida: " .. tostring(s)) end
  return tonumber(h:sub(1, 2), 16), tonumber(h:sub(3, 4), 16), tonumber(h:sub(5, 6), 16),
    (#h == 8) and tonumber(h:sub(7, 8), 16) or 255
end

local function corHex(c)
  if c.alpha == 255 then
    return string.format("#%02x%02x%02x", c.red, c.green, c.blue)
  end
  return string.format("#%02x%02x%02x%02x", c.red, c.green, c.blue, c.alpha)
end

-- Índice da paleta mais próximo (nunca o transparente)
local function indicePaleta(sprite, r, g, b)
  local pal, pula = sprite.palettes[1], sprite.transparentColor
  local melhor, dist = nil, math.huge
  for i = 0, #pal - 1 do
    if i ~= pula then
      local p = pal:getColor(i)
      local dr, dg, db = p.red - r, p.green - g, p.blue - b
      local d = dr * dr + dg * dg + db * db
      if d < dist then melhor, dist = i, d end
      if d == 0 then break end
    end
  end
  return melhor or pula
end

-- Conversor RGBA -> valor de pixel no modo do sprite
local function conversorPixel(sprite)
  local modo = sprite.colorMode
  if modo == ColorMode.RGB then
    local rgba = pc.rgba
    return function(r, g, b, a) return rgba(r, g, b, a) end
  elseif modo == ColorMode.GRAY then
    local graya = pc.graya
    return function(r, g, b, a)
      return graya(math.floor(0.299 * r + 0.587 * g + 0.114 * b + 0.5), a)
    end
  else
    local cache = {}
    local transp = sprite.transparentColor
    return function(r, g, b, a)
      if a == 0 then return transp end
      local k = (r << 16) | (g << 8) | b
      local v = cache[k]
      if not v then
        v = indicePaleta(sprite, r, g, b)
        cache[k] = v
      end
      return v
    end
  end
end

local function valorTransparente(sprite)
  if sprite.colorMode == ColorMode.INDEXED then return sprite.transparentColor end
  return 0
end

-- Imagem (qualquer modo) -> string RGBA, linha a linha
local function bytesRGBA(img, sprite, modo)
  local w, h = img.width, img.height
  if modo == ColorMode.RGB then
    local b = img.bytes
    if #b == w * h * 4 then return b end
  end
  local partes = {}
  local char = string.char
  local pal = sprite and sprite.palettes[1]
  local transp = sprite and sprite.transparentColor
  local cache = {}
  for y = 0, h - 1 do
    local linha = {}
    for x = 0, w - 1 do
      local v = img:getPixel(x, y)
      local s = cache[v]
      if not s then
        if modo == ColorMode.RGB then
          s = char(pc.rgbaR(v), pc.rgbaG(v), pc.rgbaB(v), pc.rgbaA(v))
        elseif modo == ColorMode.GRAY then
          local g = pc.grayaV(v)
          s = char(g, g, g, pc.grayaA(v))
        else
          if v == transp or not pal or v >= #pal then
            s = "\0\0\0\0"
          else
            local c = pal:getColor(v)
            s = char(c.red, c.green, c.blue, c.alpha)
          end
        end
        cache[v] = s
      end
      linha[#linha + 1] = s
    end
    partes[#partes + 1] = table.concat(linha)
  end
  return table.concat(partes)
end
H._bytesRGBA = bytesRGBA

-- Retângulo opcional {x,y,w,h} recortado ao sprite
local function retangulo(a, sw, sh)
  local x = inteiro(a.x, "x") or 0
  local y = inteiro(a.y, "y") or 0
  local w = inteiro(a.w, "w") or (sw - x)
  local h = inteiro(a.h, "h") or (sh - y)
  if w <= 0 or h <= 0 then falha("retângulo vazio") end
  local x0, y0 = math.max(0, x), math.max(0, y)
  local x1, y1 = math.min(sw, x + w), math.min(sh, y + h)
  if x1 <= x0 or y1 <= y0 then falha("o retângulo está fora do sprite (" .. sw .. "x" .. sh .. ")") end
  return x0, y0, x1 - x0, y1 - y0
end

local function transacao(nome, fn)
  local resultado
  app.transaction("Horys: " .. nome, function() resultado = fn() end)
  return resultado
end

local function nomeArquivo(s)
  local f = s.filename
  if f == nil then return "" end
  return f
end

-- ---------------------------------------------------------------------------
-- status
-- ---------------------------------------------------------------------------
local function infoSprite(s)
  local hid = s.properties["horys_id"]
  if hid == nil or hid == "" then
    hid = string.format("%08x-%08x-%08x", os.time(), math.random(0, 0xffffffff), math.random(0, 0xffffffff))
    s.properties["horys_id"] = hid
  end
  local camadas = J.lista({})
  for i, l in ipairs(camadasPlanas(s.layers)) do
    local c = { nome = l.name, visivel = l.isVisible, opacidade = l.opacity or 255, indice = i - 1 }
    if l.isGroup then c.grupo = true end
    camadas[#camadas + 1] = c
  end
  local quadros = J.lista({})
  for i, f in ipairs(s.frames) do quadros[i] = { ms = math.floor(f.duration * 1000 + 0.5) } end
  local tags = J.lista({})
  for _, t in ipairs(s.tags) do
    tags[#tags + 1] = { nome = t.name, de = t.fromFrame.frameNumber - 1, ate = t.toFrame.frameNumber - 1 }
  end
  local ativa = (app.sprite == s and app.layer) and app.layer.name or J.null
  local quadroAtivo = (app.sprite == s and app.frame) and (app.frame.frameNumber - 1) or 0
  return {
    arquivo = nomeArquivo(s),
    horys_id = hid,
    largura = s.width,
    altura = s.height,
    modo = nomeModo(s.colorMode),
    camadas = camadas,
    quadros = quadros,
    tags = tags,
    camada_ativa = ativa,
    quadro_ativo = quadroAtivo,
  }
end

function H.status()
  local sprites = J.lista({})
  for i, s in ipairs(app.sprites) do
    sprites[#sprites + 1] = { indice = i - 1, arquivo = nomeArquivo(s) }
  end
  return {
    versao_aseprite = tostring(app.version),
    versao_extensao = H.VERSAO,
    sprite = app.sprite and infoSprite(app.sprite) or J.null,
    sprites = sprites,
  }
end

-- ---------------------------------------------------------------------------
-- sprites
-- ---------------------------------------------------------------------------
function H.sprite_novo(a)
  local w, h = inteiro(a.largura, "largura", true), inteiro(a.altura, "altura", true)
  if w < 1 or h < 1 or w > 65535 or h > 65535 then falha("tamanho inválido: " .. w .. "x" .. h) end
  local s = Sprite(w, h, ColorMode.RGB)
  app.sprite = s
  local camada = s.layers[1]
  camada.name = "desenho"
  if type(a.nome) == "string" and a.nome ~= "" then s.filename = a.nome end
  return H.status()
end

function H.abrir(a)
  local arq = textoObrigatorio(a.arquivo, "arquivo")
  if not app.fs.isFile(arq) then falha("arquivo não encontrado: " .. arq) end
  local s = app.open(arq)
  if not s then falha("não consegui abrir: " .. arq) end
  app.sprite = s
  return H.status()
end

local function mesmoArquivo(a, b)
  if not a or not b or a == "" or b == "" then return false end
  local na, nb = app.fs.normalizePath(a), app.fs.normalizePath(b)
  if app.os.windows then na, nb = na:lower(), nb:lower() end
  return na == nb
end

function H.selecionar_sprite(a)
  local alvo
  if a.indice ~= nil and a.indice ~= J.null then
    local i = inteiro(a.indice, "indice")
    alvo = app.sprites[i + 1]
    if not alvo then falha("sprite " .. i .. " não existe (há " .. #app.sprites .. " abertos)") end
  elseif type(a.arquivo) == "string" and a.arquivo ~= "" then
    for _, s in ipairs(app.sprites) do
      if mesmoArquivo(s.filename, a.arquivo) or s.filename == a.arquivo then alvo = s; break end
    end
    if not alvo then falha("nenhum sprite aberto com o arquivo " .. a.arquivo) end
  else
    falha("informe 'indice' ou 'arquivo'")
  end
  app.sprite = alvo
  return H.status()
end

-- Formatos em que o Aseprite mostra uma janela de opções antes de salvar (travaria o editor)
local FORMATOS_COM_JANELA = { "gif", "jpeg", "webp", "tga", "svg", "css" }

local function semJanelasDeOpcoes(fn)
  local antes = {}
  for _, f in ipairs(FORMATOS_COM_JANELA) do
    pcall(function()
      antes[f] = app.preferences[f].show_alert
      app.preferences[f].show_alert = false
    end)
  end
  local ok, erro = pcall(fn)
  for f, v in pairs(antes) do
    pcall(function() app.preferences[f].show_alert = v end)
  end
  if not ok then error(erro, 0) end
end

function H.salvar(a)
  local s = precisaSprite()
  local copia = a.copia == true
  local destino = (type(a.arquivo) == "string" and a.arquivo ~= "") and a.arquivo or nil
  if not destino then
    if copia then falha("para salvar uma cópia, informe 'arquivo'") end
    if not s.filename or s.filename == "" or not app.fs.isFile(s.filename) then
      falha("o sprite ainda não tem arquivo; informe 'arquivo'")
    end
    destino = s.filename
  end
  local pasta = app.fs.filePath(destino)
  if pasta ~= "" and not app.fs.isDirectory(pasta) then app.fs.makeAllDirectories(pasta) end
  semJanelasDeOpcoes(function()
    if copia then
      app.command.SaveFileCopyAs{ ui = false, filename = destino }
    elseif destino == s.filename then
      app.command.SaveFile{ ui = false }
    else
      app.command.SaveFileAs{ ui = false, filename = destino }
    end
  end)
  if not app.fs.isFile(destino) then falha("o Aseprite não gravou " .. destino) end
  return { arquivo = destino }
end

-- ---------------------------------------------------------------------------
-- camadas
-- ---------------------------------------------------------------------------
function H.camada(a)
  local s = precisaSprite()
  local acao = a.acao
  if acao == "criar" then
    local nome = textoObrigatorio(a.nome, "nome")
    if acharCamadaPorNome(s, nome) then falha("já existe uma camada '" .. nome .. "'") end
    local ref, acima
    if a.abaixo_de ~= nil and a.abaixo_de ~= J.null then
      ref, acima = acharCamada(s, a.abaixo_de, "abaixo_de"), false
    elseif a.acima_de ~= nil and a.acima_de ~= J.null then
      ref, acima = acharCamada(s, a.acima_de, "acima_de"), true
    end
    local nova
    transacao("criar camada", function()
      nova = s:newLayer()
      nova.name = nome
      if ref then
        if ref.parent ~= nova.parent then nova.parent = ref.parent end
        local idx = ref.stackIndex
        nova.stackIndex = acima and (idx + 1) or idx
      end
    end)
    app.layer = nova
  elseif acao == "remover" then
    local l = acharCamada(s, a.nome, "nome")
    if #s.layers <= 1 and l.parent == s then falha("não dá para remover a única camada") end
    transacao("remover camada", function() s:deleteLayer(l) end)
  elseif acao == "renomear" then
    local l = acharCamada(s, a.nome, "nome")
    local novo = textoObrigatorio(a.novo, "novo")
    if novo ~= l.name and acharCamadaPorNome(s, novo) then falha("já existe uma camada '" .. novo .. "'") end
    transacao("renomear camada", function() l.name = novo end)
  elseif acao == "propriedades" then
    local l = acharCamada(s, a.nome, "nome")
    local op = inteiro(a.opacidade, "opacidade")
    if op and (op < 0 or op > 255) then falha("'opacidade' vai de 0 a 255") end
    transacao("propriedades da camada", function()
      if a.visivel ~= nil and a.visivel ~= J.null then l.isVisible = (a.visivel == true) end
      if op then l.opacity = op end
    end)
  elseif acao == "ordem" then
    if type(a.nomes) ~= "table" or #a.nomes == 0 then falha("'nomes' precisa listar as camadas de baixo para cima") end
    local lista = {}
    local vistos = {}
    for _, n in ipairs(a.nomes) do
      local l = acharCamada(s, n, "nomes")
      if vistos[l] then falha("camada repetida em 'nomes': " .. l.name) end
      vistos[l] = true
      if #lista > 0 and l.parent ~= lista[1].parent then
        falha("'" .. l.name .. "' está em outro grupo")
      end
      lista[#lista + 1] = l
    end
    transacao("ordem das camadas", function()
      for i, l in ipairs(lista) do l.stackIndex = i end
    end)
  elseif acao == "ativar" then
    app.layer = acharCamada(s, a.nome, "nome")
  else
    falha("ação de camada desconhecida: " .. tostring(acao))
  end
  return H.status()
end

-- ---------------------------------------------------------------------------
-- quadros
-- ---------------------------------------------------------------------------
function H.quadro(a)
  local s = precisaSprite()
  local acao = a.acao
  if acao == "criar" then
    local depois = (a.depois_de ~= nil and a.depois_de ~= J.null) and numeroQuadro(s, a.depois_de, "depois_de")
      or #s.frames
    transacao("criar quadro", function()
      if a.copiar == true then
        s:newFrame(depois)            -- copia o quadro `depois` e insere logo após
      else
        s:newEmptyFrame(depois + 1)
      end
    end)
    -- (o Frame devolvido por newFrame é o copiado, não o novo: usa o número)
    app.frame = s.frames[depois + 1]
  elseif acao == "remover" then
    local n = numeroQuadro(s, inteiro(a.indice, "indice", true), "indice")
    if #s.frames <= 1 then falha("não dá para remover o único quadro") end
    transacao("remover quadro", function() s:deleteFrame(n) end)
  elseif acao == "duracao" then
    local ms = inteiro(a.ms, "ms", true)
    if ms < 1 or ms > 65535 then falha("'ms' vai de 1 a 65535") end
    if a.todos == true then
      transacao("duração dos quadros", function()
        for _, f in ipairs(s.frames) do f.duration = ms / 1000 end
      end)
    else
      local n = numeroQuadro(s, inteiro(a.indice, "indice", true), "indice")
      transacao("duração do quadro", function() s.frames[n].duration = ms / 1000 end)
    end
  elseif acao == "ativar" then
    app.frame = s.frames[numeroQuadro(s, inteiro(a.indice, "indice", true), "indice")]
  elseif acao == "garantir" then
    local total = inteiro(a.total, "total", true)
    if total > 10000 then falha("'total' grande demais") end
    if #s.frames < total then
      transacao("garantir quadros", function()
        while #s.frames < total do s:newEmptyFrame(#s.frames + 1) end
      end)
    end
  else
    falha("ação de quadro desconhecida: " .. tostring(acao))
  end
  return H.status()
end

-- ---------------------------------------------------------------------------
-- tags
-- ---------------------------------------------------------------------------
local function acharTag(s, nome)
  for _, t in ipairs(s.tags) do
    if t.name == nome then return t end
  end
  return nil
end

function H.tag(a)
  local s = precisaSprite()
  if a.acao == "criar" then
    local nome = textoObrigatorio(a.nome, "nome")
    local de = numeroQuadro(s, inteiro(a.de, "de", true), "de")
    local ate = numeroQuadro(s, inteiro(a.ate, "ate", true), "ate")
    if ate < de then falha("'ate' vem antes de 'de'") end
    if acharTag(s, nome) then falha("já existe uma tag '" .. nome .. "'") end
    transacao("criar tag", function()
      local t = s:newTag(de, ate)
      t.name = nome
    end)
  elseif a.acao == "remover" then
    local nome = textoObrigatorio(a.nome, "nome")
    local t = acharTag(s, nome)
    if not t then falha("tag '" .. nome .. "' não existe") end
    transacao("remover tag", function() s:deleteTag(t) end)
  else
    falha("ação de tag desconhecida: " .. tostring(a.acao))
  end
  return H.status()
end

-- ---------------------------------------------------------------------------
-- paleta
-- ---------------------------------------------------------------------------
local function lerPaleta(s)
  local pal = s.palettes[1]
  local cores = J.lista({})
  for i = 0, #pal - 1 do cores[#cores + 1] = corHex(pal:getColor(i)) end
  return cores
end

function H.paleta(a)
  local s = precisaSprite()
  if a.acao == "definir" then
    if type(a.cores) ~= "table" or #a.cores == 0 then falha("'cores' precisa ter ao menos uma cor") end
    if #a.cores > 256 then falha("a paleta tem no máximo 256 cores") end
    local pal = Palette(#a.cores)
    for i, c in ipairs(a.cores) do
      local r, g, b, al = lerCor(c)
      pal:setColor(i - 1, Color{ r = r, g = g, b = b, a = al })
    end
    transacao("definir paleta", function() s:setPalette(pal) end)
  elseif a.acao ~= "ler" and a.acao ~= nil then
    falha("ação de paleta desconhecida: " .. tostring(a.acao))
  end
  return { cores = lerPaleta(s) }
end

-- ---------------------------------------------------------------------------
-- pixels
-- ---------------------------------------------------------------------------
function H.escrever(a)
  local s = precisaSprite()
  local camada = camadaDeImagem(s, a.camada)
  local fn = numeroQuadro(s, a.quadro)
  local x, y = inteiro(a.x, "x", true), inteiro(a.y, "y", true)
  local w, h = inteiro(a.w, "w", true), inteiro(a.h, "h", true)
  if w < 1 or h < 1 then falha("'w' e 'h' precisam ser maiores que zero") end
  if w * h > 16 * 1024 * 1024 then falha("região grande demais") end
  local rgba = B64.decodificar(textoObrigatorio(a.rgba, "rgba"))
  if #rgba ~= w * h * 4 then
    falha("'rgba' tem " .. #rgba .. " bytes; esperava " .. (w * h * 4) .. " (w·h·4)")
  end
  local mascara
  if a.mascara ~= nil and a.mascara ~= J.null and a.mascara ~= "" then
    mascara = B64.decodificar(a.mascara)
    if #mascara ~= w * h then
      falha("'mascara' tem " .. #mascara .. " bytes; esperava " .. (w * h) .. " (w·h)")
    end
  end

  local sw, sh = s.width, s.height
  local converter = conversorPixel(s)
  local byte = string.byte
  local escritos = 0

  transacao("escrever", function()
    local cel = camada:cel(fn)
    local img, px, py
    if cel then
      -- garante que a célula cubra o sprite inteiro (sem perder o que já estiver fora dele)
      local p, ci = cel.position, cel.image
      local x0, y0 = math.min(p.x, 0), math.min(p.y, 0)
      local x1, y1 = math.max(p.x + ci.width, sw), math.max(p.y + ci.height, sh)
      if x0 == p.x and y0 == p.y and x1 - x0 == ci.width and y1 - y0 == ci.height then
        img = ci:clone()
      else
        img = Image(x1 - x0, y1 - y0, s.colorMode)
        img:clear(valorTransparente(s))
        img:drawImage(ci, Point(p.x - x0, p.y - y0), 255, BlendMode.SRC)
      end
      px, py = x0, y0
    else
      img = Image(sw, sh, s.colorMode)
      img:clear(valorTransparente(s))
      px, py = 0, 0
    end

    local desenhar = img.drawPixel
    for j = 0, h - 1 do
      local sy = y + j
      if sy >= 0 and sy < sh then
        local base = j * w
        for i = 0, w - 1 do
          local sx = x + i
          if sx >= 0 and sx < sw and (not mascara or byte(mascara, base + i + 1) ~= 0) then
            local k = (base + i) * 4 + 1
            local r, g, b, al = byte(rgba, k, k + 3)
            desenhar(img, sx - px, sy - py, converter(r, g, b, al))
            escritos = escritos + 1
          end
        end
      end
    end

    if cel then
      cel.image = img
      if cel.position.x ~= px or cel.position.y ~= py then cel.position = Point(px, py) end
    else
      s:newCel(camada, fn, img, Point(0, 0))
    end
  end)
  return { escritos = escritos }
end

function H.ler(a)
  local s = precisaSprite()
  local fn = numeroQuadro(s, a.quadro)
  local x, y, w, h = retangulo(a, s.width, s.height)
  local img, modo
  if a.camada == nil or a.camada == J.null then
    modo = ColorMode.RGB
    img = Image(w, h, ColorMode.RGB)
    local excluir = a.excluir
    if excluir == nil or excluir == J.null then excluir = { "revisao", "referencia", "mapa-partes" } end
    local ocultadas = {}
    for _, nome in ipairs(excluir) do
      local camada = acharCamadaPorNome(s, nome)
      if camada and camada.isVisible then
        camada.isVisible = false
        table.insert(ocultadas, camada)
      end
    end
    img:drawSprite(s, fn, Point(-x, -y))
    for _, camada in ipairs(ocultadas) do camada.isVisible = true end
  else
    local camada = camadaDeImagem(s, a.camada)
    modo = s.colorMode
    img = Image(w, h, modo)
    img:clear(valorTransparente(s))
    local cel = camada:cel(fn)
    if cel then
      img:drawImage(cel.image, Point(cel.position.x - x, cel.position.y - y), 255, BlendMode.SRC)
    end
  end
  return { x = x, y = y, w = w, h = h, rgba = B64.codificar(bytesRGBA(img, s, modo)) }
end

function H.limpar_camada(a)
  local s = precisaSprite()
  local camada = camadaDeImagem(s, a.camada)
  local quadros = {}
  if a.todos == true then
    for i = 1, #s.frames do quadros[#quadros + 1] = i end
  else
    quadros[1] = numeroQuadro(s, inteiro(a.quadro, "quadro", true))
  end
  transacao("limpar camada", function()
    for _, n in ipairs(quadros) do
      local cel = camada:cel(n)
      if cel then
        if camada.isBackground then
          local img = cel.image:clone()
          img:clear(conversorPixel(s)(app.bgColor.red, app.bgColor.green, app.bgColor.blue, 255))
          cel.image = img
        else
          s:deleteCel(cel)
        end
      end
    end
  end)
  return J.objeto({})
end

function H.selecao()
  local s = precisaSprite()
  local sel = s.selection
  if sel.isEmpty then return { vazia = true, x = 0, y = 0, w = 0, h = 0 } end
  local b = sel.bounds
  return { vazia = false, x = b.x, y = b.y, w = b.width, h = b.height }
end

local function historico(a, refazer)
  precisaSprite()
  local passos = inteiro(a.passos, "passos") or 1
  if passos < 1 or passos > 1000 then falha("'passos' vai de 1 a 1000") end
  for _ = 1, passos do
    if refazer then app.redo() else app.undo() end
  end
  return J.objeto({})
end

function H.desfazer(a) return historico(a, false) end
function H.refazer(a) return historico(a, true) end

-- ---------------------------------------------------------------------------
-- painel (ui_*)
-- ---------------------------------------------------------------------------
local function precisaUI()
  if not H.ui then falha("o painel não está disponível (Aseprite sem interface)") end
  return H.ui
end

function H.ui_perguntar(a)
  local ui = precisaUI()
  local perguntas = L.normalizarPerguntas(a)
  ui.perguntar({ id = a.id, titulo = L.aparar(a.titulo ~= J.null and a.titulo or ""), perguntas = perguntas })
  return { mostrado = true }
end

function H.ui_aprovar(a)
  local ui = precisaUI()
  ui.aprovar(L.normalizarAprovacao(a))
  return { mostrado = true }
end

function H.ui_progresso(a)
  local ui = precisaUI()
  ui.progresso({ pedido = a.pedido, etapa = a.etapa, texto = a.texto, nota = a.nota })
  return J.objeto({})
end

function H.ui_imagem(a)
  local ui = precisaUI()
  ui.imagem(L.normalizarImagem(a))
  return { mostrado = true }
end

function H.ui_acabamento(a)
  local ui = precisaUI()
  ui.acabamento(L.normalizarAcabamento(a))
  return { mostrado = true }
end

function H.ui_fechar(a)
  local ui = precisaUI()
  if a.id == nil or a.id == J.null then falha("falta 'id'") end
  ui.fechar(a.id)
  return J.objeto({})
end

-- ---------------------------------------------------------------------------
-- Despacho
-- ---------------------------------------------------------------------------
local COMANDOS = {
  status = H.status, sprite_novo = H.sprite_novo, abrir = H.abrir,
  selecionar_sprite = H.selecionar_sprite, salvar = H.salvar,
  camada = H.camada, quadro = H.quadro, tag = H.tag, paleta = H.paleta,
  escrever = H.escrever, ler = H.ler, limpar_camada = H.limpar_camada,
  selecao = H.selecao, desfazer = H.desfazer, refazer = H.refazer,
  ui_perguntar = H.ui_perguntar, ui_aprovar = H.ui_aprovar,
  ui_progresso = H.ui_progresso, ui_fechar = H.ui_fechar,
  ui_imagem = H.ui_imagem, ui_acabamento = H.ui_acabamento,
}
H.COMANDOS = COMANDOS

-- "…/handlers.lua:112: mensagem" -> "mensagem"
local function limparErro(e)
  return (tostring(e):gsub("^[^\n]-%.lua:%d+: ", ""))
end

-- Executa um comando. Devolve (true, data) ou (false, "erro em português"). Nunca lança erro.
function H.executar(cmd, args)
  local fn = type(cmd) == "string" and COMANDOS[cmd] or nil
  if not fn then return false, "comando desconhecido: " .. tostring(cmd) end
  if args == nil or args == J.null then args = {} end
  if type(args) ~= "table" then return false, "'args' precisa ser um objeto" end
  local ok, res = pcall(fn, args)
  if ok then return true, res or J.objeto({}) end
  return false, limparErro(res)
end

return H
