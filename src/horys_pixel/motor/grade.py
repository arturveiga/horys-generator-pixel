"""Grade de texto -> PNG. Este script NÃO desenha nada: só traduz a grade que você escreveu,
aplica as regras mecânicas do estilo (contorno externo 2 px e sombra no chão, se pedidos),
gera as prévias para você e para o revisor e roda o PORTÃO DE MEDIDAS (medir.py, metas calibradas no Tiny).
Portão reprovado = código de saída 1 = corrija antes de chamar o revisor.

Uso:
  python grade.py gerar <arquivo.grade> [<outro.grade> ...] --saida <pasta>
  python grade.py numerar <arquivo.grade> [--quadro N]     (mostra a grade com régua de colunas e linhas)

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
                             # por fora (lado da luz, como no topo do elmo do guerreiro do Tiny)
  limite_cores 12            # opcional: exceção pedida pelo usuário (registre na ficha)
  ritmo calmo                # opcional: idle quase parado de propósito (como o arqueiro do Tiny); vai na ficha
  paleta <arquivo.json>      # opcional: outra paleta travada (mesmo formato; caminho absoluto ou relativo à KB;
                             # sem KB na config, relativo à pasta atual)
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
  Com o Aseprite configurado (chave "aseprite" da config do motor), o gerar também grava <nome>_<estado>.aseprite (uma camada
  por parte, tag do estado, paleta da legenda) e confere o arquivo reabrindo-o e comparando pixel a pixel com a folha.

CONFIG: comum.config() (HORYS_MOTOR_CONFIG -> ~/.horys-pixel/motor.json -> config_padrao.json). Sem régua configurada,
as prévias _regua e _regua_anim são puladas com aviso; o resto (folha, _8x, silhueta, gif, checagem, portão) roda.
"""
import argparse
import io
import json
import os
import sys

import numpy as np
from PIL import Image

AQUI = os.path.dirname(os.path.abspath(__file__))
try:  # como módulo (python -m horys_pixel.motor.grade) ou como script direto (python grade.py)
    from . import comum as C
except ImportError:
    import comum as C  # noqa: E402

CFG = C.config()


def _paleta_json(arquivo=None):
    return json.load(open(C.caminho_paleta(CFG, arquivo), encoding="utf-8"))


_PAL_CFG = _paleta_json()
# contorno "auto": a cor de contorno da paleta da config (no Horys, anil-noite #18122c)
CONTORNO = _PAL_CFG["contorno"].lower()
# contorno "suave": 'contorno_suave' da config ou da paleta; no Horys, #3f3c56 (sombra da rampa masmorra)
CONTORNO_SUAVE = (CFG.get("contorno_suave") or _PAL_CFG.get("contorno_suave") or "#3f3c56").lower()
LIMITES = {"personagem": 10, "inimigo": 10, "npc": 10, "criatura": 8, "animal": 8, "prop": 8, "arvore": 8,
           "tile": 12, "predio": 18, "boss": 16, "icone": 8, "retrato": 14, "efeito": 6, "recurso": 10, "agua": 6}


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def paleta(arquivo=None):
    p = _paleta_json(arquivo)
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


def cor_contorno(meta):
    """auto: contorno da paleta (Horys: anil-noite #18122c), 2 px. suave: 1 px, CONTORNO_SUAVE (Horys: #3f3c56)."""
    return meta.get("cor_contorno") or (CONTORNO if meta["contorno"] == "auto" else CONTORNO_SUAVE)


