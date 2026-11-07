-- LEGADO (migração de um .aseprite antigo, de uma camada só): NÃO é o fluxo principal.
-- O fluxo atual é horys_asset_novo preset_partes='humanoide-ferreiro' + horys_partes_recortar/estender/checar
-- (src/horys_pixel/partes.py). Este script só corta por retângulos fixos e NÃO cria anatomia oculta: depois dele,
-- ajuste a ficha (horys_ficha modular=true preset_partes='humanoide-ferreiro' partes=[...9 nomes...]), rode
-- horys_partes_estender nas junções e valide com horys_partes_checar.
-- Separa o ferreiro existente em camadas editáveis (nomes do preset), preservando o composto visual; a camada de
-- origem vira 'referencia' (oculta), como no asset modular.
local output = app.params.output
if not output or output == "" then error("passe output=<arquivo.aseprite>") end

local spr = app.activeSprite
if not spr then error("nenhum sprite aberto") end

local function find(name)
  for _, layer in ipairs(spr.layers) do if layer.name == name then return layer end end
end

local source = find("desenho") or spr.layers[1]
local cel = source:cel(1)
if not cel then error("a camada de desenho esta vazia") end
local image = cel.image
local offset = cel.position

local order = { "perna-traseira", "corpo-base", "avental-torso", "cabelo", "barba", "braco-traseiro", "braco-frente", "martelo", "oculos" }
local layers, images = {}, {}

local function part(x, y)
  -- Coordenadas no canvas 192x192; os limites seguem a anatomia do ferreiro.
  if y <= 91 or (x <= 87 and y <= 102) then return "cabelo" end
  if y >= 120 and x <= 108 then return "perna-traseira" end
  if x >= 111 and y >= 106 then return "martelo" end
  if y >= 78 and y <= 94 and x >= 94 then return "oculos" end
  if y >= 93 and y <= 111 and x >= 93 and x <= 111 then return "barba" end
  if x <= 89 and y >= 98 and y <= 120 then return "braco-traseiro" end
  if x >= 101 and y >= 103 and y <= 121 then return "braco-frente" end
  if y >= 102 and y <= 122 then return "avental-torso" end
  return "corpo-base"
end

app.transaction(function()
  for _, name in ipairs(order) do
    local layer = spr:newLayer()
    layer.name = name
    local dst = Image(spr.width, spr.height, spr.colorMode)
    layers[name], images[name] = layer, dst
  end
  for y = 0, image.height - 1 do
    for x = 0, image.width - 1 do
      local px = image:getPixel(x, y)
      if app.pixelColor.rgbaA(px) > 0 then
        local name = part(x + offset.x, y + offset.y)
        images[name]:drawPixel(x + offset.x, y + offset.y, px)
      end
    end
  end
  for _, name in ipairs(order) do spr:newCel(layers[name], 1, images[name]) end
  source.name = "referencia"
  source.isVisible = false
  local empty = find("Layer 1")
  if empty and empty ~= source then spr:deleteLayer(empty) end
  app.activeLayer = layers["braco-frente"]
end)

app.command.SaveFile { filename = output }
