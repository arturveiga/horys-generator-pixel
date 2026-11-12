"""Golem v3: da malha gerada (hy3d_mv.glb) ao personagem pronto para animar.

    blender -b --factory-startup -P golem_v3_montar.py -- --saida ..

1. importa e normaliza (altura 3,5, chão em z = 0, frente para -Y);
2. limpa: corta a placa fina do chão (sombra da imagem de entrada) e refaz a malha por voxel (manifold, densidade
   uniforme: os pesos automáticos funcionam);
3. separa o crânio (flutua) do corpo no pescoço;
4. pinta por projeção as três vistas da ficha (frente, lado, costas) em cor por vértice;
5. rig: ossos posicionados pelos marcos medidos na própria malha, pernas com IK, pesos automáticos (heat);
6. fumaça roxa e pedras flutuantes com runa como peças presas a ossos;
7. salva golem_v3.blend e renderiza frente, lateral, 3/4 e uma pose de teste (deformação).
"""
import argparse
import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

AQUI = os.path.dirname(os.path.abspath(__file__))
ENTRADA = os.path.join(os.path.dirname(AQUI), "referencia", "entrada_3d")
ALTURA = 3.5
PESCOCO_Z = 2.84      # medido: o pescoço afina para ~1,0 de largura entre 2,7 e 2,85
CHAO_CORTE = 0.06     # a placa fina do chão fica abaixo disso


