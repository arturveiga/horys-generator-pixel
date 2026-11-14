"""Calibração do revisor (KB/revisao/calibracao.md): a régua tem que passar e as versões estragadas, reprovar.

Perfis (FASE 2, 2026-11-12): --perfil 32 usa a régua do perfil (config.json "perfis") e mutações refeitas no
tamanho, incluindo as de direção (D01–D05) e de guia (G01). Saída em <trabalho>/_calibracao32.

subcomandos:
  mutacoes  -> gera as versões estragadas do corpus de teste em <trabalho>/_calibracao32/casos
  metricas  -> roda medir.py em todos os casos (modo régua) e confere o esperado; grava relatorio_metricas.md
  pacotes --casos a,b,c  -> prepara pacotes de revisão (revisar.py preparar) para o teste do revisor
  resumo    -> lê os veredito.json dos pacotes e calcula o acerto nos bons e nos ruins
"""
import argparse
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

import comum as C

AQUI = os.path.dirname(os.path.abspath(__file__))
CRUZ = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], bool)

# Calibração do portão no CORPUS DE TESTE (config 'corpus_teste', hoje a Eldiran 32x32, CC0). Não é régua de
# estilo: a régua é o Artur. Os bons têm que passar e as mutações têm que reprovar.

PERFIL = "32"
NEGATIVOS32 = {
    "m_orfaos": ["M04"], "m_sem_contorno": ["M06"], "m_blur_aa": ["M02", "M03"], "m_cores_extra": ["M03"],
    "m_quadro_congelado": ["A03"], "m_so_desliza": ["A02"], "m_corte_borda": ["A09"], "m_semitransparente": ["M02"],
    "m_dither": ["M04", "M05"], "m_escala_15": [], "m_pe_deslizando": ["A05"], "m_dir_altura": ["D01", "D03"],
    "m_dir_pe": ["D02"], "m_dir_paleta": ["D05"], "m_guia_perfil": ["G01"],
}


def pasta_cal():
    cfg = C.config()
    p = os.path.join(cfg["trabalho"], "_calibracao" + PERFIL)
    os.makedirs(os.path.join(p, "casos"), exist_ok=True)
    return cfg, p


def salvar_folha(quadros, caminho):
    Image.fromarray(np.concatenate(quadros, axis=1)).save(caminho)


def aneis(op, n):
    rem, out = op.copy(), []
    for _ in range(n):
        er = ndimage.binary_erosion(rem, structure=CRUZ)
        out.append(rem & ~er)
        rem = er
    return out, rem


