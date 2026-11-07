"""Calibração do revisor (KB/revisao/calibracao.md): a régua tem que passar e as versões estragadas, reprovar.

subcomandos:
  mutacoes  -> gera as versões estragadas da régua (Tiny) em <pasta_calibracao>/casos (uso local; não redistribuir)
  metricas  -> roda medir.py em todos os casos (modo régua) e confere o esperado; grava relatorio_metricas.md
  pacotes --casos a,b,c  -> prepara pacotes de revisão (revisar.py preparar) para o teste do revisor
  resumo    -> lê os veredito.json dos pacotes e calcula o acerto nos bons e nos ruins

Config: comum.config() (HORYS_MOTOR_CONFIG -> ~/.horys-pixel/motor.json -> config_padrao.json). Precisa da chave
"regua" (pasta com os sprites da régua; os nomes de arquivo abaixo são os do Tiny Swords). As saídas vão para
"pasta_calibracao" da config ou ~/.horys-pixel/calibracao (nunca dentro do repo nem da skill). O caso "ia_codex" usa a
imagem de "calibracao_ia" da config (sem a chave: a imagem histórica em ~/.codex/generated_images; sem o arquivo, o caso
fica de fora).
"""
import argparse
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

try:  # como módulo (python -m horys_pixel.motor.X) ou como script direto (python X.py)
    from . import comum as C
except ImportError:
    import comum as C  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
CRUZ = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], bool)

