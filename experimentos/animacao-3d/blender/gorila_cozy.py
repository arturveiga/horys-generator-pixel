"""Gorila cozy: modelo em blocos rígidos (peças presas a empties), idle/andar/ataque e render chapado em toon de 3 tons.

    blender -b --factory-startup -P gorila_cozy.py -- --saida <pasta>

Saída: <saida>/<acao>_<dir>/NNNN.png (fundo transparente, 96x96). Direções: s (frente), e (lado), n (costas).
"""
import argparse
import math
import os
import sys

import bpy
from mathutils import Vector

FPS = 8
RES = 120
PITCH = 32.0


def lin(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple((x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4) for x in c) + (1.0,)


RAMPAS = {
    "pelo": ("#4c1c48", "#70346c", "#96588c"),
    "pedra": ("#a06c88", "#c89ca0", "#f0ccb8"),
    "cinto": ("#5c3424", "#8a5332", "#8a5332"),
    "fivela": ("#a06a18", "#e6b02a", "#e6b02a"),
    "olho": ("#78f400", "#78f400", "#78f400"),
    "escuro": ("#2a1f2d", "#2a1f2d", "#2a1f2d"),
    "dente": ("#c89ca0", "#f0ccb8", "#f0ccb8"),
}


def material(nome):
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    dif = nt.nodes.new("ShaderNodeBsdfDiffuse")
    s2r = nt.nodes.new("ShaderNodeShaderToRGB")
    bw = nt.nodes.new("ShaderNodeRGBToBW")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    emi = nt.nodes.new("ShaderNodeEmission")
    ramp.color_ramp.interpolation = "CONSTANT"
    a, b, c = RAMPAS[nome]
    el = ramp.color_ramp.elements
    el[0].position, el[0].color = 0.0, lin(a)
    el[1].position, el[1].color = 0.18, lin(b)
    e3 = el.new(0.55)
    e3.color = lin(c)
    nt.links.new(dif.outputs[0], s2r.inputs[0])
    nt.links.new(s2r.outputs[0], bw.inputs[0])
    nt.links.new(bw.outputs[0], ramp.inputs[0])
    nt.links.new(ramp.outputs[0], emi.inputs[0])
    nt.links.new(emi.outputs[0], out.inputs[0])
    return m


MATS = {}


def peca(tipo, nome, loc, esc, mat, pai, rot=(0, 0, 0)):
    if tipo == "cubo":
        bpy.ops.mesh.primitive_cube_add(size=1)
        ob = bpy.context.object
        bev = ob.modifiers.new("b", "BEVEL")
        bev.width, bev.segments = 0.12, 2
    elif tipo == "esfera":
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=10, radius=0.5)
        ob = bpy.context.object
    else:
        bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.5, depth=1)
        ob = bpy.context.object
    ob.name = nome
    ob.scale = esc
    ob.rotation_euler = rot
    ob.location = loc
    ob.data.materials.append(MATS[mat])
    bpy.ops.object.shade_smooth() if tipo == "esfera" else None
    ob.parent = pai
    ob.matrix_parent_inverse = pai.matrix_world.inverted()
    return ob


def junta(nome, loc, pai=None):
    e = bpy.data.objects.new(nome, None)
    bpy.context.collection.objects.link(e)
    e.location = loc
    if pai:
        e.parent = pai
        e.location = Vector(loc) - pai.matrix_world.translation
    bpy.context.view_layer.update()
    return e


