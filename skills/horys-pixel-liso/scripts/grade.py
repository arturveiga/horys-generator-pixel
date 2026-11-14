"""Grade de texto -> PNG. Este script NÃO desenha nada: só traduz a grade que você escreveu,
aplica as regras mecânicas do estilo (contorno externo 2 px e sombra no chão, se pedidos),
gera as prévias para você e para o revisor e roda o PORTÃO DE MEDIDAS (medir.py; perfil 32 calibrado na régua Eldiran).
Portão reprovado = código de saída 1 = corrija antes de chamar o revisor.

Uso:
  python grade.py gerar <arquivo.grade> [<outro.grade> ...] --saida <pasta>
  python grade.py numerar <arquivo.grade> [--quadro N] [--guia]  (grade com régua; --guia mostra a guia por baixo)
  python grade.py diff <arquivo.grade> qA qB              (o que mudou de um quadro para o outro, com coordenadas)
  python grade.py anim <arquivo.grade>                    (deslocamento e px mudados por quadro, como o pxart)

TAMANHO PEQUENO (perfis 16/32, FASE 2 de 2026-11-12; pesquisa-16-32.md):
  perfil 32                  # 16, 32 ou 64 (padrão: pela altura da figura: até 20 -> 16; até 40 -> 32)
  contorno selout            # 1 px por fora no tom mais escuro da rampa do material vizinho (padrão dos perfis 16/32)
  direcao s                  # s (frente), n (costas), e (lado), se/ne/...: o estado vira "<estado>_<dir>"
  espelho w                  # (no arquivo da direção e) gera também a direção w, espelhada
  guia <png> [dx dy]         # silhueta de referência (guia 3D do SpriteKiln ou a referência): G01 e numerar --guia
  Desenhe por direção, nesta ordem: frente (s), costas (n), lado (e), diagonais. Passe todos os arquivos de um estado
  no mesmo 'gerar': o portão confere a coerência entre direções (D01–D05) e sai a prancha _direcoes.png.

Formato do arquivo .grade (texto UTF-8):
  # comentário
  nome curandeiro
  estado idle                # opcional; padrão = nome do arquivo
  tipo personagem            # define o limite de cores
  quadro 192                 # tamanho do quadro final (padrão 192)
  pivo 32 70                 # coluna e linha (base 0) do ponto do pé DENTRO da grade
  ms 100                     # duração de cada quadro
  contorno auto              # auto = 2 px de contorno por fora; manual = a grade já traz;
                             # nenhum = sem borda escura: linhas internas viram a sombra do material vizinho
                             # (olho, sobrancelha e boca sobre a pele continuam escuros);
                             # suave = 1 px por fora, em tom mais leve (cor_contorno, padrão #3f3c56)
  cor_contorno #3f3c56       # opcional
  sombra sim                 # elipse no chão, cor do contorno com alfa ~30%
  sem_contorno g G           # opcional: letras de efeito que não ganham contorno nem entram na silhueta
  sem_borda e w              # opcional: "borda perdida" — letras que entram na silhueta mas não ganham contorno
                             # por fora (lado da luz, como o topo de um elmo)
  limite_cores 12            # opcional: exceção pedida pelo usuário (registre na ficha)
  ritmo calmo                # opcional: idle quase parado de propósito ; vai na ficha
  paleta <arquivo.json>      # opcional: outra paleta travada (mesmo formato; caminho absoluto ou relativo à KB)
  cores
    o #18122c
    p #bc8361
  --- q0
  ....oooo....
  ...opppp o..
  --- q1
  ...

'.' é sempre transparente. Linhas mais curtas são completadas com '.' à direita; todos os quadros têm o mesmo
número de linhas.

CAMADAS (para entregar o .aseprite fatiado, pronto para animar):
  --- q0 @perna_tras            # bloco da camada 'perna_tras' no quadro q0
  ...
  --- q0 @corpo 4 20            # opcional: dx dy = onde a grade da camada começa dentro da grade do quadro
  ...
  A ordem em que cada camada aparece pela 1ª vez é a ordem de baixo para cima. Em cada pixel vale a camada de
  cima; o que fica escondido embaixo continua no .aseprite (pinte a área escondida para a parte poder se mexer).
  O contorno externo (auto/suave) é recomposto sobre o quadro inteiro e vai numa camada 'contorno'; a elipse do
  chão vai na camada 'sombra' (opacidade 77). Linhas internas de 1 px entre partes você desenha na própria camada.
  Com o Aseprite configurado (config.json "aseprite"), o gerar também grava <nome>_<estado>.aseprite (uma camada
  por parte, tag do estado, paleta da legenda) e confere o arquivo reabrindo-o e comparando pixel a pixel com a folha.
"""
import argparse
import io
import json
import os
import re
import sys

import numpy as np
from PIL import Image

AQUI = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(AQUI, "config.json"), encoding="utf-8"))
CONTORNO = "#18122c"
LIMITES_PERFIL = {"32": {"personagem": 20, "inimigo": 20, "npc": 20, "boss": 24, "criatura": 16},
                  "16": {"personagem": 10, "inimigo": 10, "npc": 10, "boss": 12, "criatura": 8}}


def limite_cores(meta):
    """Limite da grade (exceção) ou o do perfil (calibrado na régua do tamanho) ou o do tipo (perfil 64)."""
    return meta.get("limite") or LIMITES_PERFIL.get(meta.get("perfil", "64"), {}).get(meta["tipo"]) or LIMITES.get(meta["tipo"], 10)


LIMITES = {"personagem": 10, "inimigo": 10, "npc": 10, "criatura": 8, "animal": 8, "prop": 8, "arvore": 8,
           "tile": 12, "predio": 18, "boss": 16, "icone": 8, "retrato": 14, "efeito": 6, "recurso": 10, "agua": 6}


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def paleta(arquivo=None):
    p = json.load(open(os.path.join(CFG["kb"], arquivo or CFG["paleta_json"]), encoding="utf-8"))
    cores = set()
    for rampa in p["rampas"].values():
        cores.update(c.lower() for c in rampa)
    cores.add(p["contorno"].lower())
    cores.add(p["brilho"].lower())
    return cores


