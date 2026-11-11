"""Rig cut-out do golem caveira: monta as partes num esqueleto e renderiza poses/animações.

rig.json  = pose de descanso (vem de encaixe.json) + pivôs locais de cada parte + hierarquia.
Animação  = ciclo contínuo em p (0..2π), pés por IK de 2 ossos, partes secundárias com atraso de fase.
Uso: python rig.py   -> andar.gif, andar_quadros.png, rig_pivos.png
"""
import json, math
from PIL import Image, ImageDraw

ENC = json.load(open("encaixe.json"))

# pivô local de cada parte (fração da imagem da parte, antes de girar/escalar) e osso pai
OSSOS = {
    "quadril":      dict(pai=None,       pivo=(0.50, 0.20)),
    "tronco":       dict(pai="quadril",  pivo=(0.50, 0.95)),
    "cabeca":       dict(pai="tronco",   pivo=(0.50, 0.80)),
    "braco_cima_E": dict(pai="tronco",   pivo=(0.76, 0.30)),
    "antebraco_E":  dict(pai="braco_cima_E", pivo=(0.62, 0.10)),
    "braco_cima_D": dict(pai="tronco",   pivo=(0.24, 0.30)),
    "antebraco_D":  dict(pai="braco_cima_D", pivo=(0.38, 0.10)),
    "coxa_E":       dict(pai="quadril",  pivo=(0.50, 0.12)),
    "canela_E":     dict(pai="coxa_E",   pivo=(0.50, 0.10)),
    "coxa_D":       dict(pai="quadril",  pivo=(0.50, 0.12)),
    "canela_D":     dict(pai="coxa_D",   pivo=(0.50, 0.10)),
}
# ordem de desenho (de trás para frente)
ORDEM = ["braco_cima_E", "braco_cima_D", "antebraco_E", "antebraco_D", "canela_E", "canela_D",
         "coxa_E", "coxa_D", "quadril", "tronco", "cabeca"]
# bíceps atrás do tronco (o pelo do peito passa por cima); só a ombreira vem na frente
ORDEM = ["canela_E", "canela_D", "coxa_E", "coxa_D", "quadril", "braco_cima_E", "braco_cima_D", "tronco",
         "ombreira_E", "ombreira_D", "antebraco_E", "antebraco_D", "cabeca"]
# camadas extras: (osso cuja transformação usam, fração de altura da imagem do osso que fica visível)
CAMADAS = {"ombreira_E": ("braco_cima_E", 0.47), "ombreira_D": ("braco_cima_D", 0.47)}

IMG = {n: Image.open(f"partes/{n}.png").convert("RGBA") for n in OSSOS}
import numpy as _np
from scipy import ndimage as _nd
for _c, (_o, _f) in CAMADAS.items():
    _im = IMG[_o].copy(); _arr = _np.array(_im).astype(int)
    _lum = _arr[..., :3].mean(-1); _sat = _arr[..., :3].max(-1) - _arr[..., :3].min(-1)
    _pedra = (_lum > 110) & (_sat < 40) & (_arr[..., 3] > 0)
    _pedra[round(_im.height * (_f + 0.15)):] = False
    _lab, _ = _nd.label(_pedra); _maior = _np.bincount(_lab.ravel())[1:].argmax() + 1
    _m = _nd.binary_fill_holes(_nd.binary_dilation(_lab == _maior, iterations=6))   # placa + espinhos + contorno
    _a = _np.where(_m, _arr[..., 3], 0).astype(_np.uint8); _im.putalpha(Image.fromarray(_a)); IMG[_c] = _im
# 1) lateral do tronco sobre o bíceps: troca o contorno escuro por pelo (sem costura de boneco)
_t = _np.array(IMG["tronco"]).astype(int); _h, _w = _t.shape[:2]
_op = _t[..., 3] > 0
_pelo = _np.median(_t[int(_h*.45):int(_h*.6), int(_w*.15):int(_w*.25), :3].reshape(-1, 3), 0).astype(int)
for _y in range(int(_h * .18), int(_h * .72)):
    for _x in list(range(0, int(_w * .07))) + list(range(int(_w * .93), _w)):
        if _op[_y, _x] and _t[_y, _x, :3].mean() < 45: _t[_y, _x, :3] = _pelo
