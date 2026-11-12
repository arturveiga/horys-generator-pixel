"""Importa a malha gerada (hy3d_<modo>.glb), apoia no chão, vira para -Y, aplica escala de boss e renderiza
frente, lateral e 3/4 em alta resolução (sem pixelização), para avaliar só a GEOMETRIA.

    blender -b --factory-startup -P importar_hy3d.py -- --glb hy3d_mini.glb --saida .. [--girar 0]
"""
import argparse
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb", required=True)
    ap.add_argument("--saida", required=True)
    ap.add_argument("--girar", type=float, default=0.0, help="graus em Z para a frente olhar para -Y")
    ap.add_argument("--altura", type=float, default=3.5)
    ap.add_argument("--res", type=int, default=1200)
    a = ap.parse_args(argv)
    base = os.path.abspath(a.saida)
    aqui = os.path.dirname(os.path.abspath(__file__))
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    bpy.ops.import_scene.gltf(filepath=os.path.join(aqui, a.glb))
    malhas = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    ob = malhas[0]
    ob.name = "golem_malha"
    ob.parent = None
    bpy.context.view_layer.update()
    # escala e chão: bbox no mundo
    pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    zmin, zmax = min(p.z for p in pts), max(p.z for p in pts)
    k = a.altura / (zmax - zmin)
    cx = sum(p.x for p in pts) / 8
    cy = sum(p.y for p in pts) / 8
    ob.matrix_world = (Matrix.Rotation(math.radians(a.girar), 4, "Z") @ Matrix.Scale(k, 4)
                       @ Matrix.Translation((-cx, -cy, -zmin)) @ ob.matrix_world)
    for p in ob.data.polygons:
        p.use_smooth = True
    # material de argila neutra: só forma
    m = bpy.data.materials.new("argila")
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.42, 0.36, 0.3, 1)
    b.inputs["Roughness"].default_value = 0.7
    ob.data.materials.clear()
    ob.data.materials.append(m)
    sc = bpy.context.scene
    motores = {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    sc.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in motores else "BLENDER_EEVEE_NEXT"
    sc.render.resolution_x = sc.render.resolution_y = a.res
    sc.view_settings.view_transform = "Standard"
    w = bpy.data.worlds.new("mundo")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.58, 0.57, 0.56, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.4
    sc.world = w
    for nome, en, rot in (("chave", 3.5, (42, 0, -35)), ("recorte", 2.5, (60, 0, 150)), ("preenche", 0.8, (70, 0, 60))):
        d = bpy.data.lights.new(nome, "SUN")
        d.energy = en
        d.angle = math.radians(6)
        o = bpy.data.objects.new(nome, d)
        o.rotation_euler = [math.radians(v) for v in rot]
        sc.collection.objects.link(o)
    d = bpy.data.cameras.new("cam")
    d.type = "ORTHO"
    cam = bpy.data.objects.new("cam", d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    bpy.context.view_layer.update()
    pasta = os.path.join(base, "previews", "v3")
    os.makedirs(pasta, exist_ok=True)
    for nome, yaw, pitch in (("frente", 0, 6), ("lateral", -90, 6), ("tres_quartos", -35, 14)):
        rot = Matrix.Rotation(math.radians(yaw), 4, "Z") @ Matrix.Rotation(math.radians(90 - pitch), 4, "X")
        inv = rot.to_3x3().inverted()
        loc = [inv @ (ob.matrix_world @ Vector(c)) for c in ob.bound_box]
        xs, ys, zs = [p.x for p in loc], [p.y for p in loc], [p.z for p in loc]
        cam.data.ortho_scale = max(max(xs) - min(xs), max(ys) - min(ys)) * 1.08
        cam.data.clip_end = 100
        c = Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, max(zs) + 10))
        cam.matrix_world = Matrix.Translation(rot.to_3x3() @ c) @ rot
        sc.render.filepath = os.path.join(pasta, f"{nome}.png")
        bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(aqui, "golem_v3.blend"))
    print(f"[v3] {len(ob.data.vertices)} vértices, {len(ob.data.polygons)} faces, altura {a.altura}")


main()
