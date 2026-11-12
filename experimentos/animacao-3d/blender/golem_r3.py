"""Macaco-golem (Stone Gorilla Boss) low-poly + rig + idle/walk + render pixel art, tudo por bpy.

    blender -b --factory-startup -P golem.py -- --saida ..          # constrói, anima, salva golem.blend e renderiza
    blender -b --factory-startup -P golem.py -- --saida .. --previa # só a pose neutra (validar silhueta)

Referência: ../referencia/stone_gorilla_ficha.png. O modelo é a fonte única da geometria: cada peça é rígida e
presa a um osso (pedra não deforma), as pernas usam IK com o pé plantado no chão, e a câmera ortográfica tem
escala e posição FIXAS para todas as ações (calculadas uma vez da união de todos os quadros).
"""
import argparse
import json
import math
import os
import sys

import bmesh
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

# ------------------------------------------------------------------ paleta (ficha: COLOR PALETTE)
PAL = {
    "contorno": "#1a1420",
    "fur_dark": "#2a2531", "fur": "#3c3543",
    "stone_shadow": "#5f4e42", "stone_dark": "#8e7560", "stone": "#b8a089",
    "glow": "#ff9a1a", "moss": "#6bbf3f", "smoke": "#7057a8",
}
PITCH = 32.0
FPS = 8


def rgb(h):
    h = h.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
    return (*lin, 1.0)


# ------------------------------------------------------------------ materiais chapados (toon em 3 faixas)
def mat_toon(nome, escuro, medio, claro, cortes=(0.3, 0.82)):
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    dif = nt.nodes.new("ShaderNodeBsdfDiffuse")
    dif.inputs["Color"].default_value = (1, 1, 1, 1)
    s2r = nt.nodes.new("ShaderNodeShaderToRGB")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cr.interpolation = "CONSTANT"
    cr.elements[0].position, cr.elements[0].color = 0.0, rgb(escuro)
    cr.elements[1].position, cr.elements[1].color = cortes[0], rgb(medio)
    e = cr.elements.new(cortes[1])
    e.color = rgb(claro)
    emi = nt.nodes.new("ShaderNodeEmission")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(dif.outputs[0], s2r.inputs[0])
    nt.links.new(s2r.outputs["Color"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], emi.inputs["Color"])
    nt.links.new(emi.outputs[0], out.inputs["Surface"])
    return m


def mat_plano(nome, cor):
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    emi = nt.nodes.new("ShaderNodeEmission")
    emi.inputs["Color"].default_value = rgb(cor)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(emi.outputs[0], out.inputs["Surface"])
    return m


def mat_contorno():
    m = mat_plano("contorno", PAL["contorno"])
    m.use_backface_culling = True
    return m


# ------------------------------------------------------------------ geometria
MATS = {}
PECAS = []          # (obj, osso)
CONTORNO = 0.018    # espessura do casco invertido (≈ 4 px no render 4×, 1 px no final)


def _obj(nome, bm, mat, osso, chanfro=0.0, contorno=True):
    me = bpy.data.meshes.new(nome)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(nome, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(MATS[mat])
    if nome == "cupula" or (mat == "fur" and nome.startswith(("tronco", "coxa", "braco", "canela_pelo"))):
        for f in ob.data.polygons:
            f.use_smooth = True
    if chanfro:
        b = ob.modifiers.new("chanfro", "BEVEL")
        b.width, b.segments, b.limit_method = chanfro, 1, "ANGLE"
    if contorno:
        ob.data.materials.append(MATS["contorno"])
        s = ob.modifiers.new("contorno", "SOLIDIFY")
        s.thickness, s.offset = CONTORNO, 1.0
        s.use_flip_normals = True
        s.material_offset = 1
        s.use_rim = False
    PECAS.append((ob, osso))
    return ob


def _xf(bm, loc, rot=(0, 0, 0), esc=(1, 1, 1)):
    m = (Matrix.Translation(loc) @ Matrix.Rotation(math.radians(rot[2]), 4, "Z")
         @ Matrix.Rotation(math.radians(rot[1]), 4, "Y") @ Matrix.Rotation(math.radians(rot[0]), 4, "X")
         @ Matrix.Diagonal((*esc, 1)))
    bmesh.ops.transform(bm, matrix=m, verts=bm.verts)


def caixa(nome, tam, loc, mat, osso, rot=(0, 0, 0), chanfro=0.035, **kw):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    _xf(bm, loc, rot, tam)
    return _obj(nome, bm, mat, osso, chanfro, **kw)


def bola(nome, raios, loc, mat, osso, rot=(0, 0, 0), sub=2, **kw):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1.0)
    _xf(bm, loc, rot, raios)
    return _obj(nome, bm, mat, osso, **kw)