def montar():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    for k in RAMPAS:
        MATS[k] = material(k)
    J = {}
    J["raiz"] = junta("raiz", (0, 0, 0))
    J["quadril"] = junta("quadril", (0, 0, 0.62), J["raiz"])
    J["tronco"] = junta("tronco", (0, 0, 0.75), J["quadril"])
    J["cabeca"] = junta("cabeca", (0, -0.12, 1.55), J["tronco"])
    for lado, s in (("E", 1), ("D", -1)):
        J["ombro" + lado] = junta("ombro" + lado, (0.72 * s, 0, 1.42), J["tronco"])
        J["cotovelo" + lado] = junta("cotovelo" + lado, (0.86 * s, -0.05, 0.92), J["ombro" + lado])
        J["perna" + lado] = junta("perna" + lado, (0.3 * s, 0, 0.6), J["quadril"])
    bpy.context.view_layer.update()
    # tronco: barril de pelo inclinado para a frente (corcunda)
    peca("esfera", "torso", (0, 0.02, 1.12), (1.3, 0.9, 1.0), "pelo", J["tronco"], (math.radians(-12), 0, 0))
    peca("esfera", "peito", (0, -0.34, 1.12), (0.8, 0.3, 0.55), "pelo", J["tronco"])
    peca("cilindro", "cinto", (0, 0, 0.72), (0.98, 0.72, 0.12), "cinto", J["quadril"])
    peca("cubo", "fivela", (0, -0.36, 0.72), (0.18, 0.06, 0.14), "fivela", J["quadril"])
    # cabeça: capacete-caveira
    peca("cubo", "capacete", (0, -0.16, 1.66), (0.6, 0.55, 0.52), "pedra", J["cabeca"])
    for s in (1, -1):
        peca("cubo", "orbita", (0.14 * s, -0.44, 1.7), (0.18, 0.04, 0.12), "escuro", J["cabeca"])
        peca("cubo", "olho", (0.14 * s, -0.47, 1.7), (0.08, 0.03, 0.07), "olho", J["cabeca"])
    peca("cubo", "boca", (0, -0.44, 1.5), (0.34, 0.04, 0.12), "escuro", J["cabeca"])
    for i in range(4):
        peca("cubo", "dente", (-0.12 + i * 0.08, -0.46, 1.5), (0.05, 0.03, 0.1), "dente", J["cabeca"])
    # braços enormes e manoplas
    for lado, s in (("E", 1), ("D", -1)):
        peca("esfera", "ombro_" + lado, (0.74 * s, 0, 1.38), (0.62, 0.6, 0.6), "pelo", J["ombro" + lado])
        peca("cilindro", "braco_" + lado, (0.82 * s, -0.02, 1.12), (0.42, 0.42, 0.55), "pelo", J["ombro" + lado])
        peca("cilindro", "antebraco_" + lado, (0.88 * s, -0.06, 0.66), (0.4, 0.4, 0.6), "pelo", J["cotovelo" + lado])
        peca("cubo", "manopla_" + lado, (0.9 * s, -0.08, 0.26), (0.5, 0.5, 0.4), "pedra", J["cotovelo" + lado])
        peca("cilindro", "coxa_" + lado, (0.3 * s, 0, 0.42), (0.36, 0.36, 0.34), "pelo", J["perna" + lado])
        peca("cubo", "pe_" + lado, (0.32 * s, -0.08, 0.1), (0.36, 0.48, 0.2), "pelo", J["perna" + lado])
    return J


def rot(e, x=0, y=0, z=0):
    e.rotation_euler = (math.radians(x), math.radians(y), math.radians(z))


BASE = {}


def pose_zero(J):
    if not BASE:
        BASE.update({k: tuple(e.location) for k, e in J.items()})
    for k, e in J.items():
        e.rotation_euler = (0, 0, 0)
        e.location = BASE[k]


def chave(J, f):
    for e in J.values():
        e.keyframe_insert("rotation_euler", frame=f)
        e.keyframe_insert("location", frame=f)