def rampas():
    p = _paleta_json()
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
    if meta["contorno"] in ("auto", "suave"):
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
        return False, ("AVISO  .aseprite não gerado: configure \"aseprite\" na config do motor (HORYS_MOTOR_CONFIG ou "
                       "~/.horys-pixel/motor.json) (Aseprite não achado)")
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
    fora = sorted(c for c in usadas if c not in pal)
    if fora:
        erros.append(f"cores fora da paleta travada: {', '.join(fora)}")
    lim = meta.get("limite") or LIMITES.get(meta["tipo"], 10)
    (erros if len(usadas) > lim else ok).append(f"cores usadas: {len(usadas)} (limite {meta['tipo']} = {lim})")
    ys = np.where(masks[0].any(axis=1))[0]
    alt = int(ys.max() - ys.min() + 1)
    msg = f"altura do sprite com contorno: {alt} px"
    if meta["tipo"] in ("personagem", "npc", "inimigo") and not 60 <= alt <= 90:
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
    imgs, masks = zip(*(montar(meta, cores, q) for q in quadros))
    os.makedirs(saida, exist_ok=True)
    base = f"{meta['nome']}_{meta['estado']}"
    Q = meta["quadro"]
    folha = Image.new("RGBA", (Q * len(imgs), Q))
    for k, im in enumerate(imgs):
        folha.paste(Image.fromarray(im, "RGBA"), (k * Q, 0))
    folha.save(os.path.join(saida, base + ".png"))
    y0, y1, x0, x1 = recorte(imgs)
    grama = C.cor_fundo_previa(CFG)
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
    # régua: o sprite "idle" da régua (no Horys, o peão do Tiny Swords) ao lado, mesma escala (só olhar; nunca copiar)
    sem_regua = not C.regua_ok(CFG)
    arq_idle, q_idle = CFG["regua_por_categoria"].get("idle") or ("pawn_idle.png", 192)
    regua_png = None if sem_regua else os.path.join(CFG["regua"], arq_idle)
    if regua_png and os.path.exists(regua_png):
        r = np.array(Image.open(regua_png).convert("RGBA"))
        r = r[:, :q_idle] if q_idle else r
        ry0, ry1, rx0, rx1 = recorte([r])
        lado = [sobre(imgs[0][y0:y1, x0:x1], grama, 4), sobre(r[ry0:ry1, rx0:rx1], grama, 4)]
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
    ok_ase, txt_ase = exportar_aseprite(meta, cores, quadros, imgs, saida, base)
    (ok if ok_ase else (avisos if txt_ase.startswith("AVISO") else erros)).append(txt_ase.split(None, 1)[1])
    if sem_regua:
        ref = None
        avisos.append("régua não configurada (chave \"regua\" da config do motor vazia ou pasta inexistente): "
                      "_regua e _regua_anim não foram gerados")
    else:
        ref = regua_anim(meta, imgs, y0, y1, x0, x1, os.path.join(saida, base + "_regua_anim.png"))
    cod_portao, txt_portao = portao(meta, os.path.join(saida, base + ".png"), saida)
    veredito = "APROVADO" if cod_portao == 0 else "REPROVADO — corrija antes de chamar o revisor"
    linhas = [f"# checagem {base}", "", f"PORTÃO DE MEDIDAS: {veredito}", txt_portao,
              (f"(detalhes e overlay em medidas/{meta['estado']}/; régua animada: {base}_regua_anim.png vs "
               f"{CFG.get('regua_nome') or 'régua'} {ref})" if not sem_regua else
               f"(detalhes e overlay em medidas/{meta['estado']}/; sem régua configurada)"),
              ""] + [f"ERRO   {e}" for e in erros] + [f"AVISO  {a}" for a in avisos] + [f"ok     {o}" for o in ok]
    open(os.path.join(saida, base + "_checagem.txt"), "w", encoding="utf-8").write("\n".join(linhas) + "\n")
    print("\n".join(linhas))
    print(f"\narquivos em {saida}: {base}.png, _8x, _silhueta" + ("" if sem_regua else ", _regua, _regua_anim")
          + (", .gif" if len(imgs) > 1 else ""))
    return 1 if (erros or cod_portao) else 0


TIPO_MEDIR = {"npc": "personagem", "animal": "criatura"}
CONTORNO_PX = {"auto": 2, "manual": 2, "suave": 1, "nenhum": 0}