def lin(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple((x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4) for x in c) + (1.0,)


# ------------------------------------------------------------------ 1. importar
def importar(glb):
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    bpy.ops.import_scene.gltf(filepath=os.path.join(AQUI, glb))
    ob = [o for o in bpy.context.scene.objects if o.type == "MESH"][0]
    ob.name = "golem_corpo"
    mw = ob.matrix_world.copy()
    ob.parent = None
    ob.matrix_world = mw
    for o in list(bpy.context.scene.objects):
        if o is not ob:
            bpy.data.objects.remove(o)
    ob.data.transform(ob.matrix_world)
    ob.matrix_world = Matrix.Identity(4)
    vs = np.array([v.co for v in ob.data.vertices])
    lo, hi = vs.min(0), vs.max(0)
    k = ALTURA / (hi[2] - lo[2])
    c = (lo + hi) / 2
    ob.data.transform(Matrix.Scale(k, 4) @ Matrix.Translation((-c[0], -c[1], -lo[2])))
    return ob


def ativo(ob):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


def aplicar(ob, mod):
    ativo(ob)
    bpy.ops.object.modifier_apply(modifier=mod.name)


# ------------------------------------------------------------------ 2. limpar
def limpar(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    geo = bm.verts[:] + bm.edges[:] + bm.faces[:]
    r = bmesh.ops.bisect_plane(bm, geom=geo, plane_co=(0, 0, CHAO_CORTE), plane_no=(0, 0, 1), clear_inner=True)
    borda = [e for e in r["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
    if borda:
        bmesh.ops.holes_fill(bm, edges=borda, sides=0)
    for v in bm.verts:
        v.co.z -= CHAO_CORTE
    bm.to_mesh(ob.data)
    bm.free()
    rm = ob.modifiers.new("remesh", "REMESH")
    rm.mode, rm.voxel_size, rm.use_smooth_shade = "VOXEL", 0.018, True
    aplicar(ob, rm)
    sm = ob.modifiers.new("suave", "CORRECTIVE_SMOOTH")
    sm.factor, sm.iterations = 0.4, 4
    aplicar(ob, sm)
    dc = ob.modifiers.new("reduz", "DECIMATE")
    dc.ratio = 0.45
    aplicar(ob, dc)
    for p in ob.data.polygons:
        p.use_smooth = True


# ------------------------------------------------------------------ 3. crânio
def separar_cranio(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm2 = bm.copy()
    geo = bm.verts[:] + bm.edges[:] + bm.faces[:]
    r = bmesh.ops.bisect_plane(bm, geom=geo, plane_co=(0, 0, PESCOCO_Z), plane_no=(0, 0, 1), clear_outer=True)
    bmesh.ops.holes_fill(bm, edges=[e for e in r["geom_cut"] if isinstance(e, bmesh.types.BMEdge)], sides=0)
    bm.to_mesh(ob.data)
    bm.free()
    geo = bm2.verts[:] + bm2.edges[:] + bm2.faces[:]
    r = bmesh.ops.bisect_plane(bm2, geom=geo, plane_co=(0, 0, PESCOCO_Z), plane_no=(0, 0, 1), clear_inner=True)
    bmesh.ops.holes_fill(bm2, edges=[e for e in r["geom_cut"] if isinstance(e, bmesh.types.BMEdge)], sides=0)
    me = bpy.data.meshes.new("golem_cranio")
    bm2.to_mesh(me)
    bm2.free()
    cr = bpy.data.objects.new("golem_cranio", me)
    bpy.context.scene.collection.objects.link(cr)
    for p in me.polygons:
        p.use_smooth = True
    return cr


# ------------------------------------------------------------------ 4. pintura projetada
def _imagem(nome):
    from PIL import Image  # noqa: F401  (não existe no Python do Blender; usamos bpy.data.images)


def carregar(nome):
    img = bpy.data.images.load(os.path.join(ENTRADA, f"{nome}.png"))
    img.colorspace_settings.name = "sRGB"
    w, h = img.size
    px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1]   # linha 0 = topo
    a = px[..., 3] > 0.5
    ys, xs = np.nonzero(a)
    return {"px": px, "bbox": (xs.min(), ys.min(), xs.max(), ys.max()), "w": w, "h": h}


CLASSES = {   # nome: (cores de referência sRGB 0-1 vistas na ficha, cor da paleta, emissão)
    "pedra": ([(0.72, 0.63, 0.54), (0.56, 0.46, 0.38), (0.80, 0.72, 0.60)], "#a8906f", 0.0),
    "pedra_esc": ([(0.37, 0.31, 0.26), (0.45, 0.37, 0.30)], "#6b5646", 0.0),
    "pelo": ([(0.24, 0.21, 0.26), (0.16, 0.14, 0.19), (0.31, 0.27, 0.34), (0.19, 0.15, 0.17)], "#3c3543", 0.0),
    "brilho": ([(1.0, 0.6, 0.1), (0.95, 0.45, 0.05)], "#ff9a1a", 1.2),
    "musgo": ([(0.42, 0.75, 0.25), (0.33, 0.55, 0.2)], "#6bbf3f", 0.0),
    "fumaca": ([(0.44, 0.34, 0.66), (0.32, 0.22, 0.5)], "#7057a8", 0.4),
}


def _visivel(a, b, prof, celula=0.025, folga=0.07, maior=False):
    """z-buffer simples: True onde o vértice é a superfície mais próxima da câmera naquela célula (a, b)."""
    ia = np.floor(a / celula).astype(np.int64)
    ib = np.floor(b / celula).astype(np.int64)
    chave = ia * 100003 + ib
    ordem = np.argsort(chave)
    ch = chave[ordem]
    pr = -prof[ordem] if maior else prof[ordem]
    ini = np.r_[0, np.nonzero(np.diff(ch))[0] + 1]
    melhor = np.minimum.reduceat(pr, ini)
    rep = np.repeat(melhor, np.diff(np.r_[ini, len(ch)]))
    vis = np.empty(len(a), bool)
    vis[ordem] = pr <= rep + folga
    return vis


def pintar(obs):
    vistas = {n: carregar(n) for n in ("frente", "lado", "costas")}
    P = np.concatenate([np.array([v.co for v in o.data.vertices]) for o in obs])
    N = np.concatenate([np.array([v.normal for v in o.data.vertices]) for o in obs])
    lo, hi = P.min(0), P.max(0)
    nomes = list(CLASSES)
    refs = np.array([c for n in nomes for c in CLASSES[n][0]])
    idx_ref = np.array([i for i, n in enumerate(nomes) for _ in CLASSES[n][0]])

    def amostra(vista, u, v):
        b, px = vistas[vista]["bbox"], vistas[vista]["px"]
        x = np.clip(np.round(b[0] + u * (b[2] - b[0])).astype(int), 0, px.shape[1] - 1)
        y = np.clip(np.round(b[1] + v * (b[3] - b[1])).astype(int), 0, px.shape[0] - 1)
        return px[y, x]

    vz = 1 - (P[:, 2] - lo[2]) / (hi[2] - lo[2])
    ux = (P[:, 0] - lo[0]) / (hi[0] - lo[0])
    uy = (P[:, 1] - lo[1]) / (hi[1] - lo[1])
    vis_f = _visivel(P[:, 0], P[:, 2], P[:, 1]) & (N[:, 1] < 0.35)
    vis_c = _visivel(P[:, 0], P[:, 2], P[:, 1], maior=True) & (N[:, 1] > -0.35)
    cor = np.zeros((len(P), 4))
    feito = np.zeros(len(P), bool)
    for vis, vista, u in ((vis_f, "frente", ux), (vis_c, "costas", 1 - ux), (np.ones(len(P), bool), "lado", uy)):
        m = vis & ~feito
        c = amostra(vista, u[m], vz[m])
        sat = c[:, :3].max(1) - c[:, :3].min(1)
        ok = (c[:, 3] > 0.5) & ~((sat < 0.07) & (c[:, :3].mean(1) > 0.5))   # cinza claro = sombra do chão
        idx = np.nonzero(m)[0][ok]
        cor[idx] = c[ok]
        feito[idx] = True
    # cor direta da ficha por vértice (sRGB → linear); sem cor: tom de pelo
    lin_cor = np.where(cor[:, :3] <= 0.04045, cor[:, :3] / 12.92, ((cor[:, :3] + 0.055) / 1.055) ** 2.4)
    if (~feito).any() and feito.any():
        from mathutils.kdtree import KDTree
        kd = KDTree(int(feito.sum()))
        for j, i in enumerate(np.nonzero(feito)[0]):
            kd.insert(P[i], int(i))
        kd.balance()
        for i in np.nonzero(~feito)[0]:
            lin_cor[i] = lin_cor[kd.find(P[i])[1]]
    ini = 0
    mat_cor = bpy.data.materials.new("pintura_ficha")
    mat_cor.use_nodes = True
    nt = mat_cor.node_tree
    vc = nt.nodes.new("ShaderNodeVertexColor")
    vc.layer_name = "cor"
    nt.links.new(vc.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
    nt.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.85
    for o in obs:
        me = o.data
        nv = len(me.vertices)
        ca = me.color_attributes.new("cor", "FLOAT_COLOR", "POINT")
        rgba = np.c_[lin_cor[ini:ini + nv], np.ones(nv)].astype(np.float32)
        ca.data.foreach_set("color", rgba.ravel())
        ini += nv
        me.materials.clear()
        me.materials.append(mat_cor)
    print(f"[v3] fonte: frente {int(vis_f.sum())}, costas {int((vis_c & ~vis_f).sum())}, sem cor {int((~feito).sum())}")
    return
    cls = np.full(len(P), nomes.index("pelo"))
    cls[feito] = idx_ref[np.argmin(((cor[feito, None, :3] - refs[None]) ** 2).sum(-1), axis=1)]
    print(f"[v3] fonte: frente {int((vis_f).sum())}, costas {int((vis_c & ~vis_f).sum())}, sem cor {int((~feito).sum())}")
    mats = []
    for n in nomes:
        _, c, emi = CLASSES[n]
        m = bpy.data.materials.new(f"m_{n}")
        m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = lin(c)
        b.inputs["Roughness"].default_value = 0.85
        if emi:
            b.inputs["Emission Color"].default_value = lin(c)
            b.inputs["Emission Strength"].default_value = emi
        mats.append(m)
    ini = 0
    for o in obs:
        me = o.data
        nv = len(me.vertices)
        cl = cls[ini:ini + nv].copy()
        ini += nv
        ed = np.array([e.vertices[:] for e in me.edges])
        for _ in range(4):                       # filtro de maioria pelos vizinhos
            cont = np.zeros((nv, len(nomes)))
            np.add.at(cont, (np.arange(nv), cl), 1.0)
            np.add.at(cont, (ed[:, 0], cl[ed[:, 1]]), 1.0)
            np.add.at(cont, (ed[:, 1], cl[ed[:, 0]]), 1.0)
            cl = cont.argmax(1)
        me.materials.clear()
        for m in mats:
            me.materials.append(m)
        for pgn in me.polygons:
            pgn.material_index = int(np.bincount(cl[list(pgn.vertices)], minlength=len(nomes)).argmax())
        print(f"[v3] {o.name}: " + ", ".join(f"{n} {int((cl == i).mean() * 100)}%" for i, n in enumerate(nomes)))


# ------------------------------------------------------------------ 5. rig
def marco(vs, zmin, zmax, xmin):
    """Centro (x, y) dos vértices de um lado (x > xmin) numa faixa de altura."""
    m = (vs[:, 2] >= zmin) & (vs[:, 2] < zmax) & (vs[:, 0] > xmin)
    return float(vs[m, 0].mean()), float(vs[m, 1].mean())


def rig(corpo, cranio):
    vs = np.array([v.co for v in corpo.data.vertices])
    pe = marco(vs, 0.1, 0.35, 0.15)
    canela = marco(vs, 0.45, 0.65, 0.15)
    joelho_x = (canela[0] + marco(vs, 0.9, 1.0, 0.15)[0]) / 2 if False else canela[0] - 0.04
    punho = marco(vs, 0.8, 1.05, 1.0)
    manopla = marco(vs, 1.3, 1.7, 0.9)
    braco = marco(vs, 1.95, 2.2, 0.85)
    print(f"[v3] marcos: pé {pe} canela {canela} punho {punho} manopla {manopla} braço {braco}")
    dado = bpy.data.armatures.new("GolemRig")
    arm = bpy.data.objects.new("GolemRig", dado)
    bpy.context.scene.collection.objects.link(arm)
    ativo(arm)
    bpy.ops.object.mode_set(mode="EDIT")
    eb = dado.edit_bones

    def osso(nome, a, b, pai=None, deform=True, conecta=False):
        o = eb.new(nome)
        o.head, o.tail = Vector(a), Vector(b)
        if pai:
            o.parent = eb[pai]
            o.use_connect = conecta
        o.use_deform = deform
        return o

    osso("raiz", (0, 0, 0), (0, 0, 0.3), deform=False)
    osso("quadril", (0, 0.02, 1.25), (0, 0.02, 1.62), "raiz")
    osso("barriga", (0, 0.02, 1.62), (0, 0.0, 2.0), "quadril", conecta=True)
    osso("peito", (0, 0.0, 2.0), (0, 0.0, 2.55), "barriga", conecta=True)
    osso("pescoco", (0, -0.05, 2.55), (0, -0.08, PESCOCO_Z - 0.02), "peito", conecta=True)
    osso("cabeca", (0, -0.1, PESCOCO_Z + 0.08), (0, -0.1, 3.35), "pescoco", deform=False)
    for s, l in ((1, "L"), (-1, "R")):
        osso(f"ombro.{l}", (0.22 * s, 0.0, 2.48), (0.78 * s, 0.0, 2.46), "peito")
        osso(f"braco.{l}", (0.82 * s, 0.0, 2.38), (braco[0] * s + 0.05 * s, 0.0, 1.88), f"ombro.{l}")
        osso(f"antebraco.{l}", (braco[0] * s + 0.05 * s, 0.0, 1.88), (manopla[0] * s, manopla[1], 1.1),
             f"braco.{l}", conecta=True)
        osso(f"mao.{l}", (manopla[0] * s, manopla[1], 1.1), (punho[0] * s, punho[1] - 0.05, 0.72),
             f"antebraco.{l}", conecta=True)
        osso(f"coxa.{l}", (0.3 * s, 0.0, 1.3), (joelho_x * s, -0.1, 0.82), "quadril")
        osso(f"canela.{l}", (joelho_x * s, -0.1, 0.82), (pe[0] * s, 0.0, 0.26), f"coxa.{l}", conecta=True)
        osso(f"pe.{l}", (pe[0] * s, 0.0, 0.26), (pe[0] * s, -0.36, 0.05), f"canela.{l}", conecta=True)
        osso(f"pe_ik.{l}", (pe[0] * s, 0.0, 0.26), (pe[0] * s, 0.0, 0.56), "raiz", deform=False)
        osso(f"polo.{l}", (joelho_x * s, -1.4, 0.85), (joelho_x * s, -1.4, 1.15), "raiz", deform=False)
    bpy.ops.object.mode_set(mode="POSE")
    for s, l in ((1, "L"), (-1, "R")):
        ik = arm.pose.bones[f"canela.{l}"].constraints.new("IK")
        ik.target, ik.subtarget = arm, f"pe_ik.{l}"
        ik.pole_target, ik.pole_subtarget = arm, f"polo.{l}"
        ik.pole_angle = math.radians(-90)
        ik.chain_count = 2
        cr = arm.pose.bones[f"pe.{l}"].constraints.new("COPY_ROTATION")
        cr.target, cr.subtarget = arm, f"pe_ik.{l}"
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"
    # pesos automáticos (heat) no corpo; crânio rígido no osso da cabeça
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    corpo.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    sem = [v for v in corpo.data.vertices if not v.groups]
    ossos = [(b.name, b.head_local.copy(), b.tail_local.copy()) for b in arm.data.bones if b.use_deform]
    for v in sem:
        def dist(o):
            a, b = o[1], o[2]
            ab = b - a
            t = max(0.0, min(1.0, (v.co - a).dot(ab) / ab.length_squared))
            return (v.co - (a + ab * t)).length
        nome = min(ossos, key=dist)[0]
        g = corpo.vertex_groups.get(nome) or corpo.vertex_groups.new(name=nome)
        g.add([v.index], 1.0, "REPLACE")
    print(f"[v3] pesos automáticos: {len(corpo.vertex_groups)} grupos; {len(sem)} vértices sem peso → osso mais perto")
    prender(cranio, arm, "cabeca")
    return arm


def prender(ob, arm, osso):
    b = arm.data.bones[osso]
    M = arm.matrix_world @ b.matrix_local @ Matrix.Translation((0, b.length, 0))
    mw = ob.matrix_world.copy()
    ob.parent, ob.parent_type, ob.parent_bone = arm, "BONE", osso
    ob.matrix_parent_inverse = M.inverted()
    ob.matrix_world = mw


# ------------------------------------------------------------------ 6. fumaça e pedras
def extras(arm):
    m_fum = bpy.data.materials.new("fumaca")
    m_fum.use_nodes = True
    b = m_fum.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = lin("#7057a8")
    b.inputs["Emission Color"].default_value = lin("#7057a8")
    b.inputs["Emission Strength"].default_value = 0.8
    for k in range(0):   # a fumaça vem pintada da ficha no pescoço; as curvas em laço ficavam artificiais
        cu = bpy.data.curves.new(f"fumaca{k}", "CURVE")
        cu.dimensions, cu.bevel_depth, cu.bevel_resolution = "3D", 0.035, 3
        sp = cu.splines.new("NURBS")
        sp.points.add(8)
        for i in range(9):
            t = i / 8
            a = math.radians(k * 120 + t * 200)
            r = 0.32 + 0.3 * t
            sp.points[i].co = (r * math.sin(a), -0.12 - r * math.cos(a) * 0.8, PESCOCO_Z - 0.08 + 0.55 * t, 1.0)
            sp.points[i].radius = 1.3 - 1.15 * t
        sp.use_endpoint_u, sp.order_u = True, 4
        ob = bpy.data.objects.new(f"fumaca{k}", cu)
        bpy.context.scene.collection.objects.link(ob)
        ob.data.materials.append(m_fum)
        prender(ob, arm, "pescoco")
    m_ped = bpy.data.materials.new("pedra")
    m_ped.use_nodes = True
    m_ped.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = lin("#a08a70")
    m_run = bpy.data.materials.new("runa")
    m_run.use_nodes = True
    br = m_run.node_tree.nodes["Principled BSDF"]
    br.inputs["Base Color"].default_value = lin("#ff9a1a")
    br.inputs["Emission Color"].default_value = lin("#ff9a1a")
    br.inputs["Emission Strength"].default_value = 0.9
    lugares = [((0.7, -0.25, 3.3), 0.16, True), ((-0.72, -0.2, 3.25), 0.14, True), ((0.45, -0.1, 3.62), 0.09, False),
               ((-0.42, -0.1, 3.66), 0.08, False), ((1.0, -0.15, 3.05), 0.08, False), ((-1.02, -0.1, 3.0), 0.1, True)]
    bpy.ops.object.mode_set(mode="OBJECT")
    ativo(arm)
    bpy.ops.object.mode_set(mode="EDIT")
    for i, (p, _, _) in enumerate(lugares):
        o = arm.data.edit_bones.new(f"pedra{i}")
        o.head, o.tail = Vector(p), Vector((p[0], p[1], p[2] + 0.2))
        o.parent = arm.data.edit_bones["peito"]
        o.use_deform = False
    bpy.ops.object.mode_set(mode="OBJECT")
    for i, (p, r, runa) in enumerate(lugares):
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
        rng = np.random.default_rng(i)
        for v in bm.verts:
            v.co = Vector((v.co.x * r * 1.6, v.co.y * r * 1.2, v.co.z * r * 2.0)) * (0.8 + 0.4 * rng.random())
        bm.transform(Matrix.Translation(p) @ Matrix.Rotation(0.4 * i, 4, "Z"))
        me = bpy.data.meshes.new(f"pedra{i}")
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(f"pedra{i}", me)
        bpy.context.scene.collection.objects.link(ob)
        me.materials.append(m_ped)
        prender(ob, arm, f"pedra{i}")
        if runa:
            bm = bmesh.new()
            bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=r * 0.45, radius2=r * 0.45, depth=0.02)
            bm.transform(Matrix.Translation((p[0], p[1] - r * 1.15, p[2])) @ Matrix.Rotation(math.pi / 2, 4, "X"))
            me = bpy.data.meshes.new(f"runa{i}")
            bm.to_mesh(me)
            bm.free()
            ob = bpy.data.objects.new(f"runa{i}", me)
            bpy.context.scene.collection.objects.link(ob)
            me.materials.append(m_run)
            prender(ob, arm, f"pedra{i}")


# ------------------------------------------------------------------ 7. renders
def cena(res):
    sc = bpy.context.scene
    motores = {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    sc.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in motores else "BLENDER_EEVEE_NEXT"
    sc.render.resolution_x = sc.render.resolution_y = res
    sc.view_settings.view_transform = "Standard"
    w = bpy.data.worlds.new("mundo")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.6, 0.59, 0.58, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.45
    sc.world = w
    for nome, en, rot in (("chave", 2.6, (42, 0, -35)), ("recorte", 1.6, (60, 0, 150))):
        d = bpy.data.lights.new(nome, "SUN")
        d.energy, d.angle = en, math.radians(6)
        o = bpy.data.objects.new(nome, d)
        o.rotation_euler = [math.radians(v) for v in rot]
        sc.collection.objects.link(o)
    d = bpy.data.cameras.new("cam")
    d.type = "ORTHO"
    cam = bpy.data.objects.new("cam", d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    return sc, cam


def vista(sc, cam, yaw, pitch, arq):
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    rot = Matrix.Rotation(math.radians(yaw), 4, "Z") @ Matrix.Rotation(math.radians(90 - pitch), 4, "X")
    inv = rot.to_3x3().inverted()
    pts = []
    for o in sc.objects:
        if o.type in ("MESH", "CURVE"):
            ev = o.evaluated_get(dg)
            pts += [inv @ (ev.matrix_world @ Vector(c)) for c in ev.bound_box]
    xs, ys, zs = [p.x for p in pts], [p.y for p in pts], [p.z for p in pts]
    cam.data.ortho_scale = max(max(xs) - min(xs), max(ys) - min(ys)) * 1.08
    cam.data.clip_end = 100
    c = Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, max(zs) + 10))
    cam.matrix_world = Matrix.Translation(rot.to_3x3() @ c) @ rot
    sc.render.filepath = arq
    bpy.ops.render.render(write_still=True)


def pose_teste(arm):
    pb = arm.pose.bones
    pb["braco.L"].rotation_euler.x = math.radians(35)
    pb["braco.R"].rotation_euler.x = math.radians(-30)
    pb["antebraco.L"].rotation_euler.x = math.radians(25)
    pb["pe_ik.L"].location = (0, 0.25, 0.25)      # osso aponta para +Z: (x, z, -y) no mundo → sobe 0,25 e avança 0,25
    pb["quadril"].location = (0, -0.08, 0)
    pb["peito"].rotation_euler.y = math.radians(-10)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", required=True)
    ap.add_argument("--glb", default="hy3d_mv.glb")
    ap.add_argument("--res", type=int, default=1200)
    a = ap.parse_args(argv)
    base = os.path.abspath(a.saida)
    corpo = importar(a.glb)
    limpar(corpo)
    cranio = separar_cranio(corpo)
    pintar([corpo, cranio])
    arm = rig(corpo, cranio)
    extras(arm)
    cranio_sobe = 0.1
    arm.pose.bones["cabeca"].location = (0, cranio_sobe, 0)   # o crânio flutua um pouco acima do pescoço
    sc, cam = cena(a.res)
    pasta = os.path.join(base, "previews", "v3_rig")
    os.makedirs(pasta, exist_ok=True)
    for nome, yaw, pitch in (("frente", 0, 6), ("lateral", -90, 6), ("tres_quartos", -35, 14)):
        vista(sc, cam, yaw, pitch, os.path.join(pasta, f"{nome}.png"))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(AQUI, "golem_v3.blend"))
    pose_teste(arm)
    vista(sc, cam, -35, 14, os.path.join(pasta, "pose_teste.png"))
    vista(sc, cam, -90, 6, os.path.join(pasta, "pose_teste_lateral.png"))
    print(f"[v3] corpo {len(corpo.data.vertices)} vértices, crânio {len(cranio.data.vertices)} vértices; salvo")


main()
