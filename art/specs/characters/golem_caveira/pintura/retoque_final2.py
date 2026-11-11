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
px(59, 7, ORB); px(59, 8, ORB)
px(56, 4, OSSO); px(55, 5, OSSO); px(55, 10, OSSO); px(56, 11, OSSO); px(56, 5, ORB); px(56, 10, ORB)         # ponto central 2x2 (espelhado vira 2 de largura)
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
def espinho(cx0, topo, base, meia, incl=0.0):
    """incl > 0 inclina a ponta para fora (x menor no lado esquerdo)."""
    for y in range(topo, base + 1):
        k = (y - topo) / max(1, base - topo); hw = round(meia * k)
        cx = round(cx0 - incl * (base - y))
        for x in range(cx - hw, cx + hw + 1):
            px(x, y, PED_L if x < cx else (PED if x == cx else PED_S))
        px(cx - hw - 1, y, CONT); px(cx + hw + 1, y, CONT)
    px(round(cx0 - incl * (base - topo)), topo - 1, CONT)

espinho(21, 4, 16, 4, 0.35)   # ombreira: espinho principal, base larga, inclinado para fora
espinho(32, 10, 16, 2, 0.15)  # ombreira: espinho médio
espinho(9, 38, 46, 2, 0.2)    # manopla: espinho no topo externo

# --- peito: primeiro apaga as faixas da redução pintando pelo (x 37-59, y 26-50)
PELO, PELO_S, PELO_L = C("fur", 3), C("fur", 2), C("fur", 4)
PELO_E = C("fur", 1)
for y in range(26, 50):
    recuo = max(0, 3 - (y - 26)) * 2             # cantos de cima arredondados (degraus)
    for x in range(37 + recuo, M):
        if not a[y, x, 3]: continue
        dx = x - 37                              # 0 na lateral .. 22 no meio: barril
        c = PELO_E if dx < 2 else PELO_S if dx < 5 else (PELO_L if (8 <= dx <= 13 and 27 <= y <= 30) else PELO)
        px(x, y, c)

JUNTA = C("fur", 1)
def bloco(x0, y0, bw=4, bh=3):
    for x in range(x0 - 1, x0 + bw + 1):
        px(x, y0 - 1, JUNTA); px(x, y0 + bh, JUNTA)
    for y in range(y0 - 1, y0 + bh + 1):
        px(x0 - 1, y, JUNTA); px(x0 + bw, y, JUNTA)
    for x in range(x0, x0 + bw):
        px(x, y0, PED_L); px(x, y0 + bh - 1, PED_S)
        for y in range(y0 + 1, y0 + bh - 1): px(x, y, PED)

# gola em U: 1 fileira de blocos em volta do crânio
for (x, y, bw) in [(44, 16, 4), (44, 21, 4), (48, 25, 5)]:
    bloco(x, y, bw, 3)

# placas grossas inclinadas, descendo 1 px a cada 3 px em direção ao medalhão (x 60, y 40)
def placa(x0, x1, ytopo, alt=4):
    for x in range(x0, x1 + 1):
        yt = ytopo + (x - x0) // 2
        px(x, yt - 1, CONT); px(x, yt + alt, CONT)
        px(x, yt, PED_L)
        for y in range(yt + 1, yt + alt - 1): px(x, y, PED)
        px(x, yt + alt - 1, PED_S)
    for y in range(ytopo - 1, ytopo + alt + 1): px(x0 - 1, y, CONT)
placa(40, 51, 29)        # placa de cima
placa(42, 52, 37, 3)     # placa de baixo, mais fina
# tufos de pelo na borda de baixo do peito
for x0 in (41, 45, 50, 54):                      # tufos em V sobre o cinto, com ponta clara
    for dy, dx in ((0, 0), (1, 1), (2, 2), (1, 3), (0, 4)):
        px(x0 + dx, 47 + dy, PELO_E)
    px(x0 + 2, 50, PELO_L)
for (x, y) in ((44, 43), (49, 44), (53, 42)):     # traços de pelo
    px(x, y, PELO_S); px(x, y + 1, PELO_S)