IMG["tronco"] = Image.fromarray(_t.astype(_np.uint8))


def rot(p, a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return (p[0] * c - p[1] * s, p[0] * s + p[1] * c)


def descanso():
    """Posição no mundo de cada pivô e ângulo de descanso, a partir do encaixe."""
    R = {}
    for n, o in OSSOS.items():
        e = ENC[n]; im = IMG[n]
        # vetor do centro da imagem ao pivô, no espaço da parte, depois escala e rotação (PIL gira anti-horário)
        v = ((o["pivo"][0] - 0.5) * im.width * e["escala"], (o["pivo"][1] - 0.5) * im.height * e["escala"])
        v = rot(v, -e["angulo"])
        R[n] = dict(px=e["cx"] + v[0], py=e["cy"] + v[1], ang=-e["angulo"], esc=e["escala"])
    # prende cada filho na junta do pai (cotovelo, joelho): sem isso a parte fica solta onde o encaixe a pôs
    for filho, (pai, local) in JUNTAS.items():
        e = ENC[pai]; im = IMG[pai]
        v = ((local[0] - 0.5) * im.width * e["escala"], (local[1] - 0.5) * im.height * e["escala"])
        v = rot(v, -e["angulo"])
        R[filho]["px"], R[filho]["py"] = e["cx"] + v[0], e["cy"] + v[1]
    return R


# ponto da junta na imagem do pai (fração): o pivô do filho fica exatamente aí
JUNTAS = {
    "antebraco_E": ("braco_cima_E", (0.33, 0.84)),
    "antebraco_D": ("braco_cima_D", (0.67, 0.84)),
    "canela_E": ("coxa_E", (0.50, 0.88)),
    "canela_D": ("coxa_D", (0.50, 0.88)),
}


REST = descanso()


def pose(p):
    """p: {osso: (graus, dx, dy)}. Devolve transformação no mundo de cada osso (cinemática direta)."""
    T = {}
    def resolve(n):
        if n in T: return T[n]
        o = OSSOS[n]; r = REST[n]; a, dx, dy = p.get(n, (0, 0, 0))
        if o["pai"] is None:
            T[n] = (r["px"] + dx, r["py"] + dy, r["ang"] + a, a)
        else:
            px, py, pang, pdelta = resolve(o["pai"])
            rp = REST[o["pai"]]
            v = rot((r["px"] - rp["px"], r["py"] - rp["py"]), pdelta)  # posição relativa ao pai gira junto
            T[n] = (px + v[0] + dx, py + v[1] + dy, r["ang"] + pdelta + a, pdelta + a)
        return T[n]
    for n in OSSOS: resolve(n)
    return T


def render(p, tam=(1224, 1536), fundo=(70, 70, 82, 255)):
    T = pose(p); out = Image.new("RGBA", tam, fundo)
    for n in ORDEM:
        osso = CAMADAS[n][0] if n in CAMADAS else n
        im = IMG[n]; e = REST[osso]; o = OSSOS[osso]
        k = p.get("_esc", {}).get(osso, 1.0)
        im = im.resize((round(im.width * e["esc"] * k), round(im.height * e["esc"] * k)), Image.LANCZOS)
        px, py, ang, _ = T[osso]
        if n in CAMADAS:
            dt = T["tronco"][3]; db = T[osso][3]
            ang = REST[osso]["ang"] + dt + 0.4 * (db - dt)
        # pivô na imagem escalada; gira em torno dele (PIL: ângulo anti-horário, por isso -ang)
        cx, cy = o["pivo"][0] * im.width, o["pivo"][1] * im.height
        big = Image.new("RGBA", (im.width * 3, im.height * 3)); big.paste(im, (im.width, im.height))
        big = big.rotate(-ang, center=(im.width + cx, im.height + cy), resample=Image.BICUBIC)
        out.alpha_composite(big, (round(px - im.width - cx) + 100, round(py - im.height - cy)))
    return out


def lerp(a, b, t):
    return {k: tuple(x + (y - x) * t for x, y in zip(a.get(k, (0, 0, 0)), b.get(k, (0, 0, 0)))) for k in set(a) | set(b)}


# ---------------------------------------------------------------------------------------------
# Andar por ciclo contínuo (modelo do SpriteKiln): tudo é função da fase p (0..2π), periódica.
# Pés primeiro: o pé tem posição no chão; coxa e canela saem de IK de 2 ossos.
# ---------------------------------------------------------------------------------------------
PE_LOCAL = (0.50, 0.80)        # ponto do tornozelo na imagem da canela (fração)


def _ponto(n, local):
    e = ENC[n]; im = IMG[n]
    v = ((local[0] - 0.5) * im.width * e["escala"], (local[1] - 0.5) * im.height * e["escala"])
    v = rot(v, -e["angulo"]); return (e["cx"] + v[0], e["cy"] + v[1])


PE0 = {l: _ponto(f"canela_{l}", PE_LOCAL) for l in "ED"}                   # pé no chão (descanso)
L1 = {l: math.dist((REST[f"coxa_{l}"]["px"], REST[f"coxa_{l}"]["py"]),
                   (REST[f"canela_{l}"]["px"], REST[f"canela_{l}"]["py"])) for l in "ED"}
L2 = {l: math.dist((REST[f"canela_{l}"]["px"], REST[f"canela_{l}"]["py"]), PE0[l]) for l in "ED"}


def _ang(a, b): return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))


