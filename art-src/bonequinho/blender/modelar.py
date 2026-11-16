"""Bonequinho-base chibi (referência: art-src/bonequinho/referencia.png): cabeça grande e redonda, corpo pequeno, braços e
pernas curtos e grossos, mãos de luva, pés arredondados, cinza liso. Todos os personagens são variações dele: só o
capacete muda, preso no empty "Capacete | encaixe" (filho da cabeça) e na coleção "Capacete".

uso: blender -b --python modelar.py -- <pasta de saída>
Saída: bonequinho.blend, bonequinho.glb e vistas.png (frente, lado, costas, 3/4).
Convenção: olha para -Y (sul = frente), Z para cima, chão em z = 0.
"""
import os
import sys

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

SAIDA = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else os.path.dirname(__file__)
os.makedirs(SAIDA, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


def lin(c):
    return c / 12.92 if c < 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgb(hx):
    hx = hx.lstrip("#")
    return (*[lin(int(hx[i:i + 2], 16) / 255) for i in (0, 2, 4)], 1.0)


def mat(nome, hx):
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = rgb(hx)
    b.inputs["Roughness"].default_value = 0.7
    m.diffuse_color = rgb(hx)
    return m


PELE = mat("Pele | cinza", "#a9a9b2")
OLHO = mat("Olho | escuro", "#2a2a33")

RAIZ = bpy.data.collections.new("01  Boneco")
scene.collection.children.link(RAIZ)
ANCORA = bpy.data.objects.new("Boneco | âncora", None)
RAIZ.objects.link(ANCORA)
COLS = {}


def colecao(nome):
    if nome not in COLS:
        c = bpy.data.collections.new(nome)
        RAIZ.children.link(c)
        COLS[nome] = c
    return COLS[nome]


def objeto(nome, bm, col, material, liso=True):
    me = bpy.data.meshes.new(nome)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = liso
    me.materials.append(material)
    o = bpy.data.objects.new(nome, me)
    colecao(col).objects.link(o)
    o.parent = ANCORA
    return o


def esfera(nome, col, material, centro, escala, rot=(0, 0, 0), u=20, v=14):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=1.0)
    M = Matrix.Translation(Vector(centro)) @ Euler(rot).to_matrix().to_4x4() @ Matrix.Diagonal((*escala, 1))
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
    return objeto(nome, bm, col, material)


def capsula(nome, col, material, a, b, r1, r2, seg=12, aneis=4):
    """Membro liso de uma peça: tubo de a até b com as pontas arredondadas, alisado por Subdivision Surface
    (sem bolinhas de junta)."""
    a, b = Vector(a), Vector(b)
    d = b - a
    L = d.length
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=16, radius=1.0)
    for v in bm.verts:                      # esfera aberta no meio: metade de baixo em a (r1), de cima em b (r2)
        r = r2 if v.co.z > 0 else r1
        v.co.x *= r
        v.co.y *= r
        v.co.z = v.co.z * r + (L if v.co.z > 0 else 0.0)
    q = Vector((0, 0, 1)).rotation_difference(d.normalized())
    bmesh.ops.transform(bm, matrix=Matrix.Translation(a) @ q.to_matrix().to_4x4(), verts=bm.verts)
    o = objeto(nome, bm, col, material)
    m = o.modifiers.new("Liso", "SUBSURF")
    m.levels = m.render_levels = 1
    return o


# ------------------------------------------------------------------ medidas (altura total ~1,75)
QUADRIL = 0.40
OMBRO_Z = 0.80
CABECA_C, CABECA_R = (0, 0, 1.28), 0.47

# ------------------------------------------------------------------ tronco: barriguinha em pera
esfera("Tronco", "Tronco", PELE, (0, 0, 0.60), (0.26, 0.21, 0.27))
capsula("Pescoço", "Tronco", PELE, (0, 0, 0.80), (0, 0, 0.92), 0.09, 0.09)

# ------------------------------------------------------------------ cabeça grande e redonda (+ encaixe do capacete)
cab = esfera("Cabeça", "Cabeça", PELE, CABECA_C, (CABECA_R, CABECA_R * 0.96, CABECA_R * 0.98))
encaixe = bpy.data.objects.new("Capacete | encaixe", None)
colecao("Capacete").objects.link(encaixe)
encaixe.empty_display_type = "SPHERE"
encaixe.empty_display_size = 0.1
encaixe.parent = cab
encaixe.location = (0, 0, CABECA_C[2] + CABECA_R * 0.55)   # topo da cabeça: o capacete encaixa aqui

