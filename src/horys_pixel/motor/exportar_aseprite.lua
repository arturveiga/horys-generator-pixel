-- Monta um .aseprite fatiado em camadas a partir do spec.json que o grade.py escreve.
-- uso: aseprite.exe -b --script-param spec=<spec.json> --script exportar_aseprite.lua
-- spec: { largura, altura, paleta = {"#rrggbb", ...},
--         camadas = {{nome, opacidade}, ...}  (de baixo para cima),
--         quadros = {{ms, cels = {<camada> = <png RGBA do tamanho do quadro>}}, ...},
--         tags = {{nome, de, ate}}, saida = "<arquivo>.aseprite" }
local f = assert(io.open(app.params["spec"], "r"), "spec não encontrado: " .. tostring(app.params["spec"]))
local spec = json.decode(f:read("a"))
f:close()

local spr = Sprite(spec.largura, spec.altura, ColorMode.RGB)

local function cor(h)
  h = h:gsub("#", "")
  return Color{ r = tonumber(h:sub(1, 2), 16), g = tonumber(h:sub(3, 4), 16), b = tonumber(h:sub(5, 6), 16), a = 255 }
end
local pal = Palette(#spec.paleta)
for i, h in ipairs(spec.paleta) do pal:setColor(i - 1, cor(h)) end
spr:setPalette(pal)

for _ = 2, #spec.quadros do spr:newEmptyFrame() end
for i, q in ipairs(spec.quadros) do spr.frames[i].duration = (q.ms or 100) / 1000 end

local camadas = {}
for i, c in ipairs(spec.camadas) do
  local L = (i == 1) and spr.layers[1] or spr:newLayer()
  L.name = c.nome
  L.opacity = c.opacidade or 255
  camadas[c.nome] = L
end
-- a camada 1 do Sprite novo já tem uma célula vazia no quadro 1: some ao receber a primeira célula ou é apagada
for _, cel in ipairs(spr.cels) do spr:deleteCel(cel) end

for fi, q in ipairs(spec.quadros) do
  for nome, png in pairs(q.cels) do
    local L = assert(camadas[nome], "camada sem declaração: " .. nome)
    local img = Image{ fromFile = png }
    spr:newCel(L, spr.frames[fi], img, Point(0, 0))
  end
end

for _, t in ipairs(spec.tags or {}) do
  local tag = spr:newTag(t.de, t.ate)
  tag.name = t.nome
end

spr:saveAs(spec.saida)
