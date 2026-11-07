"""Etapa de CONCEITO da skill (v4): o Codex gera a imagem de conceito e este script a traz para o pixel.

A imagem do Codex NUNCA vira asset. Ela decide forma, proporção, silhueta e apelo. Depois, `converter` faz uma
.grade de partida (tamanho real, cores travadas na legenda da ficha) que é LIMPA À MÃO antes do portão.

Subcomandos:
  gerar     --prompt <prompt.md> --saida <pasta> [--img ref.png ...] [--modelo M]
            roda `codex exec` com o prompt (o Codex usa a geração de imagem embutida) e copia para <pasta> as
            imagens novas de ~/.codex/generated_images/<sessão>/exec-*.png. Grava também o log do Codex.
  converter <imagem> --legenda <arquivo.grade> --altura <px com contorno> --saida <x.grade>
            [--pivo-x auto] [--fundo auto|#rrggbb] [--tolerancia 0.08] [--sem-contorno-externo]
            recorta a figura (o fundo liso é tirado por inundação a partir dos cantos), reduz por média de área
            até a altura pedida (sem o contorno de 2 px, que o grade.py põe) e troca cada pixel pela cor mais
            próxima (OKLab) da legenda `cores` da .grade indicada. Escreve uma .grade com o mesmo cabeçalho.
            --modo moda [--tirar-contorno 1]: quantiza a imagem inteira e pega a cor mais frequente de cada bloco.
            Para conceito chapado (cel shading, contorno grosso) sai muito mais limpo que a média.
  afinar    <x.grade> --saida <y.grade> [--proteger-area x0,y0,x1,y1 ...]
            tira a cor de contorno encostada no vazio e afina as linhas internas para 1 px (Zhang-Suen).
  limpar    <x.grade> --saida <y.grade> [--min 6] [--proteger letras] [--proteger-area x0,y0,x1,y1 ...]
            funde manchas menores que --min na cor vizinha mais comum.
  Fluxo de referência fiel (construtor v04): converter --modo moda --tirar-contorno 1 -> limpar --min 4 ->
  afinar -> limpar --min 3 -> rosto à mão por cima. Os três são limpeza mecânica: não criam forma.

Regras (KB/pipeline/conceito.md):
  - não anexe sprites do Tiny Swords nem de outra obra ao Codex: a régua entra no prompt como princípios escritos;
  - anexos permitidos: assets do próprio Artur (escala e acabamento) e a paleta Horys.
"""
import argparse
import glob
import os
import shutil
import subprocess
import sys
import time

import numpy as np
from PIL import Image
from scipy import ndimage

AQUI = os.path.dirname(os.path.abspath(__file__))
try:  # como módulo (python -m horys_pixel.motor.X) ou como script direto (python X.py)
    from . import comum as C
except ImportError:
    import comum as C  # noqa: E402

GEN = os.path.join(os.path.expanduser("~"), ".codex", "generated_images")


def imagens_codex():
    return {p: os.path.getmtime(p) for p in glob.glob(os.path.join(GEN, "*", "*.png"))}


def gerar(a):
    os.makedirs(a.saida, exist_ok=True)
    prompt = open(a.prompt, encoding="utf-8").read()
    antes = imagens_codex()
    cmd = ["codex", "exec", "--skip-git-repo-check", "-s", "read-only"]
    if a.modelo:
        cmd += ["-m", a.modelo]
    for i in a.img or []:
        cmd += ["-i", i]
    cmd.append("-")
    t0 = time.time()
    r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       shell=(os.name == "nt"))
    log = os.path.join(a.saida, "codex_log.txt")
    with open(log, "w", encoding="utf-8") as f:
        f.write(f"$ {' '.join(cmd)}\n\n--- stdout\n{r.stdout}\n--- stderr\n{r.stderr}\n")
    novas = sorted((p for p, m in imagens_codex().items() if p not in antes or m > antes[p]),
                   key=os.path.getmtime)
    copiadas = []
    for k, p in enumerate(novas, 1):
        dst = os.path.join(a.saida, f"conceito_{k:02d}.png")
        while os.path.exists(dst):
            k += 100
            dst = os.path.join(a.saida, f"conceito_{k:02d}.png")
        shutil.copy2(p, dst)
        copiadas.append(dst)
    print(f"codex: código {r.returncode}, {time.time() - t0:.0f} s, log em {log}")
    if not copiadas:
        print("nenhuma imagem nova em ~/.codex/generated_images (veja o log: limite de uso, recusa ou erro)")
        return 1
    for c in copiadas:
        print("imagem:", c)
    return 0


