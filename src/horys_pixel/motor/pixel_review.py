#!/usr/bin/env python3
"""pixel_review.py — revisão técnica de pixel art (PNG) com overlay dos problemas.

Mede o que dá para medir e marca na imagem; o julgamento visual continua com quem revisa.

Uso:
  python pixel_review.py sprite.png [outro.png ...] [opções]

Opções:
  --frames N | --frame-size WxH   tira de quadros; sem isso lê <png>.json (atlas Noct/Aseprite) se existir
  --view front|side|back|other    simetria só em front (padrão: other)
  --palette ARQ                   .hex/.gpl/.md/.txt: toda cor #RRGGBB (e "R G B" no .gpl)
  --outline HEX                   cor do contorno (padrão: a mais comum na borda da figura)
  --ignore HEX[,HEX...]           cores que, ligadas ao fundo, não contam como figura (ex.: sombra no chão)
  --bg HEX                        fundo dos previews (padrão #718555, grama do Hunvix)
  --zoom N                        ampliação do overlay (padrão 10)
  --out DIR                       pasta de saída (padrão: <pasta do png>/review)
  --mockup                        imagem que não é pixel art nativa (tela, conceito, IA): mede cores,
                                  ruído e aderência à grade em vez das checagens de sprite
  --json                          imprime o relatório em JSON

Uso como biblioteca (ferramenta MCP): medir_arquivo(caminhos, paleta=None, fundo=None, ...) -> dict

Requer Pillow e numpy.
"""
import argparse
import json
import os
import re
import sys
from collections import Counter, deque
from types import SimpleNamespace

import numpy as np
from PIL import Image, ImageDraw, ImageFont

NEI4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
NEI8 = NEI4 + ((1, 1), (1, -1), (-1, 1), (-1, -1))
MARK = {  # tipo -> (cor do marcador, legenda)
    'fora_paleta': ((255, 255, 255), 'fora da paleta'),
    'orfao': ((255, 40, 40), 'pixel órfão'),
    'duplo': ((255, 214, 0), 'contorno dobrado no degrau'),
    'degrau': ((0, 220, 255), 'degrau irregular / dente'),
    'assimetria': ((255, 0, 200), 'assimetria'),
}


def legend_font():
    for name in ('arial.ttf', 'DejaVuSans.ttf', 'Arial.ttf', 'Helvetica.ttc'):
        try:
            return ImageFont.truetype(name, 13)
        except Exception:
            continue
    return ImageFont.load_default()


def hx(rgb):
    return '#%02X%02X%02X' % tuple(int(c) for c in rgb[:3])


