"""Roda dentro do Blender: lista coleções, peças, materiais e a caixa (mundo) de cada coleção de um .blend, para
montar o rig do asset. uso: blender -b x.blend --python inspecionar.py -- <saida.json>"""
import json
import re
import sys

import bpy
from mathutils import Vector

saida = sys.argv[sys.argv.index("--") + 1]


def rot(o):
    return re.sub(r"\.\d{3,}$", "", o.name)


def col(c):
    return {"nome": c.name, "objetos": sorted({rot(o) for o in c.objects}),
            "filhas": [col(f) for f in c.children]}


def caixa(objs):
    pts = [o.matrix_world @ Vector(v) for o in objs if o is not None and o.type == "MESH" for v in o.bound_box]
    if not pts:
        return None
    return [[round(min(p[i] for p in pts), 4) for i in range(3)], [round(max(p[i] for p in pts), 4) for i in range(3)]]


caixas = {}
for c in bpy.data.collections:
    cx = caixa(list(c.all_objects))
    if cx:
        caixas[c.name] = cx
vazios = {o.name: len(o.children) for o in bpy.context.scene.objects if o.type == "EMPTY"}
mats = sorted({re.sub(r"\.\d{3,}$", "", m.name) for m in bpy.data.materials if m.users})
arm = [o.name for o in bpy.context.scene.objects if o.type == "ARMATURE"]
acoes = [a.name for a in bpy.data.actions]


def qa_malhas(tol=0.002):
    """Checagem de malha (ideia do qa_check.py do blender-skills, MIT): bordas abertas, faces degeneradas, escala
    não aplicada e peça flutuando (caixa que não encosta em nenhuma outra). Peça solta vira pixel solto no render."""
    import bmesh
    out, caixas_o = {}, {}
    for o in bpy.context.scene.objects:
        if o.type != "MESH" or not o.data.polygons:
            continue
        bm = bmesh.new()
        bm.from_mesh(o.data)
        abertas = sum(1 for e in bm.edges if not e.is_manifold)
        degeneradas = sum(1 for f in bm.faces if f.calc_area() < 1e-10)
        bm.free()
        esc = [round(x, 4) for x in o.scale]
        item = {}
        if abertas:
            item["bordas_abertas"] = abertas
        if degeneradas:
            item["faces_degeneradas"] = degeneradas
        if any(abs(x - esc[0]) > 1e-4 for x in esc):
            item["escala_nao_uniforme"] = esc
        if item:
            out[o.name] = item
        caixas_o[o.name] = caixa([o])
    nomes = list(caixas_o)
    for a in nomes:
        (a0, a1) = caixas_o[a]
        toca = any(all(a0[i] - tol <= caixas_o[b][1][i] and caixas_o[b][0][i] - tol <= a1[i] for i in range(3))
                   for b in nomes if b != a)
        if len(nomes) > 1 and not toca:
            out.setdefault(a, {})["flutuando"] = True
    return out


tudo = caixa(list(bpy.context.scene.objects))
json.dump({"colecoes": col(bpy.context.scene.collection), "vazios": vazios, "materiais": mats,
           "armatures": arm, "actions": acoes, "caixas": caixas, "caixa_total": tudo,
           "qa_malhas": qa_malhas(), "altura_m": round(tudo[1][2] - tudo[0][2], 4) if tudo else None},
          open(saida, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("[horys] ok")