# --- saiote: fundo de pelo, 3 escamas pontudas iguais por lado da tanga
for y in range(56, 68):
    for x in range(38, 53):
        if a[y, x, 3]: px(x, y, PELO_E if y > 64 else PELO_S)
def escama(cx, topo, base, meia):
    for y in range(topo, base + 1):
        k = 1 - (y - topo) / max(1, base - topo); hw = round(meia * k)
        for x in range(cx - hw, cx + hw + 1):
            px(x, y, PED_L if x < cx else (PED if x == cx else PED_S))
        px(cx - hw - 1, y, CONT); px(cx + hw + 1, y, CONT)
    px(cx, base + 1, CONT)
for cx in (42, 50):                 # poucas e largas
    escama(cx, 57, 65, 3.6)
# --- cinto: blocos regulares como a gola (desenhado por cima do topo das escamas)
for x in (36, 42, 48, 54):
    bloco(x, 51, 5, 4)

# --- medalhões concêntricos: pedra, laranja, escuro, ponto laranja
import math
RUNA, RUNA_E = C("rune", 2), C("rune", 0)
def medalhao(cx, cy, esc=1.0):
    for y in range(int(cy - 6 * esc), int(cy + 7 * esc)):
        for x in range(int(cx - 6 * esc), M):
            d = math.hypot(x - cx, y - cy) / esc
            if d <= 1.1: px(x, y, RUNA)
            elif d <= 2.1: px(x, y, RUNA_E)
            elif d <= 3.1: px(x, y, RUNA)
            elif d <= 4.2: px(x, y, PED_L)
            elif d <= 5.0: px(x, y, CONT)
medalhao(59.5, 40.5)
medalhao(42.0, 80.0, 0.8)


# ===== polimento final =====
ROCK = {C("rock", i)[:3] for i in range(6)} | {C("skull", 4)[:3], C("skull", 5)[:3], C("skull", 3)[:3]}
# ombreira em 2 tons + aresta clara no topo (x 15-37, y 13-36), sem clusters soltos
for x in range(15, 38):
    col = [y for y in range(17, 37) if a[y, x, 3] and tuple(a[y, x, :3]) in ROCK]
    if not col: continue
    for k, y in enumerate(col):
        px(x, y, PED_L if k == 0 else (PED_S if k >= len(col) - 2 else PED))
# tufos em dente de serra na borda externa do braço e da coxa
def tufos(ys, x_min, x_max):
    for y in ys:
        xe = next((x for x in range(x_min, x_max) if a[y, x, 3]), None)
        if xe is None: continue
        px(xe, y, PELO); px(xe - 1, y, PELO_S); px(xe - 2, y, CONT)
        px(xe - 1, y - 1, CONT); px(xe - 1, y + 1, CONT)
tufos((37, 40, 43), 10, 20)     # braço (borda externa)
tufos((76, 79, 82), 30, 38)     # coxa
# canelas: quebra o paralelismo das faixas (sombra com espessura variando)
for x in range(33, 50):
    if x % 3 == 0 and a[91, x, 3]: px(x, 91, PED_S)
    if x % 4 == 1 and a[92, x, 3]: px(x, 92, PED)
# pés: 3 dedos iguais de osso, com junta escura
OL, OM, OS = C("skull", 5), C("skull", 4), C("skull", 3)
for x0 in (28, 35, 42):
    for x in range(x0, x0 + 6):
        px(x, 100, OL); px(x, 101, OM); px(x, 102, OM); px(x, 103, OS)
    for y in range(99, 105): px(x0 - 1, y, CONT); px(x0 + 6, y, CONT)
    for x in range(x0 - 1, x0 + 7): px(x, 104, CONT)

# espelha a metade esquerda
a[:, w - M:] = a[:, :M][:, ::-1]
Image.fromarray(a).save("frente_final2.png")
bg = Image.new("RGBA", (w, h), (40, 40, 52, 255)); bg.alpha_composite(Image.fromarray(a))
bg.resize((w * 6, h * 6), Image.NEAREST).save("frente_final2_6x.png")
s = Image.new("RGBA", (w, h), (255, 255, 255, 255)); s.paste((0, 0, 0, 255), mask=Image.fromarray(a).getchannel("A"))
s.resize((w * 4, h * 4), Image.NEAREST).save("frente_final2_silhueta.png")
