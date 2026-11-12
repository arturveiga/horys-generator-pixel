"""Híbrido: base do SpriteKiln (corpo, cauda, pernas, fogo) + peças desenhadas à mão no Liso (cabeça, chifre, asas),
ancoradas nos sockets do SpriteKiln (head_pt, wing_pt). As peças abaixo são desenho meu, quadro a quadro; o script só posiciona.
    python hibrido_compor.py  ->  hibrido/<estado>.grade"""
import json, os, numpy as np
from PIL import Image
K = '../../../art/specs/characters/dragao_16_base/out/dragao_16_base/'
PAL = {'r': '#aa455a', 'c': '#db6d60', 'l': '#f2a67f', 'a': '#e9b452', 'y': '#f7e09b', 'v': '#855290', 'w': '#c082a5', 'o': '#18122c', 'b': '#fcf7e8'}
RGB = {k: tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) for k, h in PAL.items()}
# ---- peças à mão (anchor = (coluna, linha) da peça que cai no socket)
HEAD = ['yy.......', '.yy......', '..clllc..', '.cllllcc.', '.clcobcc.', '.cccocccc', '.ccaaaacc', '..rrrrr..']
HEAD_OPEN = HEAD[:6] + ['.cooooocc', '..rrrrr..']
WING = {
 'UP':   (['...vvvv...', 'vvwwwwwv..', 'vwwwwwwwv.', '.vwwwwwwv.', '..vwwwwwwv', '....vvwwwv', '......vwwv'], (7, 7)),
 'MID':  (['.....vvvv..', '..vvwwwwwv.', 'vwwwwwwwwwv', '..vwwwv....'], (8, 4)),
 'DOWN': (['vwwwwwv', '..vwwwv'], (7, 0)),
}
FAR = (['.vv.', 'vwwv', 'vwwv', 'vwwv'], (2, 4))
HEAD_A = (4, 4)
PLAN = {   # estado: (animação do SpriteKiln, [asa por quadro], [far por quadro], [boca aberta por quadro], ms)
 'idle':     ('idle',   ['UP', 'MID', 'DOWN', 'MID'], [0, 0, 0, 0], [0, 0, 0, 0], 150),
 'voo':      ('fly',    ['UP', 'MID', 'DOWN', 'MID'], [0, 0, 1, 0], [0, 0, 0, 0], 100),
 'baforada': ('attack', ['UP', 'DOWN', 'MID', 'MID'], [0, 0, 0, 0], [0, 1, 1, 0], 120),
}
OFF = json.load(open('hibrido_off.json')) if os.path.exists('hibrido_off.json') else {'head': [0, 0], 'wing': [0, 0], 'far': [0, 0]}
d = json.load(open(K + 'dragao_16_base.json')); atl = Image.open(K + 'dragao_16_base.png').convert('RGBA'); sk = d['spritekiln']
px = [(k, np.array(v, float)) for k, v in RGB.items()]
def nearest(c): return min(px, key=lambda kv: ((kv[1] - c) ** 2).sum())[0]
def stamp(g, rows, anchor, at):
    ax, ay = anchor; ox, oy = int(round(at[0])) - ax, int(round(at[1])) - ay
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch != '.' and 0 <= oy + j < g.shape[0] and 0 <= ox + i < g.shape[1]: g[oy + j, ox + i] = ch
os.makedirs('hibrido', exist_ok=True)
for est, (anim, wings, fars, mouths, ms) in PLAN.items():
    a = sk['animations'][anim]['directions']['e']; frames = []
    for i, f in enumerate(a['frames']):
        r = d['frames'][f]['frame']; im = np.array(atl.crop((r['x'], r['y'], r['x'] + r['w'], r['y'] + r['h'])))
        g = np.full((48, 48), '.', dtype='<U1')
        so0 = a['sockets']; wp0 = (24 + so0['wing_pt'][i][0], 31 + so0['wing_pt'][i][1])
        fw = WING[wings[i]]; stamp(g, [r.replace('w', 'v') for r in fw[0]], fw[1], (wp0[0] + 2 + OFF['far'][0], wp0[1] - 3 + OFF['far'][1]))
        for y in range(48):
            for x in range(48):
                if im[y, x, 3] >= 250: g[y, x] = nearest(im[y, x, :3].astype(float))
        so = a['sockets']; S = lambda n: (24 + so[n][i][0], 31 + so[n][i][1])
        wp = S('wing_pt'); hp = S('head_pt')
        w = WING[wings[i]]; stamp(g, w[0], w[1], (wp[0] + OFF['wing'][0], wp[1] + OFF['wing'][1]))
        stamp(g, HEAD_OPEN if mouths[i] else HEAD, HEAD_A, (hp[0] + OFF['head'][0], hp[1] + OFF['head'][1]))
        frames.append(g)
    ys, xs = np.where(np.any([f != '.' for f in frames], 0)); y0, y1, x0, x1 = ys.min() - 1, ys.max() + 1, xs.min() - 1, xs.max() + 1
    W = x1 - x0 + 1
    out = f'nome dragao_16\nestado {est}\ntipo criatura\nquadro {max(32, ((W + 7) // 8) * 8 + 8)}\npivo {24 - x0} {31 - y0}\nms {ms}\ncontorno suave\ncor_contorno #18122c\nsombra sim\nlimite_cores 11\ncores\n'
    out += ''.join(f'  {k} {h}\n' for k, h in PAL.items())
    for i, g in enumerate(frames):
        out += f'--- q{i}\n' + '\n'.join(''.join(g[y, x0:x1 + 1]) for y in range(y0, y1 + 1)) + '\n'
    open(f'hibrido/{est}.grade', 'w', encoding='utf-8').write(out); print(est, W, y1 - y0 + 1)
