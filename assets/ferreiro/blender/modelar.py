"""Ferreiro anão (arte aprovada: assets/ferreiro/arte/): cabeça grande com cabelo branco espetado para trás, barba
branca grande, óculos dourados na testa, túnica bege larga com cinto marrom, braçadeiras azuis, luvas e botas
marrons, martelo curto na mão (a mão que aparece à esquerda na vista de frente).

uso: blender -b --python modelar.py -- <pasta de saída>
Saída: modelo.blend e vistas.png (frente, lado, costas, 3/4).
Convenção: olha para -Y (sul = frente), Z para cima, chão em z = 0. Altura ~2,15 m (54 px na escala do jogo).
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


# cores = tom do meio das famílias da paleta aprovada (paleta.json)
PELE = mat("Pele", "#e8b668")
TUNICA = mat("Túnica", "#e8b668")
COURO = mat("Couro escuro", "#682512")
LUVA = mat("Luva", "#913d17")
CABELO = mat("Cabelo", "#f9ebe5")
CABELO_SOMBRA = mat("Cabelo sombra", "#c6a6a6")
AZUL = mat("Braçadeira", "#3962c8")
DOURADO = mat("Dourado", "#e8b668")

RAIZ = bpy.data.collections.new("01  Ferreiro")
scene.collection.children.link(RAIZ)
ANCORA = bpy.data.objects.new("Ferreiro | âncora", None)
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


def cilindro(nome, col, material, centro, raio, altura, rot=(0, 0, 0), seg=20):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=1.0, radius2=1.0, depth=1.0)
    M = (Matrix.Translation(Vector(centro)) @ Euler(rot).to_matrix().to_4x4()
         @ Matrix.Diagonal((raio[0], raio[1], altura, 1)))
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
    return objeto(nome, bm, col, material, liso=False)


def caixa(nome, col, material, centro, tam, rot=(0, 0, 0)):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    M = Matrix.Translation(Vector(centro)) @ Euler(rot).to_matrix().to_4x4() @ Matrix.Diagonal((*tam, 1))
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
    return objeto(nome, bm, col, material, liso=False)


def capsula(nome, col, material, a, b, r1, r2):
    a, b = Vector(a), Vector(b)
    d = b - a
    L = d.length
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=16, radius=1.0)
    for v in bm.verts:
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


def espetado(nome, col, material, centro, escala, pontas=14, forca=0.28, semente=3):
    """Cabelo: esfera com tufos puxados para fora e para trás (+Y)."""
    import random
    rnd = random.Random(semente)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
    dirs = []
    for _ in range(pontas):
        d = Vector((rnd.uniform(-1, 1), rnd.uniform(-0.2, 1.0), rnd.uniform(-0.1, 1.0))).normalized()
        dirs.append(d)
    for v in bm.verts:
        n = v.co.normalized()
        ganho = max(max(0.0, n.dot(d)) ** 12 for d in dirs)
        v.co = v.co * (1 + forca * ganho)
    M = Matrix.Translation(Vector(centro)) @ Matrix.Diagonal((*escala, 1))
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
    return objeto(nome, bm, col, material, liso=False)


# ------------------------------------------------------------------ medidas (altura total ~2,15 m)
CABECA_C = Vector((0, -0.12, 1.45))

# ------------------------------------------------------------------ tronco: túnica larga, cinto, saia
esfera("Túnica", "Tronco", TUNICA, (0, 0, 0.78), (0.56, 0.52, 0.38))
esfera("Saia", "Tronco", TUNICA, (0, 0, 0.46), (0.54, 0.50, 0.22))
cilindro("Cinto", "Tronco", COURO, (0, 0, 0.60), (0.55, 0.51), 0.09)
caixa("Fivela", "Tronco", DOURADO, (0, -0.52, 0.60), (0.14, 0.04, 0.10))
caixa("Alça", "Tronco", COURO, (0, -0.02, 0.86), (0.08, 0.72, 0.06), rot=(0, 0.75, 0))

# ------------------------------------------------------------------ cabeça: rosto, nariz, barba, cabelo, óculos
esfera("Cabeça", "Cabeça", PELE, CABECA_C, (0.30, 0.28, 0.30))
esfera("Nariz", "Cabeça", PELE, CABECA_C + Vector((0, -0.29, -0.04)), (0.09, 0.08, 0.08))
for s in (-1, 1):
    esfera("Orelha", "Cabeça", PELE, CABECA_C + Vector((s * 0.30, 0.02, 0.0)), (0.05, 0.07, 0.08))
esfera("Barba", "Cabeça", CABELO, CABECA_C + Vector((0, -0.24, -0.32)), (0.40, 0.26, 0.34))
esfera("Bigode", "Cabeça", CABELO, CABECA_C + Vector((0, -0.27, -0.13)), (0.24, 0.07, 0.07))
espetado("Cabelo", "Cabeça", CABELO, CABECA_C + Vector((0, 0.16, 0.10)), (0.54, 0.46, 0.24))
esfera("Cabelo nuca", "Cabeça", CABELO_SOMBRA, CABECA_C + Vector((0, 0.20, -0.18)), (0.46, 0.26, 0.36))
cilindro("Tira dos óculos", "Cabeça", COURO, CABECA_C + Vector((0, -0.02, 0.28)), (0.33, 0.30), 0.06)
for s in (-1, 1):
    cilindro("Óculos", "Cabeça", DOURADO, CABECA_C + Vector((s * 0.13, -0.26, 0.30)), (0.10, 0.10), 0.07,
             rot=(1.5708, 0, 0))

# ------------------------------------------------------------------ braços: manga, braçadeira, luva
BRACOS = {}
for s, nome in ((-1, "Braço Esquerdo"), (1, "Braço Direito")):
    o = Vector((s * 0.52, 0, 0.98))
    c = Vector((s * 0.66, 0, 0.80))
    m = Vector((s * 0.76, -0.05, 0.56))
    BRACOS[nome] = (o, c, m)
    capsula("Braço superior", nome, TUNICA, c, o, 0.14, 0.15)
    capsula("Antebraço", nome, AZUL, m, c, 0.14, 0.14)
    esfera("Luva", nome, LUVA, m + Vector((0, 0, -0.03)), (0.20, 0.20, 0.19))

# martelo na mão do lado -X (aparece à esquerda na vista de frente)
mao = BRACOS["Braço Esquerdo"][2] + Vector((0, -0.04, -0.03))
cilindro("Cabo do martelo", "Braço Esquerdo", LUVA, mao + Vector((0, -0.06, -0.10)), (0.035, 0.035), 0.34,
         rot=(0.35, 0, 0))
cilindro("Cabeça do martelo", "Braço Esquerdo", COURO, mao + Vector((0, -0.13, -0.29)), (0.08, 0.08), 0.22,
         rot=(0, 1.5708, 0))

# ------------------------------------------------------------------ pernas curtas, botas grandes
PERNAS = {}
for s, nome in ((-1, "Perna Esquerda"), (1, "Perna Direita")):
    q = Vector((s * 0.22, 0, 0.40))
    j = Vector((s * 0.24, -0.01, 0.26))
    t = Vector((s * 0.24, 0, 0.14))
    PERNAS[nome] = (q, j, t)
    capsula("Coxa", nome, COURO, j, q, 0.11, 0.12)
    capsula("Canela", nome, COURO, t, j, 0.11, 0.11)
    esfera("Bota", nome, LUVA, (t.x, -0.05, 0.09), (0.22, 0.36, 0.13))

# ------------------------------------------------------------------ escala: modelado em 54 px, a arte aprovada tem 32
ESCALA = 32 / 54
for ob in [o for o in scene.objects if o.type == "MESH"]:
    ob.data.transform(Matrix.Diagonal((ESCALA, ESCALA, ESCALA, 1)))
    ob.data.update()

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
alvo = Vector((0, 0, 0.65))


def camera(nome, pos):
    d = bpy.data.cameras.new(nome)
    d.type = "ORTHO"
    d.ortho_scale = 1.6
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
for im in imgs:
    bpy.data.images.remove(im)
for a in tmp:
    os.remove(a)
scene.camera = cams[3]

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(SAIDA, "modelo.blend"))
print("[horys] ok", len([o for o in scene.objects if o.type == "MESH"]), "peças")