def ler_legenda(caminho):
    linhas = open(caminho, encoding="utf-8").read().splitlines()
    cab, cores, modo = [], {}, None
    for l in linhas:
        if l.startswith("---"):
            break
        cab.append(l)
        s = l.split()
        if s and s[0] == "cores":
            modo = "cores"
            continue
        if modo == "cores" and len(s) == 2 and s[1].startswith("#"):
            cores[s[0]] = s[1]
    if not cores:
        sys.exit(f"{caminho}: sem bloco 'cores'")
    return cab, cores


def tirar_fundo(rgb, fundo, tol):
    L = np.stack(C.oklab(rgb.reshape(-1, 3).astype(float)), -1).reshape(*rgb.shape[:2], 3)
    if fundo == "auto":
        h, w = rgb.shape[:2]
        cantos = np.concatenate([L[:8, :8].reshape(-1, 3), L[:8, -8:].reshape(-1, 3),
                                 L[-8:, :8].reshape(-1, 3), L[-8:, -8:].reshape(-1, 3)])
        ref = np.median(cantos, 0)
    else:
        ref = np.array(C.oklab(np.array(C.hex2rgb(fundo), float)))
    perto = np.linalg.norm(L - ref, axis=-1) < tol
    lab, _ = ndimage.label(perto)
    bordas = set(np.unique(np.r_[lab[0], lab[-1], lab[:, 0], lab[:, -1]])) - {0}
    fundo_m = np.isin(lab, list(bordas))
    fig = ~fundo_m
    lab2, n = ndimage.label(fig)
    if n > 1:  # fica só a maior figura e o que está perto dela (pedras soltas etc.)
        tam = np.bincount(lab2.ravel())
        tam[0] = 0
        fig = tam[lab2] >= max(30, tam.max() * 0.002)
    return fig


def grade_nativa(rgb):
    """O conceito do Codex é pixel art ampliada: acha o tamanho do bloco e a fase em cada eixo pelas bordas de cor
    (coerência de fase das bordas módulo o bloco)."""
    res = []
    for eixo in (1, 0):
        d = np.abs(np.diff(rgb.astype(int), axis=eixo)).sum(-1) > 60
        pos = np.nonzero(d)[eixo] + 1
        melhor = (0.0, 1.0, 0.0)
        for s in np.arange(4.0, 24.0, 0.01):
            z = np.mean(np.exp(2j * np.pi * (pos % s) / s))
            r = abs(z) * (1 + 0.002 * s)  # leve preferência pelo bloco maior (evita submúltiplos)
            if r > melhor[0]:
                melhor = (r, s, (np.angle(z) % (2 * np.pi)) / (2 * np.pi) * s)
        res.append(melhor)
    return res  # [(coerência, bloco, fase) em x, idem em y]


def amostrar_nativo(rgb, gx, gy):
    (_, sx, fx), (_, sy, fy) = gx, gy
    xs = np.arange(fx + sx / 2, rgb.shape[1], sx)
    ys = np.arange(fy + sy / 2, rgb.shape[0], sy)
    out = np.zeros((len(ys), len(xs), 3))
    for i, y in enumerate(ys):
        for j, x in enumerate(xs):
            y0, x0 = int(y), int(x)
            out[i, j] = np.median(rgb[max(0, y0 - 2):y0 + 3, max(0, x0 - 2):x0 + 3].reshape(-1, 3), 0)
    return out


def reduzir_moda(rgb, fig, cores, W, H):
    """Modo moda (construtor v04, 2026-11-05): quantiza a imagem INTEIRA na legenda (OKLab) e escolhe, em cada bloco,
    a cor MAIS FREQUENTE. Para conceito chapado (cel shading) sai bem mais limpo que a média de área, que mistura o
    contorno interno com as cores vizinhas e cria tons de transição. Bloco com menos de 50% de figura = vazio."""
    letras = list(cores)
    pal_L = np.stack(C.oklab(np.array([C.hex2rgb(cores[k]) for k in letras], float)), -1)
    idx = np.empty(fig.shape, int)
    for y0 in range(0, fig.shape[0], 256):  # em faixas, para não estourar memória em imagem grande
        L = np.stack(C.oklab(rgb[y0:y0 + 256].reshape(-1, 3).astype(float)), -1)
        d = np.linalg.norm(L[:, None, :] - pal_L[None], axis=-1)
        idx[y0:y0 + 256] = d.argmin(1).reshape(-1, fig.shape[1])
    idx[~fig] = -1
    ey, ex = fig.shape[0] / H, fig.shape[1] / W
    out = np.full((H, W), ".", dtype="<U1")
    for y in range(H):
        a0 = int(y * ey); a1 = max(int((y + 1) * ey), a0 + 1)
        for x in range(W):
            b0 = int(x * ex); b1 = max(int((x + 1) * ex), b0 + 1)
            blk = idx[a0:a1, b0:b1].ravel()
            if (blk >= 0).mean() < 0.5:
                continue
            out[y, x] = letras[np.bincount(blk[blk >= 0], minlength=len(letras)).argmax()]
    return out