# (nome, arquivo da régua, tipo, quadro, estado, flags)
POSITIVOS = [
    ("peao_idle", "pawn_idle.png", "personagem", 192, "idle", []),
    ("peao_correr", "pawn_run.png", "personagem", 192, "correr", []),
    ("guerreiro_idle", "warrior_idle.png", "personagem", 192, "idle", ["--com-equipamento"]),
    ("guerreiro_correr", "warrior_run.png", "personagem", 192, "correr", ["--com-equipamento"]),
    ("guerreiro_ataque", "warrior_attack.png", "personagem", 192, "ataque", ["--com-equipamento", "--com-efeito"]),
    ("arqueiro_idle", "archer_idle.png", "personagem", 192, "idle", ["--com-equipamento", "--ritmo", "calmo"]),
    ("arqueiro_correr", "archer_run.png", "personagem", 192, "correr", ["--com-equipamento"]),
    ("arqueiro_tiro", "archer_shoot.png", "personagem", 192, "tiro", ["--com-equipamento", "--com-efeito"]),
    ("monge_idle", "monk_idle.png", "personagem", 192, "idle", []),
    ("monge_correr", "monk_run.png", "personagem", 192, "correr", []),
    ("monge_cura", "monk_heal.png", "personagem", 192, "magia", ["--com-efeito"]),
    ("peao_martelo_idle", "pawn_idle_hammer.png", "personagem", 192, "idle", ["--com-equipamento"]),
    ("peao_martelar", "pawn_interact_hammer.png", "personagem", 192, "trabalhar", ["--com-equipamento", "--com-efeito"]),
    ("ovelha", "sheep_idle.png", "criatura", 128, "ambiente", []),
    ("arvore", "tree1.png", "arvore", 192, "ambiente", []),  # 8 quadros de 192x256 (corrigido em 2026-11-05)
    # ---- ampliação de 2026-11-05: todo o cenário da cópia local, recursos, água e os efeitos do pacote grátis
    ("arvore2", "tree2.png", "arvore", 192, "ambiente", []),
    ("arvore3", "tree3.png", "arvore", 192, "ambiente", []),
    ("arvore4", "tree4.png", "arvore", 192, "ambiente", []),
    ("arbusto2", "bush2.png", "prop", 128, "ambiente", []),
    ("pedra2", "rock2.png", "prop", 0, "base", []),
    ("pedra3", "rock3.png", "prop", 0, "base", []),
    ("casa2", "house2.png", "predio", 0, "base", []),
    ("casa3", "house3.png", "predio", 0, "base", []),
    ("quartel", "barracks.png", "predio", 0, "base", []),
    ("arqueria", "archery.png", "predio", 0, "base", ["--com-equipamento"]),  # prédio com props agregados: +3 cores
    ("mosteiro", "monastery.png", "predio", 0, "base", []),
    ("ouro", "resource_gold.png", "recurso", 0, "base", []),
    ("carne", "resource_meat.png", "recurso", 0, "base", []),
    ("madeira", "resource_wood.png", "recurso", 0, "base", []),
    ("espuma", "water_foam.png", "agua", 192, "ambiente", []),
    ("fx_poeira1", "fx/Dust_01.png", "efeito", 64, "poeira", []),
    ("fx_poeira2", "fx/Dust_02.png", "efeito", 64, "poeira", []),
    ("fx_explosao1", "fx/Explosion_01.png", "efeito", 192, "explosao", []),
    ("fx_explosao2", "fx/Explosion_02.png", "efeito", 192, "explosao", []),
    ("fx_fogo1", "fx/Fire_01.png", "efeito", 64, "fogo", []),
    ("fx_fogo2", "fx/Fire_02.png", "efeito", 64, "fogo", []),
    ("fx_fogo3", "fx/Fire_03.png", "efeito", 64, "fogo", []),
    ("fx_respingo", "fx/Water_Splash.png", "efeito", 192, "respingo", []),
    ("fx_cura", "fx/Heal_Effect.png", "efeito", 192, "cura", []),
    ("arbusto", "bush1.png", "prop", 128, "ambiente", []),
    ("pedra", "rock1.png", "prop", 0, "base", []),
    ("casa", "house1.png", "predio", 0, "base", []),
    ("castelo", "castle.png", "predio", 0, "base", []),
    ("grama_tile", "terrain_grass.png", "tile", 0, "base", ["--centro-tile", "1,1"]),
    ("icone", "icon_01.png", "icone", 0, "base", []),
    ("retrato", "avatar_01.png", "retrato", 0, "base", []),
]
# mutações do peão idle (e do tile) -> métricas que devem reprovar ([] = só o olho do revisor pega)
NEGATIVOS = {
    "m_orfaos": ["M04"], "m_contorno_1px": ["M07"], "m_contorno_preto": ["A11"], "m_blur_aa": ["M02", "M03"],
    "m_cores_extra": ["M03"], "m_quadro_congelado": ["A03"], "m_so_desliza": ["A02"], "m_pillow": [],
    "m_banding": [], "m_corte_borda": ["A09"], "m_semitransparente": ["M02"], "m_dither": ["M04", "M05"],
    "m_escala_15": [], "m_pe_deslizando": ["A05"], "m_tile_emenda": ["T01"], "ia_codex": ["M03"],
    # efeitos estragados (2026-11-05): explosão de trás para a frente, explosão cortada e poeira que não esfria
    "m_fx_reverso": ["E05", "E07"], "m_fx_cortado": ["E06"], "m_fx_sem_esfriar": ["E05"],
}


# imagem gerada por IA usada no caso negativo "ia_codex" (só existe na máquina de quem a gerou)
IA_PADRAO = os.path.join(os.path.expanduser("~"), ".codex", "generated_images", "01a19d29-72a5-79e2-abef-c04091e8bff3",
                         "exec-89b326d3-25de-4e59-9578-a5e0fb57a3d2.png")


def pasta_cal():
    cfg = C.config()
    if not C.regua_ok(cfg):
        raise SystemExit("calibrar: configure \"regua\" (pasta com os sprites da régua) na config do motor "
                         "(HORYS_MOTOR_CONFIG ou ~/.horys-pixel/motor.json)")
    p = C.pasta_calibracao(cfg)
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


