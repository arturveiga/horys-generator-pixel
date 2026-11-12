"""Macaco-golem v2: geometria orgânica (sem pixelização). Só a malha e três renders para aprovação.

    blender -b --factory-startup -P golem_v2.py -- --saida ..

Técnicas (todas nativas e gratuitas do Blender):
- corpo de gorila: esqueleto de vértices com raio → modificador Skin → Subdivision Surface → Displace (volume do pelo);
- crânio: formas suaves unidas e escavadas por Boolean (órbitas fundas, cavidade nasal, boca), presas curvas
  (Simple Deform);
- armadura: placas de pedra irregulares (malha deformada por ruído e facetada por Decimate), espinhos;
- entalhes e runas: curvas em espiral com bevel; fumaça: metaballs.
Proporções tiradas da vista frontal da ficha (referencia/stone_gorilla_ficha.png), personagem virado para -Y.
"""
import argparse
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector, noise

PAL = {"stone": "#b8a089", "stone_d": "#8e7560", "stone_s": "#5f4e42", "fur": "#3c3543", "fur_d": "#2a2531",
       "glow": "#ff9a1a", "moss": "#6bbf3f", "smoke": "#7057a8", "bone": "#d8c8a8"}


def lin(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple((x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4) for x in c) + (1.0,)


MATS = {}


def materiais():
    def pbr(nome, cor, rough=0.85, emissao=0.0):
        m = bpy.data.materials.new(nome)
        m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = lin(cor)
        b.inputs["Roughness"].default_value = rough
        if emissao:
            b.inputs["Emission Color"].default_value = lin(cor)
            b.inputs["Emission Strength"].default_value = emissao
        MATS[nome] = m
    pbr("stone", PAL["stone"])
    pbr("stone_d", PAL["stone_d"])
    pbr("fur", PAL["fur"], 1.0)
    pbr("fur_d", PAL["fur_d"], 1.0)
    pbr("bone", PAL["bone"], 0.6)
    pbr("glow", PAL["glow"], 0.4, 1.0)
    pbr("moss", PAL["moss"], 1.0)
    pbr("smoke", PAL["smoke"], 1.0, 1.5)
    pbr("cavity", "#120c18", 1.0)


def link(ob, mat=None, liso=False):
    bpy.context.scene.collection.objects.link(ob)
    if mat:
        ob.data.materials.append(MATS[mat])
    if liso and ob.type == "MESH":
        for p in ob.data.polygons:
            p.use_smooth = True
    return ob


def mesh_de_bm(nome, bm):
    me = bpy.data.meshes.new(nome)
    bm.to_mesh(me)
    bm.free()
    return bpy.data.objects.new(nome, me)


def xf(bm, loc=(0, 0, 0), rot=(0, 0, 0), esc=(1, 1, 1)):
    m = (Matrix.Translation(loc) @ Matrix.Rotation(math.radians(rot[2]), 4, "Z")
         @ Matrix.Rotation(math.radians(rot[1]), 4, "Y") @ Matrix.Rotation(math.radians(rot[0]), 4, "X")
         @ Matrix.Diagonal((*esc, 1)))
    bmesh.ops.transform(bm, matrix=m, verts=bm.verts)


def ruido(bm, amp, freq, semente):
    off = Vector((semente * 7.31, semente * 3.17, semente * 5.03))
    for v in bm.verts:
        v.co += noise.noise_vector(v.co * freq + off) * amp


# ------------------------------------------------------------------ corpo de gorila (Skin + Subsurf)
def corpo():
    N = {}   # nome: (posição, raio)

    def no(nome, pos, r):
        N[nome] = (Vector(pos), r)

    no("pelve", (0, 0.05, 1.6), 0.46)
    no("barriga", (0, 0.0, 1.95), 0.5)
    no("peito", (0, -0.02, 2.3), 0.6)
    no("dorso", (0, 0.12, 2.55), 0.5)          # corcunda atrás dos ombros
    no("pescoco", (0, -0.15, 2.65), 0.26)
    E = [("pelve", "barriga"), ("barriga", "peito"), ("peito", "dorso"), ("dorso", "pescoco")]
    for s, l in ((1, "L"), (-1, "R")):
        no(f"ombro{l}", (0.62 * s, 0.05, 2.55), 0.42)
        no(f"delt{l}", (0.92 * s, 0.05, 2.45), 0.4)
        no(f"biceps{l}", (1.1 * s, 0.02, 2.12), 0.33)
        no(f"cotovelo{l}", (1.2 * s, 0.05, 1.86), 0.3)
        no(f"antebraco{l}", (1.27 * s, -0.02, 1.55), 0.34)
        no(f"pulso{l}", (1.27 * s, -0.06, 1.25), 0.26)
        no(f"palma{l}", (1.25 * s, -0.12, 1.05), 0.36)
        E += [("dorso", f"ombro{l}"), (f"ombro{l}", f"delt{l}"), (f"delt{l}", f"biceps{l}"),
              (f"biceps{l}", f"cotovelo{l}"), (f"cotovelo{l}", f"antebraco{l}"), (f"antebraco{l}", f"pulso{l}"),
              (f"pulso{l}", f"palma{l}")]
        for k, dx in enumerate((-0.19, -0.065, 0.065, 0.19)):          # 4 dedos grossos, dobrados (punho)
            no(f"nodedo{k}{l}", (1.25 * s + dx, -0.36, 1.0), 0.115)
            no(f"dedo{k}{l}", (1.25 * s + dx * 0.95, -0.36, 0.8), 0.105)
            E += [(f"palma{l}", f"nodedo{k}{l}"), (f"nodedo{k}{l}", f"dedo{k}{l}")]
        no(f"polegar{l}", (1.02 * s, -0.3, 1.0), 0.11)
        E += [(f"palma{l}", f"polegar{l}")]
        no(f"quadril{l}", (0.36 * s, 0.03, 1.5), 0.36)
        no(f"coxa{l}", (0.5 * s, -0.02, 1.2), 0.4)
        no(f"joelho{l}", (0.58 * s, -0.06, 0.92), 0.32)
        no(f"canela{l}", (0.62 * s, 0.0, 0.6), 0.32)
        no(f"tornozelo{l}", (0.64 * s, 0.02, 0.3), 0.27)
        no(f"pe{l}", (0.66 * s, -0.12, 0.16), 0.3)
        E += [("pelve", f"quadril{l}"), (f"quadril{l}", f"coxa{l}"), (f"coxa{l}", f"joelho{l}"),
              (f"joelho{l}", f"canela{l}"), (f"canela{l}", f"tornozelo{l}"), (f"tornozelo{l}", f"pe{l}")]
        for k, dx in enumerate((-0.14, 0.0, 0.14)):                      # dedos do pé
            no(f"artelho{k}{l}", (0.66 * s + dx * 1.2, -0.46, 0.1), 0.115)
            E += [(f"pe{l}", f"artelho{k}{l}")]
    nomes = list(N)
    idx = {n: i for i, n in enumerate(nomes)}
    me = bpy.data.meshes.new("corpo")
    me.from_pydata([N[n][0] for n in nomes], [(idx[a], idx[b]) for a, b in E], [])
    ob = link(bpy.data.objects.new("corpo", me), "fur")
    sk = ob.modifiers.new("skin", "SKIN")
    sk.use_smooth_shade = True
    sk.branch_smoothing = 0.6
    for n in nomes:
        d = me.skin_vertices[0].data[idx[n]]
        r = N[n][1]
        d.radius = (r, r)
    me.skin_vertices[0].data[idx["pelve"]].use_root = True
    sub = ob.modifiers.new("sub", "SUBSURF")
    sub.levels = sub.render_levels = 2
    tex = bpy.data.textures.new("pelo", "CLOUDS")
    tex.noise_scale = 0.13
    tex.noise_depth = 2
    dp = ob.modifiers.new("pelo", "DISPLACE")
    dp.texture, dp.strength, dp.mid_level = tex, 0.11, 0.5
    sub2 = ob.modifiers.new("sub2", "SUBSURF")
    sub2.levels = sub2.render_levels = 1
    return ob


def tufos():
    """Tufos de pelo nas bordas de fora de braços, coxas e costas: cones curvos e grossos."""
    pontos = []
    for s in (1, -1):
        pontos += [((1.38 * s, 0.05, 2.15), (0, -70 * s, 0)), ((1.45 * s, 0.05, 1.9), (0, -80 * s, 0)),
                   ((0.9 * s, 0.1, 1.15), (0, -95 * s, 0)), ((0.95 * s, 0.05, 0.85), (0, -100 * s, 0)),
                   ((0.85 * s, 0.05, 0.45), (0, -105 * s, 0)), ((0.5 * s, 0.45, 2.5), (-60, -30 * s, 0)),
                   ((0.62 * s, -0.42, 1.85), (90, 0, 15 * s))]
    for i, (p, rot) in enumerate(pontos):
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.12, radius2=0.0, depth=0.32)
        xf(bm, (0, 0, -0.16))
        ruido(bm, 0.02, 4, i)
        xf(bm, p, rot)
        link(mesh_de_bm(f"tufo{i}", bm), "fur", liso=True)