def ler(caminho):
    meta = {"nome": os.path.splitext(os.path.basename(caminho))[0], "estado": None, "tipo": "personagem",
            "quadro": 192, "pivo": None, "ms": 100, "contorno": "auto", "sombra": "sim"}
    cores, quadros, erros = {}, [], []
    modo, atual = "meta", None
    for n, bruta in enumerate(open(caminho, encoding="utf-8").read().splitlines(), 1):
        linha = bruta.rstrip()
        if modo != "grade" and (not linha.strip() or linha.lstrip().startswith("#")):
            continue
        if linha.startswith("---"):
            modo = "grade"
            tok = linha.lstrip("-").split()
            nome_q = tok[0] if tok and not tok[0].startswith("@") else None
            cam = next((t for t in tok if t.startswith("@")), None)
            if cam:
                resto = tok[tok.index(cam) + 1:]
                try:
                    dx, dy = (int(resto[0]), int(resto[1])) if len(resto) >= 2 else (0, 0)
                except ValueError:
                    erros.append(f"linha {n}: deslocamento da camada precisa ser 'dx dy' inteiros")
                    dx, dy = 0, 0
                nome_q = nome_q or (quadros[-1]["nome"] if quadros else "q0")
                q = next((x for x in quadros if x["nome"] == nome_q), None)
                if q is None:
                    q = {"nome": nome_q, "linhas": [], "n0": n + 1, "camadas": []}
                    quadros.append(q)
                elif "camadas" not in q:
                    erros.append(f"linha {n}: o quadro {nome_q} já foi desenhado sem camadas")
                    q["camadas"] = []
                atual = {"nome": cam[1:], "linhas": [], "n0": n + 1, "dx": dx, "dy": dy}
                q["camadas"].append(atual)
            else:
                atual = {"nome": nome_q or f"q{len(quadros)}", "linhas": [], "n0": n + 1}
                quadros.append(atual)
            continue
        if modo == "grade":
            if not linha.strip():
                continue
            atual["linhas"].append(linha)
            continue
        partes = linha.split()
        if partes[0] == "cores":
            modo = "cores"
            continue
        if modo == "cores" and len(partes) == 2 and partes[1].startswith("#"):
            if len(partes[0]) != 1 or partes[0] == ".":
                erros.append(f"linha {n}: a letra da cor precisa ser 1 caractere diferente de '.'")
            cores[partes[0]] = partes[1].lower()
            continue
        chave = partes[0]
        if chave == "sem_contorno":
            meta["sem_contorno"] = set(partes[1:])
        elif chave == "sem_borda":
            meta["sem_borda"] = set(partes[1:])
        elif chave == "limite_cores":
            meta["limite"] = int(partes[1])
        elif chave == "paleta":
            meta["paleta"] = linha.split(None, 1)[1].strip()
        elif chave == "perfil":
            meta["perfil"] = partes[1]
        elif chave == "direcao":
            meta["direcao"] = partes[1]
        elif chave == "espelho":
            meta["espelho"] = partes[1]
        elif chave == "guia":
            g = linha.split(None, 1)[1].strip().split()
            meta["guia"] = os.path.join(os.path.dirname(os.path.abspath(caminho)), g[0])
            meta["guia_d"] = (int(g[1]), int(g[2])) if len(g) >= 3 else (0, 0)
        elif chave == "cor_contorno":
            meta["cor_contorno"] = partes[1].lower()
        elif chave in ("nome", "estado", "tipo", "contorno", "sombra", "ritmo"):
            meta[chave] = partes[1]
        elif chave in ("quadro", "ms"):
            meta[chave] = int(partes[1])
        elif chave == "pivo":
            meta["pivo"] = (int(partes[1]), int(partes[2]))
        else:
            erros.append(f"linha {n}: não entendi '{linha.strip()}'")
    meta["estado"] = meta["estado"] or os.path.splitext(os.path.basename(caminho))[0]
    if meta.get("direcao") and not meta["estado"].endswith("_" + meta["direcao"]):
        meta["estado_base"] = meta["estado"]
        meta["estado"] = f"{meta['estado']}_{meta['direcao']}"
    else:
        meta["estado_base"] = meta["estado"].rsplit("_", 1)[0] if meta.get("direcao") else meta["estado"]
    if any("camadas" in q for q in quadros):
        meta["camadas"] = compor_camadas(quadros, erros)
    if not quadros:
        erros.append("nenhum quadro ('--- q0')")
    else:
        # linhas mais curtas são completadas com '.' à direita (só a borda direita; o desenho é seu)
        w = max(len(l) for q in quadros for l in q["linhas"]) if quadros[0]["linhas"] else 0
        for q in quadros:
            q["linhas"] = [l.ljust(w, ".") for l in q["linhas"]]
        h = len(quadros[0]["linhas"])
        for q in quadros:
            if len(q["linhas"]) != h:
                erros.append(f"{q['nome']}: {len(q['linhas'])} linhas, esperado {h}")
            for i, l in enumerate(q["linhas"]):
                if len(l) != w:
                    erros.append(f"{q['nome']} linha {i} (arquivo {q['n0'] + i}): largura {len(l)}, esperado {w}")
                for j, c in enumerate(l):
                    if c != "." and c not in cores:
                        erros.append(f"{q['nome']} linha {i} col {j}: letra '{c}' sem cor na legenda")
                        break
            for c in q.get("camadas", []):
                for i, l in enumerate(c["linhas"]):
                    ruim = next((ch for ch in l if ch != "." and ch not in cores), None)
                    if ruim:
                        erros.append(f"{q['nome']} @{c['nome']} (arquivo {c['n0'] + i}): letra '{ruim}' sem cor na legenda")
    if meta["pivo"] is None:
        erros.append("falta 'pivo col lin'")
    return meta, cores, quadros, erros


def compor_camadas(quadros, erros):
    """Empilha as camadas de cada quadro (a 1ª que aparece fica embaixo) numa grade única, que o resto do script usa
    como antes. Guarda em cada camada a grade do tamanho do quadro ('grade'), com o que fica escondido."""
    ordem = []
    for q in quadros:
        if "camadas" not in q:
            erros.append(f"{q['nome']}: quadro sem camadas num arquivo com camadas (use '--- {q['nome']} @parte')")
            q["camadas"] = [{"nome": "desenho", "linhas": q["linhas"], "n0": q["n0"], "dx": 0, "dy": 0}]
        vistos = set()
        for c in q["camadas"]:
            if c["nome"] in vistos:
                erros.append(f"{q['nome']}: camada '{c['nome']}' repetida no mesmo quadro (linha {c['n0'] - 1})")
            vistos.add(c["nome"])
            if c["nome"] not in ordem:
                ordem.append(c["nome"])
    for nome in ("contorno", "sombra"):
        if nome in ordem:
            erros.append(f"o nome de camada '{nome}' é reservado (o script gera essa camada)")
    W = max((c["dx"] + max((len(l) for l in c["linhas"]), default=0)) for q in quadros for c in q["camadas"])
    H = max((c["dy"] + len(c["linhas"])) for q in quadros for c in q["camadas"])
    for q in quadros:
        comp = [["."] * W for _ in range(H)]
        por_nome = {c["nome"]: c for c in q["camadas"]}
        for nome in ordem:  # a ordem global decide o empilhamento em todos os quadros
            c = por_nome.get(nome)
            if c is None:
                continue
            g = [["."] * W for _ in range(H)]
            for i, l in enumerate(c["linhas"]):
                for j, ch in enumerate(l):
                    if ch != ".":
                        g[c["dy"] + i][c["dx"] + j] = ch
                        comp[c["dy"] + i][c["dx"] + j] = ch
            c["grade"] = ["".join(r) for r in g]
        q["linhas"] = ["".join(r) for r in comp]
    return ordem


