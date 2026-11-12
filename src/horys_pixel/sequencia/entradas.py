"""2.1 · Entradas do motor de sequência: render 3D (manifest.json), pasta de PNGs, grade (PNG + linhas × colunas),
vídeo (ffmpeg) ou atlas do Kiln. Todas viram a mesma coisa: lista de quadros RGBA uint8."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image


class ErroEntrada(ValueError):
    pass


def _rgba(im: Image.Image) -> np.ndarray:
    return np.array(im.convert("RGBA"), dtype=np.uint8)


def de_pasta(pasta) -> list[np.ndarray]:
    arqs = sorted(p for p in Path(pasta).iterdir() if p.suffix.lower() in (".png", ".webp", ".jpg", ".jpeg"))
    if not arqs:
        raise ErroEntrada(f"nenhuma imagem em {pasta}")
    return [_rgba(Image.open(p)) for p in arqs]


def fatiar_grade(imagem: np.ndarray, linhas: int, colunas: int) -> list[np.ndarray]:
    """Fatia em células iguais, da esquerda para a direita e de cima para baixo."""
    if linhas < 1 or colunas < 1:
        raise ErroEntrada("grade é [linhas, colunas], ambos >= 1")
    h, w = imagem.shape[:2]
    ch, cw = h // linhas, w // colunas
    if ch < 1 or cw < 1:
        raise ErroEntrada("grade maior que a imagem")
    return [imagem[r * ch:(r + 1) * ch, c * cw:(c + 1) * cw].copy() for r in range(linhas) for c in range(colunas)]


def de_grade(png, linhas: int, colunas: int) -> list[np.ndarray]:
    return fatiar_grade(_rgba(Image.open(png)), int(linhas), int(colunas))


def distancia_fundo(rgb: np.ndarray, cor_fundo: str = "auto", com_ref: bool = False):
    """Distância OKLab de cada pixel à cor do fundo ('auto' = mediana dos blocos 8×8 dos 4 cantos).
    com_ref=True devolve (distância, cor do fundo em OKLab)."""
    from ..motor import comum as C
    L = np.stack(C.oklab(rgb.reshape(-1, 3).astype(float)), -1).reshape(*rgb.shape[:2], 3)
    if cor_fundo == "auto":
        cantos = [L[:8, :8], L[:8, -8:], L[-8:, :8], L[-8:, -8:]]
        ref = np.median(np.concatenate([c.reshape(-1, 3) for c in cantos]), 0)
    else:
        ref = np.array(C.oklab(np.array(C.hex2rgb(cor_fundo), float)))
    d = np.linalg.norm(L - ref, axis=-1)
    return (d, ref) if com_ref else d


def achar_poses(imagem: np.ndarray, cor_fundo: str = "auto", tolerancia: float = 0.08, area_min: int = 64,
                juntar: int = 4, margem: int = 2, pequena: float = 0.15) -> list[tuple[int, int, int, int]]:
    """Caixas (x, y, w, h) das poses de uma prancha SEM grade rígida: componentes conectados do que não é fundo,
    com 'juntar' px de dilatação para unir partes soltas da mesma pose (arma, cauda, pé). Ordem de leitura: agrupa
    por linha visual (centro y) antes de ordenar por x, porque poses da mesma linha têm alturas diferentes."""
    from scipy import ndimage
    fig = (distancia_fundo(imagem[..., :3], cor_fundo) >= tolerancia) & (imagem[..., 3] >= 128)
    grupos = ndimage.binary_dilation(fig, iterations=juntar) if juntar > 0 else fig
    lab, _ = ndimage.label(grupos, structure=np.ones((3, 3)))
    h, w = fig.shape
    comps = []  # [x0, y0, x1, y1, area]
    for i, sl in enumerate(ndimage.find_objects(lab), 1):
        if sl is None:
            continue
        dentro = fig[sl] & (lab[sl] == i)
        area = int(dentro.sum())
        if area < area_min:
            continue
        ys, xs = np.nonzero(dentro)
        comps.append([sl[1].start + xs.min(), sl[0].start + ys.min(), sl[1].start + xs.max() + 1,
                      sl[0].start + ys.max() + 1, area])
    # Peças pequenas (faísca, raio, gota: < 'pequena' da maior) não viram pose: vão para a pose grande mais perto.
    # Dilatar mais junta faísca e pose, mas também junta duas poses vizinhas (medido numa prancha real do Codex).
    if comps:
        maior = max(c[4] for c in comps)
        grandes = [c for c in comps if c[4] >= maior * pequena]
        for c in comps:
            if c[4] >= maior * pequena:
                continue
            def vao(g):
                dx = max(g[0] - c[2], c[0] - g[2], 0)
                dy = max(g[1] - c[3], c[1] - g[3], 0)
                return dx * dx + dy * dy
            g = min(grandes, key=vao)
            g[0], g[1], g[2], g[3] = min(g[0], c[0]), min(g[1], c[1]), max(g[2], c[2]), max(g[3], c[3])
        comps = grandes
    caixas = []
    for x0, y0, x1, y1, _ in comps:
        y0, x0, y1, x1 = max(0, y0 - margem), max(0, x0 - margem), min(h, y1 + margem), min(w, x1 + margem)
        caixas.append((int(x0), int(y0), int(x1 - x0), int(y1 - y0)))
    if not caixas:
        raise ErroEntrada("nenhuma pose achada na prancha: ajuste cor_fundo ou a tolerância")
    if len(caixas) > 64:
        raise ErroEntrada(f"{len(caixas)} grupos na prancha (> 64): aumente area_min ou juntar")
    linhas: list[dict] = []
    for c in sorted(caixas, key=lambda c: c[1] + c[3] / 2):
        cy = c[1] + c[3] / 2
        perto = [li for li in linhas if abs(cy - li["cy"]) <= max(8, min(c[3], li["h"]) * 0.5)]
        if perto:
            li = min(perto, key=lambda li: abs(cy - li["cy"]))
            li["caixas"].append(c)
            li["cy"] = sum(b[1] + b[3] / 2 for b in li["caixas"]) / len(li["caixas"])
            li["h"] = sum(b[3] for b in li["caixas"]) / len(li["caixas"])
        else:
            linhas.append({"cy": cy, "h": c[3], "caixas": [c]})
    return [c for li in sorted(linhas, key=lambda li: li["cy"]) for c in sorted(li["caixas"], key=lambda c: c[0])]


def de_prancha(png, cor_fundo: str = "auto", tolerancia: float = 0.08, area_min: int = 64,
               juntar: int = 4) -> list[np.ndarray]:
    """Prancha de poses bagunçada (a que o ChatGPT/Codex gera): um quadro por pose, recortado COM o fundo em volta
    (o fundo.py tira depois, por célula). Para grade regular, use linhas × colunas."""
    im = _rgba(Image.open(png))
    return [im[y:y + h, x:x + w].copy() for x, y, w, h in achar_poses(im, cor_fundo, tolerancia, area_min, juntar)]


def de_video(video, fps: float | None = None) -> list[np.ndarray]:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise ErroEntrada("vídeo exige o ffmpeg no PATH (instale o ffmpeg ou entregue uma pasta de PNGs/uma grade)")
    with tempfile.TemporaryDirectory() as tmp:
        cmd = [exe, "-y", "-loglevel", "error", "-i", str(video)]
        if fps:
            cmd += ["-vf", f"fps={fps}"]
        cmd += [str(Path(tmp) / "%05d.png")]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise ErroEntrada("ffmpeg falhou: " + (r.stderr or "")[-400:])
        return de_pasta(tmp)


def de_atlas(json_path) -> list[np.ndarray]:
    from .. import kiln
    return [q.copy() for q in kiln.ler_atlas(json_path).quadros]


def eh_manifesto(caminho) -> bool:
    """True se 'caminho' é um manifest.json de render 3D (Blender/Blockbench: experimentos/animacao-3d/README.md),
    ou uma pasta que tem um."""
    p = Path(caminho)
    if p.is_dir():
        p = p / "manifest.json"
    if p.suffix.lower() != ".json" or not p.is_file():
        return False
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(d, dict) and "versao" in d and isinstance(d.get("quadros"), list)


def ler_manifesto(caminho) -> dict:
    """Lê o manifest.json do render 3D e valida o contrato: {versao, fonte, acao, fps, canvas [W,H], pivo [x,y],
    camera {...}, loop, quadros [png...]}. Devolve o dicionário com 'pasta' (Path) acrescentada."""
    p = Path(caminho)
    if p.is_dir():
        p = p / "manifest.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ErroEntrada(f"manifesto ilegível {p}: {e}")
    if int(d.get("versao", 0)) != 1:
        raise ErroEntrada(f"manifesto {p}: versao {d.get('versao')!r} não suportada (esperado 1)")
    for chave in ("canvas", "pivo", "quadros"):
        if chave not in d:
            raise ErroEntrada(f"manifesto {p}: falta '{chave}'")
    if not d["quadros"]:
        raise ErroEntrada(f"manifesto {p}: lista 'quadros' vazia")
    d["pasta"] = p.parent
    return d


def de_render3d(caminho) -> list[np.ndarray]:
    """Quadros de um render 3D com câmera fixa. Recusa canvas diferente do declarado: câmera fixa quer dizer o mesmo
    tamanho em todos (o motor não deve 'consertar' isso redimensionando)."""
    m = ler_manifesto(caminho)
    W, H = int(m["canvas"][0]), int(m["canvas"][1])
    out = []
    for nome in m["quadros"]:
        arq = m["pasta"] / nome
        if not arq.is_file():
            raise ErroEntrada(f"quadro do manifesto não encontrado: {arq}")
        q = _rgba(Image.open(arq))
        if q.shape[:2] != (H, W):
            raise ErroEntrada(f"{arq.name}: {q.shape[1]}×{q.shape[0]}, o manifesto diz {W}×{H} (câmera mudou?)")
        out.append(q)
    return out


def carregar(fonte, linhas: int | None = None, colunas: int | None = None, fps: float | None = None,
             prancha: bool = False, cor_fundo: str = "auto") -> list[np.ndarray]:
    """Decide pela forma da fonte: manifest.json (ou pasta com ele) → render 3D; diretório → pasta; .json → atlas do
    Kiln; vídeo → ffmpeg; PNG com prancha=True → poses por componentes; PNG com grade → fatias; PNG sozinho → um
    quadro."""
    p = Path(fonte)
    if not p.exists():
        raise ErroEntrada(f"fonte não encontrada: {p}")
    if eh_manifesto(p):
        return de_render3d(p)
    if p.is_dir():
        return de_pasta(p)
    suf = p.suffix.lower()
    if suf == ".json":
        return de_atlas(p)
    if suf in (".mp4", ".mov", ".webm", ".mkv", ".avi", ".gif"):
        return de_video(p, fps)
    if prancha:
        return de_prancha(p, cor_fundo)
    if linhas and colunas:
        return de_grade(p, linhas, colunas)
    return [_rgba(Image.open(p))]