def cone(nome, r1, r2, alt, loc, mat, osso, rot=(0, 0, 0), lados=6, **kw):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=lados, radius1=r1, radius2=r2, depth=alt)
    _xf(bm, loc, rot)
    return _obj(nome, bm, mat, osso, **kw)


def disco(nome, r, esp, loc, mat, osso, lados=8, **kw):
    """Disco virado para -Y (frente)."""
    return cone(nome, r, r, esp, loc, mat, osso, rot=(90, 0, 0), lados=lados, **kw)


def modelar():
    for s, lado in ((1, "L"), (-1, "R")):
        # pés: pata de pelo + punho de pedra (presos ao alvo de IK: ficam chapados no chão)
        caixa(f"pe_{lado}", (0.46, 0.54, 0.2), (0.58 * s, -0.08, 0.1), "fur", f"pe_ik.{lado}")
        for k, dx in enumerate((-0.13, 0.0, 0.13)):
            caixa(f"dedo{k}_{lado}", (0.12, 0.12, 0.12), (0.58 * s + dx, -0.38, 0.06), "fur", f"pe_ik.{lado}",
                  chanfro=0.02)
        caixa(f"punho_pe_{lado}", (0.5, 0.48, 0.12), (0.58 * s, 0.0, 0.25), "stone", f"pe_ik.{lado}")
        # canela: pelo + caneleira de pedra (pernas em A: inclinadas para fora)
        bola(f"canela_pelo_{lado}", (0.22, 0.22, 0.32), (0.51 * s, 0.0, 0.56), "fur", f"canela.{lado}")
        caixa(f"caneleira_{lado}", (0.34, 0.36, 0.34), (0.52 * s, -0.04, 0.52), "stone", f"canela.{lado}",
              rot=(0, 15 * s, 0))
        caixa(f"faixa_canela_{lado}", (0.37, 0.39, 0.08), (0.49 * s, -0.04, 0.7), "stone_d", f"canela.{lado}",
              rot=(0, 15 * s, 0))
        disco(f"joelho_{lado}", 0.14, 0.08, (0.43 * s, -0.2, 0.86), "stone", f"canela.{lado}")
        disco(f"joelho_runa_{lado}", 0.06, 0.04, (0.43 * s, -0.25, 0.86), "stone_d", f"canela.{lado}",
              contorno=False)
        # coxa de pelo
        bola(f"coxa_{lado}", (0.26, 0.25, 0.33), (0.36 * s, 0.0, 1.1), "fur", f"coxa.{lado}")
        for k, (z, ang) in enumerate(((2.0, 55), (1.8, 70), (1.62, 85))):
            cone(f"tufo_braco{k}_{lado}", 0.14, 0.0, 0.36, (1.15 * s, 0.02, z), "fur_l", f"braco.{lado}",
                 rot=(0, -ang * s, 0), lados=4)
        for k, z in enumerate((1.18, 0.98)):
            cone(f"tufo_coxa{k}_{lado}", 0.13, 0.0, 0.32, (0.62 * s, 0.0, z), "fur_l", f"coxa.{lado}",
                 rot=(0, -100 * s, 0), lados=4)
        cone(f"tufo_canela_{lado}", 0.12, 0.0, 0.28, (0.72 * s, 0.0, 0.42), "fur_l", f"canela.{lado}",
             rot=(0, -110 * s, 0), lados=4)
        # ombreira grande com espinhos e musgo
        caixa(f"ombreira_{lado}", (0.6, 0.62, 0.36), (0.86 * s, 0.0, 2.32), "stone", f"ombro.{lado}",
              rot=(0, -14 * s, 0), chanfro=0.06)
        caixa(f"ombreira2_{lado}", (0.5, 0.56, 0.18), (0.95 * s, 0.0, 2.08), "stone_d", f"ombro.{lado}",
              rot=(0, -24 * s, 0))
        cone(f"espinho_a_{lado}", 0.11, 0.0, 0.46, (0.74 * s, 0.05, 2.68), "stone", f"ombro.{lado}",
             rot=(0, -10 * s, 0))
        cone(f"espinho_b_{lado}", 0.09, 0.0, 0.36, (1.02 * s, 0.05, 2.58), "stone", f"ombro.{lado}",
             rot=(0, -30 * s, 0))
        for k, (dx, dy, r) in enumerate(((0.0, -0.06, 0.07), (0.08, -0.16, 0.05), (-0.07, -0.18, 0.04))):
            bola(f"musgo_omb_{k}_{lado}", (r, r * 0.8, 0.035), ((0.8 + dx) * s, dy, 2.5 - k * 0.02), "moss",
                 f"ombro.{lado}", rot=(0, -14 * s, 30 * k), sub=1, contorno=False)
        # braço: pelo, manopla de pedra com faixa e espinho, punho de pelo com nós de pedra
        bola(f"braco_{lado}", (0.23, 0.23, 0.36), (0.93 * s, 0.0, 1.86), "fur", f"braco.{lado}")
        caixa(f"manopla_{lado}", (0.48, 0.48, 0.5), (0.99 * s, -0.02, 1.26), "stone", f"antebraco.{lado}",
              chanfro=0.05)
        caixa(f"faixa_manopla_{lado}", (0.52, 0.52, 0.09), (0.99 * s, -0.02, 1.44), "stone_d",
              f"antebraco.{lado}")
        disco(f"runa_manopla_anel_{lado}", 0.13, 0.03, (0.99 * s, -0.26, 1.22), "stone_d", f"antebraco.{lado}",
              contorno=False)
        disco(f"runa_manopla_{lado}", 0.075, 0.04, (0.99 * s, -0.28, 1.22), "stone", f"antebraco.{lado}",
              contorno=False)
        cone(f"espinho_manopla_{lado}", 0.08, 0.0, 0.3, (1.16 * s, -0.02, 1.56), "stone", f"antebraco.{lado}",
             rot=(0, -35 * s, 0))
        caixa(f"punho_{lado}", (0.42, 0.44, 0.34), (1.0 * s, -0.04, 0.84), "fur", f"mao.{lado}", chanfro=0.06)
        for k, dx in enumerate((-0.15, -0.05, 0.05, 0.15)):
            caixa(f"no{k}_{lado}", (0.1, 0.12, 0.13), (1.0 * s + dx, -0.27, 0.9 - abs(dx) * 0.25), "stone",
                  f"mao.{lado}", chanfro=0.025)
        caixa(f"polegar_{lado}", (0.1, 0.14, 0.16), (0.8 * s, -0.18, 0.86), "fur", f"mao.{lado}", chanfro=0.03)

    # tronco: pelo, peitoral de pedra, medalhão com runa, cinto e tanga de pedra
    bola("tronco", (0.64, 0.44, 0.58), (0.0, 0.06, 1.86), "fur", "peito")
    bola("abdome", (0.36, 0.2, 0.3), (0.0, -0.26, 1.6), "fur_l", "peito", contorno=False)
    caixa("peitoral", (0.92, 0.24, 0.48), (0.0, -0.3, 2.1), "stone", "peito", chanfro=0.06)
    caixa("peitoral_topo", (1.0, 0.5, 0.16), (0.0, -0.08, 2.36), "stone_d", "peito")
    disco("medalhao", 0.24, 0.08, (0.0, -0.44, 2.06), "stone", "peito")
    disco("medalhao_anel", 0.16, 0.04, (0.0, -0.49, 2.06), "stone_d", "peito", contorno=False)
    disco("medalhao_runa", 0.08, 0.03, (0.0, -0.52, 2.06), "glow", "peito", contorno=False)
    bola("musgo_peito", (0.09, 0.04, 0.06), (0.32, -0.42, 2.31), "moss", "peito", sub=1, contorno=False)
    caixa("cinto", (0.98, 0.66, 0.16), (0.0, 0.0, 1.4), "stone_d", "quadril")
    caixa("tanga", (0.3, 0.08, 0.42), (0.0, -0.34, 1.14), "stone", "quadril", rot=(6, 0, 0))
    bola("fumaca", (0.44, 0.3, 0.2), (0.0, -0.08, 2.5), "smoke", "peito", sub=1, contorno=False)
    for s in (1, -1):
        cone(f"fumaca_mecha_{s}", 0.1, 0.0, 0.34, (0.42 * s, -0.12, 2.6), "smoke", "peito", rot=(0, -60 * s, 0),
             lados=4, contorno=False)

    # cabeça flutuante: crânio de pedra, órbitas, olhos acesos, mandíbula e presas
    # crânio: cúpula larga, rosto mais estreito embaixo, arcada em duas lombadas (sem viseira), órbitas fundas com o
    # brilho dentro, cavidade nasal, maçãs saindo do contorno, boca aberta e presas grandes
    bola("cupula", (0.37, 0.34, 0.3), (0.0, -0.04, 3.04), "stone", "cabeca")
    caixa("rosto", (0.5, 0.42, 0.3), (0.0, -0.12, 2.83), "stone", "cabeca", chanfro=0.08)
    for s in (1, -1):
        caixa(f"sobrancelha_{s}", (0.25, 0.12, 0.08), (0.14 * s, -0.31, 3.0), "stone", "cabeca",
              rot=(0, 14 * s, 0), chanfro=0.03)
        caixa(f"orbita_{s}", (0.19, 0.08, 0.16), (0.14 * s, -0.34, 2.89), "fur_d", "cabeca", chanfro=0.02,
              contorno=False)
        caixa(f"olho_{s}", (0.12, 0.04, 0.08), (0.14 * s, -0.37, 2.88), "glow", "cabeca", chanfro=0.0,
              contorno=False)
        caixa(f"maca_{s}", (0.17, 0.2, 0.11), (0.31 * s, -0.24, 2.79), "stone", "cabeca", rot=(0, -20 * s, 0),
              chanfro=0.03)
        cone(f"presa_{s}", 0.08, 0.0, 0.5, (0.17 * s, -0.4, 2.58), "tusk", "cabeca", rot=(180, 0, 6 * s),
             lados=5)
    cone("nariz", 0.07, 0.0, 0.06, (0.0, -0.345, 2.76), "fur_d", "cabeca", rot=(90, 0, 180), lados=3,
         contorno=False)
    caixa("boca", (0.36, 0.06, 0.13), (0.0, -0.33, 2.66), "fur_d", "cabeca", chanfro=0.0, contorno=False)
    caixa("mandibula", (0.46, 0.36, 0.12), (0.0, -0.16, 2.55), "stone_d", "cabeca", chanfro=0.03)

    # pedras flutuantes (cada uma no seu osso: movimento secundário)
    pedras = [((0.7, -0.1, 3.05), 0.13, True), ((-0.68, -0.1, 3.1), 0.12, True),
              ((0.4, 0.05, 3.4), 0.09, False), ((-0.38, 0.05, 3.44), 0.08, False)]
    for i, (p, r, runa) in enumerate(pedras):
        cone(f"pedra{i}", r * 1.5, r * 0.5, r * 2.6, p, "stone", f"pedra{i}", rot=(15 * i - 10, 25, 20 * i), lados=4)
        if runa and i == 0:
            caixa(f"pedra{i}_runa", (r * 0.8, 0.03, r * 1.0), (p[0], p[1] - r * 1.25, p[2]), "glow", f"pedra{i}",
                  chanfro=0.0, contorno=False)
    return pedras


