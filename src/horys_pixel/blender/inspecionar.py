"""Roda dentro do Blender: lista coleções, peças e materiais de um .blend para montar a config do personagem.
uso: blender -b x.blend --python inspecionar.py -- <saida.json>"""
import json
import re
import sys

import bpy

saida = sys.argv[sys.argv.index("--") + 1]


def rot(o):
    return re.sub(r"\.\d{3,}$", "", o.name)


def col(c):
    return {"nome": c.name, "objetos": sorted({rot(o) for o in c.objects}),
            "filhas": [col(f) for f in c.children]}


vazios = {o.name: len(o.children) for o in bpy.context.scene.objects if o.type == "EMPTY"}
mats = sorted({re.sub(r"\.\d{3,}$", "", m.name) for m in bpy.data.materials if m.users})
arm = [o.name for o in bpy.context.scene.objects if o.type == "ARMATURE"]
acoes = [a.name for a in bpy.data.actions]
json.dump({"colecoes": col(bpy.context.scene.collection), "vazios": vazios, "materiais": mats,
           "armatures": arm, "actions": acoes}, open(saida, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("[horys] ok")