def ik(quadril_t, lado, alvo):
    """Ângulos (delta de descanso) de coxa e canela para o tornozelo chegar em `alvo`.
    quadril_t = (px, py, ang, delta) do quadril. O joelho dobra para fora (E: esquerda, D: direita)."""
    rq = REST["quadril"]; rc = REST[f"coxa_{lado}"]
    v = rot((rc["px"] - rq["px"], rc["py"] - rq["py"]), quadril_t[3])
    H = (quadril_t[0] + v[0], quadril_t[1] + v[1])
    l1, l2 = L1[lado], L2[lado]
    d = min(math.dist(H, alvo), l1 + l2 - 0.01)
    a_base = _ang(H, alvo)
    a1 = math.degrees(math.acos(max(-1, min(1, (l1 * l1 + d * d - l2 * l2) / (2 * l1 * d)))))
    sinal = 1 if lado == "E" else -1          # tela: y para baixo; E dobra para x menor
    joelho_ang = a_base + sinal * a1
    K = (H[0] + l1 * math.cos(math.radians(joelho_ang)), H[1] + l1 * math.sin(math.radians(joelho_ang)))
    canela_ang = _ang(K, alvo)
    rest_coxa = _ang((rc["px"], rc["py"]), (REST[f"canela_{lado}"]["px"], REST[f"canela_{lado}"]["py"]))
    rest_canela = _ang((REST[f"canela_{lado}"]["px"], REST[f"canela_{lado}"]["py"]), PE0[lado])
    d_coxa = joelho_ang - rest_coxa - quadril_t[3]
    d_canela = canela_ang - rest_canela - quadril_t[3] - d_coxa
    return d_coxa, d_canela


# amplitudes (px na arte de 1024 de largura; no jogo ~1/3)
PASSO = dict(lift=46, bob=9, sway=14, roll=3.5, tronco=4.5, braco=4.0, antebraco=4.0, cabeca=3.0, fundo=8)


