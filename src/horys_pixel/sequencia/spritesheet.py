"""Folha de sprites para engine (Godot 4): PNG em tira horizontal + JSON no formato "hash" do Aseprite (o que os
importadores de Godot e o próprio Aseprite leem), com durações, tag do estado e pivô. Mais um GIF de prévia."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image


def salvar(quadros: list[np.ndarray], pasta, nome: str, ms: int | list[int] = 125, estado: str | None = None,
           pivo: tuple[float, float] | None = None, loop: bool = True, gif: bool = True) -> dict:
    """Grava <pasta>/<nome>.png, <nome>.json e (se 'gif') <nome>.gif. 'ms' = duração única ou uma por quadro.
    Recusa canvas diferente entre quadros (a folha não redimensiona nada). Devolve os caminhos."""
    if not quadros:
        raise ValueError("nenhum quadro para a folha")
    formas = {q.shape for q in quadros}
    if len(formas) != 1:
        raise ValueError(f"quadros com tamanhos diferentes: {sorted(formas)}")
    h, w = quadros[0].shape[:2]
    n = len(quadros)
    duracoes = [int(ms)] * n if isinstance(ms, (int, float)) else [int(x) for x in ms]
    if len(duracoes) != n:
        raise ValueError(f"{len(duracoes)} durações para {n} quadros")
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    tira = np.concatenate(quadros, axis=1)
    png = pasta / f"{nome}.png"
    Image.fromarray(tira, "RGBA").save(png)
    frames = {f"{nome} {i}.png": {"frame": {"x": i * w, "y": 0, "w": w, "h": h}, "rotated": False, "trimmed": False,
                                  "spriteSourceSize": {"x": 0, "y": 0, "w": w, "h": h},
                                  "sourceSize": {"w": w, "h": h}, "duration": duracoes[i]} for i in range(n)}
    meta = {"app": "horys-pixel", "version": "1", "image": png.name, "format": "RGBA8888",
            "size": {"w": w * n, "h": h}, "scale": "1",
            "frameTags": [{"name": estado or nome, "from": 0, "to": n - 1,
                           "direction": "forward" if loop else "forward", "repeat": "0" if loop else "1"}],
            "horys": {"pivo": list(pivo) if pivo else [w / 2, h], "loop": loop}}
    js = pasta / f"{nome}.json"
    js.write_text(json.dumps({"frames": frames, "meta": meta}, ensure_ascii=False, indent=1), encoding="utf-8")
    out = {"png": str(png), "json": str(js)}
    if gif:
        g = pasta / f"{nome}.gif"
        ims = [Image.fromarray(q, "RGBA") for q in quadros]
        ims[0].save(g, save_all=True, append_images=ims[1:], duration=duracoes, loop=0 if loop else 1,
                    disposal=2)
        out["gif"] = str(g)
    return out
