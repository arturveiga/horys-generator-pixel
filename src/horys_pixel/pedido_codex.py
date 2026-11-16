"""Pedidos prontos ao Codex (image_gen): master, vestir, vista e pose ("A ÚNICA MUDANÇA").

perfeicao.md, seção 13, item C3. A regra-mãe é que o agente não inventa forma: a forma vem de uma imagem do Codex
pedida do jeito que já funcionou (pixel art no tamanho final, simples, paleta fixa, fundo chapado de cor-chave,
todas as vistas numa imagem só) e lida depois NA GRADE (pele.ler_master ou pele.vestir).

Modos:
- master: um conceito (do Artur ou do Codex) vira a folha de vistas em pixel art no tamanho final.
- vestir: a base 1x (vistas lado a lado) vai ampliada sobre a cor-chave + "A ÚNICA MUDANÇA: vista esta figura
  como <ficha>"; a volta é relida na grade da base (pele.vestir).
- vista: desenhar a vista que falta AO LADO do master aprovado, na mesma imagem e na mesma grade.
- pose: "reproduza a imagem anexa; A ÚNICA MUDANÇA: <pose>" sobre um quadro aprovado; relida na grade dele.

Ideias do agent-sprite-forge (pixel looks e ask-pose/ask-view, MIT), reimplementadas. O texto ao modelo de imagem
vai em inglês (é o que ele segue melhor); o resto em português.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image

MODOS = ("master", "vestir", "vista", "pose")
VISTAS_PADRAO = ("front (facing the camera)", "right side (facing right)", "back (facing away)")

_REGRAS = """Rules for the image:
- Real pixel art: every sprite pixel is ONE uniform square block of the same size everywhere in the image. No
  anti-aliasing, no blur, no gradients, no dithering, no soft shadows, no glow halos, no sub-pixel detail.
- Solid flat background {chave} everywhere outside the figures (no floor, no shadow, no vignette, no grid lines,
  no text, no labels, no frame).
- 1-pixel dark outline ({contorno}) around every figure.
- Use ONLY these colours: {paleta}. 2 to 3 tones per material, one light from the top-left.
- Nothing smaller than 2x2 sprite pixels: drop tiny panels, screws, runes and thin lines; keep big readable masses.
- Top-down 3/4 game camera (looking slightly down), the same for every figure."""


def _fmt_regras(chave: str, paleta: list[str]) -> str:
    contorno = paleta[0] if paleta else "#141427"
    return _REGRAS.format(chave=chave, contorno=contorno, paleta=", ".join(paleta) if paleta else "a small palette")


def prompt_master(ficha: str, *, altura: int, paleta: list[str], chave: str = "#ff00ff",
                  vistas: tuple[str, ...] | list[str] = VISTAS_PADRAO, extras: list[str] | None = None,
                  com_conceito: bool = True) -> str:
    """Folha de vistas em pixel art no tamanho final (o pedido que deu 70 → 84 no gorila e o da virada do pirata)."""
    n = len(vistas)
    lista = "\n".join(f"  {i + 1}. {v}" for i, v in enumerate(vistas))
    itens = ""
    if extras:
        itens = "\nAfter the views, to the right and on the same ground line, also draw as separate figures:\n" + \
                "\n".join(f"  - {e}" for e in extras)
    origem = ("The attached image is the design reference (concept art). Keep its design, proportions, colours and "
              "silhouette, but SIMPLIFY it for a small game sprite.\n" if com_conceito else "")
    return f"""Use your image generation tool to create exactly ONE image. Do not write code, do not edit files.

{origem}Character: {ficha}

Draw a pixel-art sprite turnaround of this character: {n} views side by side, left to right, with clear empty
space between them, all standing on the SAME horizontal ground line and all exactly the SAME height:
{lista}{itens}
Each figure is {altura} sprite pixels tall (head/horns to feet). Wide image, figures centred vertically.

{_fmt_regras(chave, paleta)}"""


def prompt_vestir(ficha: str, *, paleta: list[str], chave: str = "#ff00ff") -> str:
    return f"""Use your image generation tool to create exactly ONE image. Do not write code, do not edit files.

The attached image is a pixel-art base body shown in several views on a {chave} background.
Reproduce the attached image EXACTLY: same canvas, same pixel grid and pixel size, same figures in the same places,
same poses, same height, same ground line, same background.
THE ONLY CHANGE: dress each figure as {ficha}. Clothes, hair and gear go ON TOP of the body, inside or slightly
around its silhouette; every view must show the same outfit from its own angle.

{_fmt_regras(chave, paleta)}"""


def prompt_vista(vista: str, *, paleta: list[str], chave: str = "#ff00ff") -> str:
    return f"""Use your image generation tool to create exactly ONE image. Do not write code, do not edit files.

The attached image is an approved pixel-art sprite on a {chave} background.
Reproduce the attached image EXACTLY (same canvas, pixel grid, pixel size and figures) and THE ONLY CHANGE: add,
to the right of the existing figures and on the same ground line, a NEW figure of the same character seen from the
{vista}, exactly as tall as the others, same colours, same outfit.

{_fmt_regras(chave, paleta)}"""


def prompt_pose(pose: str, *, paleta: list[str], chave: str = "#ff00ff") -> str:
    return f"""Use your image generation tool to create exactly ONE image. Do not write code, do not edit files.

