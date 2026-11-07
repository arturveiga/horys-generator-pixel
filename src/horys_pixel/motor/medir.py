"""Mede folhas de sprites no estilo Horys Pixel Liso (ou a régua, com --modo regua).

uso:
  python medir.py --tipo personagem --quadro 192 --folha idle=caminho.png [--folha andar=outro.png] --saida <pasta>
                  [--altura-quadro N] [--modo regua] [--com-equipamento] [--com-efeito]
                  [--loop idle,andar] [--sem-loop ataque] [--centro-tile COL,LIN ...] [--asset nome]
                  [--contorno-px 2|1|0] [--contorno-cor #hex] [--limite-cores N] [--ritmo calmo]

--contorno-px: 2 = anil 2 px (padrão, calibrado no Tiny); 1 = contorno fino de 1 px ("contorno suave");
0 = sem borda escura ("contorno nenhum"). Com 1 ou 0, órfãos e manchas são medidos só no preenchimento
(o degrau diagonal de um contorno de 1 px não é órfão) e a meta de mancha é a do preenchimento do Tiny.

Saída: <saida>/medidas.json e <saida>/overlay_<estado>.png.
Código de saída: 0 = nenhuma falha; 1 = há falhas (ver medidas.json); 2 = erro de uso.
As metas vêm de KB/revisao/metricas.md (calibradas no Tiny Swords).
Config: comum.config() (HORYS_MOTOR_CONFIG -> ~/.horys-pixel/motor.json -> config_padrao.json).
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

try:  # como módulo (python -m horys_pixel.motor.X) ou como script direto (python X.py)
    from . import comum as C
except ImportError:
    import comum as C  # noqa: E402

CRUZ = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], bool)

LIMITE_CORES = {"personagem": 10, "inimigo": 10, "criatura": 8, "boss": 16, "prop": 8, "arvore": 8,
                "tile": 12, "predio": 18, "icone": 8, "ui": 10, "retrato": 14, "efeito": 6,
                "recurso": 10, "agua": 6}  # recurso e agua: 2026-11-05 (KB/analise/banca-de-cenario.md)
CLUSTER_MIN = {"personagem": 45, "inimigo": 45, "boss": 45, "criatura": 40, "prop": 25, "arvore": 30,
               "tile": 25, "predio": 25, "icone": 20, "ui": 20, "retrato": 45, "efeito": 0,
               "recurso": 20, "agua": 0}
# Mancha média medida SÓ no preenchimento (sem a cor do contorno), usada com --contorno-px 1 ou 0.
# Calibrada em 2026-11-05 em 12 folhas de personagem do Tiny (peão, guerreiro, arqueiro, monge; idle, corrida,
# ataque, cura, trabalho): faixa 32–77 px, mínimo 32 (monge correndo). Meta = 30.
CLUSTER_MIN_PREENCHIMENTO = {"personagem": 30, "inimigo": 30, "boss": 30, "retrato": 30, "criatura": 28}
GRUPO_FIGURA = {"personagem", "inimigo", "boss", "icone", "retrato"}
GRUPO_CENARIO = {"prop", "arvore", "predio", "ui", "recurso"}
# borda do cenário (M06): (mínimo no contorno, mínimo escuro). Recalibrado em 2026-11-05 nos 22 assets de cenário do
# Tiny (árvore 3: 70% escura; pedra 2: 42% contorno; ouro: 65% escura). Ver KB/analise/banca-de-cenario.md §5.
BORDA_CENARIO = {"arvore": (0.45, 0.65), "prop": (0.40, 0.75), "predio": (0.45, 0.75), "ui": (0.45, 0.75),
                 "recurso": (0.0, 0.60)}
# órfãos (média, pior quadro) por tipo; o resto usa ORFAOS_MEDIA/ORFAOS_MAX
ORFAOS_TIPO = {"recurso": (0.012, 0.015), "efeito": (0.006, 0.015)}
METAS_ANIM = {  # (muda mínima, redesenho mínimo) — calibradas no Tiny em 2026-11-04 (KB/revisao/calibracao.md)
    "idle": (0.20, 0.12), "andar": (0.40, 0.30), "correr": (0.40, 0.30), "ataque": (0.55, 0.45),
    "tiro": (0.45, 0.35), "trabalhar": (0.50, 0.40), "magia": (0.30, 0.25),
    # dano e morte: medidos SEM o quadro de flash (2026-11-05, 13 personagens CC0 da Pixel Frog;
    # dano 12–72%/12–59%, morte 57–78%/36–56%). Ver KB/analise/dano-e-morte.md.
    "dano": (0.12, 0.12), "morte": (0.45, 0.30),
    "ambiente": (0.03, 0.03), "efeito": (0.05, 0.03)}
IDLE_CALMO = (0.04, 0.04)  # --ritmo calmo (o arqueiro do Tiny: idle quase parado de propósito)
ORFAOS_MEDIA, ORFAOS_MAX = 0.006, 0.010
TIPOS_CENARIO_ANIM = {"arvore", "prop", "predio", "tile", "ui", "icone", "retrato", "recurso", "agua"}
LOOP_PADRAO = {"idle", "andar", "correr", "ambiente", "trabalhar"}
SEVERIDADE = {  # id da métrica -> (critério da rubrica, severidade)
    "M01": ("A1", "bloqueio"), "M02": ("A2", "bloqueio"), "A11": ("A11", "bloqueio"), "M03": ("A6", "grave"),
    "M04": ("A7", "grave"), "M05": ("B2", "grave"), "M06": ("A8", "bloqueio"), "M07": ("A8", "bloqueio"),
    "M08": ("A10", "grave"), "A01": ("D1", "bloqueio"), "A02": ("D1", "bloqueio"), "A03": ("D10", "bloqueio"),
    "A04": ("D10", "grave"), "A05": ("D6", "grave"), "A08": ("D8", "grave"), "A09": ("A5", "bloqueio"),
    "T01": ("F1", "bloqueio"), "T02": ("A5", "bloqueio"), "E01": ("G2", "grave"), "E02": ("G2", "grave"),
    "E04": ("G5", "grave"), "E05": ("G2", "grave"), "E06": ("G2", "grave"), "E07": ("G2", "grave"),
    "M17": ("B1", "grave")}
# M17 (2026-11-05): fração da borda da silhueta em trechos retos (horizontais ou verticais) de >= RETA_MIN px.
# Pega figura montada com primitivas (retângulo, elipse cortada, caixa). Régua: Tiny 0,00–0,19 (guerreiro idle 0,19);
# gorila de pedra v01–v08 (reprovado no olho) 0,32–0,40; médico v16 (aprovado pelo Artur) 0,23.
RETA_MIN = 8
RETAS_MAX = 0.25
TIPOS_RETAS = {"personagem", "inimigo", "boss", "criatura", "npc", "animal"}


def aneis(op, n=3):
    rem, out = op.copy(), []
    for _ in range(n):
        er = ndimage.binary_erosion(rem, structure=CRUZ)
        out.append(rem & ~er)
        rem = er
    return out


def iguais_vizinho(f):
    """True onde o pixel tem pelo menos um vizinho (4) com o mesmo RGBA."""
    p = np.pad(f, ((1, 1), (1, 1), (0, 0)))
    c = p[1:-1, 1:-1]
    r = np.zeros(f.shape[:2], bool)
    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        r |= np.all(p[1 + dy:p.shape[0] - 1 + dy, 1 + dx:p.shape[1] - 1 + dx] == c, axis=-1)
    return r


def retas_silhueta(op):
    """Pixels da borda da silhueta que estão em trechos retos (mesma linha ou coluna, com o mesmo lado vazio) de
    pelo menos RETA_MIN px. Devolve (fração da borda, máscara)."""
    borda = op & ~ndimage.binary_erosion(op, structure=CRUZ)
    reto = np.zeros_like(borda)
    for B, O, R in ((borda, op, reto), (borda.T, op.T, reto.T)):
        h = B.shape[0]
        for i in range(h):
            for viz in (i - 1, i + 1):
                vazio = ~O[viz] if 0 <= viz < h else np.ones(B.shape[1], bool)
                lab, n = ndimage.label(B[i] & vazio)
                if not n:
                    continue
                tam = np.bincount(lab)
                longos = np.nonzero(tam >= RETA_MIN)[0]
                longos = longos[longos > 0]
                if len(longos):
                    R[i] |= np.isin(lab, longos)
    return float(reto.sum() / max(borda.sum(), 1)), reto


def medir_quadro(f, ctx):
    rgb, a = f[..., :3], f[..., 3]
    op = a == 255
    res, marcas = {}, []
    if not op.any():
        return {"vazio": True}, marcas
    oc = np.array(ctx["contorno"])
    e_oc = op & np.all(rgb == oc, axis=-1)
    e_brilho = np.zeros_like(op)
    for b in ctx["brilho"]:
        e_brilho |= op & np.all(rgb == np.array(b), axis=-1)
    L, _, _ = C.oklab(rgb)
    r1, r2, _r3 = aneis(op, 3)
    res["anel1"] = float((e_oc & r1).sum() / max(r1.sum(), 1))
    res["anel2"] = float((e_oc & r2).sum() / max(r2.sum(), 1))
    res["anel1_escuro"] = float(((op & (L < 0.56)) & r1).sum() / max(r1.sum(), 1))
    fino = ctx.get("contorno_px", 2) < 2
    # órfãos (contorno fino: só no preenchimento; no contorno, órfão é o pixel sem vizinho nem na diagonal)
    orf = op & ~iguais_vizinho(f) & ~e_brilho
    if fino:
        lab8, _n8 = ndimage.label(e_oc, structure=np.ones((3, 3), bool))
        tam8 = np.bincount(lab8.ravel())
        sozinho = e_oc & (tam8[lab8] == 1)
        orf = (orf & ~e_oc) | sozinho
    res["orfaos_pct"] = float(orf.sum() / op.sum())
    for y, x in zip(*np.nonzero(orf)):
        marcas.append((int(x), int(y), (255, 40, 40)))
    # clusters (4-conexo; todas as cores opacas, ou só o preenchimento com contorno fino)
    tamanhos = []
    base_m = (op & ~e_oc) if fino else op
    cores = np.unique(rgb[base_m].reshape(-1, 3), axis=0)
    for c in cores:
        m = base_m & np.all(rgb == c, axis=-1)
        lab, n = ndimage.label(m, structure=CRUZ)
        if n:
            tamanhos.extend(np.bincount(lab.ravel())[1:].tolist())
    res["cluster_medio"] = float(np.mean(tamanhos)) if tamanhos else 0.0
    # escuro fora do contorno
    preench = op & ~e_oc
    if ctx.get("contorno_px", 2) < 2 and "contorno_paleta" in ctx:
        # sem contorno de 2 px, o anil da paleta só aparece no rosto (olho, sobrancelha, boca): é traço, não sujeira
        preench = preench & ~np.all(rgb == np.array(ctx["contorno_paleta"]), axis=-1)
    res["escuro_pct"] = float((preench & (L < 0.36)).sum() / max(preench.sum(), 1))
    # degraus irregulares na silhueta
    pts = C.degraus_irregulares(op)
    res["degraus"] = len(pts)
    for x, y in pts:
        marcas.append((x, y, (255, 230, 40)))
    # borda em trechos retos (forma geométrica)
    res["retas"], reto = retas_silhueta(op)
    for y, x in zip(*np.nonzero(reto)):
        marcas.append((int(x), int(y), (255, 140, 0)))
    # luz: correlação de L com x (frente) e y (cima) no preenchimento
    m = preench & ~e_brilho
    ys, xs = np.nonzero(m)
    if len(xs) > 20 and np.std(L[m]) > 1e-6:
        res["luz_x"] = float(np.corrcoef(xs, L[m])[0, 1])
        res["luz_y"] = float(np.corrcoef(ys, L[m])[0, 1])
    # contraste com o chão
    if preench.any():
        for nome, Lc in ctx["chao_L"].items():
            res[f"contraste_{nome}"] = float((np.abs(L[preench] - Lc) >= 0.12).mean())
    # geometria
    ys, xs = np.nonzero(op)
    res["altura"], res["largura"] = int(ys.max() - ys.min() + 1), int(xs.max() - xs.min() + 1)
    res["area"] = int(op.sum())
    res["centro_y"] = float(ys.mean())
    cx = f.shape[1] // 2
    banda = op[:, max(0, cx - 12):cx + 13]
    linhas = np.nonzero(banda.any(1))[0]
    res["pe"] = int(linhas.max()) if len(linhas) else int(ys.max())
    # borda do quadro
    borda = np.zeros_like(op)
    borda[0, :] = borda[-1, :] = borda[:, 0] = borda[:, -1] = True
    res["na_borda"] = int((op & borda).sum())
    for y, x in zip(*np.nonzero(op & borda)):
        marcas.append((int(x), int(y), (255, 0, 255)))
    # sombra no chão
    semi = (a > 0) & (a < 255)
    res["semi"] = int(semi.sum())
    if semi.any():
        sy, sx = np.nonzero(semi)
        res["sombra_largura_rel"] = float((sx.max() - sx.min() + 1) / max(res["largura"], 1))
    return res, marcas


def quadro_flash(f):
    """Quadro de flash de dano: a silhueta inteira (>= 85%) numa cor só e clara (L >= 0,80)."""
    op = f[..., 3] == 255
    if op.sum() < 20:
        return False
    cores, cont = np.unique(f[..., :3][op].reshape(-1, 3), axis=0, return_counts=True)
    k = int(np.argmax(cont))
    return cont[k] / op.sum() >= 0.85 and float(C.oklab(cores[k:k + 1])[0][0]) >= 0.80


def diferenca(a, b):
    oa, ob = a[..., 3] > 0, b[..., 3] > 0
    u = oa | ob
    if not u.any():
        return 0.0
    return float((u & np.any(a != b, axis=-1)).sum() / u.sum())


def redesenho(a, b, raio=6):
    melhor = 1.0
    for dy in range(-raio, raio + 1):
        for dx in range(-raio, raio + 1):
            bs = np.roll(np.roll(b, dy, 0), dx, 1)
            melhor = min(melhor, diferenca(a, bs))
            if melhor == 0:
                return 0.0
    return melhor


def boil(q0, q1, q2):
    """Pixels que mudam num quadro e voltam no seguinte, isolados (os 8 vizinhos não mudaram)."""
    volta = np.all(q0 == q2, axis=-1)
    mudou = np.any(q1 != q0, axis=-1)
    cand = volta & mudou & (q1[..., 3] == 255) & (q0[..., 3] == 255)
    if not cand.any():
        return 0.0, []
    viz = ndimage.convolve(mudou.astype(np.uint8), np.ones((3, 3), np.uint8), mode="constant") - mudou
    isolado = cand & (viz == 0)
    interior = (q0[..., 3] == 255).sum()
    return float(isolado.sum() / max(interior, 1)), list(zip(*np.nonzero(isolado)))


def emenda_tile(t):
    """Compara a costura (última coluna/linha com a primeira) com as colunas/linhas vizinhas de dentro do tile.
    Devolve (razão, detalhes): razão > 1 = a costura muda mais que o percentil 90 de dentro (+ folga)."""
    n = t.shape[0]
    rh = np.array([np.any(t[:, x] != t[:, x + 1], axis=-1).mean() for x in range(n - 1)])
    rv = np.array([np.any(t[y, :] != t[y + 1, :], axis=-1).mean() for y in range(n - 1)])
    sh = float(np.any(t[:, -1] != t[:, 0], axis=-1).mean())
    sv = float(np.any(t[-1, :] != t[0, :], axis=-1).mean())
    lim_h = max(np.percentile(rh, 90) * 1.5, np.percentile(rh, 90) + 0.10)
    lim_v = max(np.percentile(rv, 90) * 1.5, np.percentile(rv, 90) + 0.10)
    return max(sh / lim_h, sv / lim_v), {"costura_h": round(sh, 3), "limite_h": round(float(lim_h), 3),
                                         "costura_v": round(sv, 3), "limite_v": round(float(lim_v), 3)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tipo", required=True, choices=sorted(LIMITE_CORES))
    ap.add_argument("--quadro", type=int, default=0, help="largura do quadro (0 = imagem inteira)")
    ap.add_argument("--altura-quadro", type=int, default=0)
    ap.add_argument("--folha", action="append", required=True, help="estado=caminho.png")
    ap.add_argument("--saida", required=True)
    ap.add_argument("--asset", default="")
    ap.add_argument("--modo", choices=["normal", "regua"], default="normal")
    ap.add_argument("--com-equipamento", action="store_true")
    ap.add_argument("--com-efeito", action="store_true")
    ap.add_argument("--ritmo", choices=["normal", "calmo"], default="normal", help="ritmo do idle (ficha: 'ritmo')")
    ap.add_argument("--loop", default="")
    ap.add_argument("--sem-loop", default="")
    ap.add_argument("--centro-tile", action="append", default=[], help="COL,LIN de um tile que deve repetir sem emenda")
    ap.add_argument("--contorno-px", type=int, choices=[0, 1, 2], default=2,
                    help="2 = anil 2 px (padrão); 1 = contorno fino ('suave'); 0 = sem borda escura ('nenhum')")
    ap.add_argument("--contorno-cor", default="", help="cor do contorno, se não for a da paleta (ex.: #3f3c56)")
    ap.add_argument("--limite-cores", type=int, default=0, help="limite pedido pelo usuário (vem da ficha/grade)")
    ap.add_argument("--paleta", default="", help="paleta JSON alternativa, absoluta ou relativa à KB (sem KB: relativa à pasta atual)")
    args = ap.parse_args()

    cfg = C.config()
    pal = C.carregar_paleta(cfg, args.paleta or None)
    regua = args.modo == "regua"
    ctx = {"contorno": C.hex2rgb(cfg["contorno_regua"]) if regua else pal["contorno"],
           "brilho": [C.hex2rgb(h) for h in cfg["brilho_regua"]] if regua else pal["brilho"],
           "chao_L": {k: float(C.oklab(np.array(C.hex2rgb(v)))[0]) for k, v in cfg["chao"].items()},
           "contorno_px": 2 if regua else args.contorno_px, "contorno_paleta": pal["contorno"]}
    if args.contorno_cor and not regua:
        ctx["contorno"] = C.hex2rgb(args.contorno_cor)
    os.makedirs(args.saida, exist_ok=True)
    loops = set(x for x in args.loop.split(",") if x)
    sem_loops = set(x for x in args.sem_loop.split(",") if x)
    limite_cores = args.limite_cores or (LIMITE_CORES[args.tipo] + (3 if args.com_equipamento else 0)
                                         + (3 if args.com_efeito else 0))

    saida = {"asset": args.asset, "tipo": args.tipo, "modo": args.modo, "contorno": C.rgb2hex(ctx["contorno"]),
             "limite_cores": limite_cores, "contorno_px": ctx["contorno_px"], "folhas": {}, "falhas": [], "avisos": []}

    def falha(mid, estado, valor, meta, texto):
        crit, sev = SEVERIDADE.get(mid, ("?", "grave"))
        saida["falhas"].append({"id": mid, "criterio": crit, "severidade": sev, "estado": estado,
                                "valor": valor, "meta": meta, "texto": texto})

    def aviso(mid, estado, texto):
        saida["avisos"].append({"id": mid, "estado": estado, "texto": texto})

    for item in args.folha:
        estado, _, caminho = item.partition("=")
        if not caminho:
            print("use --folha estado=caminho.png", file=sys.stderr)
            return 2
        cat = C.categoria_estado(estado) if args.tipo not in ("prop", "arvore", "tile", "predio", "icone", "ui", "retrato", "recurso", "agua") else "ambiente"
        if args.tipo == "efeito":
            cat = "efeito"  # o nome do efeito ("poeira", "Dust_01") não é idle: sem metas de pé, quique e massa
        if args.tipo == "criatura" and cat == "idle":
            cat = "ambiente" if regua or "ambiente" in estado else "idle"
        quadros = C.carregar_folha(caminho, args.quadro, args.altura_quadro)
        full = np.array(Image.open(caminho).convert("RGBA"))
        rgb_all, a_all = full[..., :3], full[..., 3]
        op_all = a_all == 255
        info = {"arquivo": os.path.abspath(caminho), "sha256": C.sha256(caminho), "categoria": cat,
                "quadros": len(quadros), "tamanho_quadro": list(quadros[0].shape[1::-1])}
        # ---- imagem inteira
        cores = np.unique(rgb_all[op_all].reshape(-1, 3), axis=0)
        info["M03_cores"] = int(len(cores))
        if len(cores) > limite_cores:
            falha("M03", estado, int(len(cores)), f"<= {limite_cores}", f"{len(cores)} cores (limite {limite_cores})")
        if not regua:
            fora = [tuple(c) for c in cores.tolist() if tuple(c) not in pal["cores"]]
            info["M01_cores_fora"] = [C.rgb2hex(c) for c in fora[:20]]
            n_fora = int(sum((op_all & np.all(rgb_all == np.array(c), axis=-1)).sum() for c in fora)) if fora else 0
            info["M01_px_fora"] = n_fora
            if n_fora:
                falha("M01", estado, n_fora, 0, f"{n_fora} px em {len(fora)} cores fora da paleta: {', '.join(info['M01_cores_fora'][:6])}")
        semi = (a_all > 0) & (a_all < 255)
        if semi.any():
            if regua:
                Ls = C.oklab(rgb_all[semi])[0]
                # cenário: duas sombras sobrepostas somam alfa (~119 na árvore 4 do Tiny)
                teto = 125 if args.tipo in GRUPO_CENARIO else 90
                ruim = (a_all[semi] < 60) | (a_all[semi] > teto) | (Ls > 0.30)
            else:
                # a sombra no chão do grade.py é sempre o anil da paleta (alfa 77), mesmo com contorno fino de outra cor
                cor_ok = np.all(rgb_all[semi] == np.array(ctx["contorno"]), axis=-1) | np.all(rgb_all[semi] == np.array(pal["contorno"]), axis=-1)
                ruim = (a_all[semi] < 70) | (a_all[semi] > 80) | ~cor_ok
            n_ruim = int(ruim.sum())
        else:
            n_ruim = 0
        info["M02_alfa_invalido"] = n_ruim
        if n_ruim:
            falha("M02", estado, n_ruim, 0, f"{n_ruim} px semitransparentes que não são a sombra no chão")
        pretos = int((op_all & np.all(rgb_all == 0, axis=-1)).sum())
        if pretos:
            falha("A11", estado, pretos, 0, f"{pretos} px de preto puro")
        # ---- por quadro
        pq, marcas = [], []
        for f in quadros:
            r, m = medir_quadro(f, ctx)
            pq.append(r)
            marcas.append(m)
        validos = [r for r in pq if not r.get("vazio")]
        if not validos:
            falha("A09", estado, 0, ">0", "folha vazia")
            saida["folhas"][estado] = info
            continue
        res = {}
        res["M04_orfaos_media"] = float(np.mean([r["orfaos_pct"] for r in validos]))
        res["M04_orfaos_max"] = float(np.max([r["orfaos_pct"] for r in validos]))
        res["M05_cluster_medio"] = float(np.mean([r["cluster_medio"] for r in validos]))
        res["M06_anel1_mediana"] = float(np.median([r["anel1"] for r in validos]))
        res["M07_anel2_mediana"] = float(np.median([r["anel2"] for r in validos]))
        res["M06_anel1_escuro_mediana"] = float(np.median([r["anel1_escuro"] for r in validos]))
        res["M08_escuro_max"] = float(np.max([r["escuro_pct"] for r in validos]))
        res["M10_degraus_total"] = int(sum(r["degraus"] for r in validos))
        res["M17_retas_media"] = float(np.mean([r["retas"] for r in validos]))
        lx = [r["luz_x"] for r in validos if "luz_x" in r]
        ly = [r["luz_y"] for r in validos if "luz_y" in r]
        if lx:
            res["M15_luz_x"], res["M15_luz_y"] = float(np.mean(lx)), float(np.mean(ly))
        for nome in cfg["chao"]:
            vals = [r.get(f"contraste_{nome}") for r in validos if f"contraste_{nome}" in r]
            if vals:
                res[f"M14_contraste_{nome}"] = float(np.mean(vals))
        res["altura"] = [min(r["altura"] for r in validos), max(r["altura"] for r in validos)]
        res["largura"] = [min(r["largura"] for r in validos), max(r["largura"] for r in validos)]
        info["resumo"] = res
        # metas de imagem
        om, ox = ORFAOS_TIPO.get(args.tipo, (ORFAOS_MEDIA, ORFAOS_MAX))
        if res["M04_orfaos_media"] > om or res["M04_orfaos_max"] > ox:
            falha("M04", estado, round(res["M04_orfaos_media"] * 100, 3), f"<= {om:.1%} (pior quadro {ox:.1%})",
                  f"órfãos {res['M04_orfaos_media'] * 100:.2f}% (pior quadro {res['M04_orfaos_max'] * 100:.2f}%)")
        cmin = CLUSTER_MIN_PREENCHIMENTO.get(args.tipo, CLUSTER_MIN[args.tipo]) if ctx["contorno_px"] < 2 else CLUSTER_MIN[args.tipo]
        if cmin and res["M05_cluster_medio"] < cmin:
            falha("M05", estado, round(res["M05_cluster_medio"], 1), f">= {cmin}", f"cluster médio {res['M05_cluster_medio']:.0f} px")
        if ctx["contorno_px"] == 0:
            pass  # sem borda escura: o anel externo é preenchimento, não há meta de contorno
        elif ctx["contorno_px"] == 1 and (args.tipo in GRUPO_FIGURA or args.tipo == "criatura"):
            m1 = 0.60 if (args.com_equipamento or args.com_efeito) else 0.70
            if res["M06_anel1_mediana"] < m1:
                falha("M06", estado, round(res["M06_anel1_mediana"], 3), f">= {m1}", f"anel 1 do contorno fino {res['M06_anel1_mediana']:.0%}")
        elif args.tipo in GRUPO_FIGURA or args.tipo == "criatura":
            m1, m2 = (0.65, 0.60) if args.tipo in ("criatura", "icone") else (0.70, 0.65)
            if args.com_equipamento:  # lâmina e cabo sem contorno (como no Tiny)
                m1 = min(m1, 0.60)
            if args.com_efeito:  # smear e partículas não levam contorno
                m1 = min(m1, 0.55)
            if res["M06_anel1_mediana"] < m1:
                falha("M06", estado, round(res["M06_anel1_mediana"], 3), f">= {m1}", f"anel 1 do contorno {res['M06_anel1_mediana']:.0%}")
            if res["M07_anel2_mediana"] < m2:
                falha("M07", estado, round(res["M07_anel2_mediana"], 3), f">= {m2}", f"anel 2 do contorno {res['M07_anel2_mediana']:.0%}")
        elif args.tipo in GRUPO_CENARIO:
            bc, be = BORDA_CENARIO[args.tipo]
            if res["M06_anel1_mediana"] < bc or res["M06_anel1_escuro_mediana"] < be:
                falha("M06", estado, round(res["M06_anel1_mediana"], 3), f">= {bc:.2f} no contorno e >= {be:.2f} escuro",
                      f"borda: {res['M06_anel1_mediana']:.0%} contorno, {res['M06_anel1_escuro_mediana']:.0%} escura")
        if args.tipo != "efeito" and res["M08_escuro_max"] > 0.01:
            falha("M08", estado, round(res["M08_escuro_max"], 4), "<= 1%", f"{res['M08_escuro_max']:.1%} do preenchimento escuro (L < 0,36)")
        por_q = res["M10_degraus_total"] / len(validos)
        res["M10_degraus_por_quadro"] = round(por_q, 1)
        if por_q > 15 and (args.tipo in GRUPO_FIGURA or args.tipo == "criatura"):  # só figuras (2026-11-05); a régua (peão do Tiny) fica em ~11 por quadro: tufos de cabelo contam como "degrau"
            aviso("M10", estado, f"{por_q:.0f} degraus irregulares por quadro na silhueta (régua ~11; amarelo no overlay)")
        if args.tipo in TIPOS_RETAS and res["M17_retas_media"] > RETAS_MAX:
            falha("M17", estado, round(res["M17_retas_media"], 3), f"<= {RETAS_MAX}",
                  f"{res['M17_retas_media']:.0%} da borda da silhueta em trechos retos de {RETA_MIN}+ px: forma de primitiva "
                  f"(caixa, retângulo, elipse cortada). Quebre as quinas e use curvas com degraus (laranja no overlay)")
        if args.tipo in GRUPO_FIGURA and "M15_luz_x" in res and not (res["M15_luz_x"] >= 0.10 or res["M15_luz_y"] <= -0.20):
            aviso("M15", estado, f"luz: x {res['M15_luz_x']:+.2f}, y {res['M15_luz_y']:+.2f} (esperado x ≥ +0,10 ou y ≤ −0,20)")
        if args.tipo in GRUPO_FIGURA:
            for nome in cfg["chao"]:
                v = res.get(f"M14_contraste_{nome}")
                if v is not None and v < 0.40:
                    aviso("M14", estado, f"contraste com o chão {nome}: {v:.0%} do preenchimento (esperado ≥ 40%)")
        na_borda = sum(r["na_borda"] for r in validos)
        if na_borda and args.quadro:
            if args.tipo in TIPOS_CENARIO_ANIM or args.tipo == "efeito":
                aviso("A09", estado, f"{na_borda} px encostando na borda do quadro (a copa ou o prop pode estar cortado)")
            else:
                falha("A09", estado, na_borda, 0, f"{na_borda} px encostando na borda do quadro (cortado)")
        # ---- animação
        anim = {}
        n = len(quadros)
        if n >= 2 and args.tipo not in ("tile", "icone", "retrato", "ui"):
            loop = (estado in loops) or (cat in LOOP_PADRAO and estado not in sem_loops)
            pares = list(range(n if loop else n - 1))
            if cat in ("dano", "morte"):
                # o quadro de flash (silhueta inteira numa cor clara) muda ~100% e inflaria a média: fica de fora
                flash = [i for i, f in enumerate(quadros) if quadro_flash(f)]
                anim["flash_quadros"] = flash
                if len(flash) > 1:
                    aviso("A12", estado, f"{len(flash)} quadros de flash ({flash}): o flash é 1 quadro (segure pela duração)")
                pares = [i for i in pares if i not in flash and (i + 1) % n not in flash]
            d = [diferenca(quadros[i], quadros[(i + 1) % n]) for i in pares]
            rd = [redesenho(quadros[i], quadros[(i + 1) % n]) for i in pares]
            anim["A01_muda"] = float(np.mean(d)) if d else 1.0
            anim["A02_redesenho"] = float(np.mean(rd)) if rd else 1.0
            anim["A03_iguais"] = int(sum(1 for i in pares if np.array_equal(quadros[i], quadros[(i + 1) % n])))
            if loop and n >= 3:
                anim["A04_costura"] = float(d[-1] / max(np.mean(d[:-1]), 1e-6))
            pes = [r["pe"] for r in validos]
            anim["A05_linha_pe"] = int(max(pes) - min(pes))
            cy = [r["centro_y"] for r in validos]
            anim["A06_quique"] = float(max(cy) - min(cy))
            ar = [r["area"] for r in validos]
            anim["A07_massa"] = float((max(ar) - min(ar)) / max(np.mean(ar), 1))
            b_tot, b_pts = 0.0, []
            for i in range(n):
                v, pts = boil(quadros[i - 1], quadros[i], quadros[(i + 1) % n])
                b_tot = max(b_tot, v)
                for (y, x) in pts:
                    marcas[i].append((int(x), int(y), (40, 220, 255)))
            anim["A08_boil_max"] = b_tot
            anim["A10_quadros_com_sombra"] = int(sum(1 for r in validos if r.get("semi", 0) > 0))
            anim["loop"] = loop
            info["animacao"] = anim
            mmin, rmin = METAS_ANIM.get(cat, METAS_ANIM["idle"])
            if cat == "idle" and args.ritmo == "calmo":
                mmin, rmin = IDLE_CALMO
            if cat == "idle" and args.ritmo != "calmo" and anim["A02_redesenho"] < METAS_ANIM["idle"][1] and anim["A02_redesenho"] >= IDLE_CALMO[1]:
                aviso("A02", estado, "idle quase parado: se for de propósito, declare 'ritmo: calmo' na ficha")
            if anim["A01_muda"] < mmin:
                falha("A01", estado, round(anim["A01_muda"], 3), f">= {mmin}", f"muda {anim['A01_muda']:.0%} por quadro (meta {mmin:.0%} para {cat})")
            if anim["A02_redesenho"] < rmin:
                falha("A02", estado, round(anim["A02_redesenho"], 3), f">= {rmin}", f"redesenho {anim['A02_redesenho']:.0%} (meta {rmin:.0%} para {cat}): a forma só desliza")
            if anim["A03_iguais"]:
                if cat == "ambiente":
                    aviso("A03", estado, f"{anim['A03_iguais']} par(es) de quadros idênticos: para segurar a pose, prefira a duração do quadro")
                else:
                    falha("A03", estado, anim["A03_iguais"], 0, f"{anim['A03_iguais']} par(es) de quadros idênticos (quadro parado)")
            if "A04_costura" in anim and not (0.4 <= anim["A04_costura"] <= 1.8):
                texto = f"costura do loop {anim['A04_costura']:.2f}× a média: o último quadro não encaixa no primeiro"
                if cat == "ambiente":
                    aviso("A04", estado, texto)
                else:
                    falha("A04", estado, round(anim["A04_costura"], 2), "0,4 a 1,8", texto)
            if cat in ("idle", "ambiente") and args.tipo not in TIPOS_CENARIO_ANIM and args.tipo != "efeito":
                pes = [r["pe"] for r in validos]
                saltos = [abs(pes[(i + 1) % len(pes)] - pes[i]) for i in range(len(pes) if loop else len(pes) - 1)]
                anim["A05_salto_max"] = int(max(saltos)) if saltos else 0
                if anim["A05_salto_max"] > 2:
                    falha("A05", estado, anim["A05_salto_max"], "<= 2", f"a linha do pé salta {anim['A05_salto_max']} px de um quadro para o outro (pés pulando)")
                elif anim["A05_linha_pe"] > 2:
                    aviso("A05", estado, f"a linha do pé desce/sobe {anim['A05_linha_pe']} px ao longo do idle (suave; confira se é intencional)")
            lim_boil = 0.02 if args.com_efeito else 0.01
            if anim["A08_boil_max"] > lim_boil:
                falha("A08", estado, round(anim["A08_boil_max"], 4), f"<= {lim_boil:.0%}", f"boil {anim['A08_boil_max']:.1%} (pixels piscando)")
            faixa = {"idle": (0.5, 5.0), "andar": (1.0, 7.0), "correr": (2.0, 10.0)}.get(cat)
            if faixa and not (faixa[0] <= anim["A06_quique"] <= faixa[1]):
                aviso("A06", estado, f"quique {anim['A06_quique']:.1f} px (faixa {faixa[0]}–{faixa[1]})")
            if cat in ("idle", "andar", "correr") and anim["A07_massa"] > 0.12:
                aviso("A07", estado, f"área varia {anim['A07_massa']:.0%} entre quadros (massa constante?)")
            if args.tipo in ("personagem", "inimigo", "criatura", "boss") and cat != "morte" and anim["A10_quadros_com_sombra"] < n / 2:
                aviso("A10", estado, "sem sombra no chão na maioria dos quadros")
        # ---- tiles
        if args.tipo == "tile":
            H, W = full.shape[:2]
            if H % 64 or W % 64:
                falha("T02", estado, f"{W}x{H}", "múltiplo de 64", f"atlas {W}×{H} fora da grade de 64")
            emendas = {}
            for ct in args.centro_tile:
                col, lin = (int(v) for v in ct.split(","))
                t = full[lin * 64:(lin + 1) * 64, col * 64:(col + 1) * 64]
                razao, det = emenda_tile(t)
                emendas[ct] = {"razao": round(razao, 3), **det}
                if razao > 1.0:
                    falha("T01", estado, round(razao, 3), "<= 1,0", f"tile {ct}: a costura muda {razao:.1f}× o limite (h {det['costura_h']}, v {det['costura_v']}): emenda visível")
            info["T01_emenda"] = emendas
        # ---- efeitos
        if args.tipo == "efeito":
            Lq = []
            for f in quadros:
                op = f[..., 3] == 255
                Lq.append(float(C.oklab(f[..., :3][op])[0].mean()) if op.any() else 0.0)
            meio = len(Lq) // 2
            seg = Lq[meio:]
            incl = float(np.polyfit(range(len(seg)), seg, 1)[0]) if len(seg) >= 2 else 0.0
            info["E01_inclinacao_L"] = incl
            if incl > 0.01:  # aviso desde 2026-11-05: a poeira do Tiny (Dust_02) dá +0,0102; quem reprova é a E05
                aviso("E01", estado, f"o L médio sobe {incl:+.3f}/quadro na 2ª metade (efeito quente deve esfriar)")

            def nucleo(f):
                op = f[..., 3] == 255
                return float((C.oklab(f[..., :3][op])[0] >= 0.90).sum()) if op.any() else 0.0

            nucs = [nucleo(f) for f in quadros]
            n_ini = max(nucs)  # o pico do núcleo claro (na cura do Tiny ele cresce até o meio)
            n_fim = max(nucs[-max(1, len(quadros) // 3):])
            areas = [float((f[..., 3] == 255).sum()) for f in quadros]
            efeito_loop = estado in loops
            if n_ini > 0:
                info["E05_nucleo_fim_rel"] = n_fim / n_ini
                if n_fim / n_ini > 0.40:  # régua (9 efeitos do Tiny, 2026-11-05): no máximo 0,19 (cura)
                    falha("E05", estado, round(n_fim / n_ini, 3), "<= 0,40",
                          f"o núcleo claro no último terço é {n_fim / n_ini:.0%} do pico (o efeito não esfria)")
            if not efeito_loop and len(quadros) >= 3 and max(areas) > 0:
                info["E06_area_final_rel"] = areas[-1] / max(areas)
                info["E07_pico_rel"] = int(np.argmax(areas)) / (len(areas) - 1)
                if areas[-1] / max(areas) > 0.10:  # régua: 0,2–9%
                    falha("E06", estado, round(areas[-1] / max(areas), 3), "<= 10%",
                          f"o último quadro ainda tem {areas[-1] / max(areas):.0%} da área do pico (some de uma vez?)")
                if info["E07_pico_rel"] > 0.60:  # régua: no máximo 56%
                    falha("E07", estado, round(info["E07_pico_rel"], 2), "<= 0,60",
                          f"o pico de área vem tarde ({info['E07_pico_rel']:.0%} da duração): o efeito deve expandir rápido")
            nuc = []
            for f in quadros[:2]:
                op = f[..., 3] == 255
                nuc.append(float((C.oklab(f[..., :3][op])[0] >= 0.90).mean()) if op.any() else 0.0)
            info["E02_nucleo"] = max(nuc)
            if max(nuc) < 0.10:
                falha("E02", estado, round(max(nuc), 3), ">= 10%", "sem núcleo claro nos 2 primeiros quadros")
            oc = np.array(ctx["contorno"])
            e_oc = (op_all & np.all(rgb_all == oc, axis=-1)).sum() / max(op_all.sum(), 1)
            info["E04_contorno"] = float(e_oc)
            if e_oc > 0.05:
                falha("E04", estado, round(float(e_oc), 3), "<= 5%", f"{e_oc:.0%} do efeito na cor do contorno")
        info["por_quadro"] = pq
        saida["folhas"][estado] = info
        # ---- overlay
        bbox = C.bbox_uniao(quadros, margem=4)
        img = C.grade_quadros(quadros, bbox, C.hex2rgb(cfg["fundo_prancha"]), limite=cfg["limite_imagem"],
                              rotulos=[f"q{i}" for i in range(len(quadros))], marcas=marcas,
                              titulo=f"overlay {estado}: vermelho=órfão amarelo=degrau magenta=borda ciano=boil")
        img.save(os.path.join(args.saida, f"overlay_{estado}.png"))

    with open(os.path.join(args.saida, "medidas.json"), "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=1)
    print(f"{len(saida['falhas'])} falha(s), {len(saida['avisos'])} aviso(s) -> {os.path.join(args.saida, 'medidas.json')}")
    for x in saida["falhas"]:
        print(f"  FALHA {x['id']} ({x['criterio']}, {x['severidade']}) [{x['estado']}]: {x['texto']}")
    for x in saida["avisos"]:
        print(f"  aviso {x['id']} [{x['estado']}]: {x['texto']}")
    return 1 if saida["falhas"] else 0


if __name__ == "__main__":
    sys.exit(main())