# ------------------------------------------------------------------ braços curtos e grossos, mão de luva
BRACOS = {}
for s, nome in ((-1, "Braço Esquerdo"), (1, "Braço Direito")):
    o = Vector((s * 0.24, 0, OMBRO_Z - 0.06))
    m = Vector((s * 0.33, -0.01, 0.47))
    BRACOS[nome] = (o, m)
    capsula("Braço", nome, PELE, m, o, 0.10, 0.085)      # braço e mão numa peça só: a mão (embaixo) mais larga

# ------------------------------------------------------------------ pernas curtas, pés arredondados
PERNAS = {}
for s, nome in ((-1, "Perna Esquerda"), (1, "Perna Direita")):
    q = Vector((s * 0.13, 0, QUADRIL))
    j = Vector((s * 0.14, -0.01, 0.13))     # joelho do rig quase no tornozelo: a perna inteira é uma peça lisa
    t = Vector((s * 0.14, 0, 0.10))
    PERNAS[nome] = (q, j, t)
    capsula("Coxa", nome, PELE, t, q + Vector((0, 0, 0.04)), 0.095, 0.105)   # perna lisa, quadril ao tornozelo
    esfera("Pé", nome, PELE, (t.x, -0.04, 0.065), (0.12, 0.16, 0.075))

# ------------------------------------------------------------------ vistas de modelagem
bpy.context.view_layer.update()
mundo = bpy.data.worlds.new("Mundo")
scene.world = mundo
mundo.use_nodes = True
mundo.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.05, 0.06, 1)
mundo.node_tree.nodes["Background"].inputs[1].default_value = 1.5
estudio = bpy.data.collections.new("02  Estúdio")
scene.collection.children.link(estudio)
sol_d = bpy.data.lights.new("Luz principal", "SUN")
sol_d.energy = 3.5
sol = bpy.data.objects.new("Luz principal", sol_d)
estudio.objects.link(sol)
sol.rotation_euler = Vector((0.52, 0.53, -0.67)).to_track_quat("-Z", "Y").to_euler()
alvo = Vector((0, 0, 0.88))


def camera(nome, pos):
    d = bpy.data.cameras.new(nome)
    d.type = "ORTHO"
    d.ortho_scale = 2.2
    c = bpy.data.objects.new(nome, d)
    estudio.objects.link(c)
    c.location = alvo + Vector(pos)
    c.rotation_euler = (alvo - c.location).to_track_quat("-Z", "Y").to_euler()
    return c


cams = [camera("Frente", (0, -20, 0)), camera("Perfil", (20, 0, 0)), camera("Costas", (0, 20, 0)),
        camera("Três quartos", (12, -14, 9))]
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = scene.render.resolution_y = 512
scene.render.film_transparent = True
tmp = []
for c in cams:
    scene.camera = c
    arq = os.path.join(SAIDA, f"_vista_{c.name}.png")
    scene.render.filepath = arq
    bpy.ops.render.render(write_still=True)
    tmp.append(arq)
imgs = [bpy.data.images.load(a) for a in tmp]
W = 512 * len(imgs)
prancha = bpy.data.images.new("vistas", W, 512, alpha=True)
px = [0.0] * (W * 512 * 4)
for k, im in enumerate(imgs):
    src = list(im.pixels)
    for y in range(512):
        ini = (y * W + k * 512) * 4
        px[ini:ini + 512 * 4] = src[y * 512 * 4:(y + 1) * 512 * 4]
prancha.pixels = px
prancha.filepath_raw = os.path.join(SAIDA, "vistas.png")
prancha.file_format = "PNG"
prancha.save()
for a in tmp:
    os.remove(a)
scene.camera = cams[3]

bpy.ops.export_scene.gltf(filepath=os.path.join(SAIDA, "bonequinho.glb"), export_format="GLB", use_selection=False,
                          export_cameras=False, export_lights=False)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(SAIDA, "bonequinho.blend"))
print("[horys] ok", len([o for o in scene.objects if o.type == "MESH"]), "peças")