def ciclo(p, A=PASSO):
    sp, cp = math.sin(p), math.cos(p)
    fE, fD = -math.sin(p - 0.5), math.sin(p - 0.5)     # braço à frente (+) / atrás (-), atrasado
    pose_ = {
        # quadril: mais baixo nos contatos (cos 2p), pende para o pé de apoio, inclina para o lado livre
        "quadril": (A["roll"] * sp, A["sway"] * sp, A["bob"] * (1 + math.cos(2 * p)) / 2 + 1),
        # tronco gira contra o quadril, com atraso (overlap)
        "tronco": (-A["tronco"] * math.sin(p - 0.4), 0, -1.5 * math.cos(2 * p - 0.6)),
        "cabeca": (-A["cabeca"] * math.sin(p - 0.9), 0, 3 * math.cos(2 * p - 1.6) - 1.5 * math.cos(2 * p - 0.6)),
        # braços contra as pernas; antebraço atrasado
        # braço que recua sobe o ombro (em vez de só abrir em leque)
        "braco_cima_E": (A["braco"] * sp, 0, 3 * min(0.0, fE)), "braco_cima_D": (A["braco"] * sp, 0, 3 * min(0.0, fD)),
        "antebraco_E": (A["antebraco"] * math.sin(p - 0.6), 0, A["fundo"] * fE),
        "antebraco_D": (A["antebraco"] * math.sin(p - 0.6), 0, A["fundo"] * fD),
        "_esc": {"antebraco_E": 1 + 0.05 * fE, "antebraco_D": 1 + 0.05 * fD},
    }
    # pés: E no ar quando sin p > 0, D quando sin p < 0; no chão, fixos na posição de descanso
    T = pose(pose_)
    for lado, fase in (("E", sp), ("D", -sp)):
        x0, y0 = PE0[lado]
        lift = A["lift"] * max(0.0, fase) ** 1.3
        alvo = (x0 + (-1 if lado == "E" else 1) * 0.06 * lift, y0 - lift)   # pé livre abre um pouco
        dc, dk = ik(T["quadril"], lado, alvo)
        pose_[f"coxa_{lado}"] = (dc, 0, 0); pose_[f"canela_{lado}"] = (dk, 0, 0)
    return pose_


N_QUADROS, MS = 24, 42        # HD por esqueleto: fluido (~24 fps, ciclo de 1 s)

if __name__ == "__main__":
    quadros = [render(ciclo(2 * math.pi * i / N_QUADROS)).crop((0, 150, 1224, 1400)) for i in range(N_QUADROS)]
    peq = [q.resize((q.width // 3, q.height // 3), Image.LANCZOS) for q in quadros]
    peq[0].save("andar.gif", save_all=True, append_images=peq[1:], duration=MS, loop=0, disposal=2)
    chave = quadros[::N_QUADROS // 8]           # 8 quadros-chave para a folha de revisão
    folha = Image.new("RGBA", (peq[0].width * 4, peq[0].height * 2))
    for i, q in enumerate(peq[::N_QUADROS // 8]): folha.paste(q, ((i % 4) * q.width, (i // 4) * q.height))
    folha.save("andar_quadros.png")
    w, h = quadros[0].size; f = Image.new("RGBA", (w * 4, h * 2))
    for i, q in enumerate(chave): f.paste(q, ((i % 4) * w, (i // 4) * h))
    f.resize((f.width // 2, f.height // 2)).save("revisao_quadros.png")
    r = render({}); d = ImageDraw.Draw(r)
    for n, t in pose({}).items(): d.ellipse((t[0] + 92, t[1] - 8, t[0] + 108, t[1] + 8), outline=(255, 255, 0, 255), width=3)
    for l in "ED": d.ellipse((PE0[l][0] + 92, PE0[l][1] - 8, PE0[l][0] + 108, PE0[l][1] + 8), outline=(0, 255, 255, 255), width=3)
    r.save("rig_pivos.png")
    json.dump({"ossos": OSSOS, "ordem": ORDEM, "descanso": REST, "passo": PASSO}, open("rig.json", "w"), indent=1)
