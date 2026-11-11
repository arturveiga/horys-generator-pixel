"""Retoque à mão da frente do golem: crânio (runa da testa, sobrancelha, nariz, dentes, presas) e espinhos.
Desenha na metade esquerda (x < 60) e espelha. Coordenadas no 1x de frente_v3_base.png (120x109)."""
import numpy as np, yaml
from PIL import Image

a = np.array(Image.open("frente_v3_base.png")); h, w = a.shape[:2]; M = w // 2
pal = yaml.safe_load(open(r"..\..\..\palettes\golem.yaml", encoding="utf-8"))["ramps"]
C = lambda nome, i: tuple(int(pal[nome][i][j:j + 2], 16) for j in (1, 3, 5)) + (255,)
OSSO, OSSO_L, OSSO_S, OSSO_E = C("skull", 4), C("skull", 5), C("skull", 3), C("skull", 2)
ESC, ORB = C("socket", 0), C("socket", 1)
PED_L, PED, PED_S, PED_E = C("rock", 5), C("rock", 4), C("rock", 3), C("rock", 2)
CONT = C("socket", 0)

def px(x, y, c):
    if 0 <= x < M and 0 <= y < h: a[y, x] = c

def linha(y, x0, x1, c):
    for x in range(x0, x1 + 1): px(x, y, c)

# --- runa da testa: anel de círculos concêntricos centrado entre x 59|60, y 7.5
for (x, y) in [(57, 3), (58, 3), (59, 3), (56, 4), (55, 5), (55, 6), (55, 7), (55, 8), (55, 9), (55, 10),
               (56, 11), (57, 12), (58, 12), (59, 12)]:
    px(x, y, ORB)
for y in range(4, 12):                 # limpa o miolo em osso
    for x in range(56 if 4 < y < 11 else 57, 60): px(x, y, OSSO)
px(59, 7, ORB); px(59, 8, ORB)         # ponto central 2x2 (espelhado vira 2 de largura)
# --- sobrancelha em V, escura, logo acima dos olhos (y 14-15)
linha(14, 51, 54, ESC); linha(15, 55, 57, ESC)
# --- nariz: triângulo invertido
linha(19, 58, 59, ESC); px(59, 20, ESC)
# --- dentes: fileira alternada em y 22-23 e presas descendo
for x in range(53, 60):
    c = OSSO_L if x % 2 else ESC
    px(x, 22, c); px(x, 23, c)
for y in (24, 25, 26): px(54, y, OSSO_L); px(53, y, CONT); px(55, y, CONT)
px(54, 27, CONT)

# --- espinhos: triângulo com face clara à esquerda e sombra à direita, contorno escuro
def espinho(cx, topo, base, meia):
    for y in range(topo, base + 1):
        k = (y - topo) / max(1, base - topo); hw = round(meia * k)
        for x in range(cx - hw, cx + hw + 1):
            px(x, y, PED_L if x < cx else (PED if x == cx else PED_S))
        px(cx - hw - 1, y, CONT); px(cx + hw + 1, y, CONT)
    px(cx, topo - 1, CONT)

espinho(19, 4, 15, 3)      # ombreira, espinho grande externo
espinho(30, 7, 16, 2)      # ombreira, espinho do meio
espinho(39, 11, 17, 2)     # ombreira, espinho interno
espinho(9, 38, 46, 2)      # manopla, espinho no topo externo

# espelha a metade esquerda
a[:, w - M:] = a[:, :M][:, ::-1]
Image.fromarray(a).save("frente_v3.png")
bg = Image.new("RGBA", (w, h), (40, 40, 52, 255)); bg.alpha_composite(Image.fromarray(a))
bg.resize((w * 6, h * 6), Image.NEAREST).save("frente_v3_6x.png")
s = Image.new("RGBA", (w, h), (255, 255, 255, 255)); s.paste((0, 0, 0, 255), mask=Image.fromarray(a).getchannel("A"))
s.resize((w * 4, h * 4), Image.NEAREST).save("frente_v3_silhueta.png")
