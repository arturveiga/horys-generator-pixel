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

# ===== polimento 2 =====
FURS = {C("fur", i)[:3] for i in range(5)}
def ehpedra(x, y): return a[y, x, 3] and tuple(a[y, x, :3]) in ROCK
def contorno(x, y): return a[y, x, 3] and tuple(a[y, x, :3]) == CONT[:3]
# base do peito: sombra projetada sobre o cinto, sem pontilhado
for x in range(38, M):
    if a[50, x, 3] and tuple(a[50, x, :3]) in FURS: px(x, 50, PELO_E)
# coxa: 3 tufos regulares (2 px para fora, 3 px de altura, ponta de 1 px)
for yt in (75, 79, 83):
    xe = next((x for x in range(28, 40) if a[yt + 1, x, 3]), None)
    if xe is None: continue
    for dy, out in ((0, 1), (1, 2), (2, 1)):
        for k in range(1, out + 1): px(xe - k, yt + dy, PELO_S)
        px(xe - out - 1, yt + dy, CONT)
    px(xe - 1, yt - 1, CONT); px(xe - 1, yt + 3, CONT)
# dedos dos pés: pedra clara com 1 px creme no topo, canto externo arredondado
for x0 in (28, 35, 42):
    for x in range(x0, x0 + 6):
        px(x, 100, OL); px(x, 101, PED_L); px(x, 102, PED); px(x, 103, PED_S)
    px(x0, 100, CONT)
# saiote: limpa até a tanga e redesenha 2 escamas largas por lado
for y in range(56, 68):
    for x in range(36, 55):
        if a[y, x, 3] and not contorno(x, y): px(x, y, PELO_E if y > 64 else PELO_S)
for cx in (42, 50):
    escama(cx, 57, 64, 3.9)

# ===== polimento 3: manopla limpa por dentro, sem mudar a forma =====
NOISE = ROCK | {C("socket", 1)[:3], C("socket", 2)[:3]}
def recolor_faixa(y0, y1, x0=0, x1=26):
    for x in range(x0, x1):
        col = [y for y in range(y0, y1 + 1) if a[y, x, 3] and tuple(a[y, x, :3]) in NOISE]
        for k, y in enumerate(col):
            px(x, y, PED_L if k == 0 else (PED_S if k >= len(col) - 2 else PED))
recolor_faixa(48, 57)                       # faixa 1
for x in range(2, 26):                      # junta entre faixas, seguindo a borda
    if a[58, x, 3] and tuple(a[58, x, :3]) in NOISE: px(x, 58, JUNTA)
recolor_faixa(59, 68, 0, 14)                # faixa 2 (só a parte de pedra)
FIST = NOISE | FURS
for y in range(69, 76):                     # punho de pedra: nós claros em cima, 2 juntas curtas embaixo
    for x in range(0, 20):
        if a[y, x, 3] and tuple(a[y, x, :3]) in FIST:
            c = PED_L if y == 69 else (PED_S if y >= 74 else PED)
            if y >= 72 and x in (6, 11): c = JUNTA
            px(x, y, c)
# base do peito sem xadrez
for x in range(38, M):
    if a[47, x, 3] and tuple(a[47, x, :3]) in FURS: px(x, 47, PELO_E)
    if a[48, x, 3] and tuple(a[48, x, :3]) in FURS: px(x, 48, PELO_E)
    if a[46, x, 3] and tuple(a[46, x, :3]) in FURS: px(x, 46, PELO_S)
for x0 in (41, 45, 50, 54):                 # tufos em V de novo por cima
    for dy, dx in ((0, 0), (1, 1), (2, 2), (1, 3), (0, 4)): px(x0 + dx, 44 + dy, PELO_E)
    px(x0 + 2, 47, PELO_L)
# ombreira: sombra média de 2 px na base de cada coluna
for x in range(15, 38):
    col = [y for y in range(17, 37) if a[y, x, 3] and tuple(a[y, x, :3]) in ROCK]
    for y in col[-2:]: px(x, y, PED_S)