def dilatar_cruz(m):
    d = m.copy()
    d[1:, :] |= m[:-1, :]
    d[:-1, :] |= m[1:, :]
    d[:, 1:] |= m[:, :-1]
    d[:, :-1] |= m[:, 1:]
    return d


def tom_escuro():
    """cor -> tom mais escuro da rampa dela (para o selout)."""
    out = {}
    for r in rampas().values():
        for c in r:
            out.setdefault(c, r[0])
    return out


def cor_contorno(meta):
    """auto: anil-noite #18122c (2 px). suave: 1 px, padrão #3f3c56 (sombra da rampa masmorra), mais leve."""
    return meta.get("cor_contorno") or (CONTORNO if meta["contorno"] == "auto" else "#3f3c56")


def rampas():
    p = json.load(open(os.path.join(CFG["kb"], CFG["paleta_json"]), encoding="utf-8"))
    return {nome: [c.lower() for c in r] for nome, r in p["rampas"].items()}


def tirar_linhas(letras, cores):
    """contorno nenhum: cada linha escura interna vira a sombra do material vizinho.
    Mantém escuro só o que está desenhado sobre pele (olho, sobrancelha, boca)."""
    R = rampas()
    sombra = {}
    for nome, r in R.items():
        for c in r:
            sombra.setdefault(c, (nome, r[0]))
    h, w = len(letras), len(letras[0])
    g = [list(l) for l in letras]
    escuro = cores.get
    eh_o = lambda i, j: 0 <= i < h and 0 <= j < w and escuro(g[i][j]) == CONTORNO
    visto = set()
    for i in range(h):
        for j in range(w):
            if not eh_o(i, j) or (i, j) in visto:
                continue
            comp, pilha, viz = [], [(i, j)], []
            visto.add((i, j))
            while pilha:
                a, b = pilha.pop()
                comp.append((a, b))
                for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    na, nb = a + da, b + db
                    if eh_o(na, nb):
                        if (na, nb) not in visto:
                            visto.add((na, nb)); pilha.append((na, nb))
                    elif 0 <= na < h and 0 <= nb < w and g[na][nb] != ".":
                        viz.append(sombra.get(escuro(g[na][nb]), ("?", None))[0])
            pele = sum(1 for v in viz if v.startswith("pele"))
            if viz and pele >= 0.8 * len(viz):
                continue                      # rosto: fica escuro
            for a, b in comp:
                for da, db in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                    na, nb = a + da, b + db
                    if 0 <= na < h and 0 <= nb < w and g[na][nb] not in ".":
                        cor = escuro(g[na][nb])
                        if cor != CONTORNO and cor in sombra:
                            g[a][b] = "#" + sombra[cor][1]
                            break
                else:
                    g[a][b] = "."
    return g


def montar(meta, cores, q):
    Q = meta["quadro"]
    px, py = Q // 2, round(Q * 127 / 192)
    img = np.zeros((Q, Q, 4), np.uint8)
    gx, gy = meta["pivo"]
    ox, oy = px - gx, py - gy
    letras = q["linhas"]
    if meta["contorno"] == "nenhum":
        letras = tirar_linhas(letras, cores)
    mask = np.zeros((Q, Q), bool)
    sb = np.zeros((Q, Q), bool)
    for i, l in enumerate(letras):
        for j, c in enumerate(l):
            if c == ".":
                continue
            y, x = oy + i, ox + j
            if not (0 <= x < Q and 0 <= y < Q):
                raise SystemExit(f"{q['nome']}: pixel ({j},{i}) cai fora do quadro {Q}; ajuste o pivô")
            img[y, x] = (*hex_rgb(c if c.startswith("#") else cores[c]), 255)
            if c not in meta.get("sem_contorno", ()):
                mask[y, x] = True
            if c in meta.get("sem_borda", ()):
                sb[y, x] = True
    efeito = (img[..., 3] > 0) & ~mask
    partes = img[..., 3] > 0
    if meta["contorno"] == "selout":
        # 1 px por fora, no tom mais escuro da rampa do material vizinho (o de cima, senão o do lado, senão o de baixo)
        escuro = tom_escuro()
        firme = mask & ~sb
        r1 = dilatar_cruz(mask) & ~mask & ~efeito
        r1 &= ~(dilatar_cruz(sb) & ~dilatar_cruz(firme))
        for y, x in zip(*np.nonzero(r1)):
            for dy, dx in ((1, 0), (0, 1), (0, -1), (-1, 0)):
                yy, xx = y + dy, x + dx
                if 0 <= yy < Q and 0 <= xx < Q and mask[yy, xx]:
                    c = "#%02x%02x%02x" % tuple(img[yy, xx, :3])
                    img[y, x] = (*hex_rgb("#" + escuro.get(c, cor_contorno(meta).lstrip("#")).lstrip("#")), 255)
                    break
        mask = mask | r1
    elif meta["contorno"] in ("auto", "suave"):
        firme = mask & ~sb
        r1 = dilatar_cruz(mask) & ~mask & ~efeito
        r1 &= ~(dilatar_cruz(sb) & ~dilatar_cruz(firme))   # borda perdida: sem contorno junto de sem_borda
        aneis = [r1]
        if meta["contorno"] == "auto":
            aneis.append(dilatar_cruz(firme | r1) & ~(mask | r1) & ~efeito)
        for r in aneis:
            img[r] = (*hex_rgb(cor_contorno(meta)), 255)
            mask = mask | r
    if meta["sombra"] == "sim" and mask.any():
        fundo = np.where(mask[max(0, py - 8):py + 3].any(axis=0))[0]
        larg = (fundo.max() - fundo.min() + 1) * 0.85 if fundo.size else 20
        a, b = larg / 2, larg * 0.4 / 2
        yy, xx = np.mgrid[0:Q, 0:Q]
        elip = (((xx + 0.5 - px) / a) ** 2 + ((yy + 0.5 - py) / b) ** 2 <= 1) & ~mask & ~efeito
        img[elip] = (*hex_rgb(cor_contorno(meta)), 77)
    q["_partes"] = partes          # o que veio da grade (para as camadas do .aseprite)
    q["_origem"] = (ox, oy)
    return img, mask


ALFA_SOMBRA = 77


def camadas_rgba(meta, cores, q, img):
    """Uma imagem Q×Q por camada, de baixo para cima: sombra, contorno e as partes desenhadas.
    Onde a parte aparece no quadro, a cor é a do quadro final (vale para 'contorno nenhum'); onde fica escondida,
    é a cor da própria letra."""
    Q = meta["quadro"]
    ox, oy = q["_origem"]
    partes = q["_partes"]
    alfa = img[..., 3]
    sombra = np.zeros_like(img)
    m = (alfa > 0) & (alfa < 255)
    sombra[m] = img[m]
    sombra[m, 3] = 255                      # a transparência vai na opacidade da camada
    contorno = np.zeros_like(img)
    m = (alfa == 255) & ~partes
    contorno[m] = img[m]
    saida = [("sombra", sombra, ALFA_SOMBRA), ("contorno", contorno, 255)]
    topo = np.full((Q, Q), -1, int)        # índice da camada visível em cada pixel
    imgs = []
    for k, cam in enumerate(q["camadas"]):
        im = np.zeros_like(img)
        for i, l in enumerate(cam["grade"]):
            for j, c in enumerate(l):
                if c != ".":
                    im[oy + i, ox + j] = (*hex_rgb(cores[c]), 255)
                    topo[oy + i, ox + j] = k
        imgs.append(im)
    for k, (cam, im) in enumerate(zip(q["camadas"], imgs)):
        vis = (topo == k) & partes
        im[vis] = img[vis]
        im[(topo == k) & ~partes] = 0       # 'contorno nenhum' pode apagar linha: some também da camada
        saida.append((cam["nome"], im, 255))
    return saida