# ------------------------------------------------------------------ pedra irregular
def pedra(nome, loc, esc, rot=(0, 0, 0), semente=0, mat="stone", forma="caixa", facetas=0.28, amp=0.06):
    bm = bmesh.new()
    if forma == "caixa":
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=3, use_grid_fill=True)
    elif forma == "tubo":
        bmesh.ops.create_cone(bm, cap_ends=True, segments=14, radius1=0.5, radius2=0.5, depth=1.0)
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=2, use_grid_fill=True)
    else:
        bmesh.ops.create_icosphere(bm, subdivisions=3, radius=0.5)
    xf(bm, esc=esc)
    ruido(bm, amp, 3.0, semente)
    xf(bm, loc, rot)
    ob = link(mesh_de_bm(nome, bm), mat)
    bv = ob.modifiers.new("bev", "BEVEL")
    bv.width, bv.segments, bv.limit_method = 0.02, 1, "ANGLE"
    dc = ob.modifiers.new("facetas", "DECIMATE")
    dc.ratio = facetas
    return ob


def espinho(nome, base, direcao, comp, raio, semente):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=7, radius1=raio, radius2=raio * 0.08, depth=comp)
    xf(bm, (0, 0, comp / 2))
    ruido(bm, raio * 0.15, 5, semente)
    d = Vector(direcao).normalized()
    q = Vector((0, 0, 1)).rotation_difference(d)
    bmesh.ops.transform(bm, matrix=Matrix.Translation(base) @ q.to_matrix().to_4x4(), verts=bm.verts)
    return link(mesh_de_bm(nome, bm), "stone")