# ------------------------------------------------------------------ rig
OSSOS_CIMA = {}   # ossos que apontam para +Z: location local (x, y, z) = mundo (x, z, -y)


def rig(pedras):
    dado = bpy.data.armatures.new("GolemRig")
    arm = bpy.data.objects.new("GolemRig", dado)
    bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    eb = dado.edit_bones

    def osso(nome, cab, cauda, pai=None, deform=True):
        b = eb.new(nome)
        b.head, b.tail = Vector(cab), Vector(cauda)
        b.roll = 0.0
        if pai:
            b.parent = eb[pai]
        b.use_deform = deform
        return b

    osso("raiz", (0, 0, 0), (0, 0, 0.3))
    osso("quadril", (0, 0, 1.35), (0, 0, 1.55), "raiz")
    osso("peito", (0, 0, 1.55), (0, 0, 2.3), "quadril")
    osso("cabeca", (0, -0.05, 2.62), (0, -0.05, 3.02), "peito")
    for i, (p, _, _) in enumerate(pedras):
        osso(f"pedra{i}", p, (p[0], p[1], p[2] + 0.2), "peito")
    for s, l in ((1, "L"), (-1, "R")):
        osso(f"ombro.{l}", (0.5 * s, 0, 2.3), (0.86 * s, 0, 2.3), "peito")
        osso(f"braco.{l}", (0.9 * s, 0, 2.2), (0.96 * s, 0, 1.55), f"ombro.{l}")
        osso(f"antebraco.{l}", (0.96 * s, 0, 1.55), (1.0 * s, -0.02, 1.0), f"braco.{l}")
        osso(f"mao.{l}", (1.0 * s, -0.02, 1.0), (1.0 * s, -0.04, 0.7), f"antebraco.{l}")
        osso(f"coxa.{l}", (0.3 * s, 0, 1.35), (0.42 * s, -0.08, 0.86), "quadril")
        osso(f"canela.{l}", (0.42 * s, -0.08, 0.86), (0.58 * s, 0, 0.25), f"coxa.{l}")
        eb[f"canela.{l}"].use_connect = True
        osso(f"pe_ik.{l}", (0.58 * s, 0, 0.25), (0.58 * s, 0, 0.55), "raiz", deform=False)
        osso(f"polo.{l}", (0.5 * s, -1.2, 0.9), (0.5 * s, -1.2, 1.2), "raiz", deform=False)
    bpy.ops.object.mode_set(mode="POSE")
    for s, l in ((1, "L"), (-1, "R")):
        ik = arm.pose.bones[f"canela.{l}"].constraints.new("IK")
        ik.target, ik.subtarget = arm, f"pe_ik.{l}"
        ik.pole_target, ik.pole_subtarget = arm, f"polo.{l}"
        ik.pole_angle = math.radians(-90)
        ik.chain_count = 2
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"
    # peças rígidas presas aos ossos (sem pele: pedra não deforma)
    for ob, nome in PECAS:
        b = dado.bones[nome]
        M = arm.matrix_world @ b.matrix_local @ Matrix.Translation((0, b.length, 0))
        ob.parent, ob.parent_type, ob.parent_bone = arm, "BONE", nome
        ob.matrix_parent_inverse = M.inverted()
    return arm