def regua_anim(meta, imgs, y0, y1, x0, x1, destino):
    """Os quadros do asset em cima e a animação equivalente da régua embaixo, na mesma escala (só olhar; nunca copiar)."""
    comum = C
    from PIL import ImageDraw
    tipo = TIPO_MEDIR.get(meta["tipo"], meta["tipo"])
    cat = comum.categoria_estado(meta["estado"]) if tipo in ("personagem", "inimigo", "boss") else tipo
    if tipo == "efeito":  # régua do efeito pelo nome do estado (efeitos do Tiny em <regua>/fx)
        nome = meta["estado"].lower()
        for chaves, c in ((("poeira", "dust", "fumaca"), "poeira"), (("fogo", "fire", "tocha", "chama"), "fogo"),
                          (("explos",), "explosao"), (("respingo", "splash", "agua"), "respingo"),
                          (("cura", "heal", "magia", "brilho"), "cura_fx")):
            if any(k in nome for k in chaves):
                cat = c
                break
    porcat = CFG["regua_por_categoria"]
    par = porcat.get(cat) or porcat.get("idle")
    if not par:
        return None
    arq, q = par
    caminho = os.path.join(CFG["regua"], arq)
    if not os.path.exists(caminho):
        return None
    ref = np.array(Image.open(caminho).convert("RGBA"))
    q = q or ref.shape[0]
    rq = [ref[:, i * q:(i + 1) * q] for i in range(max(1, ref.shape[1] // q))]  # q = largura; altura inteira (árvore 192×256)
    ry0, ry1, rx0, rx1 = recorte(rq)
    esc = 3
    grama = C.cor_fundo_previa(CFG)
    linhas = [("nosso: " + meta["estado"], [sobre(im[y0:y1, x0:x1], grama, esc) for im in imgs]),
              (f"{CFG.get('regua_nome') or 'régua'} ({cat}): {arq}", [sobre(r[ry0:ry1, rx0:rx1], grama, esc) for r in rq])]
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
    return arq


def portao(meta, png, saida):
    """Roda o medir.py nesta folha com o contorno e o limite de cores da grade. Devolve (código, texto)."""
    import subprocess
    tipo = TIPO_MEDIR.get(meta["tipo"], meta["tipo"])
    pasta = os.path.join(saida, "medidas", meta["estado"])
    cmd = [sys.executable, os.path.join(AQUI, "medir.py"), "--tipo", tipo, "--quadro", str(meta["quadro"]),
           "--folha", f"{meta['estado']}={png}", "--saida", pasta, "--asset", meta["nome"],
           "--contorno-px", str(CONTORNO_PX.get(meta["contorno"], 2)),
           "--limite-cores", str(meta.get("limite") or LIMITES.get(meta["tipo"], 10))]
    if meta["contorno"] in ("auto", "suave"):
        cmd += ["--contorno-cor", cor_contorno(meta)]
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


def numerar(caminho, quadro):
    meta, cores, quadros, erros = ler(caminho)
    if not quadros:
        print("\n".join(erros))
        return 1
    q = quadros[quadro]
    w = len(q["linhas"][0])
    print("     " + "".join(str(j // 10 % 10) if j % 10 == 0 else " " for j in range(w)))
    print("     " + "".join(str(j % 10) for j in range(w)))
    for i, l in enumerate(q["linhas"]):
        marca = "<pivô" if meta["pivo"] and i == meta["pivo"][1] else ""
        print(f"{i:>3}  {l}  {marca}")
    if erros:
        print("\n".join(erros))
    return 0


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
    a = ap.parse_args()
    if a.cmd == "numerar":
        return numerar(a.arquivo, a.quadro)
    pal = paleta()
    return max(gerar(c, a.saida, pal) for c in a.arquivos)


if __name__ == "__main__":
    sys.exit(main())