def espiral(nome, centro, normal, r_ext, voltas=3.0, esp=0.018, mat="stone_d"):
    """Espiral entalhada (curva com bevel) sobre uma superfície virada para 'normal'."""
    cu = bpy.data.curves.new(nome, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = esp
    cu.bevel_resolution = 1
    sp = cu.splines.new("POLY")
    n = int(voltas * 40)
    sp.points.add(n - 1)
    d = Vector(normal).normalized()
    q = Vector((0, 0, 1)).rotation_difference(d).to_matrix()
    for i in range(n):
        t = i / (n - 1)
        a = t * voltas * 2 * math.pi
        r = r_ext * (0.12 + 0.88 * t)
        p = Vector(centro) + q @ Vector((r * math.cos(a), r * math.sin(a), 0.0))
        sp.points[i].co = (*p, 1.0)
    return link(bpy.data.objects.new(nome, cu), mat)


def armadura():
    # peito: duas placas peitorais grandes + gola + placas da barriga, medalhão no centro
    for s in (1, -1):
        pedra(f"peitoral{s}", (0.34 * s, -0.5, 2.38), (0.58, 0.22, 0.46), (8, 0, -12 * s), 1 + s)
        pedra(f"gola{s}", (0.26 * s, -0.3, 2.66), (0.46, 0.34, 0.16), (-10, 0, -8 * s), 3 + s)
        pedra(f"costela{s}", (0.3 * s, -0.48, 2.02), (0.36, 0.14, 0.2), (12, 0, -10 * s), 5 + s, "stone_d")
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=0.26, radius2=0.24, depth=0.12)
    ruido(bm, 0.008, 6, 9)
    xf(bm, (0, -0.64, 2.3), (90, 0, 0))
    link(mesh_de_bm("medalhao", bm), "stone")
    espiral("medalhao_espiral", (0, -0.705, 2.3), (0, -1, 0), 0.21, 3.2)
    # ombreiras: três placas sobrepostas por lado + espinhos + musgo
    for s in (1, -1):
        pedra(f"omb_a{s}", (0.95 * s, -0.02, 2.82), (0.72, 0.8, 0.3), (0, -18 * s, 0), 11 + s, facetas=0.3)
        pedra(f"omb_b{s}", (1.12 * s, -0.02, 2.58), (0.6, 0.78, 0.26), (0, -38 * s, 0), 13 + s, "stone_d")
        pedra(f"omb_c{s}", (1.25 * s, 0.0, 2.36), (0.42, 0.7, 0.22), (0, -58 * s, 0), 15 + s)
        espinho(f"esp_a{s}", Vector((0.82 * s, 0.05, 2.92)), (0.25 * s, 0.1, 1), 0.62, 0.13, 17 + s)
        espinho(f"esp_b{s}", Vector((1.2 * s, 0.05, 2.78)), (0.7 * s, 0.1, 1), 0.48, 0.11, 19 + s)
        espinho(f"esp_c{s}", Vector((0.62 * s, 0.25, 2.85)), (0.1 * s, 0.4, 1), 0.36, 0.09, 21 + s)
        pedra(f"musgo_omb{s}", (0.98 * s, -0.25, 2.98), (0.3, 0.22, 0.06), (0, -18 * s, 20), 23 + s, "moss",
              forma="bola", facetas=0.5, amp=0.04)
    # manoplas: tubo de pedra em volta do antebraço, faixa, espiral de fora, espinhos
    for s in (1, -1):
        pedra(f"manopla{s}", (1.27 * s, -0.03, 1.55), (0.66, 0.62, 0.6), (0, 0, 0), 31 + s, forma="tubo",
              facetas=0.35, amp=0.04)
        pedra(f"faixa_manopla{s}", (1.27 * s, -0.03, 1.86), (0.72, 0.68, 0.1), (0, 0, 0), 33 + s, "stone_d",
              forma="tubo", facetas=0.4, amp=0.02)
        espiral(f"espiral_manopla{s}", (1.27 * s, -0.36, 1.52), (0.2 * s, -1, 0), 0.17, 2.6)
        espinho(f"esp_man{s}", Vector((1.55 * s, 0.0, 1.75)), (1 * s, 0, 0.6), 0.42, 0.1, 35 + s)
        espinho(f"esp_man2{s}", Vector((1.5 * s, 0.1, 1.45)), (1 * s, 0.2, 0.3), 0.3, 0.08, 37 + s)
        # nós de pedra nos dedos
        pedra(f"nos{s}", (1.25 * s, -0.47, 1.05), (0.54, 0.12, 0.13), (0, 0, 0), 39 + s, "stone_d", facetas=0.4,
              amp=0.015)
    # cinto, tanga de pedra, joelheiras com espiral, caneleiras e faixas dos pés
    for k in range(8):
        a = math.radians(-90 + k * 45)
        p = (0.55 * math.cos(a), 0.05 + 0.45 * math.sin(a), 1.72)
        pedra(f"cinto{k}", p, (0.36, 0.2, 0.2), (0, 0, math.degrees(a) + 90), 41 + k, "stone_d", facetas=0.35,
              amp=0.03)
    pedra("tanga", (0, -0.52, 1.38), (0.34, 0.1, 0.56), (8, 0, 0), 51, facetas=0.35, amp=0.03)
    for k, (dx, dz) in enumerate(((-0.24, 1.48), (0.24, 1.48), (-0.12, 1.32), (0.12, 1.32))):
        pedra(f"saiote{k}", (dx, -0.48, dz), (0.2, 0.08, 0.3), (6, 0, 8 * (1 if dx > 0 else -1)), 53 + k,
              facetas=0.4, amp=0.02)
    for s in (1, -1):
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=18, radius1=0.21, radius2=0.19, depth=0.12)
        ruido(bm, 0.01, 6, 61 + s)
        xf(bm, (0.6 * s, -0.36, 0.95), (80, 0, 0))
        link(mesh_de_bm(f"joelheira{s}", bm), "stone")
        espiral(f"espiral_joelho{s}", (0.6 * s, -0.42, 0.96), (0, -1, 0.15), 0.16, 2.4)
        pedra(f"caneleira{s}", (0.63 * s, -0.02, 0.58), (0.58, 0.56, 0.32), (0, 0, 0), 63 + s, forma="tubo",
              facetas=0.35, amp=0.035)
        pedra(f"faixa_pe{s}", (0.65 * s, -0.04, 0.32), (0.62, 0.62, 0.12), (0, 0, 0), 65 + s, "stone_d",
              forma="tubo", facetas=0.4, amp=0.02)
        pedra(f"musgo_can{s}", (0.6 * s, -0.3, 0.72), (0.18, 0.06, 0.08), (0, 0, 0), 67 + s, "moss",
              forma="bola", facetas=0.5, amp=0.03)


