"""Roda DENTRO do Blender (só stdlib + bpy): monta o .blend do casco visual (casco.py).

uso: blender -b --python casco_blender.py -- <casco.json> <saida.blend>
Uma coleção por parte (Tronco, Cabeça, Braço/Perna Esquerda/Direita), um objeto por peça, todos filhos do empty
"Casco | âncora" na base. Olha para -Y, chão em z = 0. Material único cinza: a projeção da arte pinta as famílias.
"""
import json
import sys

import bmesh
import bpy

args = sys.argv[sys.argv.index("--") + 1:]
dados = json.load(open(args[0], encoding="utf-8"))
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

mat = bpy.data.materials.new("Casco")
mat.diffuse_color = (0.5, 0.5, 0.5, 1)


def lin(c):
    return c / 12.92 if c < 0.04045 else ((c + 0.055) / 1.055) ** 2.4


fam_mats = {}
for nome, hx in (dados.get("cores") or {}).items():
    m = bpy.data.materials.new("Fam | " + nome)
    m.diffuse_color = (*[lin(int(hx[i:i + 2], 16) / 255) for i in (1, 3, 5)], 1)
    fam_mats[nome] = m
raiz = bpy.data.collections.new("01  Casco")
scene.collection.children.link(raiz)
ancora = bpy.data.objects.new("Casco | âncora", None)
raiz.objects.link(ancora)
cols = {}
for p in dados["pecas"]:
    if p["colecao"] not in cols:
        c = bpy.data.collections.new(p["colecao"])
        raiz.children.link(c)
        cols[p["colecao"]] = c
    me = bpy.data.meshes.new(p["objeto"])
    me.from_pydata([tuple(v) for v in p["verts"]], [], [tuple(f) for f in p["faces"]])
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    if p.get("familias"):
        usadas = sorted(set(p["familias"]).union(*[set(x) for x in (p.get("familias_vista") or {}).values()]))
        for n in usadas:
            me.materials.append(fam_mats[n])
        pos = {n: i for i, n in enumerate(usadas)}
        for poly, n in zip(me.polygons, p["familias"]):
            poly.material_index = pos[n]
        for vista, fams in (p.get("familias_vista") or {}).items():
            at = me.attributes.new("horys_fam_" + vista, "INT", "FACE")
            at.data.foreach_set("value", [pos[n] for n in fams])
    else:
        me.materials.append(mat)
    o = bpy.data.objects.new(p["objeto"], me)
    cols[p["colecao"]].objects.link(o)
    o.parent = ancora
bpy.ops.wm.save_as_mainfile(filepath=args[1])
print("[horys] ok", len(dados["pecas"]), "peças")
