-- Monta uma Image a partir de RGBA cru em base64 (caminho da aprovação sem arquivo) e imprime pixels de conferência.
local ext = app.params.ext
local M = assert(loadfile(app.fs.joinPath(ext, "modulos.lua")))(ext, "0.1.0")
local img = M.arquivos.imagemDeRgbaBase64(app.params.rgba, tonumber(app.params.w), tonumber(app.params.h))
local function px(x, y)
  local c = img:getPixel(x, y)
  return string.format("%d,%d,%d,%d", app.pixelColor.rgbaR(c), app.pixelColor.rgbaG(c), app.pixelColor.rgbaB(c), app.pixelColor.rgbaA(c))
end
print("TAM " .. img.width .. "x" .. img.height)
print("P00 " .. px(0, 0))
print("P21 " .. px(2, 1))
local a = M.logica.normalizarAprovacao({ id = "x", titulo = "t", imagem_rgba = app.params.rgba, imagem_w = app.params.w, imagem_h = app.params.h })
print("NORM " .. tostring(a.imagem_w) .. "x" .. tostring(a.imagem_h))