def acoes(J):
    base_z = J["quadril"].location.z
    A = {}
    # idle: 4 quadros, respira (sobe/desce 1 px) e braços balançam pouco
    poses = [(0, 0), (-0.02, 3), (-0.035, 5), (-0.02, 3)]
    A["idle"] = []
    for i, (dz, a) in enumerate(poses):
        f = 1 + i
        pose_zero(J)
        J["quadril"].location.z = base_z + dz
        rot(J["tronco"], x=a * 0.6)
        rot(J["ombroE"], x=-a)
        rot(J["ombroD"], x=-a)
        rot(J["cabeca"], x=-a * 0.5)
        chave(J, f)
        A["idle"].append(f)
    # andar: contato, passagem (corpo sobe, pé levantado), contato oposto, passagem
    A["andar"] = []
    for i, k in enumerate([1, 0, -1, 0]):
        f = 11 + i
        pose_zero(J)
        lado = "E" if i == 1 else "D"
        J["quadril"].location.z = base_z + (-0.03 if k else 0.03)
        rot(J["pernaE"], x=36 * k)
        rot(J["pernaD"], x=-36 * k)
        if k == 0:
            J["perna" + lado].location.z += 0.1
            rot(J["perna" + lado], x=-15)
        rot(J["ombroE"], x=-26 * k)
        rot(J["ombroD"], x=26 * k)
        rot(J["tronco"], x=6)
        chave(J, f)
        A["andar"].append(f)
    # ataque: preparo (braços acima), golpe (soco duplo no chão), impacto, volta
    A["ataque"] = []
    seq = [
        dict(o=-150, c=-20, t=-12, z=0.03),
        dict(o=-178, c=-8, t=-20, z=0.07),
        dict(o=-30, c=-10, t=32, z=-0.12),
        dict(o=-30, c=-10, t=32, z=-0.12),
        dict(o=-24, c=-6, t=26, z=-0.16),
        dict(o=-10, c=0, t=10, z=-0.04),
    ]
    for i, p in enumerate(seq):
        f = 21 + i
        pose_zero(J)
        J["quadril"].location.z = base_z + p["z"]
        rot(J["ombroE"], x=p["o"], y=-8)
        rot(J["ombroD"], x=p["o"], y=8)
        rot(J["cotoveloE"], x=p["c"])
        rot(J["cotoveloD"], x=p["c"])
        rot(J["tronco"], x=p["t"])
        rot(J["cabeca"], x=-p["t"] * 0.5)
        chave(J, f)
        A["ataque"].append(f)
    for ob in bpy.data.objects:
        ad = ob.animation_data
        if ad and ad.action:
            try:
                for fc in ad.action.fcurves:
                    for kp in fc.keyframe_points:
                        kp.interpolation = "CONSTANT"
            except AttributeError:
                pass
    return A


def camera_e_luz():
    cena = bpy.context.scene
    cam_d = bpy.data.cameras.new("cam")
    cam_d.type = "ORTHO"
    cam_d.ortho_scale = 4.5
    cam = bpy.data.objects.new("cam", cam_d)
    cena.collection.objects.link(cam)
    cena.camera = cam
    sol_d = bpy.data.lights.new("sol", "SUN")
    sol_d.energy = 3.0
    sol = bpy.data.objects.new("sol", sol_d)
    cena.collection.objects.link(sol)
    sol.rotation_euler = (math.radians(45), math.radians(-30), math.radians(-35))
    w = cena.world or bpy.data.worlds.new("w")
    cena.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.0
    r = cena.render
    motores = {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    r.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in motores else "BLENDER_EEVEE_NEXT"
    r.resolution_x = r.resolution_y = RES
    r.film_transparent = True
    r.filter_size = 0.0
    cena.view_settings.view_transform = "Standard"
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGBA"
    return cam


def posicionar(cam, yaw):
    alvo = Vector((0, 0, 1.25))
    p = math.radians(PITCH)
    y = math.radians(yaw)
    d = 10
    off = Vector((math.sin(y) * math.cos(p), -math.cos(y) * math.cos(p), math.sin(p))) * d
    cam.location = alvo + off
    cam.rotation_euler = (alvo - cam.location).to_track_quat("-Z", "Y").to_euler()


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", required=True)
    a = ap.parse_args(argv)
    J = montar()
    A = acoes(J)
    cam = camera_e_luz()
    cena = bpy.context.scene
    for dnome, yaw in (("s", 0), ("e", -90), ("n", 180)):
        posicionar(cam, yaw)
        for nome, quadros in A.items():
            pasta = os.path.join(a.saida, f"{nome}_{dnome}")
            os.makedirs(pasta, exist_ok=True)
            for i, f in enumerate(quadros):
                cena.frame_set(f)
                cena.render.filepath = os.path.join(pasta, f"{i:04d}.png")
                bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(a.saida, "gorila_cozy.blend"))


main()
