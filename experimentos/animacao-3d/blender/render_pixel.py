"""Render determinístico de ações 3D para pixel art (caminho nativo A3).

Uso (headless, nunca salva o .blend nem mexe nas preferências do usuário):

    blender -b cena.blend -P render_pixel.py -- --config cfg.json

Para cada ação listada no config, renderiza quadro a quadro em
<saida>/<acao>/0000.png ... e escreve <saida>/<acao>/manifest.json
(contrato versao 1, lido pelo loader render3d do horys_pixel.sequencia).

Regras fixas: câmera ortográfica com pitch/yaw fixos, enquadrada UMA vez pelo
bbox da ação inteira (nunca por quadro); Eevee; fundo transparente; filtro 0 /
sem AA; gerência de cor Standard; luz de mundo chapada (amiga do cel).
"""

import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector
from bpy_extras.object_utils import world_to_camera_view

PADRAO = {
    "saida": "../renders",
    "resolucao": [256, 256],
    "pitch": 32.0,
    "yaw": 0.0,
    "margem": 0.08,
    "fps": None,
    "loop": True,
    "raiz": None,
    "objetos": None,
    "luz_mundo": 1.0,
    "sol": {"forca": 2.0, "angulo": [50.0, 0.0, 30.0]},
    "acoes": [],
}


def ler_config():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="render_pixel.py")
    ap.add_argument("--config", required=True)
    args = ap.parse_args(argv)
    with open(args.config, encoding="utf-8") as f:
        cfg = dict(PADRAO, **json.load(f))
    base = os.path.dirname(os.path.abspath(args.config))
    cfg["saida"] = os.path.normpath(os.path.join(base, cfg["saida"]))
    if not cfg["acoes"]:
        sys.exit("config sem 'acoes'")
    return cfg


