"""Golem v3: idle (4) e walk (8) no rig do golem_v3.blend, shader toon com contorno e render pixel art em
três direções (s, se, e) com câmera ortográfica de escala FIXA para tudo.

    blender -b blender/golem_v3.blend -P golem_v3_animar.py -- --saida .. [--previa]

Saída: renders/<acao>_<dir>_{bruto256,x4}/ + manifest.json (contrato v1 do Horys); golem_v3_anim.blend.
"""
import argparse
import json
import math
import os
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

AQUI = os.path.dirname(os.path.abspath(__file__))
PITCH, FPS = 32.0, 8
CRANIO_SOBE = 0.1


def lin(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple((x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4) for x in c) + (1.0,)


# ------------------------------------------------------------------ animação
def mover(pb, dx=0.0, dy=0.0, dz=0.0):
    """Osso que aponta para +Z: location local (x, y, z) = mundo (x, z, -y)."""
    pb.location = (dx, dz, -dy)


def zerar(arm):
    for pb in arm.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_euler = (0, 0, 0)


def chave(arm, f):
    for pb in arm.pose.bones:
        pb.keyframe_insert("location", frame=f)
        pb.keyframe_insert("rotation_euler", frame=f)


def nova_acao(arm, nome):
    ad = arm.animation_data or arm.animation_data_create()
    ad.action = None
    act = bpy.data.actions.new(nome)
    act.use_fake_user = True
    ad.action = act
    return act


def pedras(arm):
    return sorted(pb.name for pb in arm.pose.bones if pb.name.startswith("pedra"))


def anim_walk(arm, n=8):
    """Andar pesado: pé de apoio recua em velocidade constante (no lugar), pé no ar em arco; corpo baixo no
    contato com squash, giro de quadril e contragiro do peito; braço oposto à perna; crânio e pedras atrasam."""
    act = nova_acao(arm, "Golem_Walk")
    S, ALT, BOB, BAL = 0.32, 0.24, 0.1, 0.045
    pb = arm.pose.bones
    for f in range(n + 1):
        zerar(arm)
        p = (f % n) / n
        for l, fase in (("L", 0.0), ("R", 0.5)):
            q = (p + fase) % 1.0
            if q < 0.5:
                y, z = -S + 2 * S * (q / 0.5), 0.0
            else:
                u = (q - 0.5) / 0.5
                y, z = S - 2 * S * u, ALT * math.sin(math.pi * u)
            mover(pb[f"pe_ik.{l}"], dy=y, dz=z)
            pb[f"pe_ik.{l}"].rotation_euler.x = math.radians(-18) * math.sin(math.pi * max(0.0, (q - 0.5) / 0.5))
            sinal = 1 if l == "L" else -1
            pb[f"braco.{l}"].rotation_euler.x = math.radians(22) * math.cos(2 * math.pi * q) * sinal
            pb[f"antebraco.{l}"].rotation_euler.x = math.radians(10) * (1 + math.cos(2 * math.pi * q)) * sinal
        contato = (1 + math.cos(4 * math.pi * p)) / 2
        mover(pb["quadril"], dx=BAL * math.sin(2 * math.pi * p), dz=-0.02 - 0.07 * contato ** 2)
        pb["quadril"].rotation_euler.y = math.radians(7) * math.sin(2 * math.pi * p)
        pb["peito"].rotation_euler.y = -math.radians(10) * math.sin(2 * math.pi * p)
        pb["peito"].rotation_euler.x = math.radians(4) * contato ** 3          # o peso afunda no contato
        atraso = (p - 1 / n) % 1.0
        c2 = (1 + math.cos(4 * math.pi * atraso)) / 2
        mover(pb["cabeca"], dz=CRANIO_SOBE + 0.04 - 0.07 * c2)
        for l in ("L", "R"):
            mover(pb[f"ombro.{l}"], dz=-0.04 * contato ** 2)
        for i, nome in enumerate(pedras(arm)):
            mover(pb[nome], dz=0.03 * math.cos(4 * math.pi * (p - (i + 2) / n)))
        chave(arm, f)
    return act


def anim_idle(arm, n=4):
    act = nova_acao(arm, "Golem_Idle")
    pb = arm.pose.bones
    for f in range(n + 1):
        zerar(arm)
        p = (f % n) / n
        r = math.sin(2 * math.pi * p)
        mover(pb["quadril"], dz=-0.02 - 0.02 * (1 - r))
        pb["peito"].rotation_euler.x = math.radians(-3) * r                    # peito enche
        for l in ("L", "R"):
            mover(pb[f"ombro.{l}"], dz=0.05 * r)
            pb[f"braco.{l}"].rotation_euler.x = math.radians(2) * r * (1 if l == "L" else -1)
        mover(pb["cabeca"], dz=CRANIO_SOBE + 0.04 * math.sin(2 * math.pi * (p - 0.25)))
        pb["cabeca"].rotation_euler.y = math.radians(3) * math.sin(2 * math.pi * p)
        for i, nome in enumerate(pedras(arm)):
            mover(pb[nome], dz=0.06 * math.sin(2 * math.pi * (p + 0.25 * i)))
        chave(arm, f)
    return act


# ------------------------------------------------------------------ toon + contorno
def toon(ob, contorno_mat):
    """Cor da ficha × faixas de luz constantes (3 tons por cor) + casco invertido de 1 px."""
    m = bpy.data.materials.new(f"toon_{ob.name}")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    dif = nt.nodes.new("ShaderNodeBsdfDiffuse")
    s2r = nt.nodes.new("ShaderNodeShaderToRGB")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cr.interpolation = "CONSTANT"
    cr.elements[0].position, cr.elements[0].color = 0.0, (0.55, 0.55, 0.6, 1)
    cr.elements[1].position, cr.elements[1].color = 0.28, (0.85, 0.85, 0.85, 1)
    e = cr.elements.new(0.7)
    e.color = (1.08, 1.06, 1.0, 1)
    vc = nt.nodes.new("ShaderNodeVertexColor")
    vc.layer_name = "cor"
    mul = nt.nodes.new("ShaderNodeMix")
    mul.data_type, mul.blend_type = "RGBA", "MULTIPLY"
    mul.inputs["Factor"].default_value = 1.0
    emi = nt.nodes.new("ShaderNodeEmission")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(dif.outputs[0], s2r.inputs[0])
    nt.links.new(s2r.outputs["Color"], ramp.inputs["Fac"])
    nt.links.new(vc.outputs["Color"], mul.inputs[6])
    nt.links.new(ramp.outputs["Color"], mul.inputs[7])
    nt.links.new(mul.outputs[2], emi.inputs["Color"])
    nt.links.new(emi.outputs[0], out.inputs["Surface"])
    ob.data.materials.clear()
    ob.data.materials.append(m)
    ob.data.materials.append(contorno_mat)
    s = ob.modifiers.new("contorno", "SOLIDIFY")
    s.thickness, s.offset, s.use_flip_normals, s.material_offset, s.use_rim = 0.018, 1.0, True, 1, False


def mat_contorno():
    m = bpy.data.materials.new("contorno")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    emi = nt.nodes.new("ShaderNodeEmission")
    emi.inputs["Color"].default_value = lin("#1a1420")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(emi.outputs[0], out.inputs["Surface"])
    m.use_backface_culling = True
    return m


# ------------------------------------------------------------------ render
def preparar(sc):
    motores = {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    sc.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in motores else "BLENDER_EEVEE_NEXT"
    sc.render.film_transparent = True
    sc.render.filter_size = 0.0
    sc.render.fps = FPS
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.view_settings.view_transform = "Standard"
    for nome, valor in (("taa_render_samples", 1), ("use_gtao", False), ("use_shadows", False),
                        ("use_raytracing", False)):
        if hasattr(sc.eevee, nome):
            setattr(sc.eevee, nome, valor)
    for o in [o for o in sc.objects if o.type in ("LIGHT", "CAMERA")]:
        bpy.data.objects.remove(o)
    w = sc.world or bpy.data.worlds.new("mundo")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (1, 1, 1, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.12
    sc.world = w
    d = bpy.data.lights.new("sol", "SUN")
    d.energy, d.angle, d.use_shadow = 3.0, 0.0, False
    sol = bpy.data.objects.new("sol", d)
    sc.collection.objects.link(sol)
    dc = bpy.data.cameras.new("cam")
    dc.type = "ORTHO"
    cam = bpy.data.objects.new("cam", dc)
    sc.collection.objects.link(cam)
    sc.camera = cam
    return cam, sol


def orientar(cam, sol, yaw):
    cam.matrix_world = Matrix.Rotation(math.radians(yaw), 4, "Z") @ Matrix.Rotation(math.radians(90 - PITCH), 4, "X")
    sol.rotation_euler = (math.radians(30), math.radians(40), math.radians(yaw))


def pontos(sc):
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for o in sc.objects:
        if o.type == "MESH" and not o.hide_render:
            ev = o.evaluated_get(dg)
            pts += [ev.matrix_world @ Vector(c) for c in ev.bound_box]
    return pts


def enquadrar(cam, pts, altura_px, res, escala=None):
    rot = cam.matrix_world.to_3x3()
    loc = [rot.inverted() @ p for p in pts]
    xs, ys, zs = [p.x for p in loc], [p.y for p in loc], [p.z for p in loc]
    cam.data.ortho_scale = escala or (max(ys) - min(ys)) * res / altura_px
    cx = (min(xs) + max(xs)) / 2
    cy = min(ys) + cam.data.ortho_scale * (0.5 - 0.08)
    cam.data.clip_start, cam.data.clip_end = 0.01, 100
    cam.matrix_world = Matrix.Translation(rot @ Vector((cx, cy, max(zs) + 10))) @ rot.to_4x4()
    return cam.data.ortho_scale


def usar(arm, act):
    ad = arm.animation_data
    ad.action = act
    if hasattr(ad, "action_slot") and len(act.slots):
        ad.action_slot = act.slots[0]


def renderizar(sc, cam, arm, act, nome, n, pasta_base, res, sufixo, yaw):
    usar(arm, act)
    sc.render.resolution_x = sc.render.resolution_y = res
    pasta = os.path.join(pasta_base, f"{nome}_{sufixo}")
    os.makedirs(pasta, exist_ok=True)
    arqs = []
    for f in range(n):
        sc.frame_set(f)
        arq = f"{f:04d}.png"
        sc.render.filepath = os.path.join(pasta, arq)
        bpy.ops.render.render(write_still=True)
        arqs.append(arq)
    co = world_to_camera_view(sc, cam, Vector((0, 0, 0)))
    man = {"versao": 1, "fonte": "blender", "acao": nome, "fps": FPS, "canvas": [res, res],
           "pivo": [round(co.x * res, 2), round((1 - co.y) * res, 2)],
           "camera": {"pitch": PITCH, "yaw": yaw, "ortho_scale": round(cam.data.ortho_scale, 6)},
           "loop": True, "quadros": arqs}
    with open(os.path.join(pasta, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(man, fh, ensure_ascii=False, indent=2)
    print(f"[anim] {nome}_{sufixo}: {n} quadros")


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", required=True)
    ap.add_argument("--altura", type=float, default=207)
    ap.add_argument("--previa", action="store_true")
    a = ap.parse_args(argv)
    base = os.path.abspath(a.saida)
    sc = bpy.context.scene
    arm = bpy.data.objects["GolemRig"]
    cont = mat_contorno()
    # sola dos pés (tampa do corte do chão): pelo escuro em vez do cinza herdado
    corpo = bpy.data.objects["golem_corpo"]
    ca = corpo.data.color_attributes["cor"]
    escuro = lin("#2a2531")
    for v in corpo.data.vertices:
        if v.co.z < 0.07 or (v.co.z < 0.2 and v.normal.z < -0.6):
            ca.data[v.index].color = escuro
    for nome in ("golem_corpo", "golem_cranio"):
        toon(bpy.data.objects[nome], cont)
    walk = anim_walk(arm)
    idle = anim_idle(arm)
    cam, sol = preparar(sc)
    pts = []
    for act, n in ((walk, 8), (idle, 4)):
        usar(arm, act)
        for f in range(n):
            sc.frame_set(f)
            pts += pontos(sc)
    orientar(cam, sol, 0.0)
    escala = enquadrar(cam, pts, a.altura, 256)
    sc.frame_start, sc.frame_end = 0, 7
    pasta = os.path.join(base, "renders")
    dirs = (("se", -45.0),) if a.previa else (("s", 0.0), ("se", -45.0), ("e", -90.0))
    for dire, yaw in dirs:
        orientar(cam, sol, yaw)
        enquadrar(cam, pts, a.altura, 256, escala)
        for act, nome, n in ((idle, "idle", 4), (walk, "walk", 8)):
            for res, suf in ((256, "bruto256"), (1024, "x4")):
                if a.previa and res == 1024:
                    continue
                renderizar(sc, cam, arm, act, f"{nome}_{dire}", n, pasta, res, suf, yaw)
    usar(arm, walk)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(AQUI, "golem_v3_anim.blend"))
    print("[anim] golem_v3_anim.blend salvo")


main()