# ------------------------------------------------------------------ crânio flutuante, presas, fumaça
def cranio():
    antes = set(bpy.data.objects)
    _cranio()
    C = Vector((0, -0.34, 3.0))
    pai = bpy.data.objects.new("cabeca", None)
    pai.location = C
    bpy.context.scene.collection.objects.link(pai)
    for ob in set(bpy.data.objects) - antes - {pai}:
        if ob.name == "fumaca":
            continue
        mw = ob.matrix_world.copy()
        ob.parent = pai
        ob.matrix_parent_inverse = Matrix.Translation(C).inverted()
    pai.scale = (1.3, 1.3, 1.3)
    pai.location = C + Vector((0, -0.04, 0.16))


def _gauss(d, r):
    return math.exp(-(d / r) ** 2)


def _cranio():
    """Crânio de gorila esculpido por função: esfera densa deformada vértice a vértice (crista e cúpula largas,
    arcada saliente, órbitas fundas, cavidade nasal triangular, maçãs largas, focinho projetado)."""
    C = Vector((0, -0.34, 3.0))
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=5, radius=1.0)
    olhos = [Vector((0.135 * s, -0.33, -0.03)) for s in (1, -1)]
    for v in bm.verts:
        n = v.co.normalized()
        p = Vector((n.x * 0.34, n.y * 0.33, n.z * (0.25 if n.z > 0 else 0.31)))
        frente = max(0.0, -n.y)
        baixo = max(0.0, -n.z)
        # focinho: a metade de baixo da frente avança e alarga
        p.y -= 0.16 * frente ** 1.5 * (baixo ** 0.8 if n.z < 0.05 else 0.0)
        p.x *= 1.0 + 0.22 * baixo * frente
        # arcada: faixa saliente logo acima dos olhos
        z0 = 0.02 + 0.22 * min(abs(n.x), 0.45)          # arcada em V: desce para o meio (cara de raiva)
        p.y -= 0.12 * frente ** 2 * _gauss(n.z - z0, 0.1)
        p.z -= 0.04 * frente ** 2 * _gauss(n.z - z0, 0.1) * (1 - min(abs(n.x) / 0.45, 1))
        # maçãs: saliências para os lados, na altura de baixo dos olhos
        for s in (1, -1):
            d = (Vector((n.x, n.y, n.z)) - Vector((0.72 * s, -0.55, -0.3)).normalized()).length
            p += Vector((s * 0.06, -0.03, 0)) * _gauss(d, 0.32)
        # órbitas: afundam para dentro (direção da normal)
        for o in olhos:
            d = (p - o).length
            p -= n * 0.11 * _gauss(d, 0.075)
        # cavidade nasal: triângulo invertido (mais largo em cima)
        nz = p.z + 0.15
        if -0.07 < nz < 0.05 and frente > 0.6:
            larg = 0.05 * (nz + 0.07) / 0.12 + 0.012
            if abs(p.x) < larg:
                p -= n * 0.07 * (1 - abs(p.x) / larg)
        # base achatada (o crânio termina na arcada dentária)
        if p.z < -0.22:
            p.z = -0.22 + (p.z + 0.22) * 0.25
        # crista sagital suave
        p.z += 0.03 * _gauss(n.x, 0.18) * max(0.0, n.z) * max(0.0, n.y + 0.3)
        v.co = C + p
    ob = link(mesh_de_bm("cranio", bm), "stone", liso=True)
    # cavidades escuras no fundo das órbitas, olhos acesos dentro
    def bola(nome, loc, esc, mat):
        b = bmesh.new()
        bmesh.ops.create_icosphere(b, subdivisions=3, radius=1.0)
        xf(b, loc, esc=esc)
        return link(mesh_de_bm(nome, b), mat, liso=True)
    for s, o in zip((1, -1), olhos):
        bola(f"orbita{s}", C + o + Vector((0, 0.035, 0)), (0.07, 0.03, 0.06), "cavity")
        bola(f"olho{s}", C + o + Vector((0, 0.015, -0.005)), (0.045, 0.02, 0.032), "glow")
    bola("nariz_fundo", C + Vector((0, -0.36, -0.15)), (0.03, 0.02, 0.045), "cavity")
    # espiral entalhada na cúpula, acompanhando a superfície
    espiral("espiral_cranio", C + Vector((0, -0.1, 0.225)), (0, -0.4, 1), 0.12, 2.5, 0.011)
    # boca: fundo escuro, fileira de dentes de cima, mandíbula aberta com dentes de baixo
    for k, dx in enumerate((-0.1, -0.035, 0.035, 0.1)):
        b = bmesh.new()
        bmesh.ops.create_cone(b, cap_ends=True, segments=6, radius1=0.026, radius2=0.006, depth=0.08)
        xf(b, C + Vector((dx, -0.43 + abs(dx) * 0.25, -0.25)), (180, 0, 0))
        link(mesh_de_bm(f"dente{k}", b), "bone", liso=True)
    b = bmesh.new()
    bmesh.ops.create_icosphere(b, subdivisions=4, radius=1.0)
    for v in b.verts:
        n = v.co.normalized()
        v.co = Vector((n.x * 0.24 * (1 + 0.25 * max(0, -n.y)), n.y * 0.2, n.z * 0.07))
    xf(b, C + Vector((0, -0.2, -0.43)), (14, 0, 0))
    link(mesh_de_bm("mandibula", b), "stone_d", liso=True)
    for k, dx in enumerate((-0.07, 0.07)):
        bb = bmesh.new()
        bmesh.ops.create_cone(bb, cap_ends=True, segments=6, radius1=0.022, radius2=0.005, depth=0.06)
        xf(bb, C + Vector((dx, -0.38, -0.39)))
        link(mesh_de_bm(f"dente_baixo{k}", bb), "bone", liso=True)
    # presas grandes e curvas saindo da arcada de cima
    for s in (1, -1):
        b = bmesh.new()
        bmesh.ops.create_cone(b, cap_ends=True, segments=10, radius1=0.06, radius2=0.004, depth=0.46)
        bmesh.ops.subdivide_edges(b, edges=b.edges[:], cuts=6)
        xf(b, (0, 0, -0.23))
        pr = link(mesh_de_bm(f"presa{s}", b), "bone", liso=True)
        sd = pr.modifiers.new("curva", "SIMPLE_DEFORM")
        sd.deform_method, sd.angle, sd.deform_axis = "BEND", math.radians(-45), "X"
        pr.location = C + Vector((0.16 * s, -0.4, -0.21))
        pr.rotation_euler = (math.radians(-6), math.radians(-10 * s), 0)