def ler_grade_corpo(caminho):
    linhas = open(caminho, encoding="utf-8").read().splitlines()
    i0 = next(i for i, l in enumerate(linhas) if l.startswith("---"))
    corpo = [l for l in linhas[i0 + 1:] if not l.startswith("---")]
    W = max(len(l) for l in corpo)
    return linhas[:i0 + 1], np.array([list(l.ljust(W, ".")) for l in corpo])


def gravar_grade(caminho, cab, g):
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("\n".join(cab) + "\n")
        for row in g:
            s = "".join(row).rstrip(".")
            f.write((s or ".") + "\n")


def areas(lista, forma):
    m = np.zeros(forma, bool)
    for r in lista or []:
        x0, y0, x1, y1 = (int(v) for v in r.split(","))
        m[y0:y1 + 1, x0:x1 + 1] = True
    return m


def afinar(a):
    """Limpeza mecânica das linhas de contorno da conversão (não cria forma):
    1) a cor do contorno encostada no vazio vira a cor vizinha (o grade.py põe o anel de 2 px por fora);
    2) as linhas internas são afinadas para 1 px (Zhang-Suen); o pixel tirado vira a cor vizinha mais comum.
    As áreas de --proteger-area (x0,y0,x1,y1, inclusive) não mudam: rosto, olho, fivela."""
    cab, g = ler_grade_corpo(a.grade)
    _, cores = ler_legenda(a.grade)
    cor_oc = next((l.split()[1].lower() for l in cab if l.split()[:1] == ["cor_contorno"]), "#18122c")
    oc = next((k for k, v in cores.items() if v.lower() == cor_oc), None)
    if oc is None:
        sys.exit(f"{a.grade}: nenhuma letra com a cor de contorno {cor_oc}")
    H, W = g.shape
    prot = areas(a.proteger_area, g.shape)

    def vizinha(y, x):
        v = [g[j, i] for j in (y - 1, y, y + 1) for i in (x - 1, x, x + 1)
             if (j, i) != (y, x) and 0 <= j < H and 0 <= i < W and g[j, i] not in (oc, ".")]
        return max(sorted(set(v)), key=v.count) if v else None

    borda = 0
    for _ in range(2):
        mud = []
        for y, x in zip(*np.nonzero((g == oc) & ~prot)):
            if any(not (0 <= j < H and 0 <= i < W) or g[j, i] == "."
                   for j, i in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1))):
                c = vizinha(y, x)
                if c:
                    mud.append((y, x, c))
        for y, x, c in mud:
            g[y, x] = c
        borda += len(mud)
    m = np.pad((g == oc).astype(np.uint8), 1)

    def passo(m, k):
        P = [m[:-2, 1:-1], m[:-2, 2:], m[1:-1, 2:], m[2:, 2:], m[2:, 1:-1], m[2:, :-2], m[1:-1, :-2], m[:-2, :-2]]
        B = sum(P)
        seq = P + [P[0]]
        A = sum(((seq[i] == 0) & (seq[i + 1] == 1)).astype(int) for i in range(8))
        cond = ((P[0] * P[2] * P[4] == 0) & (P[2] * P[4] * P[6] == 0)) if k == 0 else \
               ((P[0] * P[2] * P[6] == 0) & (P[0] * P[4] * P[6] == 0))
        rem = (m[1:-1, 1:-1] == 1) & (B >= 2) & (B <= 6) & (A == 1) & cond & ~np.pad(prot, 0)
        m2 = m.copy()
        m2[1:-1, 1:-1][rem] = 0
        return m2, rem.any()

    while True:
        m, r1 = passo(m, 0)
        m, r2 = passo(m, 1)
        if not (r1 or r2):
            break
    fino = m[1:-1, 1:-1] == 1
    mud = [(y, x, vizinha(y, x)) for y, x in zip(*np.nonzero((g == oc) & ~fino))]
    for y, x, c in mud:
        if c:
            g[y, x] = c
    gravar_grade(a.saida, cab, g)
    print(f"{a.saida}: {borda} px de contorno na borda e {sum(1 for *_, c in mud if c)} px de linha grossa viraram cor")
    return 0


