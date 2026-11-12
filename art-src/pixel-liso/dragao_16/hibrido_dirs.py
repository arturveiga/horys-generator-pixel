"""Vistas de cima do dragão (frente s e costas n): base do SpriteKiln + cabeça e asas desenhadas à mão no Liso,
ancoradas nos sockets de cada direção. As peças são desenho meu; o script só posiciona (e espelha a asa para o outro lado).
    python hibrido_dirs.py -> hibrido/idle_s.grade, hibrido/idle_n.grade"""
import json, os, numpy as np
from PIL import Image
K = '../../../art/specs/characters/dragao_16_base/out/dragao_16_base/'
PAL = {'r': '#aa455a', 'c': '#db6d60', 'l': '#f2a67f', 'a': '#e9b452', 'y': '#f7e09b', 'v': '#855290', 'w': '#c082a5', 'o': '#18122c', 'b': '#fcf7e8'}
RGB = {k: np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], float) for k, h in PAL.items()}
HEAD_S = ['.y.....y.', '.yclllcy.', 'clllllllc', 'cloblbolc', 'clolllolc', '.ccaaacc.', '..rrrrr..']
HEAD_N = ['.y.....y.', '.yclllcy.', 'clllllllc', 'cllllllcc', '.rcccccr.']
# asa direita vista de cima (raiz na coluna 0); a esquerda é o espelho
WING = {
 'UP':   (['.......vv.', '......vwwv', '.....vwwwv', '...vvwwwv.', '..vwwwwv..', 'vvwwwwv...'], (0, 5)),
 'MID':  (['.vvvvvvvv.', 'vwwwwwwwwv', '.vvwwwvvv.'], (0, 1)),
 'DOWN': (['vvwwwwv...', '.vwwwwwvv.', '..vwwwwwwv', '....vvvwwv', '......vvv.'], (0, 0)),
}
IDLE_WINGS = ['UP', 'MID', 'DOWN', 'MID']
d = json.load(open(K + 'dragao_16_base.json')); atl = Image.open(K + 'dragao_16_base.png').convert('RGBA'); sk = d['spritekiln']
def nearest(c): return min(RGB, key=lambda k: ((RGB[k] - c) ** 2).sum())
def put(g, rows, anchor, at, flip=False):
    if flip: rows = [r[::-1] for r in rows]; anchor = (len(rows[0]) - 1 - anchor[0], anchor[1])
    ox, oy = int(round(at[0])) - anchor[0], int(round(at[1])) - anchor[1]
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch != '.' and 0 <= oy + j < g.shape[0] and 0 <= ox + i < g.shape[1]: g[oy + j, ox + i] = ch
def comp(dn, head, hanchor):
    a = sk['animations']['idle']['directions'][dn]; frames = []
    for i, f in enumerate(a['frames']):
        r = d['frames'][f]['frame']; im = np.array(atl.crop((r['x'], r['y'], r['x'] + r['w'], r['y'] + r['h'])))
        g = np.full((48, 48), '.', dtype='<U1')
        for y in range(48):
            for x in range(48):
                if im[y, x, 3] >= 250: g[y, x] = nearest(im[y, x, :3].astype(float))
        so = a['sockets']; wp = (24 + so['wing_pt'][i][0], 31 + so['wing_pt'][i][1]); hp = (24 + so['head_pt'][i][0], 31 + so['head_pt'][i][1])
        w = WING[IDLE_WINGS[i]]
        put(g, w[0], w[1], wp, flip=wp[0] < 24); put(g, w[0], w[1], (48 - wp[0] - 1, wp[1]), flip=wp[0] >= 24)
        put(g, head, hanchor, hp); frames.append(g)
    ys, xs = np.where(np.any([f != '.' for f in frames], 0)); y0, y1, x0, x1 = ys.min() - 1, ys.max() + 1, xs.min() - 1, xs.max() + 1
    W = x1 - x0 + 1
    out = f'nome dragao_16\nestado idle_{dn}\ntipo criatura\nquadro {max(32, ((W + 7) // 8) * 8 + 8)}\npivo {24 - x0} {31 - y0}\nms 150\ncontorno suave\ncor_contorno #18122c\nsombra sim\nlimite_cores 11\ncores\n'
    out += ''.join(f'  {k} {h}\n' for k, h in PAL.items())
    for i, g in enumerate(frames):
        out += f'--- q{i}\n' + '\n'.join(''.join(g[y, x0:x1 + 1]) for y in range(y0, y1 + 1)) + '\n'
    open(f'hibrido/idle_{dn}.grade', 'w', encoding='utf-8').write(out); print(dn, W, y1 - y0 + 1)
comp('s', HEAD_S, (4, 3)); comp('n', HEAD_N, (4, 2))