def parse_hex(s):
    s = s.strip().lstrip('#')
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def luminance(rgb):
    r, g, b = (float(c) for c in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def load_palette(path):
    txt = open(path, encoding='utf-8', errors='ignore').read()
    cols = {'#' + m[1:].upper() for m in re.findall(r'#[0-9A-Fa-f]{6}', txt)}
    if path.lower().endswith('.gpl'):
        for line in txt.splitlines():
            p = line.split()
            if len(p) >= 3 and all(t.isdigit() for t in p[:3]):
                cols.add(hx([int(t) for t in p[:3]]))
    return cols


def load_frames(path, args):
    a = np.array(Image.open(path).convert('RGBA'))
    H, W = a.shape[:2]
    tags, rects = {}, None
    if args.frame_size:
        fw, fh = (int(v) for v in args.frame_size.lower().split('x'))
        rects = [(x, y, fw, fh) for y in range(0, H, fh) for x in range(0, W, fw)]
    elif args.frames:
        fw = W // args.frames
        rects = [(i * fw, 0, fw, H) for i in range(args.frames)]
    else:
        js = os.path.splitext(path)[0] + '.json'
        if os.path.exists(js):
            try:
                meta = json.load(open(js, encoding='utf-8'))
                fr = meta.get('frames')
                items = list(fr.values()) if isinstance(fr, dict) else (fr or [])
                rects = []
                for it in items:
                    r = it.get('frame', it)
                    rects.append((r['x'], r['y'], r.get('w', r.get('width')), r.get('h', r.get('height'))))
                m = meta.get('meta', {}) or {}
                if isinstance(m.get('animations'), dict):
                    tags = {k: list(v) for k, v in m['animations'].items()}
                for t in m.get('frameTags', []) or []:
                    tags[t['name']] = list(range(t['from'], t['to'] + 1))
            except Exception as e:  # atlas estranho: segue como imagem única
                print(f'aviso: atlas {js} ignorado ({e})', file=sys.stderr)
                rects, tags = None, {}
    if not rects:
        rects = [(0, 0, W, H)]
    return [a[y:y + h, x:x + w].copy() for (x, y, w, h) in rects], tags


def figure_mask(f, ignore):
    """Figura = pixels opacos que não fazem parte do fundo. O fundo é o transparente ligado à borda
    do quadro, incluindo as cores de --ignore quando encostam nele (sombra no chão)."""
    H, W = f.shape[:2]
    opaque = f[:, :, 3] > 0
    ign = np.zeros((H, W), bool)
    for c in ignore:
        ign |= opaque & (f[:, :, 0] == c[0]) & (f[:, :, 1] == c[1]) & (f[:, :, 2] == c[2])
    passable = (~opaque) | ign
    bg = np.zeros((H, W), bool)
    q = deque()
    for x in range(W):
        for y in (0, H - 1):
            if passable[y, x] and not bg[y, x]:
                bg[y, x] = True
                q.append((x, y))
    for y in range(H):
        for x in (0, W - 1):
            if passable[y, x] and not bg[y, x]:
                bg[y, x] = True
                q.append((x, y))
    while q:
        x, y = q.popleft()
        for dx, dy in NEI4:
            X, Y = x + dx, y + dy
            if 0 <= X < W and 0 <= Y < H and passable[Y, X] and not bg[Y, X]:
                bg[Y, X] = True
                q.append((X, Y))
    return opaque & ~bg


def same(f, x, y, c):
    return tuple(int(v) for v in f[y, x, :3]) == c


def find_orphans(f, mask):
    H, W = mask.shape
    out = []
    for y, x in zip(*np.nonzero(mask)):
        c = tuple(int(v) for v in f[y, x, :3])
        if not any(0 <= x + dx < W and 0 <= y + dy < H and mask[y + dy, x + dx] and same(f, x + dx, y + dy, c)
                   for dx, dy in NEI8):
            out.append((int(x), int(y)))
    return out


def outline_color(f, mask):
    H, W = mask.shape
    cnt = Counter()
    for y, x in zip(*np.nonzero(mask)):
        if any(not (0 <= x + dx < W and 0 <= y + dy < H) or not mask[y + dy, x + dx] for dx, dy in NEI4):
            cnt[tuple(int(v) for v in f[y, x, :3])] += 1
    return cnt.most_common(1)[0][0] if cnt else None


def find_doubles(f, mask, oc):
    """Contorno com 'L' num degrau: o pixel do canto engrossa a diagonal (pixel duplo fora da quina).
    Quinas de verdade (dois braços retos de 2+ px) não contam."""
    H, W = mask.shape
    O = mask & (f[:, :, 0] == oc[0]) & (f[:, :, 1] == oc[1]) & (f[:, :, 2] == oc[2])

    def o(x, y):
        return 0 <= x < W and 0 <= y < H and bool(O[y, x])

    def arm(x, y, dx, dy):
        n, X, Y = 0, x + dx, y + dy
        while o(X, Y):
            n, X, Y = n + 1, X + dx, Y + dy
        return n

    out = []
    for y, x in zip(*np.nonzero(O)):
        hit = False
        for hdx in (-1, 1):
            for vdy in (-1, 1):
                if o(x + hdx, y) and o(x, y + vdy) and not o(x + hdx, y + vdy):
                    if min(arm(x, y, hdx, 0), arm(x, y, 0, vdy)) == 1:
                        hit = True
        if hit:
            out.append((int(x), int(y)))
    return out


def jaggies_profile(idx, vals):
    """Borda externa (uma posição por linha ou coluna). Marca 'dentes' (1 px que vai e volta) e degraus
    irregulares (2-1-2, 1-3-1...) dentro de um trecho que anda sempre para o mesmo lado."""
    groups = []
    for i, v in zip(idx, vals):
        if groups and groups[-1][2] == v and i == groups[-1][0] + groups[-1][1]:
            groups[-1][1] += 1
        else:
            groups.append([i, 1, v])
    issues = []
    for j in range(1, len(groups) - 1):
        a, b, c = groups[j - 1], groups[j], groups[j + 1]
        if a[2] == c[2] and b[2] != a[2] and b[1] <= 1 and abs(b[2] - a[2]) == 1:
            issues.append((b[0], b[2], 'dente'))
    segs, cur, sign = [], [], 0
    for j in range(len(groups) - 1):
        dx = groups[j + 1][2] - groups[j][2]
        if dx == 0:
            continue
        sg = 1 if dx > 0 else -1
        if cur and sg != sign:
            segs.append(cur)
            cur = []
        sign = sg
        cur.append((groups[j][0], groups[j][2], groups[j][1] / abs(dx)))
    if cur:
        segs.append(cur)
    for seg in segs:
        for k in range(1, len(seg) - 1):
            s0, s1, s2 = seg[k - 1][2], seg[k][2], seg[k + 1][2]
            if ((s1 > s0 and s1 > s2) or (s1 < s0 and s1 < s2)) and abs(s0 - s2) <= 0.5 * max(s0, s2):
                issues.append((seg[k][0], seg[k][1], 'degrau'))
    return issues


def find_jaggies(mask):
    pts = []
    rows = [y for y in range(mask.shape[0]) if mask[y].any()]
    if rows:
        xl = [int(np.nonzero(mask[y])[0].min()) for y in rows]
        xr = [int(np.nonzero(mask[y])[0].max()) for y in rows]
        for (y, x, _k) in jaggies_profile(rows, xl) + jaggies_profile(rows, xr):
            pts.append((x, y))
    cols = [x for x in range(mask.shape[1]) if mask[:, x].any()]
    if cols:
        yt = [int(np.nonzero(mask[:, x])[0].min()) for x in cols]
        for (x, y, _k) in jaggies_profile(cols, yt):
            pts.append((x, y))
    return sorted(set(pts))


def find_asymmetry(mask):
    ys, xs = np.nonzero(mask)
    if not len(xs):
        return [], 0.0
    axis2 = int(xs.min() + xs.max())
    out = []
    for y, x in zip(ys, xs):
        mx = axis2 - x
        if not (0 <= mx < mask.shape[1] and mask[y, mx]):
            out.append((int(x), int(y)))
    return out, len(out) / len(xs)


def metrics(mask):
    ys, xs = np.nonzero(mask)
    if not len(xs):
        return None
    return {'x0': int(xs.min()), 'y0': int(ys.min()), 'x1': int(xs.max()), 'y1': int(ys.max()),
            'largura': int(xs.max() - xs.min() + 1), 'altura': int(ys.max() - ys.min() + 1),
            'pes_y': int(ys.max()), 'topo_y': int(ys.min()), 'centro_x': round(float(xs.mean()), 2)}


def review_frame(f, args, palette, ignore, bgc):
    H, W = f.shape[:2]
    mask = figure_mask(f, ignore)
    rep = {'quadro': f'{W}x{H}', 'erros': [], 'avisos': [], 'marcas': {}}
    alpha = f[:, :, 3]
    semi = int(((alpha > 0) & (alpha < 255)).sum())
    if semi:
        rep['erros'].append(f'{semi} px com alpha parcial (antialiasing/blur): pixel art pede alpha 0 ou 255')
    m = metrics(mask)
    rep['metricas'] = m
    if m is None:
        rep['avisos'].append('quadro vazio')
        return rep, mask
    if m['x0'] == 0 or m['y0'] == 0 or m['x1'] == W - 1 or m['y1'] == H - 1:
        rep['erros'].append('a figura encosta na borda do quadro (corte ou falta de folga)')
    cols = Counter(hx(f[y, x]) for y, x in zip(*np.nonzero(mask)))
    rep['cores'] = len(cols)
    rep['paleta_usada'] = dict(cols.most_common())
    if len(cols) > 16:
        rep['avisos'].append(f'{len(cols)} cores na figura (personagem/prop: até ~16)')
    if '#000000' in cols:
        rep['erros'].append(f'preto puro em {cols["#000000"]} px (contorno pede o tom escuro da rampa)')
    if palette:
        off = {c: n for c, n in cols.items() if c not in palette}
        if off:
            rep['erros'].append('cores fora da paleta: ' + ', '.join(f'{c} ({n} px)' for c, n in off.items()))
            rep['marcas']['fora_paleta'] = [(int(x), int(y)) for y, x in zip(*np.nonzero(mask)) if hx(f[y, x]) in off]
    orf = find_orphans(f, mask)
    if orf:
        rep['avisos'].append(f'{len(orf)} pixel(s) órfão(s) (sem vizinho da mesma cor): ruído, a menos que seja brilho de propósito')
        rep['marcas']['orfao'] = orf
    oc = parse_hex(args.outline) if args.outline else outline_color(f, mask)
    rep['contorno'] = hx(oc) if oc else None
    if oc:
        dbl = find_doubles(f, mask, oc)
        if dbl:
            rep['avisos'].append(f'{len(dbl)} px de contorno dobrado em degrau (pixel duplo fora da quina engrossa a linha)')
            rep['marcas']['duplo'] = dbl
        if bgc is not None:
            dl = abs(luminance(oc) - luminance(bgc))
            if dl < 40:
                rep['avisos'].append(f'contorno {hx(oc)} com pouco contraste com o fundo (ΔL={dl:.0f})')
    jag = find_jaggies(mask)
    if jag:
        rep['avisos'].append(f'{len(jag)} ponto(s) de borda externa com dente ou degrau irregular')
        rep['marcas']['degrau'] = jag
    if args.view == 'front':
        asym, ratio = find_asymmetry(mask)
        rep['assimetria_silhueta'] = round(ratio * 100, 1)
        if ratio > 0.04:
            rep['avisos'].append(f'silhueta {ratio * 100:.1f}% assimétrica (vista de frente): confira se é intencional')
        rep['marcas']['assimetria'] = asym
    if bgc is not None:
        ys, xs = np.nonzero(mask)
        lb = luminance(bgc)
        close = sum(1 for y, x in zip(ys, xs) if abs(luminance(f[y, x]) - lb) < 18)
        share = close / len(xs)
        rep['mistura_com_fundo'] = round(share * 100, 1)
        if share > 0.25:
            rep['avisos'].append(f'{share * 100:.0f}% da figura tem valor parecido com o fundo {hx(bgc)}: pode sumir no chão')
    return rep, mask


def review_animation(frames, masks, reps, tags):
    out = []
    groups = tags or ({'todos': list(range(len(frames)))} if len(frames) > 1 else {})
    for name, idx in groups.items():
        ms = [reps[i]['metricas'] for i in idx if reps[i].get('metricas')]
        if len(ms) < 2:
            continue
        pes = sorted({m['pes_y'] for m in ms})
        alt = sorted({m['altura'] for m in ms})
        cx = [m['centro_x'] for m in ms]
        info = {'tag': name, 'quadros': idx, 'pes_y': pes, 'alturas': alt,
                'deriva_centro_x': round(max(cx) - min(cx), 2), 'pixels_mudados': [], 'avisos': []}
        if pes[-1] - pes[0] > 1:
            info['avisos'].append(f'linha dos pés varia {pes[-1] - pes[0]} px (apoio instável; ideal ≤ 1)')
        if alt[-1] - alt[0] > 3:
            info['avisos'].append(f'altura varia {alt[-1] - alt[0]} px entre quadros (volume/escala instável)')
        for a, b in zip(idx, idx[1:] + idx[:1]):
            fa, fb = frames[a], frames[b]
            if fa.shape != fb.shape:
                continue
            diff = int((np.abs(fa.astype(int) - fb.astype(int)).sum(axis=2) > 0).sum())
            info['pixels_mudados'].append(diff)
            moving = any(k in name.lower() for k in ('walk', 'run', 'attack', 'anda', 'corr', 'ataq'))
            if diff == 0 and moving and a != b:
                info['avisos'].append(f'quadros {a} e {b} idênticos num movimento contínuo (quadro parado)')
        out.append(info)
    return out


def compare_assets(results):
    """Mesmo personagem em vistas diferentes: altura e linha dos pés precisam bater."""
    base = [(r['arquivo'], r['quadros'][0].get('metricas')) for r in results if r['quadros'] and r['quadros'][0].get('metricas')]
    if len(base) < 2:
        return []
    out = []
    alts = {os.path.basename(f): m['altura'] for f, m in base}
    pes = {os.path.basename(f): m['pes_y'] for f, m in base}
    if max(alts.values()) - min(alts.values()) > 1:
        out.append('alturas diferentes entre os arquivos: ' + ', '.join(f'{k} {v}px' for k, v in alts.items()))
    if max(pes.values()) - min(pes.values()) > 0:
        out.append('linha dos pés diferente entre os arquivos: ' + ', '.join(f'{k} y={v}' for k, v in pes.items()))
    return out


def draw_px(d, x, y, z, color, ox=0, oy=0):
    d.rectangle([ox + x * z, oy + y * z, ox + x * z + z - 1, oy + y * z + z - 1], fill=color)


def render_overlay(f, rep, path, bgc, z):
    H, W = f.shape[:2]
    pad = 2
    legend_h = 18 * (len(MARK) + 1)
    im = Image.new('RGB', ((W + 2 * pad) * z, (H + 2 * pad) * z + legend_h), bgc)
    d = ImageDraw.Draw(im)
    for y in range(H):
        for x in range(W):
            if f[y, x, 3] > 0:
                draw_px(d, x + pad, y + pad, z, tuple(int(c) for c in f[y, x, :3]))
    grid = tuple(max(0, c - 18) for c in bgc)
    for x in range(W + 1):
        d.line([(x + pad) * z, pad * z, (x + pad) * z, (H + pad) * z], fill=grid)
    for y in range(H + 1):
        d.line([pad * z, (y + pad) * z, (W + pad) * z, (y + pad) * z], fill=grid)
    for kind, pts in rep.get('marcas', {}).items():
        col = MARK[kind][0]
        for (x, y) in pts:
            X, Y = (x + pad) * z, (y + pad) * z
            if kind == 'assimetria':
                d.ellipse([X + z // 3, Y + z // 3, X + z - z // 3, Y + z - z // 3], fill=col)
            else:
                d.rectangle([X + 1, Y + 1, X + z - 2, Y + z - 2], outline=col, width=max(1, z // 5))
    ly = (H + 2 * pad) * z + 4
    for kind, (col, label) in MARK.items():
        n = len(rep.get('marcas', {}).get(kind, []))
        d.rectangle([6, ly + 3, 16, ly + 13], outline=col, width=2)
        d.text((22, ly), f'{label}: {n}', fill=(255, 255, 255), font=legend_font())
        ly += 18
    im.save(path)


def render_sheet(frames, masks, reps, path, bgc):
    """Silhuetas, quadros 4x com guias (pés, topo e centro do 1º quadro), e 1x/2x."""
    z = 4
    H = max(f.shape[0] for f in frames)
    W = max(f.shape[1] for f in frames)
    n = len(frames)
    gap = 4
    sheet = Image.new('RGB', (n * (W * z + gap) + gap, (H * z + gap) * 2 + H * 2 + gap * 3 + 4), bgc)
    d = ImageDraw.Draw(sheet)
    m0 = reps[0].get('metricas')
    for i, (f, m) in enumerate(zip(frames, masks)):
        ox = gap + i * (W * z + gap)
        for y in range(f.shape[0]):
            for x in range(f.shape[1]):
                if m[y, x]:
                    draw_px(d, x, y, z, (36, 26, 42), ox, gap)
                if f[y, x, 3] > 0:
                    draw_px(d, x, y, z, tuple(int(c) for c in f[y, x, :3]), ox, gap * 2 + H * z)
        if m0:
            oy = gap * 2 + H * z
            d.line([ox, oy + (m0['pes_y'] + 1) * z, ox + W * z, oy + (m0['pes_y'] + 1) * z], fill=(255, 60, 60))
            d.line([ox, oy + m0['topo_y'] * z, ox + W * z, oy + m0['topo_y'] * z], fill=(60, 220, 255))
            cx = int(round(m0['centro_x'] * z + z / 2))
            d.line([ox + cx, oy, ox + cx, oy + H * z], fill=(255, 220, 0))
        small = Image.fromarray(f, 'RGBA')
        sy = gap * 3 + 2 * H * z
        bgimg = Image.new('RGBA', small.size, bgc + (255,))
        bgimg.alpha_composite(small)
        sheet.paste(bgimg.convert('RGB'), (ox, sy))
        sheet.paste(bgimg.convert('RGB').resize((small.width * 2, small.height * 2), Image.NEAREST), (ox + small.width + 4, sy))
    sheet.save(path)


def mockup_analysis(path):
    """Para telas/conceitos (inclusive gerados por IA): pixel art de verdade tem poucas cores, vizinhos
    iguais ou bem diferentes, e mudanças de cor alinhadas a uma grade de tamanho fixo."""
    rgb = np.array(Image.open(path).convert('RGB')).astype(int)
    H, W, _ = rgb.shape
    codes = rgb[:, :, 0] * 65536 + rgb[:, :, 1] * 256 + rgb[:, :, 2]
    uniq = int(len(np.unique(codes)))
    dh = np.abs(rgb[:, 1:] - rgb[:, :-1]).sum(axis=2)
    equal = int((dh == 0).sum())
    near = int(((dh > 0) & (dh <= 24)).sum())
    strong = dh > 48
    xs = np.nonzero(strong)[1] + 1
    grid, score = 1, 1.0
    for k in range(8, 1, -1):  # maior ampliação inteira em que quase toda mudança forte cai na grade
        hist = np.bincount(xs % k, minlength=k)
        sc = hist.max() / max(1, len(xs))
        if sc >= 0.85:
            grid, score = k, float(sc)
            break
    near_ratio = near / max(1, near + equal)
    rep = {'arquivo': path, 'tamanho': f'{W}x{H}', 'cores_unicas': uniq,
           'vizinhos_quase_iguais_pct': round(near_ratio * 100, 1),
           'grade_px': grid, 'aderencia_grade_pct': round(score * 100, 1), 'leitura': []}
    if uniq > 512:
        rep['leitura'].append(f'{uniq} cores únicas: pixel art de verdade fica entre 16 e 64 por tela inteira')
    if near_ratio > 0.25:
        rep['leitura'].append(f'{near_ratio * 100:.0f}% dos vizinhos são "quase iguais": gradiente, ruído ou compressão '
                              '(sinal de imagem gerada ou redimensionada, não de pixel art limpa)')
    if grid == 1 and (uniq > 256 or near_ratio > 0.25):
        rep['leitura'].append('sem grade fixa: as bordas não caem num múltiplo inteiro (densidade misturada, pixels tortos)')
    elif grid == 1:
        rep['leitura'].append('pixel art nativa em 1x (grade de 1 px)')
    else:
        rep['leitura'].append(f'pixel art ampliada {grid}x com grade consistente')
    return rep


def _paleta_de(paleta):
    """paleta: caminho (.hex/.gpl/.json/.md/.txt) ou lista/conjunto de '#RRGGBB'."""
    if paleta is None:
        return None
    if isinstance(paleta, (str, os.PathLike)):
        return load_palette(os.fspath(paleta))
    return {'#' + str(c).strip().lstrip('#').upper() for c in paleta}


def _cor_de(c):
    if c is None or c == '':
        return None
    if isinstance(c, str):
        return parse_hex(c)
    return tuple(int(v) for v in c[:3])


def medir_arquivo(caminhos, paleta=None, fundo='#718555', quadros=None, tamanho_quadro=None, vista='other',
                  contorno=None, ignorar=None, zoom=10, saida=None, mockup=False):
    """Revisão técnica de um ou mais PNG, em dados estruturados (a mesma análise da CLI).

    caminhos: um caminho ou lista. paleta: caminho de paleta ou lista de hex. fundo: hex do fundo dos previews (None =
    sem checagens contra o fundo). quadros: N quadros na horizontal; tamanho_quadro: 'LxA'. vista: front|side|back|other.
    contorno: hex do contorno (padrão: o mais comum na borda). ignorar: lista de hex ligadas ao fundo (sombra no chão).
    saida: pasta dos overlays (padrão: <pasta do png>/review). mockup: True mede tela/conceito (cores, ruído, grade).

    Devolve {"arquivos": [...], "entre_arquivos": [...], "erros": [...], "avisos": [...], "ok": bool,
    "overlays": [caminhos], "folhas": [caminhos]}. Em cada quadro, "marcas" traz a contagem por tipo e
    "marcas_pontos" os pontos (x, y)."""
    if isinstance(caminhos, (str, os.PathLike)):
        caminhos = [caminhos]
    caminhos = [os.fspath(c) for c in caminhos]
    if mockup:
        reps = [mockup_analysis(c) for c in caminhos]
        return {'modo': 'mockup', 'arquivos': reps, 'entre_arquivos': [], 'erros': [],
                'avisos': [f"{os.path.basename(r['arquivo'])}: {x}" for r in reps for x in r['leitura']],
                'ok': True, 'overlays': [], 'folhas': []}
    ign = ignorar or []
    if isinstance(ign, str):
        ign = [c for c in ign.split(',') if c.strip()]
    args = SimpleNamespace(frames=quadros, frame_size=tamanho_quadro, view=vista,
                           outline=None if contorno is None else ('#' + '%02X%02X%02X' % _cor_de(contorno)),
                           zoom=zoom, out=os.fspath(saida) if saida else None)
    results = _revisar(caminhos, args, _paleta_de(paleta), [_cor_de(c) for c in ign], _cor_de(fundo))
    cross = compare_assets(results)
    arquivos, erros, avisos, overlays, folhas = [], [], [], [], []
    for r in results:
        nome = os.path.basename(r['arquivo'])
        qs = []
        for i, q in enumerate(r['quadros']):
            qq = {k: v for k, v in q.items() if k != 'marcas'}
            qq['marcas'] = {k: len(v) for k, v in q.get('marcas', {}).items()}
            qq['marcas_pontos'] = {k: [list(pt) for pt in v] for k, v in q.get('marcas', {}).items()}
            qs.append(qq)
            erros += [f'{nome} q{i}: {e}' for e in q['erros']]
            avisos += [f'{nome} q{i}: {w}' for w in q['avisos']]
            overlays.append(q['overlay'])
        for a in r['animacao']:
            avisos += [f"{nome} anim {a['tag']}: {w}" for w in a['avisos']]
        folhas.append(r['folha'])
        arquivos.append({**r, 'quadros': qs})
    avisos += [f'entre arquivos: {w}' for w in cross]
    return {'modo': 'sprite', 'arquivos': arquivos, 'entre_arquivos': cross, 'erros': erros, 'avisos': avisos,
            'ok': not erros, 'overlays': overlays, 'folhas': folhas}


def _revisar(pngs, args, palette, ignore, bgc):
    results = []
    for p in pngs:
        frames, tags = load_frames(p, args)
        out_dir = args.out or os.path.join(os.path.dirname(os.path.abspath(p)), 'review')
        os.makedirs(out_dir, exist_ok=True)
        stem = os.path.splitext(os.path.basename(p))[0]
        reps, masks = [], []
        for i, f in enumerate(frames):
            rep, mask = review_frame(f, args, palette, ignore, bgc)
            ov = os.path.join(out_dir, f'{stem}_q{i}_revisao.png')
            render_overlay(f, rep, ov, bgc or (40, 40, 52), args.zoom)
            rep['overlay'] = ov
            reps.append(rep)
            masks.append(mask)
        sheet = os.path.join(out_dir, f'{stem}_folha.png')
        render_sheet(frames, masks, reps, sheet, bgc or (40, 40, 52))
        results.append({'arquivo': p, 'quadros': reps, 'animacao': review_animation(frames, masks, reps, tags),
                        'folha': sheet, 'tags': tags})
    return results


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8')
        except Exception:
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('pngs', nargs='+')
    ap.add_argument('--frames', type=int)
    ap.add_argument('--frame-size')
    ap.add_argument('--view', default='other', choices=['front', 'side', 'back', 'other'])
    ap.add_argument('--palette')
    ap.add_argument('--outline')
    ap.add_argument('--ignore', default='')
    ap.add_argument('--bg', default='#718555')
    ap.add_argument('--zoom', type=int, default=10)
    ap.add_argument('--out')
    ap.add_argument('--mockup', action='store_true')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()

    if args.mockup:
        reps = [mockup_analysis(p) for p in args.pngs]
        if args.json:
            print(json.dumps(reps, ensure_ascii=False, indent=1))
        else:
            for r in reps:
                print(f"\n== {r['arquivo']} ({r['tamanho']})")
                print(f"cores únicas: {r['cores_unicas']} | vizinhos quase iguais: {r['vizinhos_quase_iguais_pct']}% | "
                      f"grade: {r['grade_px']} px ({r['aderencia_grade_pct']}% das bordas na grade)")
                for line in r['leitura']:
                    print(' -', line)
        return

    palette = load_palette(args.palette) if args.palette else None
    ignore = [parse_hex(c) for c in args.ignore.split(',') if c.strip()]
    bgc = parse_hex(args.bg) if args.bg else None
    results = _revisar(args.pngs, args, palette, ignore, bgc)
    cross = compare_assets(results)
    if args.json:
        slim = []
        for r in results:
            rr = dict(r)
            rr['quadros'] = [{k: v for k, v in q.items() if k != 'marcas'} | {'marcas': {k: len(v) for k, v in q.get('marcas', {}).items()}}
                             for q in r['quadros']]
            slim.append(rr)
        print(json.dumps({'arquivos': slim, 'entre_arquivos': cross}, ensure_ascii=False, indent=1))
        return
    for r in results:
        print(f"\n== {r['arquivo']}  ({len(r['quadros'])} quadro(s); folha: {r['folha']})")
        for i, q in enumerate(r['quadros']):
            m = q.get('metricas') or {}
            head = (f"q{i}: {q['quadro']}, figura {m.get('largura')}x{m.get('altura')} (pés y={m.get('pes_y')}), "
                    f"{q.get('cores', 0)} cores, contorno {q.get('contorno')}")
            if 'assimetria_silhueta' in q:
                head += f", assimetria {q['assimetria_silhueta']}%"
            print(head)
            for e in q['erros']:
                print('   ERRO  ', e)
            for w in q['avisos']:
                print('   aviso ', w)
            print('   overlay', q['overlay'])
        for a in r['animacao']:
            print(f"anim {a['tag']}: pés y {a['pes_y']}, alturas {a['alturas']}, deriva do centro {a['deriva_centro_x']} px, "
                  f"px mudados {a['pixels_mudados']}")
            for w in a['avisos']:
                print('   aviso ', w)
    for w in cross:
        print('\nENTRE ARQUIVOS:', w)


if __name__ == '__main__':
    main()