# ===== polimento 4 =====
from scipy import ndimage as nd
def merge_pequenos(x0, x1, y0, y1, grupo, minimo=3):
    """Funde grupos < minimo px à cor vizinha dominante, só dentro do mesmo material (grupo de cores)."""
    sub = a[y0:y1, x0:x1]
    key = sub[..., 0].astype(int) * 65536 + sub[..., 1].astype(int) * 256 + sub[..., 2]
    ok = np.array([[sub[y, x, 3] > 0 and tuple(sub[y, x, :3]) in grupo for x in range(sub.shape[1])] for y in range(sub.shape[0])])
    for c in np.unique(key[ok]):
        lab, n = nd.label((key == c) & ok)
        for i in range(1, n + 1):
            ys, xs = np.where(lab == i)
            if len(ys) >= minimo: continue
            viz = [key[yy, xx] for y, x in zip(ys, xs) for yy, xx in ((y-1,x),(y+1,x),(y,x-1),(y,x+1))
                   if 0 <= yy < key.shape[0] and 0 <= xx < key.shape[1] and ok[yy, xx] and key[yy, xx] != c]
            if viz:
                v = max(set(viz), key=viz.count)
                for y, x in zip(ys, xs): sub[y, x, :3] = (v >> 16, (v >> 8) & 255, v & 255)
merge_pequenos(10, 37, 34, 47, FURS)          # braço
merge_pequenos(28, 58, 84, 99, ROCK)          # canelas
merge_pequenos(30, 50, 72, 86, FURS)          # pelo em volta do joelho
# braço: direção de luz (escuro na borda interna, médio no alto da externa)
for y in range(34, 47):
    xs = [x for x in range(10, 37) if a[y, x, 3] and tuple(a[y, x, :3]) in FURS]
    if not xs: continue
    for x in xs[-2:]: px(x, y, PELO_E)
    if y <= 39:
        for x in xs[:2]: px(x, y, PELO)
