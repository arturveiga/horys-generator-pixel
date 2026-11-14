"""Monta as pranchas que o revisor olha (ampliadas em nearest, entre 200 e ~1500 px).

uso:
  python prancha.py --tipo personagem --quadro 192 --folha idle=caminho.png [--folha andar=...] --saida <pasta_revisao>
                    [--medidas medidas.json] [--altura-quadro N] [--centro-tile COL,LIN ...]

Gera, por estado: regua_lado_a_lado_<e>.png, quadros_4x_<e>.png, silhueta_<e>.png, cinza_<e>.png,
diferencas_<e>.png, cebola_<e>.png, sobre_chao_<e>.png, recortes_8x_<e>_<k>.png; tiles: mosaico_4x4.png e
bordas.png; efeitos: fundos_<e>.png. Escreve indice.md com o que cada imagem mostra.
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

import comum as C

FUNDO_CLARO = (236, 232, 222)


def rotular(img, texto):
    W, H = img.size
    out = Image.new("RGB", (W, H + 20), (40, 40, 46))
    out.paste(img, (0, 20))
    ImageDraw.Draw(out).text((4, 3), texto, fill=(255, 220, 120), font=C.fonte(13))
    return out


def lado_a_lado(imgs, gap=8, fundo=(40, 40, 46)):
    W = sum(i.size[0] for i in imgs) + gap * (len(imgs) - 1)
    H = max(i.size[1] for i in imgs)
    out = Image.new("RGB", (W, H), fundo)
    x = 0
    for i in imgs:
        out.paste(i, (x, 0))
        x += i.size[0] + gap
    return out


def empilhar(imgs, gap=8, fundo=(40, 40, 46)):
    W = max(i.size[0] for i in imgs)
    H = sum(i.size[1] for i in imgs) + gap * (len(imgs) - 1)
    out = Image.new("RGB", (W, H), fundo)
    y = 0
    for i in imgs:
        out.paste(i, (0, y))
        y += i.size[1] + gap
    return out


def caber(img, limite):
    W, H = img.size
    if max(W, H) <= limite:
        return img
    f = limite / max(W, H)
    return img.resize((max(1, int(W * f)), max(1, int(H * f))), Image.NEAREST)


def silhueta(f, cor):
    s = np.zeros_like(f)
    op = f[..., 3] == 255
    s[op] = list(cor) + [255]
    return s


def cinza(f):
    L = C.oklab(f[..., :3])[0]
    g = np.clip(L * 255, 0, 255).astype(np.uint8)
    out = f.copy()
    out[..., 0] = out[..., 1] = out[..., 2] = g
    return out


def recortes(quadros, marcas_por_q, saida, estado, cfg, max_rec=4, lado=24, e=8):
    """Até 4 recortes 8x em volta das marcas do overlay (órfãos, degraus, boil), com grade de 1 px."""
    feitos = []
    candidatos = []
    for qi, pts in enumerate(marcas_por_q):
        for (x, y) in pts:
            candidatos.append((qi, x, y))
    usados = []
    for (qi, x, y) in candidatos:
        if any(qi == q and abs(x - ux) < lado and abs(y - uy) < lado for (q, ux, uy) in usados):
            continue
        usados.append((qi, x, y))
        if len(usados) >= max_rec:
            break
    for k, (qi, x, y) in enumerate(usados):
        f = quadros[qi]
        H, W = f.shape[:2]
        x0, y0 = max(0, x - lado // 2), max(0, y - lado // 2)
        x1, y1 = min(W, x0 + lado), min(H, y0 + lado)
        cel = C.compor_sobre(f[y0:y1, x0:x1], C.hex2rgb(cfg["fundo_prancha"])).resize(((x1 - x0) * e, (y1 - y0) * e), Image.NEAREST)
        d = ImageDraw.Draw(cel)
        for gx in range(x0, x1):
            X = (gx - x0) * e
            d.line([(X, 0), (X, cel.size[1])], fill=(0, 0, 0) if gx % 8 == 0 else (90, 90, 90), width=1)
        for gy in range(y0, y1):
            Y = (gy - y0) * e
            d.line([(0, Y), (cel.size[0], Y)], fill=(0, 0, 0) if gy % 8 == 0 else (90, 90, 90), width=1)
        X, Y = (x - x0) * e, (y - y0) * e
        d.rectangle([X - 2, Y - 2, X + e + 1, Y + e + 1], outline=(255, 0, 0), width=3)
        img = rotular(cel, f"quadro {qi}, x {x0}..{x1 - 1}, y {y0}..{y1 - 1}; marcado: ({x},{y})")
        nome = f"recortes_8x_{estado}_{k}.png"
        img.save(os.path.join(saida, nome))
        feitos.append(nome)
    return feitos


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tipo", required=True)
    ap.add_argument("--quadro", type=int, default=0)
    ap.add_argument("--altura-quadro", type=int, default=0)
    ap.add_argument("--folha", action="append", required=True)
    ap.add_argument("--saida", required=True)
    ap.add_argument("--medidas", default="")
    ap.add_argument("--centro-tile", action="append", default=[])
    args = ap.parse_args()

    cfg = C.config()
    lim = cfg["limite_imagem"]
    fundo = C.hex2rgb(cfg["fundo_prancha"])
    contorno = C.hex2rgb("#18122c")
    os.makedirs(args.saida, exist_ok=True)
    medidas = {}
    if args.medidas and os.path.exists(args.medidas):
        with open(args.medidas, encoding="utf-8") as f:
            medidas = json.load(f)
    indice = ["# Pranchas de revisão", ""]

    for item in args.folha:
        estado, _, caminho = item.partition("=")
        quadros = C.carregar_folha(caminho, args.quadro, args.altura_quadro)
        n = len(quadros)
        bbox = C.bbox_uniao(quadros, margem=4)
        cat = C.categoria_estado(estado)
        if args.tipo in ("tile", "predio", "prop", "arvore", "icone", "ui", "retrato", "criatura", "efeito"):
            cat_regua = args.tipo
        else:
            cat_regua = cat
        # ---- régua lado a lado
        arq, qr = cfg["regua_por_categoria"].get(cat_regua, cfg["regua_por_categoria"]["idle"])
        caminho_regua = os.path.join(cfg["regua"], arq)
        if os.path.exists(caminho_regua):
            rq = C.carregar_folha(caminho_regua, qr)
            rb = C.bbox_uniao(rq, margem=4)
            aw, ah = bbox[2] - bbox[0], bbox[3] - bbox[1]
            rw, rh = rb[2] - rb[0], rb[3] - rb[1]
            ncol = max(min(n, 8), min(len(rq), 8))
            e = C.escala_para_caber(max(aw, rw), max(ah, rh), ncol, 2 * max(1, -(-max(n, len(rq)) // ncol)), lim, maximo=4)
            a_img = C.grade_quadros(quadros, bbox, fundo, limite=lim, escala=e, colunas=min(n, ncol), grade=0,
                                    rotulos=[f"q{i}" for i in range(n)], titulo=f"ASSET ({estado}, {n} quadros)")
            r_img = C.grade_quadros(rq, rb, fundo, limite=lim, escala=e, colunas=min(len(rq), ncol), grade=0,
                                    rotulos=[f"q{i}" for i in range(len(rq))], titulo=f"RÉGUA Tiny Swords: {arq} ({len(rq)} quadros) — mesma escala {e}x")
            nome = f"regua_lado_a_lado_{estado}.png"
            caber(empilhar([a_img, r_img]), lim).save(os.path.join(args.saida, nome))
            indice.append(f"- `{nome}`: o asset em cima e a régua do Tiny da mesma categoria embaixo, **na mesma escala** ({e}×). Pergunta: aguenta ficar no mesmo jogo?")
        # ---- quadros 4x com grade
        nome = f"quadros_4x_{estado}.png"
        C.grade_quadros(quadros, bbox, fundo, limite=lim, rotulos=[f"q{i}" for i in range(n)],
                        titulo=f"{estado}: quadros ampliados, grade a cada 8 px (coordenadas do quadro)").save(os.path.join(args.saida, nome))
        indice.append(f"- `{nome}`: todos os quadros ampliados com grade de 8 px e coordenadas.")
        # ---- silhueta 1x e 0,5x (ampliadas 4x para ver), comparada à régua
        f0 = quadros[0]
        s = silhueta(f0, contorno)[bbox[1]:bbox[3], bbox[0]:bbox[2]]
        s_img = C.compor_sobre(s, FUNDO_CLARO)
        meia = s_img.resize((max(1, s_img.size[0] // 2), max(1, s_img.size[1] // 2)), Image.NEAREST)
        partes = [rotular(s_img.resize((s_img.size[0] * 4, s_img.size[1] * 4), Image.NEAREST), "silhueta 1x (vista 4x)"),
                  rotular(meia.resize((meia.size[0] * 4, meia.size[1] * 4), Image.NEAREST), "silhueta 0,5x (vista 4x)")]
        if os.path.exists(caminho_regua):
            rs = silhueta(rq[0], contorno)[rb[1]:rb[3], rb[0]:rb[2]]
            rs_img = C.compor_sobre(rs, FUNDO_CLARO)
            partes.append(rotular(rs_img.resize((rs_img.size[0] * 4, rs_img.size[1] * 4), Image.NEAREST), "régua 1x (vista 4x)"))
        nome = f"silhueta_{estado}.png"
        caber(lado_a_lado(partes), lim).save(os.path.join(args.saida, nome))
        indice.append(f"- `{nome}`: silhueta do quadro 0 numa cor, em 1× e 0,5× (ampliadas 4×), ao lado da régua. Lê sem nada dentro?")
        # ---- cinza
        nome = f"cinza_{estado}.png"
        C.grade_quadros([cinza(f) for f in quadros], bbox, fundo, limite=lim, grade=0,
                        rotulos=[f"q{i}" for i in range(n)], titulo=f"{estado}: só valor (OKLab L)").save(os.path.join(args.saida, nome))
        indice.append(f"- `{nome}`: só o valor (cinza). As massas continuam separadas?")
        # ---- animação: diferenças e cebola
        if n >= 2:
            difs = []
            for i in range(n):
                a, b = quadros[i], quadros[(i + 1) % n]
                base = cinza(b).astype(np.int32)
                base[..., :3] = (base[..., :3] * 0.45 + 140 * 0.55).astype(np.int32)
                mud = np.any(a != b, axis=-1) & ((a[..., 3] > 0) | (b[..., 3] > 0))
                novo = mud & (b[..., 3] > 0)
                sumiu = mud & (b[..., 3] == 0)
                out = base.astype(np.uint8)
                out[..., 3] = np.maximum(a[..., 3], b[..., 3])
                out[novo] = [230, 40, 40, 255]
                out[sumiu] = [40, 90, 230, 255]
                difs.append(out)
            nome = f"diferencas_{estado}.png"
            C.grade_quadros(difs, bbox, fundo, limite=lim, grade=0,
                            rotulos=[f"q{i}->q{(i + 1) % n}" for i in range(n)],
                            titulo=f"{estado}: vermelho = pixel novo/mudado no quadro seguinte; azul = sumiu").save(os.path.join(args.saida, nome))
            indice.append(f"- `{nome}`: o que muda de um quadro para o seguinte. Muito vermelho só na borda = só desliza; vermelho espalhado na forma = redesenho.")
            # cebola: contornos de todos os quadros sobrepostos + trajetória do centro
            x0, y0, x1, y1 = bbox
            e = max(2, min(6, lim // max(x1 - x0, y1 - y0)))
            cel = Image.new("RGB", ((x1 - x0) * e, (y1 - y0) * e), FUNDO_CLARO)
            d = ImageDraw.Draw(cel)
            for i, f in enumerate(quadros):
                t = i / max(n - 1, 1)
                cor = (int(40 + 200 * t), 60, int(230 - 190 * t))
                op = f[..., 3] == 255
                borda = op & ~np.pad(op, 1)[2:, 1:-1] | op & ~np.pad(op, 1)[:-2, 1:-1] | op & ~np.pad(op, 1)[1:-1, 2:] | op & ~np.pad(op, 1)[1:-1, :-2]
                for yy, xx in zip(*np.nonzero(borda[y0:y1, x0:x1])):
                    d.rectangle([xx * e, yy * e, xx * e + e - 1, yy * e + e - 1], fill=cor)
                ys, xs = np.nonzero(op)
                if len(xs):
                    cx, cy = (xs.mean() - x0) * e, (ys.mean() - y0) * e
                    d.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=cor)
                    d.text((cx + 6, cy - 6), str(i), fill=cor, font=C.fonte(12))
            nome = f"cebola_{estado}.png"
            caber(rotular(cel, f"{estado}: bordas de todos os quadros (azul = q0 → vermelho = último) e o centro de massa de cada um"), lim).save(os.path.join(args.saida, nome))
            indice.append(f"- `{nome}`: sobreposição das bordas e trajetória do centro. Os caminhos são arcos? A ponta e as mãos atrasam?")
        # ---- sobre o chão
        partes = []
        for nome_chao, hx in cfg["chao"].items():
            cor = C.hex2rgb(hx)
            x0, y0, x1, y1 = bbox
            pedaco = quadros[0][y0:y1, x0:x1]
            img1 = C.compor_sobre(pedaco, cor)
            partes.append(rotular(img1.resize((img1.size[0] * 3, img1.size[1] * 3), Image.NEAREST), f"sobre {nome_chao} (3x)"))
            partes.append(rotular(img1.resize((img1.size[0] * 1, img1.size[1] * 1), Image.NEAREST), "1x"))
        nome = f"sobre_chao_{estado}.png"
        caber(lado_a_lado(partes), lim).save(os.path.join(args.saida, nome))
        indice.append(f"- `{nome}`: quadro 0 sobre a grama e o piso de masmorra, em 3× e no tamanho real. Destaca do chão?")
        # ---- recortes 8x nas marcas do overlay
        marcas = []
        fol = medidas.get("folhas", {}).get(estado, {})
        if fol:
            # reconstrói as marcas a partir das medidas: órfãos, degraus e boil não ficam no json; recalcula órfãos e degraus aqui
            pass
        for f in quadros:
            op = f[..., 3] == 255
            pts = C.degraus_irregulares(op)[:3]
            from medir import iguais_vizinho  # reaproveita a mesma regra de órfão
            orf = op & ~iguais_vizinho(f)
            pts += [(int(x), int(y)) for y, x in zip(*np.nonzero(orf))][:3]
            marcas.append(pts)
        feitos = recortes(quadros, marcas, args.saida, estado, cfg)
        if feitos:
            indice.append(f"- `recortes_8x_{estado}_*.png` ({len(feitos)}): regiões marcadas (órfão ou degrau) a 8×, com grade de 1 px. Confira se o problema é real.")
        # ---- efeitos: fundos
        if args.tipo == "efeito":
            fundos = [(244, 235, 204), (104, 160, 87), (63, 60, 86)]
            linhas = [C.grade_quadros(quadros, bbox, fb, limite=lim, grade=0, rotulos=[f"q{i}" for i in range(n)]) for fb in fundos]
            nome = f"fundos_{estado}.png"
            caber(empilhar(linhas), lim).save(os.path.join(args.saida, nome))
            indice.append(f"- `{nome}`: o efeito sobre fundo claro, médio e escuro.")

    # ---- tiles
    if args.tipo == "tile" and args.centro_tile:
        full = np.array(Image.open(args.folha[0].partition("=")[2]).convert("RGBA"))
        mos, bords = [], []
        for ct in args.centro_tile:
            col, lin = (int(v) for v in ct.split(","))
            t = full[lin * 64:(lin + 1) * 64, col * 64:(col + 1) * 64]
            m = np.tile(t, (4, 4, 1))
            mos.append(rotular(C.compor_sobre(m, fundo).resize((512, 512), Image.NEAREST), f"tile {ct} repetido 4x4 (2x)"))
            b = np.tile(t, (2, 2, 1))
            bi = C.compor_sobre(b, fundo).resize((512, 512), Image.NEAREST)
            d = ImageDraw.Draw(bi)
            d.line([(256, 0), (256, 512)], fill=(255, 0, 0), width=1)
            d.line([(0, 256), (512, 256)], fill=(255, 0, 0), width=1)
            bords.append(rotular(bi, f"tile {ct} 2x2 (4x): costuras na linha vermelha"))
        caber(lado_a_lado(mos), lim).save(os.path.join(args.saida, "mosaico_4x4.png"))
        caber(lado_a_lado(bords), lim).save(os.path.join(args.saida, "bordas.png"))
        indice.append("- `mosaico_4x4.png`: o tile repetido. Aparece costura ou padrão gritante?")
        indice.append("- `bordas.png`: as costuras a 4× (linha vermelha). Some a emenda?")

    indice += ["", "Overlay das métricas: `overlay_<estado>.png` (vermelho = órfão, amarelo = degrau, magenta = borda, ciano = boil)."]
    with open(os.path.join(args.saida, "indice.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(indice) + "\n")
    print("pranchas em", args.saida)
    return 0


if __name__ == "__main__":
    sys.exit(main())