def mutacoes(_a):
    cfg, p = pasta_cal()
    R = cfg["regua"]
    oc = np.array(C.hex2rgb(cfg["contorno_regua"]), np.uint8)
    base = C.carregar_folha(os.path.join(R, "pawn_idle.png"), 192)
    rng = np.random.default_rng(7)
    casos = {}

    def novo(nome, quadros, tipo="personagem", quadro=192, estado="idle", flags=None):
        caminho = os.path.join(p, "casos", nome + ".png")
        salvar_folha(quadros, caminho)
        casos[nome] = {"arquivo": caminho, "tipo": tipo, "quadro": quadro, "estado": estado, "flags": flags or [],
                       "esperado": "NAO_PASSA", "metricas": NEGATIVOS.get(nome, [])}

    q = []
    for f in base:  # órfãos: 1,5% do interior vira pixel isolado de outra cor
        g = f.copy()
        op = g[..., 3] == 255
        _, miolo = aneis(op, 3)
        ys, xs = np.nonzero(miolo)
        sel = rng.choice(len(xs), size=max(1, int(0.015 * op.sum())), replace=False)
        for i in sel:
            g[ys[i], xs[i], :3] = (239, 225, 171) if tuple(g[ys[i], xs[i], :3]) != (239, 225, 171) else (151, 123, 107)
        q.append(g)
    novo("m_orfaos", q)
    q = []
    for f in base:  # contorno de 1 px: o 2º anel vira a cor de dentro
        g = f.copy()
        op = g[..., 3] == 255
        (r1, r2, r3), _ = aneis(op, 3)
        e_oc = np.all(g[..., :3] == oc, axis=-1)
        alvo = r2 & e_oc
        dentro = ~(r1 | r2) & op & ~e_oc
        idx = ndimage.distance_transform_edt(~dentro, return_distances=False, return_indices=True)
        g[alvo] = g[idx[0][alvo], idx[1][alvo]]
        q.append(g)
    novo("m_contorno_1px", q)
    q = []
    for f in base:
        g = f.copy()
        g[np.all(g[..., :3] == oc, axis=-1) & (g[..., 3] == 255), :3] = 0
        q.append(g)
    novo("m_contorno_preto", q)
    novo("m_blur_aa", [np.array(Image.fromarray(f).filter(ImageFilter.GaussianBlur(0.8))) for f in base])
    q = []
    for f in base:  # cores quase iguais espalhadas
        g = f.copy().astype(np.int16)
        yy, xx = np.mgrid[0:192, 0:192]
        m = (g[..., 3] == 255) & ((xx + yy) % 5 == 0) & ~np.all(g[..., :3] == oc, axis=-1)
        g[m, 0] = np.clip(g[m, 0] + 6, 0, 255)
        q.append(g.astype(np.uint8))
    novo("m_cores_extra", q)
    q = [f.copy() for f in base]
    q[4] = q[3].copy()
    novo("m_quadro_congelado", q)
    desloc = [0, 1, 1, 2, 2, 1, 1, 0]
    novo("m_so_desliza", [np.roll(base[0], d, axis=0) for d in desloc])
    escuro = np.array((71, 65, 68), np.uint8)  # o tom mais escuro de preenchimento do peão
    q = []
    for f in base:  # pillow: anel escuro logo dentro do contorno
        g = f.copy()
        op = g[..., 3] == 255
        (r1, r2, r3, r4), _ = aneis(op, 4)
        g[(r3 | r4) & ~np.all(g[..., :3] == oc, axis=-1), :3] = escuro
        q.append(g)
    novo("m_pillow", q)
    q = []
    for f in base:  # banding: faixas paralelas ao contorno
        g = f.copy()
        op = g[..., 3] == 255
        rs, _ = aneis(op, 8)
        m = (rs[4] | rs[6]) & ~np.all(g[..., :3] == oc, axis=-1)
        g[m, :3] = (173, 160, 129)
        q.append(g)
    novo("m_banding", q)
    q = []
    for f in base:
        g = np.zeros_like(f)
        g[:, :192 - 75] = f[:, 75:]
        q.append(g)
    novo("m_corte_borda", q)
    q = []
    for f in base:
        g = f.copy()
        op = g[..., 3] == 255
        _, miolo = aneis(op, 3)
        g[miolo, 3] = 150
        q.append(g)
    novo("m_semitransparente", q)
    q = []
    for f in base:  # dither em xadrez no cabelo
        g = f.copy()
        yy, xx = np.mgrid[0:192, 0:192]
        m = np.all(g[..., :3] == (151, 123, 107), axis=-1) & ((xx + yy) % 2 == 0)
        g[m, :3] = (94, 84, 85)
        q.append(g)
    novo("m_dither", q)
    q = []
    for f in base:  # escala 1,5x (pixels de tamanhos misturados)
        big = np.array(Image.fromarray(f).resize((288, 288), Image.NEAREST))
        q.append(big[48:240, 48:240])
    novo("m_escala_15", q)
    novo("m_pe_deslizando", [np.roll(f, 3 if i % 2 else 0, axis=0) for i, f in enumerate(base)])
    tile = np.array(Image.open(os.path.join(R, "terrain_grass.png")).convert("RGBA"))
    t = tile.copy()
    t[64:128, 124:128] = np.roll(t[64:128, 124:128], 7, axis=0)
    caminho = os.path.join(p, "casos", "m_tile_emenda.png")
    Image.fromarray(t).save(caminho)
    casos["m_tile_emenda"] = {"arquivo": caminho, "tipo": "tile", "quadro": 0, "estado": "base",
                              "flags": ["--centro-tile", "1,1"], "esperado": "NAO_PASSA", "metricas": ["T01"]}
    ia = cfg["calibracao_ia"] if "calibracao_ia" in cfg else IA_PADRAO
    if ia and os.path.exists(ia):
        im = Image.open(ia).convert("RGBA").resize((192, 192), Image.LANCZOS)
        caminho = os.path.join(p, "casos", "ia_codex.png")
        im.save(caminho)
        casos["ia_codex"] = {"arquivo": caminho, "tipo": "personagem", "quadro": 0, "estado": "base", "flags": [],
                             "esperado": "NAO_PASSA", "metricas": ["M03"]}
    exp = C.carregar_folha(os.path.join(R, "fx", "Explosion_01.png"), 192)
    novo("m_fx_reverso", exp[::-1], tipo="efeito", estado="explosao")
    novo("m_fx_cortado", exp[:max(3, len(exp) // 2)], tipo="efeito", estado="explosao")
    po = C.carregar_folha(os.path.join(R, "fx", "Dust_01.png"), 64)
    novo("m_fx_sem_esfriar", [po[0]] * 2 + [po[0]] * (len(po) - 2), tipo="efeito", quadro=64, estado="poeira")
    for nome, arq, tipo, quadro, estado, flags in POSITIVOS:
        casos[nome] = {"arquivo": os.path.join(R, arq), "tipo": tipo, "quadro": quadro, "estado": estado,
                       "flags": flags, "esperado": "PASSA", "metricas": []}
    with open(os.path.join(p, "casos.json"), "w", encoding="utf-8") as f:
        json.dump(casos, f, ensure_ascii=False, indent=1)
    print(len(casos), "casos em", os.path.join(p, "casos.json"))
    return 0


def metricas(_a):
    cfg, p = pasta_cal()
    casos = json.load(open(os.path.join(p, "casos.json"), encoding="utf-8"))
    linhas = ["| caso | esperado | falhas das métricas | resultado |", "|---|---|---|---|"]
    acertos = {"PASSA": [0, 0], "NAO_PASSA": [0, 0]}
    for nome, c in casos.items():
        saida = os.path.join(p, "medidas", nome)
        cmd = [sys.executable, os.path.join(AQUI, "medir.py"), "--tipo", c["tipo"], "--quadro", str(c["quadro"]),
               "--folha", f"{c['estado']}={c['arquivo']}", "--saida", saida, "--modo", "regua", "--asset", nome] + c["flags"]
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
    sub.add_parser("mutacoes")
    sub.add_parser("metricas")
    pp = sub.add_parser("pacotes")
    pp.add_argument("--casos", required=True)
    sub.add_parser("resumo")
    a = ap.parse_args()
    return {"mutacoes": mutacoes, "metricas": metricas, "pacotes": pacotes, "resumo": resumo}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