def mover(pb, dx=0.0, dy=0.0, dz=0.0):
    """Desloca um osso que aponta para +Z em coordenadas do mundo."""
    pb.location = (dx, dz, -dy)


# ------------------------------------------------------------------ animações
def chave(arm, f, nomes):
    for n in nomes:
        pb = arm.pose.bones[n]
        pb.keyframe_insert("location", frame=f)
        pb.keyframe_insert("rotation_euler", frame=f)


def zerar(arm):
    for pb in arm.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_euler = (0, 0, 0)


def nova_acao(arm, nome):
    ad = arm.animation_data or arm.animation_data_create()
    ad.action = None
    act = bpy.data.actions.new(nome)
    act.use_fake_user = True
    ad.action = act
    return act


TODOS = None


def anim_walk(arm, pedras, n=8):
    """Andar pesado em 8 quadros. Pé de apoio recua em velocidade constante (no lugar, sem deslizar em relação ao
    chão que passa); pé no ar sobe em arco. Corpo baixo no contato, alto na passagem, balança para o pé de apoio;
    braço oposto à perna; cabeça e pedras atrasam 1 quadro."""
    act = nova_acao(arm, "Golem_Walk")
    S, ALT, BOB, BAL = 0.35, 0.26, 0.11, 0.05
    nomes = [pb.name for pb in arm.pose.bones]
    for f in range(n + 1):
        zerar(arm)
        p = (f % n) / n
        for l, fase in (("L", 0.0), ("R", 0.5)):
            q = (p + fase) % 1.0
            if q < 0.5:                       # apoio: da frente (-S) para trás (+S), no chão
                y, z = -S + 2 * S * (q / 0.5), 0.0
            else:                             # balanço: de trás para a frente, em arco
                u = (q - 0.5) / 0.5
                y, z = S - 2 * S * u, ALT * math.sin(math.pi * u)
            mover(arm.pose.bones[f"pe_ik.{l}"], dy=y, dz=z)
            # braço oposto: L para trás quando a perna L está na frente
            arm.pose.bones[f"braco.{l}"].rotation_euler.x = math.radians(24) * math.cos(2 * math.pi * q)
            arm.pose.bones[f"antebraco.{l}"].rotation_euler.x = math.radians(12) * (1 + math.cos(2 * math.pi * q))
        contato = (1 + math.cos(4 * math.pi * p)) / 2          # 1 nos contatos (p = 0 e 0.5)
        mover(arm.pose.bones["quadril"], dx=BAL * math.sin(2 * math.pi * p), dz=-0.04 - BOB * contato ** 2)
        mover(arm.pose.bones["peito"], dz=-0.035 * contato ** 4)                  # squash no contato
        arm.pose.bones["quadril"].rotation_euler.y = math.radians(8) * math.sin(2 * math.pi * p)   # giro
        arm.pose.bones["peito"].rotation_euler.y = -math.radians(13) * math.sin(2 * math.pi * p)  # contragiro
        arm.pose.bones["peito"].rotation_euler.z = math.radians(3) * math.sin(2 * math.pi * p)   # inclina para o apoio
        atraso = (p - 1 / n) % 1.0
        c2 = (1 + math.cos(4 * math.pi * atraso)) / 2
        mover(arm.pose.bones["cabeca"], dz=0.05 - 0.08 * c2)
        for l in ("L", "R"):
            mover(arm.pose.bones[f"ombro.{l}"], dz=-0.05 * contato ** 2)
        for i in range(len(pedras)):
            mover(arm.pose.bones[f"pedra{i}"], dz=0.025 * math.cos(4 * math.pi * (p - (i + 2) / n)))  # seguem o quique com atraso
        chave(arm, f, nomes)
    return act


