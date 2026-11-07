-- Lógica das janelas que não depende da interface: montar respostas, pedidos e estilos,
-- validar o que o servidor manda para o painel e quebrar textos em linhas.
-- Tudo aqui é testável no modo batch (sem Dialog).

local M = ...
local J = M.jsonx

local L = {}

function L.aparar(s)
  return (tostring(s or ""):gsub("^%s+", ""):gsub("%s+$", ""))
end

local aparar = L.aparar

-- Quebra um texto em linhas de até `largura` caracteres (respeita as quebras do texto).
-- Conta caracteres UTF-8, não bytes.
function L.quebrarLinhas(texto, largura)
  largura = largura or 60
  local linhas = {}
  texto = tostring(texto or ""):gsub("\r\n", "\n")
  for paragrafo in (texto .. "\n"):gmatch("(.-)\n") do
    local atual, tam = {}, 0
    if paragrafo:match("^%s*$") then
      linhas[#linhas + 1] = ""
    else
      for palavra in paragrafo:gmatch("%S+") do
        local n = utf8.len(palavra) or #palavra
        if tam > 0 and tam + 1 + n > largura then
          linhas[#linhas + 1] = table.concat(atual, " ")
          atual, tam = {}, 0
        end
        atual[#atual + 1] = palavra
        tam = tam + (tam > 0 and 1 or 0) + n
      end
      if #atual > 0 then linhas[#linhas + 1] = table.concat(atual, " ") end
    end
  end
  -- tira linhas vazias do fim
  while #linhas > 0 and linhas[#linhas] == "" do linhas[#linhas] = nil end
  return linhas
end

local function texto(v)
  if v == nil or v == J.null then return "" end
  return tostring(v)
end

-- Valida e normaliza os args de ui_perguntar. Devolve a lista de perguntas.
function L.normalizarPerguntas(args)
  if type(args) ~= "table" then error("args ausentes", 0) end
  if args.id == nil or texto(args.id) == "" then error("falta o 'id' da pergunta", 0) end
  local lista = args.perguntas
  if type(lista) ~= "table" or #lista == 0 then error("'perguntas' precisa ter ao menos uma pergunta", 0) end
  local saida = {}
  for i, p in ipairs(lista) do
    if type(p) ~= "table" then error("pergunta " .. i .. " inválida", 0) end
    local enunciado = aparar(texto(p.pergunta))
    if enunciado == "" then error("pergunta " .. i .. " sem texto", 0) end
    local opcoes = {}
    if type(p.opcoes) == "table" then
      for j, o in ipairs(p.opcoes) do
        if type(o) == "table" then
          local rotulo = aparar(texto(o.rotulo))
          if rotulo == "" then error("pergunta " .. i .. ", opção " .. j .. " sem rótulo", 0) end
          opcoes[#opcoes + 1] = { rotulo = rotulo, descricao = aparar(texto(o.descricao)) }
        elseif type(o) == "string" and aparar(o) ~= "" then
          opcoes[#opcoes + 1] = { rotulo = aparar(o), descricao = "" }
        end
      end
    end
    saida[i] = {
      pergunta = enunciado,
      cabecalho = aparar(texto(p.cabecalho)),
      multipla = p.multipla == true,
      opcoes = opcoes,
    }
  end
  return saida
end

-- escolhas[i] = { selecionados = {índices das opções marcadas}, outro = "texto" }
-- Devolve (respostas, faltando): respostas = {[texto da pergunta] = resposta};
-- faltando = lista de perguntas sem resposta (cabeçalho ou texto).
function L.montarRespostas(perguntas, escolhas)
  local respostas = J.objeto({})
  local faltando = {}
  for i, p in ipairs(perguntas) do
    local e = escolhas and escolhas[i] or {}
    local outro = aparar(e.outro)
    local resposta
    if outro ~= "" then
      resposta = outro
    else
      local rotulos = {}
      local sel = {}
      for _, j in ipairs(e.selecionados or {}) do sel[#sel + 1] = j end
      table.sort(sel)
      for _, j in ipairs(sel) do
        local o = p.opcoes[j]
        if o then rotulos[#rotulos + 1] = o.rotulo end
      end
      if not p.multipla and #rotulos > 1 then rotulos = { rotulos[1] } end
      if #rotulos > 0 then resposta = table.concat(rotulos, ", ") end
    end
    if resposta then
      respostas[p.pergunta] = resposta
    else
      faltando[#faltando + 1] = (p.cabecalho ~= "" and p.cabecalho) or p.pergunta
    end
  end
  return respostas, faltando
end

-- Valida os args de ui_aprovar
function L.normalizarAprovacao(args)
  if type(args) ~= "table" then error("args ausentes", 0) end
  if args.id == nil or texto(args.id) == "" then error("falta o 'id' da aprovação", 0) end
  local img = args.imagem
  if img == J.null or img == "" then img = nil end
  if img ~= nil and type(img) ~= "string" then error("'imagem' precisa ser PNG em base64", 0) end
  -- RGBA cru (preferido: monta a Image sem gravar arquivo, então sem pedido de permissão do Aseprite)
  local rgba = args.imagem_rgba
  if rgba == J.null or rgba == "" then rgba = nil end
  local w, h = tonumber(args.imagem_w), tonumber(args.imagem_h)
  if rgba ~= nil and (type(rgba) ~= "string" or not w or not h or w < 1 or h < 1) then
    error("'imagem_rgba' precisa de base64 e de imagem_w/imagem_h", 0)
  end
  return {
    id = args.id,
    titulo = aparar(texto(args.titulo)),
    texto = texto(args.texto),
    imagem = img,
    imagem_rgba = rgba,
    imagem_w = w and math.floor(w) or nil,
    imagem_h = h and math.floor(h) or nil,
  }
end

function L.montarAprovacao(id, aprovado, comentario)
  return { tipo = "aprovacao", id = id, aprovado = aprovado and true or false, comentario = aparar(comentario) }
end

-- "idle, andar; atacar" -> {"idle", "andar", "atacar"}
function L.lerEstados(s)
  local estados = J.lista({})
  local vistos = {}
  for parte in tostring(s or ""):gmatch("[^,;\n]+") do
    local e = aparar(parte)
    if e ~= "" and not vistos[e] then
      vistos[e] = true
      estados[#estados + 1] = e
    end
  end
  return estados
end

-- "32" -> "32x32"; "32x48" / "32 x 48" / "32X48" -> "32x48"; "" -> nil
function L.normalizarTamanho(s)
  s = aparar(s)
  if s == "" then return nil end
  local w, h = s:match("^(%d+)%s*[xX×]%s*(%d+)$")
  if not w then
    w = s:match("^(%d+)$")
    h = w
  end
  if not w then return nil, "tamanho inválido (use 32 ou 32x48)" end
  w, h = tonumber(w), tonumber(h)
  if w < 1 or h < 1 or w > 4096 or h > 4096 then return nil, "tamanho fora do limite (1 a 4096)" end
  return string.format("%dx%d", w, h)
end

local EXT_IMAGEM = { png = true, jpg = true, jpeg = true, gif = true, webp = true, bmp = true, aseprite = true, ase = true }

function L.ehImagem(caminho)
  local ext = tostring(caminho or ""):match("%.([%w]+)$")
  return ext ~= nil and EXT_IMAGEM[ext:lower()] == true
end

-- dados: {descricao, referencia, tipo, estilo, motor, estados (texto), tamanho (texto)}
-- Devolve (pedido) ou (nil, erro).
function L.montarPedido(d)
  local descricao = aparar(d.descricao)
  if descricao == "" then return nil, "Descreva o que criar." end
  local tipo, estilo, motor = aparar(d.tipo), aparar(d.estilo), aparar(d.motor)
  if tipo == "" then return nil, "Escolha o tipo." end
  if estilo == "" then return nil, "Escolha o estilo." end
  if motor == "" then return nil, "Escolha o motor." end
  local pedido = {
    descricao = descricao,
    tipo = tipo,
    estilo = estilo,
    motor = motor,
    estados = L.lerEstados(d.estados),
  }
  local ref = aparar(d.referencia)
  -- Dialog:file vazio pode devolver o diretório atual com separador final.
  if ref ~= "" and not ref:match("[/\\]$") then pedido.referencia = ref end
  local tamanho, erro = L.normalizarTamanho(d.tamanho)
  if erro then return nil, erro end
  pedido.tamanho = tamanho
  return pedido
end

-- dados: {nome, imagens = {caminhos}, motor}
function L.montarEstilo(d)
  local nome = aparar(d.nome)
  if nome == "" then return nil, "Dê um nome ao estilo." end
  local imagens = J.lista({})
  local vistas = {}
  for _, c in ipairs(d.imagens or {}) do
    c = aparar(c)
    if c ~= "" and not vistas[c] then
      vistas[c] = true
      imagens[#imagens + 1] = c
    end
  end
  if #imagens == 0 then return nil, "Adicione ao menos uma imagem." end
  local motor = aparar(d.motor)
  if motor == "" then return nil, "Escolha o motor." end
  return { nome = nome, imagens = imagens, motor = motor }
end

-- Conteúdo do arquivo de token -> token (sem espaços nem quebras)
function L.limparToken(conteudo)
  return (tostring(conteudo or ""):gsub("%s+", ""))
end

-- Pasta de casa: USERPROFILE (Windows) ou HOME
function L.caminhoToken(getenv, juntar)
  local casa = getenv("USERPROFILE")
  if not casa or casa == "" then casa = getenv("HOME") end
  if not casa or casa == "" then return nil end
  return juntar(juntar(casa, ".horys-pixel"), "token")
end

-- Lista do servidor (estilos/tipos/motores) -> lista de textos
function L.listaDeTextos(v)
  local saida = {}
  if type(v) == "table" then
    for _, x in ipairs(v) do
      if type(x) == "string" and x ~= "" then saida[#saida + 1] = x end
    end
  end
  return saida
end

-- Texto de uma linha para o andamento: "pedido · etapa — texto (nota)"
function L.linhaProgresso(p)
  local partes = {}
  if p.pedido and texto(p.pedido) ~= "" then partes[#partes + 1] = "Pedido " .. texto(p.pedido) end
  if p.etapa and texto(p.etapa) ~= "" then partes[#partes + 1] = texto(p.etapa) end
  local s = table.concat(partes, " · ")
  if p.texto and texto(p.texto) ~= "" then s = (s ~= "" and (s .. ": ") or "") .. texto(p.texto) end
  if p.nota ~= nil and p.nota ~= J.null and texto(p.nota) ~= "" then s = s .. " (nota " .. texto(p.nota) .. ")" end
  return s
end

return L