def fumaca():
    # fumaça roxa: metaballs em volta do pescoço, saindo para os lados
    mb = bpy.data.metaballs.new("fumaca")
    mb.resolution = mb.render_resolution = 0.05
    mb.threshold = 0.5
    pts = [((0, -0.2, 2.62), 0.26), ((0.2, -0.28, 2.66), 0.17), ((-0.2, -0.26, 2.68), 0.17),
           ((0.36, -0.3, 2.78), 0.12), ((-0.4, -0.28, 2.82), 0.11), ((0.48, -0.25, 2.93), 0.08),
           ((-0.52, -0.22, 2.98), 0.07), ((0, -0.38, 2.7), 0.15)]
    for p, r in pts:
        e = mb.elements.new()
        e.co, e.radius = p, r * 1.7
    link(bpy.data.objects.new("fumaca", mb), "smoke")


def pedras_flutuantes():
    lugares = [((0.62, -0.3, 3.35), 0.15, True), ((-0.66, -0.25, 3.3), 0.14, True), ((0.38, -0.2, 3.62), 0.09, False),
               ((-0.4, -0.18, 3.66), 0.08, False), ((0.92, -0.2, 3.1), 0.08, False), ((-0.95, -0.15, 3.05), 0.1, True)]
    for i, (p, r, runa) in enumerate(lugares):
        pedra(f"flutua{i}", p, (r * 2.0, r * 1.4, r * 2.4), (15 * i, 30, 20 * i), 81 + i, forma="bola",
              facetas=0.12, amp=r * 0.35)
        if runa:
            espiral(f"runa{i}", (p[0], p[1] - r * 0.72, p[2]), (0, -1, 0), r * 0.55, 2.0, 0.012, "glow")