# canelas: junta escura contínua entre as faixas (linha mais escura da coluna vira junta)
for x in range(30, 57):
    col = [y for y in range(86, 98) if a[y, x, 3] and tuple(a[y, x, :3]) in ROCK]
    if len(col) > 6: px(x, col[len(col) * 4 // 7], JUNTA)
# manopla: junta até o contorno externo e oclusão no encontro com o braço
for x in range(0, 8):
    if a[58, x, 3] and not contorno(x, 58): px(x, 58, JUNTA)
for x in range(4, 24):
    if a[47, x, 3] and not contorno(x, 47): px(x, 47, PELO_E)
# base do peito contínua acima da faixa escura (sem pontilhado), tufos por cima
for x in range(38, M):
    for y in (42, 43):
        if a[y, x, 3] and tuple(a[y, x, :3]) in FURS: px(x, y, PELO)
# entalhe da ombreira perto do espinho médio
px(34, 17, PED_L); px(33, 17, PED_L)
# pontas ligadas só na diagonal (contorno serrilhado das coxas e braços): apaga
for y in range(30, 100):
    for x in range(1, M - 1):
        if not a[y, x, 3]: continue
        orto = sum(a[yy, xx, 3] > 0 for yy, xx in ((y-1,x),(y+1,x),(y,x-1),(y,x+1)))
        if orto == 0: a[y, x] = (0, 0, 0, 0)

# ===== polimento 5 =====
PED_SS = C("rock", 2)
# base do peito em faixas chapadas + 4 tufos em V (2 por lado)
for x in range(38, M):
    for y, c in ((42, PELO), (43, PELO), (44, PELO), (45, PELO), (46, PELO_S), (47, PELO_E), (48, PELO_E)):
        if a[y, x, 3] and tuple(a[y, x, :3]) in FURS: px(x, y, c)
for x0 in (44, 52):
    px(x0, 44, PELO_E); px(x0 + 1, 45, PELO_E); px(x0 + 2, 44, PELO_E); px(x0 + 1, 46, PELO_L)
# sujeira escura dentro da placa da ombreira
for y in range(16, 22):
    for x in range(29, 37):
        if a[y, x, 3] and tuple(a[y, x, :3]) not in ROCK:
            viz = sum(1 for yy, xx in ((y-1,x),(y+1,x),(y,x-1),(y,x+1)) if a[yy, xx, 3] and tuple(a[yy, xx, :3]) in ROCK)
            if viz >= 3: px(x, y, PED)
# espinho da manopla sólido (base 5, altura 5)
for y in range(36, 47):
    for x in range(4, 14):
        if a[y, x, 3] and tuple(a[y, x, :3]) in ROCK | {CONT[:3]} and y < 44: a[y, x] = (0, 0, 0, 0)
espinho(8, 38, 43, 2, 0)
# saiote: escamas iguais, base 7, 1 px de roxo escuro entre elas
for y in range(56, 67):
    for x in range(36, 55):
        if a[y, x, 3] and not contorno(x, y): px(x, y, PELO_E if y > 64 else PELO_S)
for cx in (42, 50):
    escama(cx, 57, 64, 3.0)
# manopla faixa 1: sombra um tom abaixo da face
for x in range(0, 26):
    col = [y for y in range(48, 58) if a[y, x, 3] and tuple(a[y, x, :3]) in ROCK]
    for y in col[-2:]: px(x, y, PED_SS)

# ===== polimento 6 =====
# coxa: apaga o serrilhado miúdo e põe 3 tufos regulares (base 2, ponta 1, 3 px entre eles)
for y in range(73, 87):
    for x in range(26, 35):
        a[y, x] = (0, 0, 0, 0)
    xe = next((x for x in range(35, 45) if a[y, x, 3]), None)
    if xe is not None and tuple(a[y, xe, :3]) != CONT[:3]: px(xe, y, CONT)
for yt in (75, 80, 85):
    xe = next((x for x in range(34, 45) if a[yt, x, 3]), 35)
    px(xe, yt - 1, PELO_S); px(xe - 1, yt, PELO_S); px(xe, yt, PELO_S); px(xe, yt + 1, PELO_S)
    px(xe, yt - 2, CONT); px(xe - 1, yt - 1, CONT); px(xe - 2, yt, CONT); px(xe - 1, yt + 1, CONT); px(xe, yt + 2, CONT)
# canelas: sem creme (só pedra clara na aresta)
for y in range(86, 99):
    for x in range(28, 58):
        if a[y, x, 3] and tuple(a[y, x, :3]) in {C("skull", i)[:3] for i in range(6)} | {C("socket", 2)[:3]}:
            px(x, y, PED_L)
# ombreira: borda inferior em degraus regulares 3-2-1 descendo para fora
for x in range(12, 38):
    col = [y for y in range(20, 38) if a[y, x, 3] and tuple(a[y, x, :3]) in ROCK]
    if not col: continue
    alvo = 30 + max(0, (26 - x)) // 3          # mais baixo para fora
    for y in col:
        if y > alvo + 2: px(x, y, PELO)

# espelha a metade esquerda
a[:, w - M:] = a[:, :M][:, ::-1]

# runa da tanga (assimétrica: desenhada depois do espelho) - espiral quadrado + raio em zigue-zague
RN = C("rune", 2); PEDT = C("rock", 4)
for y in range(61, 76):
    for x in range(56, 64):
        if a[y, x, 3] and tuple(a[y, x, :3]) in {C("rune", i)[:3] for i in range(5)}: a[y, x] = PEDT
for (x, y) in [(57,62),(58,62),(59,62),                         # topo, canto direito aberto
               (57,63),(57,64),(57,65),(57,66),                 # lado esquerdo
               (58,66),(59,66),(60,66),(61,66),(61,65),(61,64),(61,63), # base e lado direito
               (60,64),(59,64),                                 # gancho para dentro
               (59,67),(59,68),(58,68),(58,69),(58,70),(59,70),(60,70),(60,71),(60,72),(59,72),(59,73),(59,74)]:
    a[y, x] = RN


Image.fromarray(a).save("frente_final8.png")
bg = Image.new("RGBA", (w, h), (40, 40, 52, 255)); bg.alpha_composite(Image.fromarray(a))
bg.resize((w * 6, h * 6), Image.NEAREST).save("frente_final8_6x.png")
s = Image.new("RGBA", (w, h), (255, 255, 255, 255)); s.paste((0, 0, 0, 255), mask=Image.fromarray(a).getchannel("A"))
s.resize((w * 4, h * 4), Image.NEAREST).save("frente_final8_silhueta.png")