def exportar_aseprite(meta, cores, quadros, imgs, saida, base):
    """Grava <base>.aseprite pelo Aseprite em modo batch e confere reabrindo o arquivo. Devolve (ok, texto)."""
    import subprocess
    exe = CFG.get("aseprite")
    if not exe or not os.path.exists(exe):
        return False, "AVISO  .aseprite não gerado: configure \"aseprite\" no config.json da skill (Aseprite não achado)"
    pasta = os.path.join(saida, "_aseprite")
    os.makedirs(pasta, exist_ok=True)
    nomes = ["sombra", "contorno"] + meta["camadas"]
    spec_q = []
    for k, (q, img) in enumerate(zip(quadros, imgs)):
        cels = {}
        for nome, im, _ in camadas_rgba(meta, cores, q, img):
            if not (im[..., 3] > 0).any():
                continue
            png = os.path.join(pasta, f"q{k}_{nome}.png")
            Image.fromarray(im, "RGBA").save(png)
            cels[nome] = png.replace("\\", "/")
        spec_q.append({"ms": meta["ms"], "cels": cels})
    pal = [cores[c] for c in cores]
    if meta["contorno"] in ("auto", "suave") and cor_contorno(meta) not in [p.lower() for p in pal]:
        pal = [cor_contorno(meta)] + pal
    destino = os.path.join(saida, base + ".aseprite")
    if os.path.exists(destino):
        os.remove(destino)
    spec = {"largura": meta["quadro"], "altura": meta["quadro"], "paleta": pal,
            "camadas": [{"nome": n, "opacidade": ALFA_SOMBRA if n == "sombra" else 255} for n in nomes],
            "quadros": spec_q, "tags": [{"nome": meta["estado"], "de": 1, "ate": len(quadros)}],
            "saida": destino.replace("\\", "/")}
    spec_path = os.path.join(pasta, "spec.json")
    json.dump(spec, open(spec_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    lua = os.path.join(AQUI, "exportar_aseprite.lua")
    r = subprocess.run([exe, "-b", "--script-param", f"spec={spec_path}", "--script", lua],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if not os.path.exists(destino):
        return False, "ERRO   o Aseprite não gravou o .aseprite: " + (r.stderr or r.stdout).strip()[-400:]
    # conferência: reabre o arquivo, achata cada quadro e compara com a folha
    import glob
    for velho in glob.glob(os.path.join(pasta, "conferencia*")):
        os.remove(velho)
    folha_conf = os.path.join(pasta, "conferencia.png")
    r2 = subprocess.run([exe, "-b", destino, "--sheet", folha_conf, "--sheet-type", "horizontal",
                         "--data", os.path.join(pasta, "conferencia.json"), "--format", "json-array",
                         "--list-layers", "--list-tags"],
                        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if not os.path.exists(folha_conf):
        return False, "ERRO   não consegui reabrir o .aseprite para conferir: " + (r2.stderr or r2.stdout).strip()[-300:]
    conf = np.array(Image.open(folha_conf).convert("RGBA")).astype(int)
    Q = meta["quadro"]
    difs = []
    if conf.shape[:2] != (Q, Q * len(imgs)):
        difs.append(f"folha reaberta {conf.shape[1]}×{conf.shape[0]} ≠ {Q * len(imgs)}×{Q}")
    for k, img in enumerate(imgs):
        if difs:
            break
        a = conf[:, k * Q:(k + 1) * Q]
        b = img.astype(int)
        if a.shape != b.shape:
            difs.append(f"q{k}: tamanho {a.shape[:2]} ≠ {b.shape[:2]}")
            continue
        # pixel transparente: só o alfa importa; opaco: cor exata; sombra: alfa ±1 (arredondamento da opacidade)
        ruim = (np.abs(a[..., 3] - b[..., 3]) > 1) | ((b[..., 3] == 255) & (np.abs(a[..., :3] - b[..., :3]).max(-1) > 0))
        if ruim.any():
            difs.append(f"q{k}: {int(ruim.sum())} px diferentes")
    try:
        lido = json.load(open(os.path.join(pasta, "conferencia.json"), encoding="utf-8"))
        camadas_lidas = [l["name"] for l in lido.get("meta", {}).get("layers", [])]
    except (OSError, ValueError):
        camadas_lidas = []
    if camadas_lidas != nomes:
        difs.append(f"camadas lidas {camadas_lidas} ≠ esperadas {nomes}")
    if difs:
        return False, "ERRO   .aseprite gravado mas a conferência falhou: " + "; ".join(difs)
    return True, (f"ok     .aseprite: {len(nomes)} camadas ({', '.join(nomes)}), tag '{meta['estado']}', "
                  f"{len(imgs)} quadro(s); reaberto e igual à folha pixel a pixel")


def recorte(imgs, pad=4):
    alfa = np.zeros(imgs[0].shape[:2], bool)
    for im in imgs:
        alfa |= im[..., 3] > 0
    ys, xs = np.where(alfa)
    return max(0, ys.min() - pad), ys.max() + pad + 1, max(0, xs.min() - pad), xs.max() + pad + 1


def sobre(im_rgba, cor, escala):
    pil = Image.fromarray(im_rgba, "RGBA")
    fundo = Image.new("RGBA", pil.size, (*hex_rgb(cor), 255))
    fundo.alpha_composite(pil)
    return fundo.convert("RGB").resize((pil.width * escala, pil.height * escala), Image.NEAREST)


def checar(meta, cores, quadros, pal, imgs, masks):
    ok, avisos = [], []
    erros = []
    usadas = {cores[c] for q in quadros for l in q["linhas"] for c in l if c != "."}
    usadas |= {cores[c] for q in quadros for cam in q.get("camadas", []) for l in cam["grade"] for c in l if c != "."}
    if meta["contorno"] in ("auto", "suave"):
        usadas.add(cor_contorno(meta))
    if meta["contorno"] == "selout":
        usadas |= {"#%02x%02x%02x" % tuple(c) for im in imgs for c in im[..., :3][im[..., 3] == 255].reshape(-1, 3)}
    fora = sorted(c for c in usadas if c not in pal)
    if fora:
        erros.append(f"cores fora da paleta travada: {', '.join(fora)}")
    lim = limite_cores(meta)
    (erros if len(usadas) > lim else ok).append(f"cores usadas: {len(usadas)} (limite {meta['tipo']} = {lim})")
    ys = np.where(masks[0].any(axis=1))[0]
    alt = int(ys.max() - ys.min() + 1)
    msg = f"altura do sprite com contorno: {alt} px"
    perfil = meta.get("perfil", "64")
    faixa = CFG.get("perfis", {}).get(perfil, {}).get("altura") if perfil != "64" else None
    if meta["tipo"] in ("personagem", "npc", "inimigo") and faixa and not faixa[0] <= alt <= faixa[1] + 4:
        avisos.append(msg + f" (perfil {perfil}: {faixa[0]}–{faixa[1]} px, um pouco mais com arma ou penacho)")
    elif meta["tipo"] in ("personagem", "npc", "inimigo") and not faixa and not 60 <= alt <= 90:
        avisos.append(msg + " (humanoide: 64–72, até ~90 com penacho ou arma)")
    else:
        ok.append(msg)
    # pixels órfãos: nenhum vizinho 4-conexo da mesma letra
    for q in quadros:
        g = q["linhas"]
        h, w = len(g), len(g[0])
        orf = []
        for i in range(h):
            for j in range(w):
                c = g[i][j]
                if c == ".":
                    continue
                viz = [g[i + di][j + dj] for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1))
                       if 0 <= i + di < h and 0 <= j + dj < w]
                if c not in viz:
                    orf.append(f"({j},{i})")
        if orf:
            avisos.append(f"{q['nome']}: {len(orf)} pixel(s) órfão(s) (col,lin): {' '.join(orf[:12])}"
                          + (" …" if len(orf) > 12 else "") + " — ok só se for olho, brilho ou detalhe intencional")
    for k in range(1, len(quadros)):
        a, b = imgs[k - 1][..., :4], imgs[k][..., :4]
        dif = (a != b).any(axis=-1)
        uniao = (a[..., 3] > 0) | (b[..., 3] > 0)
        pct = 100 * dif.sum() / max(1, uniao.sum())
        (avisos if pct == 0 else ok).append(f"{quadros[k - 1]['nome']}→{quadros[k]['nome']}: {pct:.0f}% dos pixels mudam"
                                            + (" (quadro parado)" if pct == 0 else ""))
    return erros, avisos, ok


def gerar(caminho, saida, pal):
    meta, cores, quadros, erros = ler(caminho)
    if erros:
        print(f"[ERRO] {caminho}:\n  " + "\n  ".join(erros))
        return 1
    if not meta.get("perfil"):
        alt = max(len(q["linhas"]) for q in quadros) + (2 if meta["contorno"] in ("auto", "selout", "suave") else 0)
        meta["perfil"] = perfil_por_altura(alt)
    if meta["perfil"] != "64" and meta["contorno"] == "auto" and not meta.get("_contorno_explicito"):
        print(f"[aviso] perfil {meta['perfil']}: o anil de 2 px come o sprite; use 'contorno selout' (ou suave)")
    imgs, masks = zip(*(montar(meta, cores, q) for q in quadros))
    os.makedirs(saida, exist_ok=True)
    base = f"{meta['nome']}_{meta['estado']}"
    Q = meta["quadro"]
    folha = Image.new("RGBA", (Q * len(imgs), Q))
    for k, im in enumerate(imgs):
        folha.paste(Image.fromarray(im, "RGBA"), (k * Q, 0))
    folha.save(os.path.join(saida, base + ".png"))
    y0, y1, x0, x1 = recorte(imgs)
    grama = CFG["chao"]["grama"]
    sobre(imgs[0][y0:y1, x0:x1], grama, 8).save(os.path.join(saida, base + "_8x.png"))
    # silhueta 1x e 0,5x, ampliadas 4x
    m = masks[0][y0:y1, x0:x1]
    sil = np.full((*m.shape, 4), 255, np.uint8)
    sil[m] = (*hex_rgb(CONTORNO), 255)
    s1 = Image.fromarray(sil, "RGBA")
    s05 = s1.resize((max(1, s1.width // 2), max(1, s1.height // 2)), Image.NEAREST)
    prancha = Image.new("RGB", (s1.width * 4 + s05.width * 4 + 16, s1.height * 4), (255, 255, 255))
    prancha.paste(s1.resize((s1.width * 4, s1.height * 4), Image.NEAREST).convert("RGB"), (0, 0))
    prancha.paste(s05.resize((s05.width * 4, s05.height * 4), Image.NEAREST).convert("RGB"), (s1.width * 4 + 16, 0))
    prancha.save(os.path.join(saida, base + "_silhueta.png"))
    # sem régua externa (o Artur é a régua): prancha "boas práticas" + o que o Artur já aprovou, na mesma escala
    cp = dict(CFG)
    cp.update(CFG.get("perfis", {}).get(meta["perfil"], {}))
    regua_png = regua_da_direcao(cp, meta)
    if not regua_png:
        boas_praticas(imgs[0][y0:y1, x0:x1], os.path.join(saida, base + "_regua.png"), meta)
    if regua_png and os.path.exists(regua_png):
        rq = cp.get("quadro_regua", 36)
        r = np.array(Image.open(regua_png).convert("RGBA"))[:, :rq]
        ry0, ry1, rx0, rx1 = recorte([r])
        esc = 4 if meta["perfil"] == "64" else (8 if meta["perfil"] == "32" else 12)
        lado = [sobre(imgs[0][y0:y1, x0:x1], grama, esc), sobre(r[ry0:ry1, rx0:rx1], grama, esc)]
        hmax = max(i.height for i in lado)
        comp = Image.new("RGB", (sum(i.width for i in lado) + 24, hmax), hex_rgb(grama))
        comp.paste(lado[0], (0, hmax - lado[0].height))
        comp.paste(lado[1], (lado[0].width + 24, hmax - lado[1].height))
        comp.save(os.path.join(saida, base + "_regua.png"))
    if len(imgs) > 1:
        # todos os quadros lado a lado em 4x, numerados, para o revisor comparar quadro a quadro
        from PIL import ImageDraw
        cel = [sobre(im[y0:y1, x0:x1], grama, 4) for im in imgs]
        cw, ch = cel[0].width, cel[0].height
        folha4 = Image.new("RGB", (cw * min(5, len(cel)), (ch + 14) * ((len(cel) + 4) // 5)), (40, 40, 48))
        for k, c in enumerate(cel):
            x, y = (k % 5) * cw, (k // 5) * (ch + 14)
            folha4.paste(c, (x, y + 14))
            ImageDraw.Draw(folha4).text((x + 3, y + 1), f"q{k}", fill=(255, 220, 120))
        folha4.save(os.path.join(saida, base + "_quadros_4x.png"))
        gif = [sobre(im[y0:y1, x0:x1], grama, 4) for im in imgs]
        gif[0].save(os.path.join(saida, base + ".gif"), save_all=True, append_images=gif[1:],
                    duration=meta["ms"], loop=0, disposal=2)
    if meta.get("paleta"):
        pal = paleta(meta["paleta"])
    erros, avisos, ok = checar(meta, cores, quadros, pal, imgs, masks)
    if not meta.get("camadas"):                 # grade sem camadas: o .aseprite sai com uma camada só
        meta["camadas"] = ["desenho"]
        for q in quadros:
            q["camadas"] = [{"nome": "desenho", "grade": q["linhas"]}]
    if meta.get("guia"):
        prancha_guia(meta, imgs, os.path.join(saida, base + "_guia.png"))
    if meta.get("espelho") and meta.get("direcao"):
        ew = Image.open(os.path.join(saida, base + ".png")).transpose(Image.FLIP_LEFT_RIGHT)
        n = len(imgs)
        parts = [ew.crop(((n - 1 - k) * Q, 0, (n - k) * Q, Q)) for k in range(n)]
        fw = Image.new("RGBA", (Q * n, Q))
        for k, pq in enumerate(parts):
            fw.paste(pq, (k * Q, 0))
        nome_w = f"{meta['nome']}_{meta['estado_base']}_{meta['espelho']}.png"
        fw.save(os.path.join(saida, nome_w))
        ok.append(f"direção {meta['espelho']} espelhada de {meta['direcao']}: {nome_w}")
    ok_ase, txt_ase = exportar_aseprite(meta, cores, quadros, imgs, saida, base)
    (ok if ok_ase else (avisos if txt_ase.startswith("AVISO") else erros)).append(txt_ase.split(None, 1)[1])
    ref = regua_anim(meta, imgs, y0, y1, x0, x1, os.path.join(saida, base + "_regua_anim.png"), regua_png)
    cod_portao, txt_portao = portao(meta, os.path.join(saida, base + ".png"), saida)
    veredito = "APROVADO" if cod_portao == 0 else "REPROVADO — corrija antes de chamar o revisor"
    linhas = [f"# checagem {base}", "", f"PORTÃO DE MEDIDAS: {veredito}", txt_portao,
              f"(detalhes e overlay em medidas/{meta['estado']}/; prancha boas práticas e aprovados do Artur: {base}_regua.png)",
              ""] + [f"ERRO   {e}" for e in erros] + [f"AVISO  {a}" for a in avisos] + [f"ok     {o}" for o in ok]
    open(os.path.join(saida, base + "_checagem.txt"), "w", encoding="utf-8").write("\n".join(linhas) + "\n")
    print("\n".join(linhas))
    print(f"\narquivos em {saida}: {base}.png, _8x, _silhueta, _regua, _regua_anim" + (", .gif" if len(imgs) > 1 else ""))
    return 1 if (erros or cod_portao) else 0


def perfil_por_altura(h):
    return "16" if h <= 20 else ("32" if h <= 40 else "64")


def aprovados(meta, n=4):
    """Os assets que o Artur aprovou (config 'aprovados'): os mais recentes, do mesmo tipo primeiro."""
    pasta = CFG.get("aprovados", "")
    if not pasta or not os.path.isdir(pasta):
        return []
    arqs = [os.path.join(pasta, f) for f in os.listdir(pasta) if f.lower().endswith(".png")]
    arqs.sort(key=lambda f: (meta.get("tipo", "") not in os.path.basename(f), -os.path.getmtime(f)))
    return arqs[:n]


def boas_praticas(rec, destino, meta=None):
    """O sprite em 1×, 2×, 4× e 8× sobre grama e masmorra (lê no tamanho real?) e, embaixo, o que o Artur já
    aprovou, na mesma escala de 4× (a régua é ele)."""
    linhas = []
    for nome in ("grama", "masmorra"):
        cor = CFG["chao"][nome]
        cel = [sobre(rec, cor, e) for e in (1, 2, 4, 8)]
        h = max(c.height for c in cel)
        b = Image.new("RGB", (sum(c.width for c in cel) + 12 * len(cel), h), hex_rgb(cor))
        x = 0
        for c in cel:
            b.paste(c, (x, h - c.height))
            x += c.width + 12
        linhas.append(b)
    apr = aprovados(meta or {})
    if apr:
        from PIL import ImageDraw
        cel = [sobre(rec, CFG["chao"]["grama"], 4)]
        for f in apr:
            a = np.array(Image.open(f).convert("RGBA"))
            ys, xs = np.nonzero(a[..., 3] > 0)
            if len(ys):
                cel.append(sobre(a[ys.min():ys.max() + 1, xs.min():xs.max() + 1], CFG["chao"]["grama"], 4))
        h = max(c.height for c in cel)
        b = Image.new("RGB", (sum(c.width for c in cel) + 16 * len(cel), h + 16), (40, 40, 48))
        ImageDraw.Draw(b).text((3, 2), "nosso | aprovados pelo Artur: " + ", ".join(os.path.basename(f)[:-4] for f in apr),
                               fill=(255, 220, 120))
        x = 0
        for c in cel:
            b.paste(c, (x, 16 + h - c.height))
            x += c.width + 16
        linhas.append(b)
    out = Image.new("RGB", (max(b.width for b in linhas), sum(b.height for b in linhas) + 8 * len(linhas)), (20, 20, 26))
    y = 0
    for b in linhas:
        out.paste(b, (0, y))
        y += b.height + 8
    out.save(destino)


def carregar_guia(meta):
    """A guia recortada para o quadro, alinhada como a grade (pivô) e deslocada por 'guia <png> dx dy'."""
    Q = meta["quadro"]
    g = np.array(Image.open(meta["guia"]).convert("RGBA"))
    if g.shape[1] > Q and g.shape[1] % g.shape[0] == 0:
        g = g[:, :g.shape[0]]
    out = np.zeros((Q, Q, 4), np.uint8)
    op = g[..., 3] > 0
    ys, xs = np.nonzero(op)
    yb = ys.max()
    cx = int(round(xs[ys >= yb - 2].mean()))
    px, py = Q // 2, round(Q * 127 / 192)
    dx, dy = meta.get("guia_d", (0, 0))
    for y, x in zip(ys, xs):
        yy, xx = y - yb + py + dy, x - cx + px + dx
        if 0 <= yy < Q and 0 <= xx < Q:
            out[yy, xx] = g[y, x]
    return out


def prancha_guia(meta, imgs, destino):
    """Guia | desenho | desenho sobre a silhueta da guia (magenta = só na guia; ciano = só no desenho), em 8×."""
    g = carregar_guia(meta)
    a = imgs[0]
    ga, da = g[..., 3] > 0, a[..., 3] == 255
    sob = np.zeros_like(a)
    sob[ga & da] = (120, 120, 130, 255)
    sob[ga & ~da] = (255, 0, 200, 255)
    sob[da & ~ga] = (0, 220, 255, 255)
    y0, y1, x0, x1 = recorte([g, a])
    cel = [sobre(x[y0:y1, x0:x1], CFG["chao"]["grama"], 8) for x in (g, a, sob)]
    out = Image.new("RGB", (sum(c.width for c in cel) + 24, cel[0].height), (20, 20, 26))
    x = 0
    for c in cel:
        out.paste(c, (x, 0))
        x += c.width + 12
    out.save(destino)
    Image.fromarray(g).save(destino.replace("_guia.png", "_guia_alinhada.png"))


def prancha_direcoes(metas_imgs, destino):
    """As direções de um estado lado a lado (1º quadro, 8×), alinhadas no pivô, com linhas no topo da cabeça, no olho
    (1/4 da altura) e no pé de cada uma: o que não alinha salta à vista."""
    from PIL import ImageDraw
    ordem = ["s", "se", "e", "ne", "n", "nw", "w", "sw"]
    itens = sorted(metas_imgs, key=lambda mi: ordem.index(mi[0]["direcao"]) if mi[0]["direcao"] in ordem else 9)
    y0, y1, x0, x1 = recorte([im for _, im in itens])
    esc = 8
    cel = [sobre(im[y0:y1, x0:x1], CFG["chao"]["grama"], esc) for _, im in itens]
    W = sum(c.width for c in cel) + 12 * len(cel)
    out = Image.new("RGB", (W, cel[0].height + 16), (20, 20, 26))
    d = ImageDraw.Draw(out)
    x = 0
    for (m, im), c in zip(itens, cel):
        out.paste(c, (x, 16))
        d.text((x + 3, 2), m["direcao"], fill=(255, 220, 120))
        op = im[y0:y1, x0:x1, 3] == 255
        ys = np.nonzero(op.any(1))[0]
        for yy, cor in ((ys.min(), (255, 80, 80)), (ys.min() + (ys.max() - ys.min()) // 4, (80, 200, 255)),
                        (ys.max() + 1, (255, 255, 80))):
            d.line([(x, 16 + yy * esc), (x + c.width, 16 + yy * esc)], fill=cor, width=1)
        x += c.width + 12
    out.save(destino)


TIPO_MEDIR = {"npc": "personagem", "animal": "criatura"}
CONTORNO_PX = {"auto": 2, "manual": 2, "suave": 1, "nenhum": 0, "selout": 1}


def regua_da_direcao(cp, meta):
    """Caminho da folha da régua na direção do asset (Eldiran: pNN_<dir>.png; lado w usa o e), ou '' sem régua."""
    if not cp.get("regua") or not cp.get("regua_png"):
        return ""
    d = meta.get("direcao", "s")
    d = {"w": "e", "sw": "e", "se": "e", "nw": "n", "ne": "n"}.get(d, d)
    nome = re.sub(r"_(s|n|e)\.png$", f"_{d}.png", cp["regua_png"])
    caminho = os.path.join(cp["regua"], nome)
    return caminho if os.path.exists(caminho) else os.path.join(cp["regua"], cp["regua_png"])


def regua_anim(meta, imgs, y0, y1, x0, x1, destino, regua_png):
    """Os quadros do asset em cima e a animação da régua (mesma direção) embaixo, na mesma escala (só olhar)."""
    from PIL import ImageDraw
    if not regua_png or not os.path.exists(regua_png):
        return None
    q = CFG.get("quadro_regua", 36)
    ref = np.array(Image.open(regua_png).convert("RGBA"))
    rq = [ref[:, i * q:(i + 1) * q] for i in range(max(1, ref.shape[1] // q))]
    ry0, ry1, rx0, rx1 = recorte(rq)
    esc = 4 if meta.get("perfil") == "64" else 8
    grama = CFG["chao"]["grama"]
    nome_regua = os.path.basename(regua_png)
    linhas = [("nosso: " + meta["estado"], [sobre(im[y0:y1, x0:x1], grama, esc) for im in imgs]),
              (f"régua ({CFG.get('regua_nome', 'régua')}): {nome_regua}", [sobre(r[ry0:ry1, rx0:rx1], grama, esc) for r in rq])]
    por_linha = 8
    blocos = []
    for titulo, cel in linhas:
        cw, ch = max(c.width for c in cel), max(c.height for c in cel)
        nl = (len(cel) + por_linha - 1) // por_linha
        b = Image.new("RGB", (cw * min(por_linha, len(cel)), 16 + (ch + 12) * nl), (40, 40, 48))
        d = ImageDraw.Draw(b)
        d.text((3, 2), titulo, fill=(255, 220, 120))
        for k, c in enumerate(cel):
            x, y = (k % por_linha) * cw, 16 + (k // por_linha) * (ch + 12)
            b.paste(c, (x, y + 12 + ch - c.height))
            d.text((x + 3, y), f"q{k}", fill=(200, 200, 200))
        blocos.append(b)
    out = Image.new("RGB", (max(b.width for b in blocos), sum(b.height for b in blocos) + 8), (20, 20, 26))
    out.paste(blocos[0], (0, 0))
    out.paste(blocos[1], (0, blocos[0].height + 8))
    out.save(destino)
    return nome_regua


def portao(meta, png, saida):
    """Roda o medir.py nesta folha com o contorno e o limite de cores da grade. Devolve (código, texto)."""
    import subprocess
    tipo = TIPO_MEDIR.get(meta["tipo"], meta["tipo"])
    pasta = os.path.join(saida, "medidas", meta["estado"])
    cmd = [sys.executable, os.path.join(AQUI, "medir.py"), "--tipo", tipo, "--quadro", str(meta["quadro"]),
           "--folha", f"{meta['estado']}={png}", "--saida", pasta, "--asset", meta["nome"],
           "--contorno-px", str(1 if meta["contorno"] == "manual" and meta.get("perfil", "64") != "64"
                                else CONTORNO_PX.get(meta["contorno"], 2)),
           "--limite-cores", str(limite_cores(meta))]
    if meta["contorno"] in ("auto", "suave"):
        cmd += ["--contorno-cor", cor_contorno(meta)]
    cmd += ["--perfil", meta.get("perfil", "64")]
    if meta["contorno"] == "selout":
        cmd.append("--selout")
    for m in [meta] + meta.get("_irmaos", []):
        if m.get("guia"):
            gp = os.path.join(saida, f"{m['nome']}_{m['estado']}_guia_alinhada.png")
            if os.path.exists(gp):
                cmd += ["--guia", f"{m['estado']}={gp}"]
    for m, png_irmao in meta.get("_folhas_irmas", []):
        cmd += ["--folha", f"{m['estado']}={png_irmao}"]
    if meta.get("sem_contorno"):
        cmd.append("--com-efeito")
    if meta.get("paleta"):
        cmd += ["--paleta", meta["paleta"]]
    if meta.get("ritmo") == "calmo":
        cmd += ["--ritmo", "calmo"]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode not in (0, 1):
        return 1, "ERRO   o medir.py não rodou: " + (r.stderr or r.stdout).strip()[-400:]
    return r.returncode, r.stdout.strip()


def numerar(caminho, quadro, guia=False):
    meta, cores, quadros, erros = ler(caminho)
    if not quadros:
        print("\n".join(erros))
        return 1
    q = quadros[quadro]
    w = len(q["linhas"][0])
    linhas = q["linhas"]
    if guia and meta.get("guia") and meta.get("pivo"):
        # a guia aparece como ':' onde a grade está vazia ('.') e a guia tem silhueta
        Q = meta["quadro"]
        g = carregar_guia(meta)[..., 3] > 0
        px, py = Q // 2, round(Q * 127 / 192)
        ox, oy = px - meta["pivo"][0], py - meta["pivo"][1]
        linhas = ["".join(":" if c == "." and 0 <= oy + i < Q and 0 <= ox + j < Q and g[oy + i, ox + j] else c
                          for j, c in enumerate(l)) for i, l in enumerate(linhas)]
        print("(':' = silhueta da guia onde a grade está vazia)")
    print("     " + "".join(str(j // 10 % 10) if j % 5 == 0 else " " for j in range(w)))
    print("     " + "".join(str(j % 10) for j in range(w)))
    for i, l in enumerate(linhas):
        marca = "<pivô" if meta["pivo"] and i == meta["pivo"][1] else ""
        print(f"{i:>3}  {l}  {marca}")
    if erros:
        print("\n".join(erros))
    return 0


def _mapa(q):
    return {(j, i): c for i, l in enumerate(q["linhas"]) for j, c in enumerate(l) if c != "."}


def diff(caminho, qa, qb):
    meta, cores, quadros, erros = ler(caminho)
    if erros:
        print("\n".join(erros))
        return 1
    Q = {q["nome"]: q for q in quadros}
    a, b = _mapa(Q[qa]), _mapa(Q[qb])
    mud = sorted(set(a) | set(b), key=lambda p: (p[1], p[0]))
    mud = [p for p in mud if a.get(p) != b.get(p)]
    print(f"{qa} -> {qb}: {len(mud)} px mudam de {len(set(a) | set(b))} ({100 * len(mud) / max(1, len(set(a) | set(b))):.0f}%)")
    por_linha = {}
    for (x, y) in mud:
        por_linha.setdefault(y, []).append(f"{x}:{a.get((x, y), '.')}>{b.get((x, y), '.')}")
    for y in sorted(por_linha):
        print(f"  lin {y:>3}: " + " ".join(por_linha[y]))
    return 0


def anim(caminho):
    """Por quadro: deslocamento do centro de massa e do pé, px mudados, e px por letra (membro mudando de tamanho)."""
    meta, cores, quadros, erros = ler(caminho)
    if erros:
        print("\n".join(erros))
        return 1
    info = []
    for q in quadros:
        m = _mapa(q)
        xs = [p[0] for p in m]
        ys = [p[1] for p in m]
        cont = {}
        for c in m.values():
            cont[c] = cont.get(c, 0) + 1
        info.append({"cx": sum(xs) / len(xs), "cy": sum(ys) / len(ys), "pe": max(ys), "n": len(m), "cont": cont, "m": m})
    letras = sorted(set().union(*(i["cont"] for i in info)))
    print("quadro   desloc(cx,cy)   pé   px   mudam   " + " ".join(f"{c:>4}" for c in letras))
    for k, (q, i) in enumerate(zip(quadros, info)):
        ant = info[k - 1]
        mud = sum(1 for p in set(i["m"]) | set(ant["m"]) if i["m"].get(p) != ant["m"].get(p))
        print(f"{q['nome']:<8} {i['cx'] - info[0]['cx']:+5.1f},{i['cy'] - info[0]['cy']:+5.1f}   {i['pe']:>4} {i['n']:>4} "
              f"{100 * mud / max(1, len(set(i['m']) | set(ant['m']))):5.0f}%   " + " ".join(f"{i['cont'].get(c, 0):>4}" for c in letras))
    for c in letras:
        v = [i["cont"].get(c, 0) for i in info]
        if max(v) and (max(v) - min(v)) / max(v) > 0.10 and max(v) >= 6:
            print(f"  aviso: '{c}' varia {min(v)}–{max(v)} px entre quadros (parte mudando de tamanho? ok se gira ou some)")
    return 0


def gerar_estado(arquivos, saida, pal):
    """Gera cada direção e depois o portão conjunto (D01–D05) e a prancha _direcoes.png por estado."""
    lidos = [(c, ler(c)) for c in arquivos]
    codigos = [gerar(c, saida, pal) for c in arquivos]
    grupos = {}
    for c, (meta, cores, quadros, erros) in lidos:
        if meta.get("direcao") and not erros:
            grupos.setdefault((meta["nome"], meta["estado_base"]), []).append((c, meta, cores, quadros))
    for (nome, est), itens in grupos.items():
        if len(itens) < 2:
            continue
        metas_imgs = []
        for c, meta, cores, quadros in itens:
            if not meta.get("perfil"):
                alt = max(len(q["linhas"]) for q in quadros) + 2
                meta["perfil"] = perfil_por_altura(alt)
            metas_imgs.append((meta, montar(meta, cores, quadros[0])[0]))
        prancha_direcoes(metas_imgs, os.path.join(saida, f"{nome}_{est}_direcoes.png"))
        m0 = dict(itens[0][1])
        m0["estado"] = f"{est}_{m0['direcao']}"
        m0["_folhas_irmas"] = [(m, os.path.join(saida, f"{nome}_{m['estado']}.png")) for _, m, _, _ in itens[1:]]
        m0["_irmaos"] = [m for _, m, _, _ in itens[1:]]
        for _, m, _, _ in itens:
            if m.get("espelho"):
                m0["_folhas_irmas"].append(({"estado": f"{est}_{m['espelho']}"},
                                            os.path.join(saida, f"{nome}_{est}_{m['espelho']}.png")))
        m0["estado"] = f"{est}_{itens[0][1]['direcao']}"
        cod, txt = portao(dict(m0, estado=m0["estado"]), os.path.join(saida, f"{nome}_{m0['estado']}.png"),
                          os.path.join(saida, "_conjunto"))
        print(f"\n# PORTÃO CONJUNTO {nome} {est} ({', '.join(m['direcao'] for _, m, _, _ in itens)}): "
              + ("APROVADO" if cod == 0 else "REPROVADO") + "\n" + txt)
        open(os.path.join(saida, f"{nome}_{est}_conjunto.txt"), "w", encoding="utf-8").write(txt + "\n")
        codigos.append(cod)
    return max(codigos)


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gerar")
    g.add_argument("arquivos", nargs="+")
    g.add_argument("--saida", required=True)
    n = sub.add_parser("numerar")
    n.add_argument("arquivo")
    n.add_argument("--quadro", type=int, default=0)
    n.add_argument("--guia", action="store_true")
    d = sub.add_parser("diff")
    d.add_argument("arquivo")
    d.add_argument("qa")
    d.add_argument("qb")
    an = sub.add_parser("anim")
    an.add_argument("arquivo")
    a = ap.parse_args()
    if a.cmd == "numerar":
        return numerar(a.arquivo, a.quadro, a.guia)
    if a.cmd == "diff":
        return diff(a.arquivo, a.qa, a.qb)
    if a.cmd == "anim":
        return anim(a.arquivo)
    pal = paleta()
    return gerar_estado(a.arquivos, a.saida, pal)


if __name__ == "__main__":
    sys.exit(main())
