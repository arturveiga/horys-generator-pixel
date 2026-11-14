"""Monta a entrega de um asset: uma folha PNG por estado (quadros na horizontal, como no Tiny), o JSON
(formato json-array do Aseprite + bloco "horys") e um GIF de prévia por estado (3x, nearest)."""
import json
import os

import numpy as np
from PIL import Image


def montar(quadros_por_estado, receita, saida, nome):
    os.makedirs(saida, exist_ok=True)
    W, H = receita.QUADRO
    arquivos, frames_json, tags = {}, [], []
    idx = 0
    for estado, quadros in quadros_por_estado.items():
        cfg = receita.ESTADOS[estado]
        folha = np.concatenate(quadros, axis=1)
        caminho = os.path.join(saida, f"{nome}_{estado}.png")
        Image.fromarray(folha).save(caminho)
        arquivos[f"folha {estado}"] = caminho
        for i in range(len(quadros)):
            frames_json.append({"filename": f"{nome}_{estado} {i}.png", "frame": {"x": i * W, "y": 0, "w": W, "h": H},
                                "duration": cfg.get("ms", 100), "sheet": os.path.basename(caminho)})
        tags.append({"name": estado, "from": idx, "to": idx + len(quadros) - 1, "direction": "forward"})
        idx += len(quadros)
        # GIF de prévia (3x) sobre fundo neutro
        gif = []
        for q in quadros:
            base = Image.new("RGBA", (W, H), (138, 146, 144, 255))
            base.alpha_composite(Image.fromarray(q))
            gif.append(base.convert("RGB").resize((W * 3, H * 3), Image.NEAREST))
        g = os.path.join(saida, f"{nome}_{estado}.gif")
        gif[0].save(g, save_all=True, append_images=gif[1:], duration=cfg.get("ms", 100), loop=0)
        arquivos[f"gif {estado}"] = g
    meta = {"frames": frames_json,
            "meta": {"app": "horys-pixel-liso/motor.py", "size": {"w": W, "h": H}, "frameTags": tags},
            "horys": {"estilo": "horys-pixel-liso", "paleta": "v0.1", "pivo": list(getattr(receita, "PIVO", (W // 2, H - 1))),
                      "eventos": getattr(receita, "EVENTOS", {}), "estados": receita.ESTADOS}}
    j = os.path.join(saida, f"{nome}.json")
    with open(j, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    arquivos["json"] = j
    return arquivos