The attached image is an approved pixel-art sprite on a {chave} background.
Reproduce the attached image EXACTLY (same canvas, pixel grid, pixel size, character, colours and position of the
feet). THE ONLY CHANGE: {pose}. Body parts that do not take part in this change stay identical, pixel for pixel.

{_fmt_regras(chave, paleta)}"""


def ampliar_sobre_chave(rgba: np.ndarray, *, escala: int = 12, chave: str = "#ff00ff", margem: int = 6) -> Image.Image:
    """Folha 1x → anexo do Codex: vizinho mais próximo × escala, fundo chapado de cor-chave, margem em pixels 1x."""
    from .pele import hex_rgb
    h, w = rgba.shape[:2]
    fundo = np.zeros((h + 2 * margem, w + 2 * margem, 3), np.uint8)
    fundo[:] = hex_rgb(chave)
    a = rgba[..., 3:4].astype(np.float64) / 255.0 if rgba.shape[-1] == 4 else np.ones((h, w, 1))
    fundo[margem:margem + h, margem:margem + w] = np.rint(
        rgba[..., :3] * a + fundo[margem:margem + h, margem:margem + w] * (1 - a)).astype(np.uint8)
    return Image.fromarray(fundo).resize(((w + 2 * margem) * escala, (h + 2 * margem) * escala), Image.NEAREST)


def montar_prompt(modo: str, *, ficha: str = "", altura: int = 48, paleta: list[str] | None = None,
                  chave: str = "#ff00ff", vistas: list[str] | None = None, extras: list[str] | None = None,
                  vista: str = "", pose: str = "", com_conceito: bool = True) -> str:
    paleta = list(paleta or [])
    if modo == "master":
        if not ficha:
            raise ValueError("master: passe a 'ficha' (quem é, silhueta, cores, o que não pode ter)")
        return prompt_master(ficha, altura=altura, paleta=paleta, chave=chave, vistas=tuple(vistas or VISTAS_PADRAO),
                             extras=extras, com_conceito=com_conceito)
    if modo == "vestir":
        if not ficha:
            raise ValueError("vestir: passe a 'ficha' da roupa")
        return prompt_vestir(ficha, paleta=paleta, chave=chave)
    if modo == "vista":
        if not vista:
            raise ValueError("vista: diga qual vista falta (ex.: 'left side (facing left)')")
        return prompt_vista(vista, paleta=paleta, chave=chave)
    if modo == "pose":
        if not pose:
            raise ValueError("pose: diga a mudança (ex.: 'the right arm raises the sword above the head')")
        return prompt_pose(pose, paleta=paleta, chave=chave)
    raise ValueError(f"modo '{modo}' inválido: use {', '.join(MODOS)}")


@dataclass
class Pedido:
    pasta: Path
    prompt: Path
    anexos: list[Path]
    tentativas: list[Path] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)


def preparar(pasta: str | Path, modo: str, *, imagem: str | None = None, escala: int = 12, chave: str = "#ff00ff",
             **kw) -> Pedido:
    """Grava prompt.md e o anexo (no vestir/vista/pose a imagem 1x vai ampliada sobre a chave) em <pasta>."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    texto = montar_prompt(modo, chave=chave, **kw)
    pr = pasta / "prompt.md"
    pr.write_text(texto, encoding="utf-8")
    anexos: list[Path] = []
    if imagem:
        im = Image.open(imagem)
        if modo == "master":
            anexos.append(Path(imagem))
        else:
            rgba = np.asarray(im.convert("RGBA"))
            if max(rgba.shape[:2]) > 256:
                raise ValueError(f"{modo}: a imagem deve ser a folha 1x (recebi {rgba.shape[1]}x{rgba.shape[0]})")
            amp = pasta / "anexo.png"
            ampliar_sobre_chave(rgba, escala=escala, chave=chave).save(amp)
            anexos.append(amp)
    elif modo != "master":
        raise ValueError(f"{modo}: passe a 'imagem' 1x aprovada")
    (pasta / "pedido.json").write_text(json.dumps({"modo": modo, "chave": chave, "escala": escala,
                                                   "anexos": [str(a) for a in anexos], **{k: v for k, v in kw.items()}},
                                                  ensure_ascii=False, indent=2), encoding="utf-8")
    return Pedido(pasta, pr, anexos)


def gerar(pedido: Pedido, n: int = 3, timeout: int = 1800) -> Pedido:
    """Roda o Codex n vezes (uma imagem por chamada) e copia as imagens para <pasta>/tentativa_NN.png.
    Tentativa ruim se descarta, não se conserta (perfeicao.md F2)."""
    k = len(list(pedido.pasta.glob("tentativa_*.png")))
    for i in range(n):
        sub = pedido.pasta / f"_codex_{k + i + 1:02d}"
        cmd = [sys.executable, "-m", "horys_pixel.motor.conceito", "gerar", "--prompt", str(pedido.prompt),
               "--saida", str(sub)]
        for a in pedido.anexos:
            cmd += ["--img", str(a)]
        t0 = time.time()
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                           env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        imgs = sorted(sub.glob("conceito_*.png"))
        pedido.logs.append(f"tentativa {k + i + 1}: código {r.returncode}, {time.time() - t0:.0f} s, "
                           f"{len(imgs)} imagem(ns)")
        if imgs:
            dst = pedido.pasta / f"tentativa_{k + i + 1:02d}.png"
            dst.write_bytes(imgs[-1].read_bytes())
            pedido.tentativas.append(dst)
    return pedido