# ------------------------------------------------------------------ cena e renders
def cena_render(res):
    sc = bpy.context.scene
    motores = {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    sc.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in motores else "BLENDER_EEVEE_NEXT"
    sc.render.resolution_x = sc.render.resolution_y = res
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "Standard"
    w = bpy.data.worlds.new("mundo")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = lin("#c9c6c2")
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.35
    sc.world = w
    for nome, en, rot in (("chave", 3.2, (42, 0, -35)), ("recorte", 2.5, (60, 0, 150)), ("preenche", 0.8, (70, 0, 60))):
        d = bpy.data.lights.new(nome, "SUN")
        d.energy = en
        d.angle = math.radians(8)
        o = bpy.data.objects.new(nome, d)
        o.rotation_euler = [math.radians(a) for a in rot]
        sc.collection.objects.link(o)
    if hasattr(sc.eevee, "use_gtao"):
        sc.eevee.use_gtao = True
    d = bpy.data.cameras.new("cam")
    d.type = "ORTHO"
    cam = bpy.data.objects.new("cam", d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    return sc, cam


def vista(sc, cam, yaw, pitch, arq):
    rot = Matrix.Rotation(math.radians(yaw), 4, "Z") @ Matrix.Rotation(math.radians(90 - pitch), 4, "X")
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for o in sc.objects:
        if o.type in ("MESH", "CURVE", "META") and not o.hide_render:
            ev = o.evaluated_get(dg)
            pts += [ev.matrix_world @ Vector(c) for c in ev.bound_box]
    inv = rot.to_3x3().inverted()
    loc = [inv @ p for p in pts]
    xs, ys, zs = [p.x for p in loc], [p.y for p in loc], [p.z for p in loc]
    cam.data.ortho_scale = max(max(xs) - min(xs), max(ys) - min(ys)) * 1.08
    cam.data.clip_end = 100
    c = Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, max(zs) + 10))
    cam.matrix_world = Matrix.Translation(rot.to_3x3() @ c) @ rot
    sc.render.filepath = arq
    bpy.ops.render.render(write_still=True)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", required=True)
    ap.add_argument("--res", type=int, default=1200)
    a = ap.parse_args(argv)
    base = os.path.abspath(a.saida)
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    materiais()
    corpo()
    # tufos de cone saíram (liam como espinhos pretos); o volume do pelo vem do Displace
    armadura()
    cranio()
    fumaca()
    pedras_flutuantes()
    sc, cam = cena_render(a.res)
    pasta = os.path.join(base, "previews", "v2")
    os.makedirs(pasta, exist_ok=True)
    for nome, yaw, pitch in (("frente", 0, 6), ("lateral", -90, 6), ("tres_quartos", -35, 14)):
        vista(sc, cam, yaw, pitch, os.path.join(pasta, f"{nome}.png"))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(base, "blender", "golem_v2.blend"))
    print("[v2] ok")


main()