def converter(a):
    cab, cores = ler_legenda(a.legenda)
    im = np.array(Image.open(a.imagem).convert("RGBA"))
    rgb = im[..., :3]
    if a.nativo:
        gx, gy = grade_nativa(rgb)
        print(f"grade nativa: bloco {gx[1]:.2f} x {gy[1]:.2f} px (coerência {gx[0]:.2f}/{gy[0]:.2f})")
        peq = amostrar_nativo(rgb, gx, gy)
        fig_s = tirar_fundo(peq.clip(0, 255).astype(np.uint8), a.fundo, a.tolerancia)
        ys, xs = np.nonzero(fig_s)
        peq, opaco = peq[ys.min():ys.max() + 1, xs.min():xs.max() + 1], fig_s[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        H, W = opaco.shape
    else:
        fig = (im[..., 3] > 127) if (im[..., 3] < 255).any() else tirar_fundo(rgb, a.fundo, a.tolerancia)
        ys, xs = np.nonzero(fig)
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        rgb, fig = rgb[y0:y1, x0:x1], fig[y0:y1, x0:x1]
        alvo = a.altura - (0 if a.sem_contorno_externo else 4)  # o grade.py põe 2 px de contorno em volta
        if a.modo == "moda":
            # o contorno do conceito ocupa os anéis que --tirar-contorno vai descascar: reduz já contando com eles
            alvo += 2 * a.tirar_contorno
        esc = alvo / rgb.shape[0]
        W, H = max(1, round(rgb.shape[1] * esc)), alvo
        if a.modo == "moda":
            moda = reduzir_moda(rgb, fig, cores, W, H)
        else:
            # média de área só sobre os pixels da figura (o fundo não vaza para a borda)
            pil_rgb = Image.fromarray((rgb * fig[..., None]).astype(np.uint8)).resize((W, H), Image.BOX)
            pil_m = Image.fromarray((fig * 255).astype(np.uint8)).resize((W, H), Image.BOX)
            m = np.array(pil_m).astype(float) / 255
            peq = np.array(pil_rgb).astype(float) / np.maximum(m[..., None], 1e-6)
            opaco = m >= 0.5
    letras = list(cores)
    if not a.nativo and a.modo == "moda":
        grade = moda
    else:
        pal = np.array([C.hex2rgb(cores[k]) for k in letras], float)
        pal_L = np.stack(C.oklab(pal), -1)
        px_L = np.stack(C.oklab(peq.reshape(-1, 3).clip(0, 255)), -1)
        d = np.linalg.norm(px_L[:, None, :] - pal_L[None], axis=-1)
        idx = d.argmin(1).reshape(H, W)
        grade = np.where(opaco, np.array(letras)[idx], ".")
    # tira manchas de 1 px isoladas (ruído da redução), trocando pelo vizinho mais comum
    for _ in range(2):
        for y in range(H):
            for x in range(W):
                c = grade[y, x]
                if c == ".":
                    continue
                viz = [grade[j, i] for j, i in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1))
                       if 0 <= j < H and 0 <= i < W]
                if c not in viz:
                    nv = [v for v in viz if v != "."]
                    if nv:
                        grade[y, x] = max(sorted(set(nv)), key=nv.count)
    # o conceito já traz contorno: descasca o anel externo da cor do contorno para o grade.py pôr um de 2 px limpo
    if a.tirar_contorno:
        cor_oc = next((l.split()[1].lower() for l in cab if l.split()[:1] == ["cor_contorno"]), "#18122c")
        oc = [k for k, v in cores.items() if v.lower() == cor_oc]
        for _ in range(a.tirar_contorno):
            vazio = grade == "."
            viz = np.zeros_like(vazio)
            viz[1:] |= vazio[:-1]; viz[:-1] |= vazio[1:]; viz[:, 1:] |= vazio[:, :-1]; viz[:, :-1] |= vazio[:, 1:]
            viz[0] = viz[-1] = True; viz[:, 0] = viz[:, -1] = True
            grade[np.isin(grade, oc) & viz] = "."
    if a.modo == "moda" and not a.nativo:  # recorta a borda que ficou vazia depois de descascar
        ys, xs = np.nonzero(grade != ".")
        grade = grade[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        H, W = grade.shape
    # pivô: base da figura, no meio dos pixels da última linha com figura (ou o x pedido)
    ult = np.nonzero((grade != ".").any(1))[0].max()
    xs_base = np.nonzero(grade[max(0, ult - 3):ult + 1] != ".")[1]
    px = int(np.median(xs_base)) if a.pivo_x == "auto" else int(a.pivo_x)
    novo_cab = []
    for l in cab:
        s = l.split()
        if s and s[0] == "pivo":
            l = f"pivo {px} {int(ult)}"
        novo_cab.append(l)
    if not any(l.split()[:1] == ["pivo"] for l in novo_cab):
        novo_cab.insert(0, f"pivo {px} {int(ult)}")
    with open(a.saida, "w", encoding="utf-8") as f:
        f.write("# PONTO DE PARTIDA convertido do conceito: limpar à mão antes do portão\n")
        f.write(f"# origem: {os.path.abspath(a.imagem)}\n")
        f.write("\n".join(novo_cab) + "\n--- q0\n")
        for y in range(H):
            f.write("".join(grade[y]).rstrip(".") + "\n" if (grade[y] != ".").any() else ".\n")
    usadas = sorted(set(grade[grade != "."]))
    print(f"{a.saida}: {W}x{H} px (+ contorno), pivô ({px},{ult}), cores usadas {len(usadas)}: {' '.join(usadas)}")
    return 0


def limpar(a):
    """Limpeza mecânica da conversão: funde manchas (4-conexas, mesma letra) menores que --min px na letra vizinha
    mais comum. Não cria forma; tira o ruído da redução. As letras de --proteger (olho, brilho) ficam."""
    linhas = open(a.grade, encoding="utf-8").read().splitlines()
    i0 = next(i for i, l in enumerate(linhas) if l.startswith("---"))
    corpo = [l for l in linhas[i0 + 1:] if not l.startswith("---")]
    W = max(len(l) for l in corpo)
    g = np.array([list(l.ljust(W, ".")) for l in corpo])
    prot = set(a.proteger)
    prot_area = areas(a.proteger_area, g.shape)
    for _ in range(4):
        mudou = 0
        for c in sorted(set(g.ravel()) - {"."} - prot):
            lab, n = ndimage.label(g == c)
            tam = np.bincount(lab.ravel())
            for k in np.nonzero((tam < a.min) & (np.arange(len(tam)) > 0))[0]:
                m = lab == k
                if (m & prot_area).any():
                    continue
                borda = ndimage.binary_dilation(m) & ~m
                viz = [v for v in g[borda] if v != "." and v != c]
                if not viz:
                    continue
                g[m] = max(sorted(set(viz)), key=viz.count)
                mudou += 1
        if not mudou:
            break
    with open(a.saida, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas[:i0 + 1]) + "\n")
        for row in g:
            s = "".join(row).rstrip(".")
            f.write((s or ".") + "\n")
    print(f"{a.saida}: manchas < {a.min} px fundidas")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    lp = sub.add_parser("limpar")
    lp.add_argument("grade")
    lp.add_argument("--saida", required=True)
    lp.add_argument("--min", type=int, default=6)
    lp.add_argument("--proteger", default="")
    lp.add_argument("--proteger-area", action="append", help="x0,y0,x1,y1 (inclusive); repita para mais de uma")
    af = sub.add_parser("afinar")
    af.add_argument("grade")
    af.add_argument("--saida", required=True)
    af.add_argument("--proteger-area", action="append", help="x0,y0,x1,y1 (inclusive); repita para mais de uma")
    g = sub.add_parser("gerar")
    g.add_argument("--prompt", required=True)
    g.add_argument("--saida", required=True)
    g.add_argument("--img", action="append")
    g.add_argument("--modelo", default="")
    c = sub.add_parser("converter")
    c.add_argument("imagem")
    c.add_argument("--legenda", required=True)
    c.add_argument("--altura", type=int, default=100, help="altura com contorno (ignorada com --nativo)")
    c.add_argument("--nativo", action="store_true",
                   help="lê o conceito na grade de pixel dele (um pixel por bloco), sem reamostrar")
    c.add_argument("--saida", required=True)
    c.add_argument("--modo", choices=("media", "moda"), default="media",
                   help="media = média de área (padrão antigo); moda = quantiza a imagem inteira e pega a cor mais "
                        "frequente de cada bloco (melhor para conceito chapado; use com --tirar-contorno 1)")
    c.add_argument("--pivo-x", default="auto")
    c.add_argument("--fundo", default="auto")
    c.add_argument("--tolerancia", type=float, default=0.08)
    c.add_argument("--sem-contorno-externo", action="store_true")
    c.add_argument("--tirar-contorno", type=int, default=0,
                   help="descasca N anéis externos da cor do contorno (o conceito já vem contornado)")
    a = ap.parse_args()
    return {"gerar": gerar, "converter": converter, "limpar": limpar, "afinar": afinar}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