def mutacoes32(_a):
    """Mutações do perfil 32 a partir do corpus de teste: órfãos, contorno, blur, cores, quadro parado, deslize..."""
    cfg, p = pasta_cal()
    cp = C.config_perfil(cfg, PERFIL)
    R, Q = cp["corpus_teste"], cp["quadro_teste"]
    rng = np.random.default_rng(7)
    casos = {}
    carregar = lambda n: C.carregar_folha(os.path.join(R, n + ".png"), Q)

    def novo(nome, quadros, estado="andar", flags=None, extra=None):
        caminho = os.path.join(p, "casos", nome + ".png")
        salvar_folha(quadros, caminho)
        casos[nome] = {"arquivo": caminho, "tipo": "personagem", "quadro": Q, "estado": estado, "flags": flags or [],
                       "esperado": "NAO_PASSA", "metricas": NEGATIVOS32.get(nome, []), **(extra or {})}
        return caminho

    base = carregar("p05_s")
    preto = np.array((0, 0, 0), np.uint8)
    q = []
    for f in base:  # ruído: 8% do miolo vira o tom vizinho (baixo contraste), espalhado
        g = f.copy()
        op = g[..., 3] == 255
        _, miolo = aneis(op, 2)
        ys, xs = np.nonzero(miolo & ~np.all(g[..., :3] == preto, axis=-1))
        for i in rng.choice(len(xs), size=max(1, int(0.08 * op.sum())), replace=False):
            g[ys[i], xs[i], :3] = np.clip(g[ys[i], xs[i], :3].astype(int) + 28, 0, 255)
        q.append(g)
    novo("m_orfaos", q)
    q = []
    for f in base:  # sem contorno: o anel preto vira a cor de dentro
        g = f.copy()
        op = g[..., 3] == 255
        (r1, r2), _ = aneis(op, 2)
        e_oc = np.all(g[..., :3] == preto, axis=-1) & r1
        dentro = op & ~r1
        idx = ndimage.distance_transform_edt(~dentro, return_distances=False, return_indices=True)
        g[e_oc] = g[idx[0][e_oc], idx[1][e_oc]]
        q.append(g)
    novo("m_sem_contorno", q)
    novo("m_blur_aa", [np.array(Image.fromarray(f).filter(ImageFilter.GaussianBlur(0.6))) for f in base])
    q = []
    for f in base:
        g = f.copy().astype(np.int16)
        yy, xx = np.mgrid[0:Q, 0:Q]
        m = (g[..., 3] == 255) & ((xx + yy) % 3 == 0) & ~np.all(g[..., :3] == 0, axis=-1)
        g[m, 0] = np.clip(g[m, 0] + 6, 0, 255)
        q.append(g.astype(np.uint8))
    novo("m_cores_extra", q)
    q = [f.copy() for f in base]
    q[2] = q[1].copy()
    novo("m_quadro_congelado", q)
    novo("m_so_desliza", [np.roll(base[0], d, axis=0) for d in (0, 1, 0, 1)])
    novo("m_corte_borda", [np.pad(f[:, 12:], ((0, 0), (0, 12), (0, 0))) for f in base])
    q = []
    for f in base:
        g = f.copy()
        op = g[..., 3] == 255
        _, miolo = aneis(op, 2)
        g[miolo, 3] = 150
        q.append(g)
    novo("m_semitransparente", q)
    q = []
    for f in base:  # dither em xadrez no maior material (não preto, não pele)
        g = f.copy()
        op = g[..., 3] == 255
        cs, ct = np.unique(g[..., :3][op].reshape(-1, 3), axis=0, return_counts=True)
        ordem = [c for c in cs[np.argsort(-ct)] if tuple(c) not in ((0, 0, 0), (255, 229, 229))]
        a, b = ordem[0], ordem[1]
        yy, xx = np.mgrid[0:Q, 0:Q]
        m = np.all(g[..., :3] == a, axis=-1) & ((xx + yy) % 2 == 0)
        g[m, :3] = b
        q.append(g)
    novo("m_dither", q)
    q = []
    for f in base:
        big = np.array(Image.fromarray(f).resize((Q * 3 // 2, Q * 3 // 2), Image.NEAREST))
        o = Q // 4
        q.append(big[o:o + Q, o:o + Q])
    novo("m_escala_15", q)
    novo("m_pe_deslizando", [np.roll(f, -3 if i % 2 else 0, axis=0) for i, f in enumerate(base)], estado="idle")
    # direções: s, n, e da mesma figura com uma estragada
    s_, n_, e_ = carregar("p05_s"), carregar("p05_n"), carregar("p05_e")

    def escala_vert(fs, k):
        out = []
        for f in fs:
            op = f[..., 3] > 0
            ys = np.nonzero(op.any(1))[0]
            h = ys.max() - ys.min() + 1
            im = Image.fromarray(f[ys.min():ys.max() + 1]).resize((f.shape[1], int(h * k)), Image.NEAREST)
            g = np.zeros_like(f)
            a = np.array(im)
            a = a[-(ys.max() + 1):]
            g[ys.max() + 1 - a.shape[0]:ys.max() + 1] = a
            out.append(g)
        return out

    def dir_caso(nome, ns, flags_extra=None):
        caminhos = {}
        for d, fs in (("s", s_), ("n", ns), ("e", e_)):
            caminhos[d] = os.path.join(p, "casos", f"{nome}_{d}.png")
            salvar_folha(fs, caminhos[d])
        casos[nome] = {"arquivo": caminhos["s"], "tipo": "personagem", "quadro": Q, "estado": "andar_s",
                       "flags": ["--folha", f"andar_n={caminhos['n']}", "--folha", f"andar_e={caminhos['e']}"] + (flags_extra or []),
                       "esperado": "NAO_PASSA", "metricas": NEGATIVOS32[nome]}

    dir_caso("m_dir_altura", escala_vert(n_, 1.25))
    dir_caso("m_dir_pe", [np.roll(f, -3, axis=0) for f in n_])
    q = []
    for f in n_:  # costas com a paleta trocada (5 tons a mais, em degradê)
        g = f.copy()
        op = g[..., 3] == 255
        ys = np.nonzero(op)[0]
        for k, y in enumerate(range(ys.min(), ys.max() + 1)):
            m = op[y] & ~np.all(g[y, :, :3] == 0, axis=-1)
            g[y, m, 2] = np.clip(g[y, m, 2].astype(int) + (k % 6) * 9, 0, 255)
        q.append(g)
    dir_caso("m_dir_paleta", q)
    # guia: a vista de lado contra a guia de frente (desenhou de perfil quando a guia pedia frente)
    guia = os.path.join(p, "casos", "guia_frente.png")
    salvar_folha(s_[:1], guia)
    cam = novo("m_guia_perfil", e_)
    casos["m_guia_perfil"]["flags"] = ["--guia", f"andar={guia}"]
    # positivos: a régua inteira, e cada figura com as 3 direções juntas (D01–D05 têm que passar) e com a guia de si mesma
    import glob
    figs = {}
    for arq in sorted(glob.glob(os.path.join(R, "p*.png"))):
        nome = os.path.basename(arq)[:-4]
        flags = ["--com-equipamento"] if nome == "p18_e" else []  # segura um item (21 cores)
        casos["r_" + nome] = {"arquivo": arq, "tipo": "personagem", "quadro": Q, "estado": "andar", "flags": flags,
                              "esperado": "PASSA", "metricas": []}
        figs.setdefault(nome[:3], {})[nome[4:]] = arq
    for fig, ds in figs.items():
        if len(ds) == 3:
            casos["d_" + fig] = {"arquivo": ds["s"], "tipo": "personagem", "quadro": Q, "estado": "andar_s",
                                 "flags": ["--folha", f"andar_n={ds['n']}", "--folha", f"andar_e={ds['e']}",
                                           "--com-equipamento", "--guia", f"andar_s={ds['s']}"],
                                 "esperado": "PASSA", "metricas": []}
    with open(os.path.join(p, "casos.json"), "w", encoding="utf-8") as f:
        json.dump(casos, f, ensure_ascii=False, indent=1)
    print(len(casos), "casos em", os.path.join(p, "casos.json"))
    return 0


def mutacoes(_a):
    if PERFIL != "32":
        print(f"perfil {PERFIL} sem corpus de teste: só o perfil 32 tem calibração", file=sys.stderr)
        return 2
    return mutacoes32(_a)


def metricas(_a):
    cfg, p = pasta_cal()
    casos = json.load(open(os.path.join(p, "casos.json"), encoding="utf-8"))
    linhas = ["| caso | esperado | falhas das métricas | resultado |", "|---|---|---|---|"]
    acertos = {"PASSA": [0, 0], "NAO_PASSA": [0, 0]}
    for nome, c in casos.items():
        saida = os.path.join(p, "medidas", nome)
        cmd = [sys.executable, os.path.join(AQUI, "medir.py"), "--tipo", c["tipo"], "--quadro", str(c["quadro"]),
               "--folha", f"{c['estado']}={c['arquivo']}", "--saida", saida, "--modo", "regua", "--asset", nome,
               "--perfil", PERFIL] + c["flags"]
        subprocess.run(cmd, capture_output=True, text=True)
        med = json.load(open(os.path.join(saida, "medidas.json"), encoding="utf-8"))
        ids = sorted({x["id"] for x in med["falhas"]})
        if c["esperado"] == "PASSA":
            ok = not ids
        else:
            ok = (not c["metricas"]) or any(m in ids for m in c["metricas"])
        acertos[c["esperado"]][0] += ok
        acertos[c["esperado"]][1] += 1
        nota = "ok" if ok else "ERRO"
        if c["esperado"] == "NAO_PASSA" and not c["metricas"]:
            nota = "só visual" + (" (métricas também pegaram)" if ids else "")
        linhas.append(f"| {nome} | {c['esperado']} | {', '.join(ids) or '—'} | {nota} |")
    txt = "\n".join(linhas)
    txt += (f"\n\nBons sem falha: {acertos['PASSA'][0]}/{acertos['PASSA'][1]} · "
            f"ruins pegos pelas métricas esperadas (ou só visuais): {acertos['NAO_PASSA'][0]}/{acertos['NAO_PASSA'][1]}\n")
    open(os.path.join(p, "relatorio_metricas.md"), "w", encoding="utf-8").write(txt)
    print(txt)
    return 0


def pacotes(a):
    cfg, p = pasta_cal()
    casos = json.load(open(os.path.join(p, "casos.json"), encoding="utf-8"))
    for nome in a.casos.split(","):
        c = casos[nome]
        pasta = os.path.join(p, "revisoes", nome, "v01")
        cmd = [sys.executable, os.path.join(AQUI, "revisar.py"), "preparar", "--pasta", pasta, "--asset", nome,
               "--tipo", c["tipo"], "--etapa", "efeito" if c["tipo"] == "efeito" else ("tile" if c["tipo"] == "tile" else "animacao" if c["quadro"] else "cor"),
               "--rodada", "1", "--quadro", str(c["quadro"]), "--folha", f"{c['estado']}={c['arquivo']}", "--modo", "regua"] + c["flags"]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        print(f"[{nome}] esperado {c['esperado']}\n" + r.stdout.strip().splitlines()[-1])
    return 0


def resumo(_a):
    cfg, p = pasta_cal()
    casos = json.load(open(os.path.join(p, "casos.json"), encoding="utf-8"))
    base = os.path.join(p, "revisoes")
    linhas = ["| caso | esperado | veredito | critérios reprovados |", "|---|---|---|---|"]
    tp = tn = np_ = nn = 0
    for nome in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        v_path = os.path.join(base, nome, "v01", "veredito.json")
        if not os.path.exists(v_path):
            continue
        v = json.load(open(v_path, encoding="utf-8"))
        esp = casos[nome]["esperado"]
        falhas = sorted({c["id"] for c in v["criterios"] if c["resultado"] == "falha"})
        if esp == "PASSA":
            np_ += 1
            tp += v["veredito"] in ("PASSA", "INDEFINIDO")
        else:
            nn += 1
            tn += v["veredito"] == "NAO_PASSA"
        linhas.append(f"| {nome} | {esp} | {v['veredito']} | {', '.join(falhas) or '—'} |")
    txt = "\n".join(linhas) + f"\n\nAcerto nos bons: {tp}/{np_} · acerto nos ruins: {tn}/{nn}\n"
    open(os.path.join(p, "relatorio_revisor.md"), "w", encoding="utf-8").write(txt)
    print(txt)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    ap.add_argument("--perfil", choices=["16", "32", "64"], default="32")
    sub.add_parser("mutacoes")
    sub.add_parser("metricas")
    pp = sub.add_parser("pacotes")
    pp.add_argument("--casos", required=True)
    sub.add_parser("resumo")
    a = ap.parse_args()
    global PERFIL
    PERFIL = a.perfil
    return {"mutacoes": mutacoes, "metricas": metricas, "pacotes": pacotes, "resumo": resumo}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