def preparar_render(cena, cfg):
    r = cena.render
    motores = {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    r.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in motores else "BLENDER_EEVEE_NEXT"
    r.resolution_x, r.resolution_y = cfg["resolucao"]
    r.resolution_percentage = 100
    r.pixel_aspect_x = r.pixel_aspect_y = 1.0
    r.film_transparent = True
    r.filter_size = 0.0
    r.use_motion_blur = False
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGBA"
    r.image_settings.color_depth = "8"
    ee = cena.eevee
    for nome, valor in (("taa_render_samples", 1), ("use_gtao", False), ("use_bloom", False),
                        ("use_ssr", False), ("use_shadows", True), ("use_raytracing", False)):
        if hasattr(ee, nome):
            setattr(ee, nome, valor)
    vs = cena.view_settings
    vs.view_transform = "Standard"
    vs.look = "None"
    vs.exposure = 0.0
    vs.gamma = 1.0
    cena.display_settings.display_device = "sRGB"


def preparar_luz(cena, cfg):
    """Mundo chapado + um sol fixo. Só dados temporários; o .blend não é salvo."""
    mundo = bpy.data.worlds.new("_horys_mundo")
    mundo.use_nodes = True
    fundo = mundo.node_tree.nodes.get("Background")
    fundo.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    fundo.inputs["Strength"].default_value = float(cfg["luz_mundo"])
    cena.world = mundo
    sol = cfg.get("sol")
    if sol:
        dado = bpy.data.lights.new("_horys_sol", type="SUN")
        dado.energy = float(sol["forca"])
        obj = bpy.data.objects.new("_horys_sol", dado)
        obj.rotation_euler = [math.radians(a) for a in sol["angulo"]]
        cena.collection.objects.link(obj)


def objetos_alvo(cena, cfg):
    if cfg["objetos"]:
        return [cena.objects[n] for n in cfg["objetos"]]
    return [o for o in cena.objects if o.type == "MESH" and not o.hide_render]


def achar_raiz(cena, cfg):
    if cfg["raiz"]:
        return cena.objects[cfg["raiz"]]
    arm = [o for o in cena.objects if o.type == "ARMATURE"]
    if not arm:
        sys.exit("sem armature: defina 'raiz' no config")
    return arm[0]


def aplicar_acao(raiz, nome_acao):
    acao = bpy.data.actions.get(nome_acao)
    if acao is None:
        sys.exit(f"ação não encontrada: {nome_acao}")
    ad = raiz.animation_data or raiz.animation_data_create()
    ad.action = acao
    if hasattr(ad, "action_slot") and getattr(acao, "slots", None) and ad.action_slot is None:
        ad.action_slot = acao.slots[0]
    for trilha in ad.nla_tracks:
        trilha.mute = True
    return acao


def quadros_da_acao(cena, acao, item):
    ini, fim = item.get("intervalo") or [int(acao.frame_range[0]), int(acao.frame_range[1])]
    passo = max(1, int(item.get("passo", 1)))
    fim_excl = fim if item.get("loop", True) else fim + 1  # loop: último == primeiro
    return list(range(int(ini), int(fim_excl), passo)) or [int(ini)]


def pontos_mundo(cena, objs):
    deps = bpy.context.evaluated_depsgraph_get()
    pts = []
    for o in objs:
        ev = o.evaluated_get(deps)
        pts.extend(ev.matrix_world @ Vector(c) for c in ev.bound_box)
    return pts


def montar_camera(cena, cfg):
    dado = bpy.data.cameras.new("_horys_cam")
    dado.type = "ORTHO"
    cam = bpy.data.objects.new("_horys_cam", dado)
    cena.collection.objects.link(cam)
    # Yaw 0 olha para +Y (vê a frente de um modelo virado para -Y), inclinada 'pitch' graus para baixo.
    rot = Matrix.Rotation(math.radians(cfg["yaw"]), 4, "Z") @ Matrix.Rotation(math.radians(90.0 - cfg["pitch"]), 4, "X")
    cam.matrix_world = rot
    cena.camera = cam
    return cam


def enquadrar(cena, cam, pts, cfg):
    """Enquadra uma vez pelo bbox de TODOS os quadros da ação."""
    rot = cam.matrix_world.to_3x3()
    inv = rot.inverted()
    loc = [inv @ p for p in pts]
    xs = [p.x for p in loc]
    ys = [p.y for p in loc]
    zs = [p.z for p in loc]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    w, h = cfg["resolucao"]
    lado = max(max(xs) - min(xs), (max(ys) - min(ys)) * w / h) * (1 + 2 * cfg["margem"])
    cam.data.ortho_scale = max(lado, 1e-3)
    dist = (max(zs) - min(zs)) + 10.0
    cam.data.clip_start, cam.data.clip_end = 0.01, dist * 2 + 10.0
    cam.matrix_world = Matrix.Translation(rot @ Vector((cx, cy, max(zs) + 5.0))) @ rot.to_4x4()
    return cam.data.ortho_scale


def pivo_px(cena, cam, raiz, quadro, cfg):
    cena.frame_set(quadro)
    origem = raiz.matrix_world.translation.copy()
    origem.z = 0.0  # origem da raiz projetada no chão
    co = world_to_camera_view(cena, cam, origem)
    w, h = cfg["resolucao"]
    return [round(co.x * w), round((1.0 - co.y) * h)]


def renderizar_acao(cena, cam, raiz, objs, item, cfg):
    nome = item["nome"]
    acao = aplicar_acao(raiz, item.get("acao", nome))
    quadros = quadros_da_acao(cena, acao, item)
    pts = []
    for q in quadros:
        cena.frame_set(q)
        pts.extend(pontos_mundo(cena, objs))
    escala = enquadrar(cena, cam, pts, cfg)
    pasta = os.path.join(cfg["saida"], nome)
    os.makedirs(pasta, exist_ok=True)
    arquivos = []
    for i, q in enumerate(quadros):
        cena.frame_set(q)
        arq = f"{i:04d}.png"
        cena.render.filepath = os.path.join(pasta, arq)
        bpy.ops.render.render(write_still=True)
        arquivos.append(arq)
    fps_cena = cena.render.fps / cena.render.fps_base
    passo = max(1, int(item.get("passo", 1)))
    fps = item.get("fps") or cfg["fps"] or round(fps_cena / passo, 3)
    manifesto = {
        "versao": 1,
        "fonte": "blender",
        "acao": nome,
        "fps": fps,
        "canvas": list(cfg["resolucao"]),
        "pivo": pivo_px(cena, cam, raiz, quadros[0], cfg),
        "camera": {"pitch": cfg["pitch"], "yaw": cfg["yaw"], "ortho_scale": round(escala, 6)},
        "loop": bool(item.get("loop", cfg["loop"])),
        "quadros": arquivos,
    }
    with open(os.path.join(pasta, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifesto, f, ensure_ascii=False, indent=2)
    print(f"[render_pixel] {nome}: {len(arquivos)} quadros -> {pasta}")


def main():
    cfg = ler_config()
    cena = bpy.context.scene
    preparar_render(cena, cfg)
    preparar_luz(cena, cfg)
    raiz = achar_raiz(cena, cfg)
    objs = objetos_alvo(cena, cfg)
    cam = montar_camera(cena, cfg)
    for item in cfg["acoes"]:
        renderizar_acao(cena, cam, raiz, objs, item if isinstance(item, dict) else {"nome": item}, cfg)
    # Sem bpy.ops.wm.save_*: o .blend e as preferências ficam intactos.


if __name__ == "__main__":
    main()
