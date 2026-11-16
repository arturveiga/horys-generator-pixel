"""Roda DENTRO do Blender (headless): prepara a cena do jogo e renderiza ações × direções em pixel.

Uso (o horys chama): blender -b <arquivo.blend> --python dentro.py -- <trabalho.json>
trabalho.json = {"config": {...}, "paleta": {...}, "saida": "<pasta>", "cores_partes": {...}, "previa": false}

Só stdlib + bpy/mathutils (o Python do Blender não vê o horys). Reimplementa, para o horys, o que o Blender Pixel
Kit (SouthernShotty) e os scripts do robô do Codex (14/11) faziam à mão:
- câmera do jogo top-down 3/4 com a escala pela altura-alvo em px (B1);
- material toon por família com a rampa da paleta aprovada + luz facetada, cor exata por emissão (B2);
- rig de empties por pivôs a partir de coleções/nomes, sem armature (B5);
- andar e idle procedurais: pé de apoio parado no chão, IK de 2 segmentos, calcanhar/ponta, bob, braço oposto (B5);
- lote ações × direções girando a âncora (B4) e o passe de partes com uma cor chapada por parte (B6).
O contorno, a paleta travada e a limpeza ficam no pós (horys_pixel.blender.pos), em Python.
"""
import fnmatch
import json
import math
import os
import re
import sys

import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

TRAB = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
CFG = TRAB["config"]
PAL = TRAB["paleta"]
SAIDA = TRAB["saida"]
PREVIA = bool(TRAB.get("previa"))
scene = bpy.context.scene
AVISOS = []


def log(*a):
    print("[horys]", *a, flush=True)


def lin(c):
    return c / 12.92 if c < 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgb(hx):
    hx = hx.lstrip("#")
    return (*[lin(int(hx[i:i + 2], 16) / 255) for i in (0, 2, 4)], 1.0)


def rotulo(o):
    return re.sub(r"\.\d{3,}$", "", o.name)


def casa(nome, globs):
    return any(fnmatch.fnmatchcase(nome, g) for g in globs)


def colecoes(globs):
    return [c for c in bpy.data.collections if casa(c.name, globs)]


# ------------------------------------------------------------------ cena: esconder o que não é o personagem


def preparar_cena():
    esconder = CFG.get("esconder") or []
    for c in colecoes(esconder):
        c.hide_render = True
        for o in c.all_objects:
            if o is not None:            # o Blender 5.2 devolve None para objeto órfão na coleção
                o.hide_render = True
    for o in scene.objects:
        if casa(rotulo(o), esconder):
            o.hide_render = True
        if o.type in ("LIGHT", "CAMERA"):
            o.hide_render = True
    r = scene.render
    r.engine = "BLENDER_EEVEE"
    r.filter_size = 0.0
    r.film_transparent = True
    r.resolution_x = r.resolution_y = int(CFG["camera"].get("quadro", 64))
    r.resolution_percentage = 100
    r.dither_intensity = 0
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGBA"
    r.image_settings.color_depth = "8"
    if hasattr(r, "use_compositing"):
        r.use_compositing = False
    if hasattr(scene, "compositing_node_group"):
        scene.compositing_node_group = None
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    scene.eevee.taa_render_samples = 1
    if scene.world is None:
        scene.world = bpy.data.worlds.new("Horys | mundo")
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.5, 0.5, 0.5, 1)
        bg.inputs[1].default_value = float(CFG.get("luz", {}).get("ambiente", 0.25))
    # sol na direção da luz facetada: a sombra projetada (Shader to RGB) concorda com a faceta
    d = Vector(CFG.get("luz", {}).get("direcao", [-0.52, -0.53, 0.67])).normalized()
    sol = bpy.data.lights.new("Horys | sol", "SUN")
    sol.energy = float(CFG.get("luz", {}).get("sol", 3.0))
    so = bpy.data.objects.new("Horys | sol", sol)
    scene.collection.objects.link(so)
    so.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()


# ------------------------------------------------------------------ rig de empties por pivôs (B5)


class Rig:
    def __init__(self, spec):
        self.ancora = bpy.data.objects[spec["ancora"]]
        self.seg = {}
        self.pivo = {}
        self.parte = {}
        self.objs = {}
        ligar = []
        usados = set()
        for s in spec["segmentos"]:
            nome = s["nome"]
            if nome not in self.seg:
                pai_nome = s.get("pai", "ancora")
                pai = self.ancora if pai_nome == "ancora" else self.seg[pai_nome]
                e = bpy.data.objects.new("Horys | " + nome, None)
                scene.collection.objects.link(e)
                e.empty_display_size = 0.15
                e.parent = pai
                e.rotation_mode = "QUATERNION"
                base = Vector(self.pivo[pai_nome]) if pai_nome != "ancora" else Vector((0, 0, 0))
                e.location = Vector(s["pivo"]) - base
                self.seg[nome], self.pivo[nome] = e, list(s["pivo"])
                self.parte[nome] = s.get("parte") or parte_padrao(nome)
                self.objs[nome] = []
            cands = []
            for c in colecoes(s.get("colecoes") or []):
                cands += list(c.all_objects)
            if s.get("objetos"):
                cands = [o for o in cands if casa(rotulo(o), s["objetos"])]
            for o in cands:
                if o.name in usados or o is self.ancora or o.type == "EMPTY":
                    continue
                if o.parent not in (self.ancora, None):
                    continue            # filho de outra peça: segue o pai
                usados.add(o.name)
                ligar.append((o, self.seg[nome]))
                self.objs[nome].append(o)
        bpy.context.view_layer.update()
        for o, e in ligar:
            mw = o.matrix_world.copy()
            o.parent = e
            o.matrix_parent_inverse = Matrix.Identity(4)
            o.matrix_world = mw
        soltos = [o for o in self.ancora.children if o.type != "EMPTY" and not o.hide_render]
        if soltos:
            AVISOS.append(f"{len(soltos)} peças sem segmento ficam presas à âncora (ex.: {soltos[0].name})")
        self.soltos = soltos
        bpy.context.view_layer.update()
        log("rig:", {k: len(v) for k, v in self.objs.items()})

    def limpar(self):
        for e in self.seg.values():
            e.animation_data_clear()
            e.rotation_quaternion = (1, 0, 0, 0)
        for nome, e in self.seg.items():
            pai = e.parent
            base = Vector((0, 0, 0)) if pai is self.ancora else Vector(self.pivo[[k for k, v in self.seg.items() if v is pai][0]])
            e.location = Vector(self.pivo[nome]) - base