def anim_idle(arm, pedras, n=4):
    """Respiração em 4 quadros: peito e ombros sobem, cabeça atrasa, pedras flutuam fora de fase."""
    act = nova_acao(arm, "Golem_Idle")
    nomes = [pb.name for pb in arm.pose.bones]
    for f in range(n + 1):
        zerar(arm)
        p = (f % n) / n
        r = math.sin(2 * math.pi * p)
        mover(arm.pose.bones["quadril"], dz=-0.07 - 0.015 * (1 - r))
        mover(arm.pose.bones["peito"], dz=0.035 * r)
        for l in ("L", "R"):
            mover(arm.pose.bones[f"ombro.{l}"], dz=0.05 * r)
            arm.pose.bones[f"braco.{l}"].rotation_euler.x = math.radians(2) * r
        mover(arm.pose.bones["cabeca"], dz=0.035 + 0.035 * math.sin(2 * math.pi * (p - 0.25)))
        arm.pose.bones["cabeca"].rotation_euler.z = math.radians(3) * math.sin(2 * math.pi * p)
        for i in range(len(pedras)):
            mover(arm.pose.bones[f"pedra{i}"], dz=0.06 * math.sin(2 * math.pi * (p + 0.25 * i)))
        for l in ("L", "R"):
            mover(arm.pose.bones[f"pe_ik.{l}"])
        chave(arm, f, nomes)
    return act