def parte_padrao(nome):
    n = nome.lower()
    lado = "esq" if n.endswith(("_e", "-e", "esq", "esquerdo", "esquerda")) else "dir"
    if any(k in n for k in ("chifre", "cabelo", "capa", "antena", "enfeite")):
        return "enfeite"
    if "cabe" in n:
        return "cabeca"
    if any(k in n for k in ("ombro", "cotovelo", "braco", "mao")):
        return "braco-" + lado
    if any(k in n for k in ("coxa", "canela", "pe", "perna", "bota")):
        return "perna-" + lado
    if any(k in n for k in ("arma", "espada")):
        return "arma"
    return "tronco"


# ------------------------------------------------------------------ movimento procedural (B5)


def chave(o, f):
    o.keyframe_insert("location", frame=f)
    o.keyframe_insert("rotation_quaternion", frame=f)


def q_euler(x, y, z):
    return Euler((x, y, z)).to_quaternion()


def resolver_perna(quadril, joelho, tornozelo, quadril_n, tornozelo_n):
    """Joelho do IK de 2 segmentos rígidos, dobrando para o mesmo lado da pose de repouso (ou para a frente)."""
    eixo0 = (tornozelo - quadril).normalized()
    eixo = (tornozelo_n - quadril_n)
    vao = eixo.length
    eixo.normalize()
    a, b = (joelho - quadril).length, (tornozelo - joelho).length
    vao = min(vao, a + b - 1e-4)
    dobra0 = joelho - quadril - eixo0 * eixo0.dot(joelho - quadril)
    if dobra0.length < 1e-6:
        dobra0 = Vector((0, -1, 0))        # perna reta em repouso: o joelho vai para a frente (-Y)
    dobra = dobra0 - eixo * eixo.dot(dobra0)
    dobra = dobra.normalized() if dobra.length > 1e-6 else Vector((0, -1, 0))
    ao_longo = (vao * vao + a * a - b * b) / (2 * vao)
    return quadril_n + ao_longo * eixo + math.sqrt(max(0.0, a * a - ao_longo * ao_longo)) * dobra


class Corpo:
    """Papéis do rig para o movimento: tronco, cabeça, braços (ombro, cotovelo), pernas (coxa, canela, pé)."""

    def __init__(self, rig, papeis):
        self.rig = rig
        self.tronco = rig.seg[papeis["tronco"]]
        self.p_tronco = Vector(rig.pivo[papeis["tronco"]])
        self.cabeca = rig.seg.get(papeis.get("cabeca", ""))
        self.busto = rig.seg.get(papeis.get("busto", ""))      # quadrúpede: o tronco humano sobre o corpo
        self.fases = [p.get("fase") for p in papeis.get("pernas", [])]
        self.bracos = [(b["lado"], rig.seg[b["ombro"]], rig.seg.get(b.get("cotovelo", ""))) for b in papeis.get("bracos", [])]
        self.pernas = []
        for p in papeis.get("pernas", []):
            coxa, canela, pe = rig.seg[p["coxa"]], rig.seg[p["canela"]], rig.seg[p["pe"]]
            for e in (coxa, canela, pe):
                if e.parent is not rig.ancora:
                    raise ValueError(f"o segmento {e.name} da perna precisa ter pai 'ancora' (o pé fica no chão)")
            q, j, t = (Vector(rig.pivo[p[k]]) for k in ("coxa", "canela", "pe"))
            sola = self._sola(rig.objs[p["pe"]], t)
            self.pernas.append((p["lado"], q, j, t, coxa, canela, pe, sola))
        if self.pernas:
            q, j, t = self.pernas[0][1:4]
            self.escala = ((j - q).length + (t - j).length) / 1.65     # 1,65 = perna do robô de referência
        else:
            self.escala = 1.0

    def _sola(self, objs, tornozelo):
        inv = self.rig.ancora.matrix_world.inverted()
        pts = []
        for o in objs:
            if o.type != "MESH":
                continue
            mw = inv @ o.matrix_world
            pts += [mw @ v.co for v in o.data.vertices]
        if not pts:
            return [tornozelo.copy()]
        zmin = min(p.z for p in pts)
        sola = [p for p in pts if p.z < zmin + 0.03]
        return sola[:: max(1, len(sola) // 48)]

    def pose_perna(self, f, quadril_n, perna, tornozelo_n, giro):
        lado, q, j, t, coxa, canela, pe, sola = perna
        joelho_n = resolver_perna(q, j, t, quadril_n, tornozelo_n)
        for obj, ponto, repouso, agora in ((coxa, quadril_n, j - q, joelho_n - quadril_n),
                                           (canela, joelho_n, t - j, tornozelo_n - joelho_n)):
            obj.location = ponto
            obj.rotation_quaternion = repouso.rotation_difference(agora)
            chave(obj, f)
        pe.location = tornozelo_n
        pe.rotation_quaternion = giro
        chave(pe, f)


def andar(corpo, n, amp=1.0, amp_bracos=None, bracos_tras=0.0, inclina=0.0, dobra_cotovelo=None):
    """Andar de n quadros (o walk.py do robô do Codex, parametrizado pela escala da perna). Bípede: pernas em
    oposição (fase 0 e 0,5). Quadrúpede: cada perna com a sua 'fase' na config (passo: TE 0, DE 0,25, TD 0,5, DD
    0,75). amp_bracos: balanço dos braços (baixo quando ele segura uma arma com as duas mãos).
    bracos_tras: rad somados ao ombro (> 0 leva o braço para trás: ~0,35 no andar "lembra Naruto", ~1,2 na corrida
    ninja). inclina: rad de tronco para a frente. dobra_cotovelo: dobra fixa (None = a do balanço)."""
    amp_b = amp if amp_bracos is None else amp_bracos
    s = corpo.escala
    APOIO, PASSO, ALTURA = 0.61, 0.77 * s * amp, 0.46 * s * amp

    def ciclo_pe(fase):
        if fase < APOIO:
            w = fase / APOIO
            viagem = PASSO * (2 * w - 1)
            calc = -0.23 * math.cos(math.pi * min(1, w / 0.26)) * max(0, 1 - w / 0.26)
            ponta = 0.28 * max(0, (w - 0.70) / 0.30) ** 1.6
            return viagem, 0.0, calc + ponta
        u = (fase - APOIO) / (1 - APOIO)
        suave = u * u * (3 - 2 * u)
        vel = (1 - APOIO) / APOIO
        viagem = PASSO + 2 * PASSO * (vel * u - (1 + vel) * suave)
        return viagem, ALTURA * math.sin(math.pi * u) ** 1.35, 0.28 * (1 - u) - 0.23 * u + 0.11 * math.sin(math.tau * u)

    for i in range(n + 1):
        f = i + 1
        t = (i % n) / n
        ph = math.tau * t
        desl = Vector((0.058 * s * math.cos(ph + 0.32), -0.058 * s, -0.219 * s - 0.085 * s * math.cos(2 * ph - 0.22)))
        corpo.tronco.location = corpo.p_tronco + desl          # o tronco tem pai 'ancora'
        corpo.tronco.rotation_quaternion = q_euler(0.065 + inclina, 0.029 * math.cos(ph), -0.064 * math.cos(ph))
        chave(corpo.tronco, f)
        if corpo.cabeca:
            corpo.cabeca.rotation_quaternion = q_euler(-0.047 + 0.025 * math.cos(2 * ph - 0.8),
                                                      -0.023 * math.cos(ph - 0.29), 0.051 * math.cos(ph - 0.12))
            chave(corpo.cabeca, f)
        for lado, ombro, cotovelo in corpo.bracos:
            bal = -lado * math.cos(ph - 0.25)
            ombro.rotation_quaternion = q_euler(0.285 * bal * amp_b - 0.03 * amp_b + bracos_tras, -0.083 * lado * amp_b,
                                                0.032 * lado * math.sin(ph - 0.15) * amp_b)
            chave(ombro, f)
            if cotovelo:
                dob = (-0.11 + 0.09 * bal) * amp_b if dobra_cotovelo is None else dobra_cotovelo
                cotovelo.rotation_quaternion = q_euler(dob, 0,
                                                       0.027 * lado * math.cos(ph + 0.27) * amp_b)
                chave(cotovelo, f)
        R = corpo.tronco.rotation_quaternion.to_matrix()
        for k, perna in enumerate(corpo.pernas):
            lado, q, j, t0, coxa, canela, pe, sola = perna
            f0 = corpo.fases[k] if corpo.fases[k] is not None else (0 if lado < 0 else 0.5)
            fase = (t + f0) % 1
            viagem, alt, rol = ciclo_pe(fase)
            giro = Quaternion((0, 0, 1), lado * 0.026) @ Quaternion((1, 0, 0), rol)
            baixo = min((giro @ (p - t0)).z + t0.z for p in sola)
            sola_z0 = min(p.z for p in sola)
            tornozelo_n = t0 + Vector((0.044 * lado * alt, viagem, alt + sola_z0 - baixo))
            quadril_n = corpo.p_tronco + desl + R @ (q - corpo.p_tronco)
            corpo.pose_perna(f, quadril_n, perna, tornozelo_n, giro)


def idle(corpo, n, amp=1.0):
    """Idle de respiração (o idle.py do robô do Codex): tronco desce e balança, cabeça e braços em contrafase,
    pés parados no chão."""
    s = corpo.escala
    for i in range(n + 1):
        f = i + 1
        ph = math.tau * (i % n) / n
        resp = 0.5 - 0.5 * math.cos(ph)
        bal = math.sin(ph)
        desl = Vector((0.036 * s * bal, -0.027 * s * resp, -0.128 * s * resp)) * amp
        corpo.tronco.location = corpo.p_tronco + desl
        corpo.tronco.rotation_quaternion = q_euler(0.014 * resp * amp, 0.010 * bal * amp, 0.012 * bal * amp)
        chave(corpo.tronco, f)
        if corpo.cabeca:
            corpo.cabeca.rotation_quaternion = q_euler(0.034 * math.sin(ph - 0.62) * amp, -0.016 * math.sin(ph - 0.36) * amp,
                                                      -0.021 * math.sin(ph - 0.56) * amp)
            chave(corpo.cabeca, f)
        for lado, ombro, cotovelo in corpo.bracos:
            ombro.rotation_quaternion = q_euler(0.029 * math.sin(ph - 0.43 + lado * 0.47) * amp,
                                                -lado * (0.024 * resp + 0.012 * math.sin(ph - 0.34)) * amp,
                                                lado * 0.019 * math.sin(ph - 0.16) * amp)
            chave(ombro, f)
            if cotovelo:
                cotovelo.rotation_quaternion = q_euler(-0.030 * resp * amp, lado * 0.011 * math.sin(ph - 0.62) * amp, 0)
                chave(cotovelo, f)
        R = corpo.tronco.rotation_quaternion.to_matrix()
        for perna in corpo.pernas:
            lado, q, j, t0, coxa, canela, pe, sola = perna
            quadril_n = corpo.p_tronco + desl + R @ (q - corpo.p_tronco)
            corpo.pose_perna(f, quadril_n, perna, t0.copy(), Quaternion())


# ------------------------------------------------------------------ materiais toon pela paleta (B2)


def mat_toon(nome, rampa, limiares, luz, faceta):
    m = bpy.data.materials.new("Horys | " + nome)
    m.use_nodes = True
    t = m.node_tree
    t.nodes.clear()
    valor = _cadeia_luz(t, luz, faceta)
    rn = t.nodes.new("ShaderNodeValToRGB")
    rn.color_ramp.interpolation = "CONSTANT"
    el = rn.color_ramp.elements
    pos = [0.0] + list(limiares)
    while len(el) < len(rampa):
        el.new(0.99)
    while len(el) > len(rampa):
        el.remove(el[-1])
    for e, p, hx in zip(el, pos, rampa):
        e.position = p
        e.color = rgb(hx)
    t.links.new(valor, rn.inputs["Fac"])
    emi = t.nodes.new("ShaderNodeEmission")
    t.links.new(rn.outputs["Color"], emi.inputs["Color"])
    out = t.nodes.new("ShaderNodeOutputMaterial")
    t.links.new(emi.outputs[0], out.inputs["Surface"])
    m.diffuse_color = rgb(rampa[len(rampa) // 2])
    return m


def mat_chapado(nome, hx):
    m = bpy.data.materials.new("Horys | " + nome)
    m.use_nodes = True
    t = m.node_tree
    t.nodes.clear()
    emi = t.nodes.new("ShaderNodeEmission")
    emi.inputs["Color"].default_value = rgb(hx)
    out = t.nodes.new("ShaderNodeOutputMaterial")
    t.links.new(emi.outputs[0], out.inputs["Surface"])
    m.diffuse_color = rgb(hx)
    return m


def _lum(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def familia_de(mat, regras, padrao, fams):
    nome = re.sub(r"\.\d{3,}$", "", mat.name)
    for glob, fam in regras:
        if fnmatch.fnmatchcase(nome, glob):
            return fam
    if padrao and padrao != "auto":
        return padrao
    # auto: a família cuja cor do meio é a mais próxima da cor base do material
    c = list(mat.diffuse_color)[:3]
    if mat.use_nodes:
        b = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if b is not None:
            c = list(b.inputs["Base Color"].default_value)[:3]
    melhor, dmin = None, 9e9
    for nome_f, f in fams.items():
        alvo = rgb(f["rampa"][len(f["rampa"]) // 2])
        d = sum((a - b) ** 2 for a, b in zip(c, alvo)) + 0.5 * (_lum(c) - _lum(alvo)) ** 2
        if d < dmin:
            melhor, dmin = nome_f, d
    return melhor


def aplicar_paleta(alvos):
    luz = CFG.get("luz", {}).get("direcao", [-0.52, -0.53, 0.67])
    faceta = float(CFG.get("luz", {}).get("faceta", 0.73))
    fams = PAL["familias"]
    mats = {}
    for nome, f in fams.items():
        if f.get("tipo") == "emissivo" or len(f["rampa"]) == 1:
            mats[nome] = mat_chapado(nome, f["rampa"][-1])
        else:
            mats[nome] = mat_toon(nome, f["rampa"], f.get("limiares") or limiares_padrao(len(f["rampa"])), luz, faceta)
    regras = [tuple(r) for r in (CFG.get("materiais", {}).get("regras") or [])]
    padrao = CFG.get("materiais", {}).get("padrao", "auto")
    uso, troca = {}, {}
    for o in alvos:
        for i, slot in enumerate(o.material_slots):
            if slot.material is None:
                continue
            fam = familia_de(slot.material, regras, padrao, fams)
            troca[slot.material.name] = fam
            uso[fam] = uso.get(fam, 0) + 1
            slot.material = mats[fam]
    log("famílias:", uso)
    return troca, mats


def _cadeia_luz(t, luz, faceta):
    """Os nós de luz do toon: Diffuse -> Shader to RGB misturado com a faceta (normal · luz). Devolve o socket do
    valor (0..1)."""
    dif = t.nodes.new("ShaderNodeBsdfDiffuse")
    dif.inputs["Color"].default_value = (0.8, 0.8, 0.8, 1)
    s2r = t.nodes.new("ShaderNodeShaderToRGB")
    t.links.new(dif.outputs[0], s2r.inputs[0])
    geo = t.nodes.new("ShaderNodeNewGeometry")
    dot = t.nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    dot.inputs[1].default_value = Vector(luz).normalized()
    t.links.new(geo.outputs["Normal"], dot.inputs[0])
    ma = t.nodes.new("ShaderNodeMath")
    ma.operation = "MULTIPLY_ADD"
    ma.inputs[1].default_value = 0.52
    ma.inputs[2].default_value = 0.35
    t.links.new(dot.outputs["Value"], ma.inputs[0])
    mix = t.nodes.new("ShaderNodeMix")
    mix.data_type = "FLOAT"
    mix.inputs[0].default_value = 1.0 - faceta
    t.links.new(ma.outputs[0], mix.inputs[2])
    t.links.new(s2r.outputs["Color"], mix.inputs[3])
    return mix.outputs[0]


def calibrar_limiares(alvos, fams, mats, direcoes, ancora):
    """Limiares da rampa pela ÁREA: renderiza o valor de luz de cada família na pose de repouso, em todas as
    direções, e põe os limiares nos quantis da meta (3 tons: 22% sombra, 56% base, 22% luz; 2 tons: 35% sombra).
    Assim a cor-base do conceito domina e a luz e a sombra só desenham o volume (regra de rampa do horys)."""
    luz = CFG.get("luz", {}).get("direcao", [-0.52, -0.53, 0.67])
    faceta = float(CFG.get("luz", {}).get("faceta", 0.73))
    meta = CFG.get("luz", {}).get("proporcao") or {"3": [0.22, 0.78], "2": [0.35]}
    toon = [n for n, f in fams.items() if f.get("tipo") != "emissivo" and len(f["rampa"]) > 1]
    if not toon:
        return {}
    val = {}
    for k, nome in enumerate(toon):
        m = bpy.data.materials.new("Horys | valor " + nome)
        m.use_nodes = True
        t = m.node_tree
        t.nodes.clear()
        v = _cadeia_luz(t, luz, faceta)
        cc = t.nodes.new("ShaderNodeCombineColor")
        t.links.new(v, cc.inputs[0])
        cc.inputs[1].default_value = (k + 1) / 16.0
        emi = t.nodes.new("ShaderNodeEmission")
        t.links.new(cc.outputs[0], emi.inputs["Color"])
        out = t.nodes.new("ShaderNodeOutputMaterial")
        t.links.new(emi.outputs[0], out.inputs["Surface"])
        val[nome] = m
    preto = mat_chapado("valor fora", "#000000")
    inv = {m.name: n for n, m in mats.items()}
    guard = []
    for o in alvos:
        for s in o.material_slots:
            guard.append((s, s.material))
            fam = inv.get(s.material.name) if s.material else None
            s.material = val.get(fam, preto)
    vs = scene.view_settings.view_transform
    scene.view_settings.view_transform = "Raw" if "Raw" in [i.identifier for i in
                                                            scene.view_settings.bl_rna.properties["view_transform"].enum_items] else vs
    amostras = {n: [] for n in toon}
    tmp = os.path.join(SAIDA, "_render", "_calibrar")
    os.makedirs(tmp, exist_ok=True)
    for dnome, ang in direcoes.items():
        ancora.rotation_euler.z = math.radians(float(ang))
        scene.frame_set(1)
        arq = os.path.join(tmp, dnome + ".png")
        scene.render.filepath = arq
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(arq)
        img.colorspace_settings.name = "Non-Color"
        px = list(img.pixels)
        bpy.data.images.remove(img)
        cru = scene.view_settings.view_transform == "Raw"
        for i in range(0, len(px), 4):
            if px[i + 3] < 0.5:
                continue
            g = px[i + 1] if cru else lin(px[i + 1])
            k = int(round(g * 16)) - 1
            if 0 <= k < len(toon):
                r = px[i] if cru else lin(px[i])
                amostras[toon[k]].append(r)
    ancora.rotation_euler.z = 0
    scene.view_settings.view_transform = vs
    for s, m in guard:
        s.material = m
    limiares = {}
    for nome in toon:
        a = sorted(amostras[nome])
        n_tons = len(fams[nome]["rampa"])
        qs = meta.get(str(n_tons))
        if len(a) < 20 or not qs or fams[nome].get("limiares"):
            continue
        lim = [a[min(len(a) - 1, int(q * len(a)))] for q in qs]
        lim = [max(0.001, min(0.999, x)) for x in lim]
        for i in range(1, len(lim)):
            lim[i] = max(lim[i], lim[i - 1] + 0.005)
        el = next(n for n in mats[nome].node_tree.nodes if n.type == "VALTORGB").color_ramp.elements
        for e, p in zip(list(el)[1:], lim):
            e.position = p
        limiares[nome] = [round(x, 3) for x in lim]
    log("limiares calibrados:", limiares)
    return limiares


def limiares_padrao(n):
    return {2: [0.42], 3: [0.30, 0.58], 4: [0.16, 0.33, 0.49]}.get(n, [k / n for k in range(1, n)])


# ------------------------------------------------------------------ câmera do jogo (B1)


def camera_jogo(rig, alvos):
    c = CFG["camera"]
    quadro = int(c.get("quadro", 64))
    ang = math.radians(float(c.get("angulo", 43)))
    giro = math.radians(float(c.get("giro", 0)))
    cam_d = bpy.data.cameras.new("Horys | câmera do jogo")
    cam_d.type = "ORTHO"
    cam = bpy.data.objects.new("Horys | câmera do jogo", cam_d)
    scene.collection.objects.link(cam)
    scene.camera = cam
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(v) for o in alvos for v in o.bound_box]
    zc = (min(p.z for p in pts) + max(p.z for p in pts)) / 2
    alvo = rig.ancora.matrix_world.translation + Vector((0, 0, zc))
    dist = 40.0
    dirv = Vector((math.sin(giro) * math.cos(ang), -math.cos(giro) * math.cos(ang), math.sin(ang)))
    cam.location = alvo + dist * dirv
    cam.rotation_euler = (alvo - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam_d.clip_end = 200
    bpy.context.view_layer.update()
    inv = cam.matrix_world.inverted()
    loc = [inv @ p for p in pts]
    xs, ys = [p.x for p in loc], [p.y for p in loc]
    altura = max(ys) - min(ys)
    escala = altura * quadro / float(c.get("altura_px", quadro * 0.7))
    larg = max(xs) - min(xs)
    margem = int(c.get("margem_px", 2))
    if larg * quadro / escala > quadro - 2 * margem:
        escala = larg * quadro / (quadro - 2 * margem)
        AVISOS.append(f"a figura é larga: a escala foi pela largura; altura final {altura * quadro / escala:.0f} px")
    cam_d.ortho_scale = escala
    base = int(c.get("base_px", 4))
    y_quer = -escala / 2 + base * escala / quadro
    dy = min(ys) - y_quer
    dx = (min(xs) + max(xs)) / 2
    cam.location = cam.location + cam.matrix_world.to_3x3() @ Vector((dx, dy, 0))
    bpy.context.view_layer.update()
    info = {"ortho_scale": round(escala, 4), "angulo": c.get("angulo", 43), "quadro": quadro,
            "altura_px": round(altura * quadro / escala, 1), "local": list(cam.location),
            "rotacao": list(cam.rotation_euler)}
    log("câmera:", info)
    return info


def gerar_acao(rig, corpo, a):
    rig.limpar()
    n = int(a.get("quadros", 8))
    amp = float(a.get("amplitude", 1.0))
    if a["tipo"] in ("andar", "correr"):
        andar(corpo, n, amp, a.get("amplitude_bracos"), float(a.get("bracos_tras", 0.0)),
              float(a.get("inclina", 0.0)), a.get("dobra_cotovelo"))
    elif a["tipo"] == "idle":
        idle(corpo, n, amp)
    elif a["tipo"] == "ataque":
        ataque(corpo, n, amp)
    elif a["tipo"] == "soco":
        soco(corpo, n, amp)
    elif a["tipo"] == "dano":
        dano(corpo, n, amp)
    elif a["tipo"] == "morte":
        morte(corpo, n)
    elif a["tipo"] != "timeline":
        raise ValueError(f"tipo de ação {a['tipo']} (andar | correr | idle | ataque | soco | dano | morte | timeline)")
    animar_fogo(n, float(a.get("fogo", 1.0)))
    return n


FOGO_PADROES = ("*fogo*", "*chama*", "*flame*", "*fire*")
_FOGO_BASE = {}


def objetos_fogo():
    """Peças de fogo pelo nome do objeto (CFG 'fogo': {'objetos': [...]}); o nome não muda com a paleta."""
    pad = (CFG.get("fogo") or {}).get("objetos") or FOGO_PADROES
    return [o for o in scene.objects if o.type == "MESH" and any(fnmatch.fnmatch(o.name.lower(), p.lower())
                                                                  for p in pad)]


def animar_fogo(n, forca=1.0):
    """Fogo vivo: cada língua tremula a partir da própria origem (a base), esticando e encolhendo e balançando,
    cada uma numa fase. Ciclos inteiros dentro das n poses: o laço fecha sem salto."""
    objs = objetos_fogo()
    if not objs or forca <= 0:
        return
    ciclos = 2 if n >= 8 else 1
    for i, o in enumerate(objs):
        o.animation_data_clear()
        o.rotation_mode = "QUATERNION"
        if o.name not in _FOGO_BASE:
            _FOGO_BASE[o.name] = (o.rotation_quaternion.copy(), o.scale.copy())
        q0, s0 = _FOGO_BASE[o.name]
        fase = i * 2.39996
        a = forca * (0.8 + 0.4 * ((i * 0.618) % 1.0))
        for f in range(1, n + 2):
            th = math.tau * ciclos * (f - 1) / n
            estica = 0.16 * a * math.sin(th + fase) + 0.06 * a * math.sin(2 * th + fase * 1.7)
            o.scale = (s0.x * (1 - 0.45 * estica), s0.y * (1 - 0.45 * estica), s0.z * (1 + estica))
            o.rotation_quaternion = q0 @ q_euler(0.14 * a * math.sin(th + fase + 1.3),
                                                 0.14 * a * math.cos(th + fase * 0.7), 0.0)
            o.keyframe_insert("scale", frame=f)
            o.keyframe_insert("rotation_quaternion", frame=f)
    log("fogo vivo:", len(objs), "línguas")


def juntar_animacoes(arq, nome):
    """O exportador glTF do Blender solta uma animação por objeto/empty; o Estúdio (model-viewer) toca uma por
    vez. Junta todas numa só, com o nome da ação, reescrevendo só o bloco JSON do .glb."""
    import struct
    dado = open(arq, "rb").read()
    tam = struct.unpack_from("<I", dado, 12)[0]
    j = json.loads(dado[20:20 + tam])
    resto = dado[20 + tam:]
    anims = j.get("animations") or []
    if len(anims) <= 1:
        if anims:
            anims[0]["name"] = nome
    else:
        uma = {"name": nome, "channels": [], "samplers": []}
        vistos = set()
        for an in anims:
            base = len(uma["samplers"])
            uma["samplers"] += an["samplers"]
            for ch in an["channels"]:
                alvo = (ch["target"].get("node"), ch["target"]["path"])
                if alvo in vistos:
                    continue
                vistos.add(alvo)
                ch = dict(ch, sampler=ch["sampler"] + base)
                uma["channels"].append(ch)
        j["animations"] = [uma]
    js = json.dumps(j, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    js += b" " * (-len(js) % 4)
    total = 12 + 8 + len(js) + len(resto)
    with open(arq, "wb") as fh:
        fh.write(dado[:8] + struct.pack("<I", total) + struct.pack("<I", len(js)) + b"JSON" + js + resto)


# ataque de arma de duas mãos por cima (picareta, machado, martelo): (tempo 0..1, ombro, cotovelo, busto, corpo_z)
# ombro > 0 leva o que está acima do ombro para a frente e para baixo (o golpe); < 0 leva para trás (antecipação)
ATAQUE_CHAVES = [(0.0, 0.0, 0.0, 0.0, 0.0), (0.30, -0.95, -0.35, -0.16, 0.02), (0.45, -1.05, -0.4, -0.2, 0.03),
                 (0.58, 1.05, 0.25, 0.24, -0.05), (0.72, 1.18, 0.3, 0.28, -0.07), (1.0, 0.0, 0.0, 0.0, 0.0)]


def _interp(u, chaves, k):
    for a, b in zip(chaves, chaves[1:]):
        if a[0] <= u <= b[0]:
            w = (u - a[0]) / max(1e-6, b[0] - a[0])
            w = w * w * (3 - 2 * w)
            return a[k] + (b[k] - a[k]) * w
    return chaves[-1][k]


def ataque(corpo, n, amp=1.0):
    """Golpe de cima para baixo com as duas mãos: antecipação (a arma vai para trás), pausa curta no alto, golpe rápido
    para a frente e para baixo, impacto segurado, recuperação. As pernas ficam paradas no chão; o busto acompanha."""
    s = corpo.escala
    for i in range(n + 1):
        f = i + 1
        u = (i % n) / n
        om, co, bu, cz = (_interp(u, ATAQUE_CHAVES, k) * amp for k in (1, 2, 3, 4))
        desl = Vector((0, -0.04 * s * max(0.0, bu), cz * s))
        corpo.tronco.location = corpo.p_tronco + desl
        corpo.tronco.rotation_quaternion = Quaternion()
        chave(corpo.tronco, f)
        if corpo.busto:
            corpo.busto.rotation_quaternion = q_euler(bu, 0, 0)
            chave(corpo.busto, f)
        for lado, ombro, cotovelo in corpo.bracos:
            ombro.rotation_quaternion = q_euler(om, 0, 0)
            chave(ombro, f)
            if cotovelo:
                cotovelo.rotation_quaternion = q_euler(co, 0, 0)
                chave(cotovelo, f)
        for perna in corpo.pernas:
            lado, q, j, t0, coxa, canela, pe, sola = perna
            corpo.pose_perna(f, corpo.p_tronco + desl + (q - corpo.p_tronco), perna, t0.copy(), Quaternion())


# soco com o braço de lado +1: (tempo, ombro_soco, cotovelo_soco, ombro_outro, giro_tronco_z, avanço_y)
# ombro < 0 levanta o braço para a frente; giro < 0 leva o ombro +X para a frente
SOCO_CHAVES = [(0.0, 0.0, 0.0, 0.0, 0.0, 0.0), (0.25, 0.45, -1.3, -0.25, 0.3, 0.02),
               (0.40, -1.5, -0.05, 0.35, -0.4, -0.06), (0.62, -1.5, -0.05, 0.35, -0.4, -0.06),
               (1.0, 0.0, 0.0, 0.0, 0.0, 0.0)]
# dano: (tempo, inclina_tronco (< 0 = para trás), cabeça, ombros, cotovelos)
DANO_CHAVES = [(0.0, 0.0, 0.0, 0.0, 0.0), (0.15, -0.4, -0.35, -0.7, -0.6), (0.4, -0.3, -0.2, -0.5, -0.4),
               (1.0, 0.0, 0.0, 0.0, 0.0)]


def _pernas_paradas(corpo, f, desl, R):
    for perna in corpo.pernas:
        q, t0 = perna[1], perna[3]
        corpo.pose_perna(f, corpo.p_tronco + desl + R @ (q - corpo.p_tronco), perna, t0.copy(), Quaternion())


def soco(corpo, n, amp=1.0):
    """Soco reto com o braço de lado +1: puxa para trás girando o tronco, estica rápido, segura e volta."""
    s = corpo.escala
    for i in range(n + 1):
        f = i + 1
        u = (i % n) / n
        om, co, oo, gz, av = (_interp(u, SOCO_CHAVES, k) * amp for k in (1, 2, 3, 4, 5))
        desl = Vector((0, av * s * 4, 0))
        q = q_euler(0, 0, gz)
        corpo.tronco.location = corpo.p_tronco + desl
        corpo.tronco.rotation_quaternion = q
        chave(corpo.tronco, f)
        for lado, ombro, cotovelo in corpo.bracos:
            ombro.rotation_quaternion = q_euler(om if lado > 0 else oo, 0, 0)
            chave(ombro, f)
            if cotovelo:
                cotovelo.rotation_quaternion = q_euler(co if lado > 0 else -0.6 * abs(oo), 0, 0)
                chave(cotovelo, f)
        _pernas_paradas(corpo, f, desl, q.to_matrix())


def dano(corpo, n, amp=1.0):
    """Toma o golpe: tronco e cabeça jogados para trás, braços sobem soltos, volta ao repouso."""
    s = corpo.escala
    for i in range(n + 1):
        f = i + 1
        u = (i % n) / n
        it, ca, om, co = (_interp(u, DANO_CHAVES, k) * amp for k in (1, 2, 3, 4))
        desl = Vector((0, -it * s * 0.3, 0))
        q = q_euler(it, 0, 0)
        corpo.tronco.location = corpo.p_tronco + desl
        corpo.tronco.rotation_quaternion = q
        chave(corpo.tronco, f)
        if corpo.cabeca:
            corpo.cabeca.rotation_quaternion = q_euler(ca, 0, 0)
            chave(corpo.cabeca, f)
        for lado, ombro, cotovelo in corpo.bracos:
            ombro.rotation_quaternion = q_euler(om, -lado * 0.3 * abs(om), 0)
            chave(ombro, f)
            if cotovelo:
                cotovelo.rotation_quaternion = q_euler(co, 0, 0)
                chave(cotovelo, f)
        _pernas_paradas(corpo, f, desl, q.to_matrix())


def morte(corpo, n):
    """Cai de costas: o corpo inteiro gira em volta do calcanhar até deitar; o último quadro fica deitado
    (não é laço). Braços abrem na queda."""
    s = corpo.escala
    P = Vector((0, 0.12 * s / 0.2, 0))
    for i in range(n + 1):
        f = i + 1
        u = min(1.0, i / n)
        w = u * u                                           # acelera na queda
        ang = -1.5 * w
        q = q_euler(ang, 0, 0)
        R = q.to_matrix()
        sobe = Vector((0, 0, 0.2 * math.sin(-ang)))         # espessura do corpo: não afunda no chão
        corpo.tronco.location = P + R @ (corpo.p_tronco - P) + sobe
        corpo.tronco.rotation_quaternion = q
        chave(corpo.tronco, f)
        if corpo.cabeca:
            corpo.cabeca.rotation_quaternion = q_euler(-0.3 * math.sin(math.pi * u), 0, 0)
            chave(corpo.cabeca, f)
        for lado, ombro, cotovelo in corpo.bracos:
            ombro.rotation_quaternion = q_euler(-0.9 * u, -lado * 0.6 * u, 0)
            chave(ombro, f)
            if cotovelo:
                cotovelo.rotation_quaternion = q_euler(-0.3 * u, 0, 0)
                chave(cotovelo, f)
        for perna in corpo.pernas:
            q0, t0 = perna[1], perna[3]
            corpo.pose_perna(f, P + R @ (q0 - P) + sobe, perna, P + R @ (t0 - P) + sobe, q)


def enquadrar(cam, alvos, rig, corpo, acoes, direcoes):
    """Ajusta a câmera na VERTICAL pela união de todas as poses × direções (o pé que vem para a câmera desce na
    tela): a figura inteira cabe no quadro, com o ponto mais baixo em base_px. A escala continua a da pose parada
    (altura_px é a altura do personagem em pé)."""
    c = CFG["camera"]
    quadro = int(c.get("quadro", 64))
    base = int(c.get("base_px", 4))
    margem = int(c.get("margem_px", 2))
    escala = cam.data.ortho_scale
    inv = cam.matrix_world.inverted()
    ys = []
    for a in acoes.values():
        n = gerar_acao(rig, corpo, a)
        for dnome, ang in direcoes.items():
            rig.ancora.rotation_euler.z = math.radians(float(ang))
            for f in range(1, n + 1, max(1, n // 8)):
                scene.frame_set(f)
                for o in alvos:
                    mw = o.matrix_world
                    ys += [(inv @ (mw @ Vector(v))).y for v in o.bound_box]
    rig.ancora.rotation_euler.z = 0
    rig.limpar()
    scene.frame_set(1)
    if not ys:
        return
    y_quer = -escala / 2 + base * escala / quadro
    dy = min(ys) - y_quer
    cam.location = cam.location + cam.matrix_world.to_3x3() @ Vector((0, dy, 0))
    bpy.context.view_layer.update()
    alto = (max(ys) - min(ys)) * quadro / escala
    if alto > quadro - base - margem:
        AVISOS.append(f"as poses ocupam {alto:.0f} px de altura e o quadro tem {quadro}: aumente 'quadro' ou "
                      "diminua 'altura_px'")
    log("enquadrar: poses de", round(alto, 1), "px")


# ------------------------------------------------------------------ partes (B6)


def mats_partes(rig):
    cores = TRAB.get("cores_partes") or {}
    feitos = {}
    for nome, objs in list(rig.objs.items()) + [("_soltos", rig.soltos)]:
        parte = rig.parte.get(nome, "tronco")
        if parte not in feitos:
            feitos[parte] = mat_chapado("parte " + parte, cores.get(parte, "#ff8c00"))
        for o in objs:
            for ob in [o] + list(o.children_recursive):
                yield ob, feitos[parte]


def render_quadros(pasta, n, direcoes, ancora, sufixo=""):
    os.makedirs(pasta, exist_ok=True)
    quadros = range(1, n + 1)
    if PREVIA:
        quadros = sorted({1, 1 + n // 4, 1 + n // 2, 1 + 3 * n // 4})
    for dnome, ang in direcoes.items():
        ancora.rotation_euler.z = math.radians(float(ang))
        for f in quadros:
            scene.frame_set(f)
            scene.render.filepath = os.path.join(pasta, f"{dnome}{sufixo}_{f:04d}.png")
            bpy.ops.render.render(write_still=True)
    ancora.rotation_euler.z = 0


def main_3d():
    """Modo '3d' (etapa de aprovação, antes do pixel): o modelo com as cores dele, o rig e cada ação exportados
    como <stem>_<acao>.glb animado (uma animação por arquivo, a linha do tempo da cena), para o Artur girar,
    ver de todos os ângulos e apontar defeitos no Estúdio."""
    esconder = CFG.get("esconder") or []
    for c in colecoes(esconder):
        for o in list(c.all_objects):
            if o is not None:
                bpy.data.objects.remove(o, do_unlink=True)
    for o in list(scene.objects):
        if o.type in ("LIGHT", "CAMERA"):
            bpy.data.objects.remove(o, do_unlink=True)
    rig = Rig(CFG["rig"])
    corpo = Corpo(rig, CFG["papeis"])
    for e in rig.seg.values():
        e.hide_viewport = False
    acoes = CFG.get("acoes") or {"idle": {"tipo": "idle", "quadros": 8}, "andar": {"tipo": "andar", "quadros": 8}}
    stem = TRAB.get("stem") or "modelo"
    feitos = {}
    for nome_a, a in acoes.items():
        n = gerar_acao(rig, corpo, a)
        scene.frame_start, scene.frame_end = 1, n + 1          # n+1 = n de novo no 1: o laço fecha
        scene.render.fps = int(a.get("fps", 12))
        arq = os.path.join(SAIDA, f"{stem}_{nome_a}.glb")
        bpy.ops.export_scene.gltf(filepath=arq, export_format="GLB", export_animations=True,
                                  export_animation_mode="SCENE", export_cameras=False, export_lights=False,
                                  export_force_sampling=True, export_frame_step=1)
        juntar_animacoes(arq, nome_a)
        feitos[nome_a] = {"arquivo": arq, "quadros": n, "fps": int(a.get("fps", 12))}
        log("3d:", arq)
    json.dump({"acoes": feitos, "avisos": AVISOS}, open(os.path.join(SAIDA, f"{stem}_3d.json"), "w",
                                                          encoding="utf-8"), ensure_ascii=False, indent=1)
    log("ok")


def main():
    if TRAB.get("modo") == "3d":
        return main_3d()
    preparar_cena()
    rig = Rig(CFG["rig"])
    alvos = [o for o in scene.objects if o.type in ("MESH", "CURVE", "SURFACE", "META", "FONT") and not o.hide_render]
    troca, mats = aplicar_paleta(alvos)
    cam = camera_jogo(rig, alvos)
    corpo = Corpo(rig, CFG["papeis"])
    direcoes = CFG.get("direcoes") or {"sul": 0, "leste": 90, "norte": 180, "oeste": -90}
    acoes = CFG.get("acoes") or {"idle": {"tipo": "idle", "quadros": 8}, "andar": {"tipo": "andar", "quadros": 8}}
    enquadrar(bpy.data.objects["Horys | câmera do jogo"], alvos, rig, corpo, acoes, direcoes)
    limiares = {}
    if CFG.get("luz", {}).get("calibrar", True):
        limiares = calibrar_limiares(alvos, PAL["familias"], mats, direcoes, rig.ancora)
    mani = {"camera": cam, "acoes": {}, "direcoes": list(direcoes), "materiais": troca, "limiares": limiares,
            "avisos": AVISOS,
            "previa": PREVIA}
    originais = {}
    for nome_a, a in acoes.items():
        n = gerar_acao(rig, corpo, a)
        scene.frame_start, scene.frame_end = 1, n
        scene.render.fps = int(a.get("fps", 12))
        pasta = os.path.join(SAIDA, "_render", nome_a)
        render_quadros(pasta, n, direcoes, rig.ancora)
        if CFG.get("partes", True):
            for ob, m in mats_partes(rig):
                if ob.type == "MESH":
                    originais.setdefault(ob.name, [s.material for s in ob.material_slots])
                    for s in ob.material_slots:
                        s.material = m
            render_quadros(os.path.join(SAIDA, "_partes", nome_a), n, direcoes, rig.ancora)
            for nome_o, mats in originais.items():
                ob = bpy.data.objects[nome_o]
                for s, m in zip(ob.material_slots, mats):
                    s.material = m
        mani["acoes"][nome_a] = {"tipo": a["tipo"], "quadros": n, "fps": int(a.get("fps", 12))}
    scene.frame_set(1)
    json.dump(mani, open(os.path.join(SAIDA, "_render", "manifesto.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(SAIDA, "cena_horys.blend"), copy=True)
    log("ok")


main()