# ------------------------------------------------------------------ render
def preparar_render(cena, res):
    r = cena.render
    motores = {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    r.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in motores else "BLENDER_EEVEE_NEXT"
    r.resolution_x = r.resolution_y = res
    r.resolution_percentage = 100
    r.film_transparent = True
    r.filter_size = 0.0
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGBA"
    r.fps = FPS
    ee = cena.eevee
    for nome, valor in (("taa_render_samples", 1), ("use_gtao", False), ("use_bloom", False),
                        ("use_shadows", True), ("use_raytracing", False), ("use_soft_shadows", False)):
        if hasattr(ee, nome):
            setattr(ee, nome, valor)
    cena.view_settings.view_transform = "Standard"
    cena.view_settings.look = "None"


def luz(cena):
    mundo = bpy.data.worlds.new("mundo")
    mundo.use_nodes = True
    bg = mundo.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (1, 1, 1, 1)
    bg.inputs["Strength"].default_value = 0.12
    cena.world = mundo
    d = bpy.data.lights.new("sol", "SUN")
    d.energy = 3.0
    d.angle = 0.0
    d.use_shadow = False  # o casco do contorno faria sombra sobre a própria peça
    sol = bpy.data.objects.new("sol", d)
    # de cima, à direita da tela e um pouco da frente
    sol.rotation_euler = (math.radians(30), math.radians(40), 0.0)
    cena.collection.objects.link(sol)
    SOL.append(sol)


SOL = []


def camera(cena):
    d = bpy.data.cameras.new("cam")
    d.type = "ORTHO"
    cam = bpy.data.objects.new("cam", d)
    cena.collection.objects.link(cam)
    cam.matrix_world = Matrix.Rotation(math.radians(90 - PITCH), 4, "X")
    cena.camera = cam
    return cam


def pontos(cena):
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for ob, _ in PECAS:
        ev = ob.evaluated_get(dg)
        pts += [ev.matrix_world @ Vector(c) for c in ev.bound_box]
    return pts


def orientar(cam, yaw):
    """Gira câmera e sol em volta do personagem: yaw 0 = frente (s), -45 = se, -90 = e."""
    cam.matrix_world = Matrix.Rotation(math.radians(yaw), 4, "Z") @ Matrix.Rotation(math.radians(90 - PITCH), 4, "X")
    if SOL:
        SOL[0].rotation_euler = (math.radians(30), math.radians(40), math.radians(yaw))


def enquadrar(cena, cam, pts, altura_px, res, escala=None):
    """Escala FIXA: a união de todos os quadros de todas as ações cabe com 'altura_px' de altura visual."""
    rot = cam.matrix_world.to_3x3()
    inv = rot.inverted()
    loc = [inv @ p for p in pts]
    xs, ys, zs = [p.x for p in loc], [p.y for p in loc], [p.z for p in loc]
    alt = max(ys) - min(ys)
    cam.data.ortho_scale = escala or alt * res / altura_px
    cx = (min(xs) + max(xs)) / 2
    # chão perto do pé da tela: base da figura em ~92% da altura
    cy = min(ys) + cam.data.ortho_scale * (0.5 - 0.08)
    cam.data.clip_start, cam.data.clip_end = 0.01, 100
    cam.matrix_world = Matrix.Translation(rot @ Vector((cx, cy, max(zs) + 10))) @ rot.to_4x4()
    return cam.data.ortho_scale


def renderizar(cena, cam, arm, acao, nome, n, pasta_base, res, sufixo, yaw=0.0):
    ad = arm.animation_data
    ad.action = acao
    if hasattr(ad, "action_slot") and getattr(acao, "slots", None) and len(acao.slots):
        ad.action_slot = acao.slots[0]
    cena.render.resolution_x = cena.render.resolution_y = res
    pasta = os.path.join(pasta_base, f"{nome}_{sufixo}")
    os.makedirs(pasta, exist_ok=True)
    arqs = []
    for f in range(n):
        cena.frame_set(f)
        arq = f"{f:04d}.png"
        cena.render.filepath = os.path.join(pasta, arq)
        bpy.ops.render.render(write_still=True)
        arqs.append(arq)
    co = world_to_camera_view(cena, cam, Vector((0, 0, 0)))
    man = {"versao": 1, "fonte": "blender", "acao": nome, "fps": FPS, "canvas": [res, res],
           "pivo": [round(co.x * res, 2), round((1 - co.y) * res, 2)],
           "camera": {"pitch": PITCH, "yaw": yaw, "ortho_scale": round(cam.data.ortho_scale, 6)},
           "loop": True, "quadros": arqs}
    with open(os.path.join(pasta, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(man, fh, ensure_ascii=False, indent=2)
    print(f"[golem] {nome}_{sufixo}: {n} quadros")


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", required=True)
    ap.add_argument("--previa", action="store_true")
    ap.add_argument("--altura", type=float, default=198)
    a = ap.parse_args(argv)
    base = os.path.abspath(a.saida)
    cena = bpy.context.scene
    for ob in list(cena.objects):
        bpy.data.objects.remove(ob)
    MATS.update({
        "contorno": mat_contorno(),
        "fur": mat_toon("fur", PAL["fur_dark"], PAL["fur"], PAL["fur"], (0.2, 0.9)),
        "fur_l": mat_plano("fur_l", PAL["fur"]),
        "fur_d": mat_plano("fur_d", PAL["contorno"]),
        "stone": mat_toon("stone", PAL["stone_shadow"], PAL["stone_dark"], PAL["stone"]),
        "stone_d": mat_toon("stone_d", PAL["stone_shadow"], PAL["stone_shadow"], PAL["stone_dark"]),
        "tusk": mat_toon("tusk", PAL["stone_dark"], PAL["stone"], PAL["stone"], (0.15, 0.9)),
        "glow": mat_plano("glow", PAL["glow"]),
        "moss": mat_plano("moss", PAL["moss"]),
        "smoke": mat_plano("smoke", PAL["smoke"]),
    })
    pedras = modelar()
    arm = rig(pedras)
    preparar_render(cena, 1024)
    luz(cena)
    cam = camera(cena)
    if a.previa:
        cena.frame_set(0)
        enquadrar(cena, cam, pontos(cena), a.altura, 256)
        os.makedirs(os.path.join(base, "previews"), exist_ok=True)
        for res in (256, 1024):
            cena.render.resolution_x = cena.render.resolution_y = res
            cena.render.filepath = os.path.join(base, "previews", f"neutra_{res}.png")
            bpy.ops.render.render(write_still=True)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(base, "blender", "golem.blend"))
        return
    walk = anim_walk(arm, pedras)
    idle = anim_idle(arm, pedras)
    # escala fixa: união de TODOS os quadros das duas ações, medida de frente; as outras direções usam a mesma
    pts = []
    for act, n in ((walk, 8), (idle, 4)):
        arm.animation_data.action = act
        if hasattr(arm.animation_data, "action_slot") and len(act.slots):
            arm.animation_data.action_slot = act.slots[0]
        for f in range(n):
            cena.frame_set(f)
            pts += pontos(cena)
    orientar(cam, 0.0)
    escala = enquadrar(cena, cam, pts, a.altura, 256)
    cena.frame_start, cena.frame_end = 0, 7
    pasta = os.path.join(base, "renders")
    for dire, yaw in (("s", 0.0), ("se", -45.0), ("e", -90.0)):
        orientar(cam, yaw)
        enquadrar(cena, cam, pts, a.altura, 256, escala)
        for act, nome, n in ((idle, "idle", 4), (walk, "walk", 8)):
            for res, suf in ((256, "bruto256"), (1024, "x4")):
                renderizar(cena, cam, arm, act, f"{nome}_{dire}", n, pasta, res, suf, yaw)
    arm.animation_data.action = walk
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(base, "blender", "golem.blend"))
    print("[golem] golem.blend salvo")


main()
