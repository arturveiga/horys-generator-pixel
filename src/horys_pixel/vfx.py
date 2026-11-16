"""VFX pelo pixelfx, recoloridos pela rampa de um personagem (perfeicao.md, 2.9 e C8).

Crédito: os efeitos são do pixelfx (https://github.com/patch-gg/pixelfx), Copyright (c) 2026 Patch e
Copyright (c) 2026 Hugo Duprez, licença MIT (com partes adaptadas de Sprite Fusion e Hollow Crown; ver o NOTICE.md
do pixelfx). Nada do pixelfx é copiado para cá: o horys chama a linha de comando dele (`node tools/list.mjs` e
`node tools/render.mjs <id> --sheet`) num clone local e só lê a folha PNG + JSON que ela grava. O crédito vai também
no JSON de cada VFX gerado (meta.horys.credito).

Onde fica o pixelfx: preferência "pixelfx" (pasta do clone), variável PIXELFX ou D:\\pixelfx. O node: preferência
"node", variável NODE ou o `node` do PATH (Node 18 ou mais novo).

Fluxo de gerar(): render do pixelfx (rampa passada como `palette`, fundo transparente) -> amostra N quadros com as
durações somadas -> recolore por luminância na rampa (só cores da rampa, alfa binário) -> recorta no tamanho ->
grava tira PNG + JSON (formato do Aseprite, durações em ms) + prévia ampliada.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image

from . import config

PIXELFX_PADRAO = r"D:\pixelfx"
CREDITO = ("pixelfx (https://github.com/patch-gg/pixelfx), Copyright (c) 2026 Patch e Copyright (c) 2026 "
           "Hugo Duprez, licença MIT")
_ID = re.compile(r"^[a-z0-9][a-z0-9-]*/[a-z0-9][a-z0-9-]*$")
_LINHA = re.compile(r"^(\S+/\S+)\s+(loop|once)\s+([\d.]+)s\s+(\d+)x(\d+)\s+(actor\s+)?(.*)$")


class ErroVfx(Exception):
    """Falha ao achar ou rodar o pixelfx, ou parâmetro inválido (mensagem curta, em português)."""


# ---------------------------------------------------------------- onde estão o node e o pixelfx

def achar_pixelfx() -> Path | None:
    for c in (config.preferencias().get("pixelfx"), os.environ.get("PIXELFX"), PIXELFX_PADRAO):
        if c and (Path(c) / "tools" / "render.mjs").is_file():
            return Path(c)
    return None


def achar_node() -> str | None:
    for c in (config.preferencias().get("node"), os.environ.get("NODE")):
        if c and Path(c).is_file():
            return str(c)
    return shutil.which("node")


def _rodar(args: list[str], timeout: int = 300) -> str:
    node, raiz = achar_node(), achar_pixelfx()
    if not node:
        raise ErroVfx("node não encontrado (instale o Node 18+ ou grave a preferência 'node')")
    if not raiz:
        raise ErroVfx(f"pixelfx não encontrado (clone em {PIXELFX_PADRAO} ou grave a preferência 'pixelfx')")
    try:
        r = subprocess.run([node, *args], cwd=raiz, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        raise ErroVfx(f"pixelfx não respondeu em {timeout} s")
    if r.returncode != 0:
        erro = (r.stderr or r.stdout).strip().splitlines()
        raise ErroVfx("pixelfx falhou: " + (erro[0] if erro else f"código {r.returncode}"))
    return r.stdout


# ---------------------------------------------------------------- lista

_cache_lista: list[dict] | None = None


def ler_lista(saida: str) -> list[dict]:
    """Interpreta a saída de `node tools/list.mjs` (uma linha por efeito)."""
    efeitos = []
    for linha in saida.splitlines():
        m = _LINHA.match(linha.strip())
        if not m:
            continue
        efeitos.append({"id": m[1], "categoria": m[1].split("/")[0], "loop": m[2] == "loop",
                        "duracao_s": float(m[3]), "tamanho": [int(m[4]), int(m[5])],
                        "com_boneco": bool(m[6]), "descricao": m[7].strip()})
    return efeitos


def listar(filtro: str | None = None) -> list[dict]:
    """Efeitos do pixelfx. filtro: palavras (todas precisam aparecer no id ou na descrição)."""
    global _cache_lista
    if _cache_lista is None:
        _cache_lista = ler_lista(_rodar(["tools/list.mjs"], timeout=120))
        if not _cache_lista:
            raise ErroVfx("pixelfx não listou nenhum efeito")
    palavras = (filtro or "").lower().split()
    return [e for e in _cache_lista
            if all(p in f"{e['id']} {e['descricao']}".lower() for p in palavras)]


# ---------------------------------------------------------------- lógica pura

def hex_rgb(h: str) -> tuple[int, int, int]:
    s = h.strip().lstrip("#")
    if len(s) in (3, 4):
        s = "".join(c * 2 for c in s[:3])
    if len(s) not in (6, 8) or any(c not in "0123456789abcdefABCDEF" for c in s):
        raise ErroVfx(f"cor inválida: {h!r}")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def luminancia(rgb: np.ndarray) -> np.ndarray:
    """Luminância relativa (Rec. 709) de 0 a 1, em espaço linear-aproximado (sem gama, basta para ordenar)."""
    rgb = np.asarray(rgb, np.float64) / 255.0
    return rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722


def recolorir(quadros: list[np.ndarray], rampa: list[str], alfa_minimo: int = 128) -> list[np.ndarray]:
    """Recolore quadros RGBA na rampa (escuro -> claro) por luminância.

    A luminância dos pixels visíveis (alfa >= alfa_minimo) de TODOS os quadros é normalizada entre a mínima e a
    máxima do conjunto e cada pixel vira a cor da rampa no degrau mais próximo (o mesmo brilho dá a mesma cor em
    todos os quadros). Pixels abaixo de alfa_minimo ficam transparentes; os demais, opacos. Só cores da rampa saem.
    """
    if not rampa:
        raise ErroVfx("rampa vazia")
    cores = np.array([hex_rgb(c) for c in rampa], np.uint8)
    k = len(cores)
    vis = [q[..., 3] >= alfa_minimo for q in quadros]
    lums = [luminancia(q[..., :3]) for q in quadros]
    todos = np.concatenate([l[v] for l, v in zip(lums, vis)]) if quadros else np.zeros(0)
    lo, hi = (float(todos.min()), float(todos.max())) if todos.size else (0.0, 1.0)
    saida = []
    for q, l, v in zip(quadros, lums, vis):
        t = (l - lo) / (hi - lo) if hi > lo else np.full(l.shape, 1.0)
        idx = np.clip(np.rint(t * (k - 1)), 0, k - 1).astype(int)
        o = np.zeros(q.shape[:2] + (4,), np.uint8)
        o[v, :3] = cores[idx[v]]
        o[v, 3] = 255
        saida.append(o)
    return saida


def amostrar(quadros: list, duracoes: list[int], n: int | None) -> tuple[list, list[int]]:
    """Escolhe n quadros espaçados por igual; cada um dura a soma dos quadros que ele cobre (o total não muda)."""
    total = len(quadros)
    if not n or n >= total:
        return list(quadros), list(duracoes)
    if n < 1:
        raise ErroVfx("quadros precisa ser >= 1")
    idx = [(i * total) // n for i in range(n)] + [total]
    acum = np.concatenate([[0], np.cumsum(duracoes)])
    return ([quadros[idx[i]] for i in range(n)],
            [int(acum[idx[i + 1]] - acum[idx[i]]) for i in range(n)])


def caixa(quadros: list[np.ndarray]) -> tuple[int, int, int, int] | None:
    """União dos pixels visíveis de todos os quadros: (x0, y0, x1, y1), x1/y1 exclusivos. None se tudo vazio."""
    m = np.zeros(quadros[0].shape[:2], bool)
    for q in quadros:
        m |= q[..., 3] > 0
    if not m.any():
        return None
    ys, xs = np.nonzero(m)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def ajustar_tamanho(quadros: list[np.ndarray], tamanho: int | None, pivo: tuple[int, int]
                    ) -> tuple[list[np.ndarray], tuple[int, int], float]:
    """Recorta na caixa dos pixels visíveis e cabe num quadrado tamanho x tamanho.

    Se a caixa já cabe, só centraliza (a escala do pixel não muda). Se não cabe, reduz por vizinho mais próximo
    (perde detalhe: prefira um efeito menor). Devolve (quadros, pivô novo, escala).
    """
    if not tamanho:
        return quadros, pivo, 1.0
    if tamanho < 1:
        raise ErroVfx("tamanho precisa ser >= 1")
    cx = caixa(quadros)
    if cx is None:
        return [np.zeros((tamanho, tamanho, 4), np.uint8) for _ in quadros], (tamanho // 2, tamanho // 2), 1.0
    x0, y0, x1, y1 = cx
    w, h = x1 - x0, y1 - y0
    esc = min(1.0, tamanho / max(w, h))
    nw, nh = max(1, round(w * esc)), max(1, round(h * esc))
    ox, oy = (tamanho - nw) // 2, (tamanho - nh) // 2
    saida = []
    for q in quadros:
        rec = q[y0:y1, x0:x1]
        if esc < 1.0:
            rec = np.array(Image.fromarray(rec, "RGBA").resize((nw, nh), Image.NEAREST))
        o = np.zeros((tamanho, tamanho, 4), np.uint8)
        o[oy:oy + nh, ox:ox + nw] = rec
        saida.append(o)
    piv = (round((pivo[0] - x0) * esc) + ox, round((pivo[1] - y0) * esc) + oy)
    return saida, piv, esc


def tira(quadros: list[np.ndarray]) -> np.ndarray:
    return np.concatenate(quadros, axis=1)


def json_aseprite(nome: str, imagem: str, w: int, h: int, duracoes: list[int], extra: dict) -> dict:
    frames = [{"filename": f"{nome} {i}", "frame": {"x": i * w, "y": 0, "w": w, "h": h}, "rotated": False,
               "trimmed": False, "spriteSourceSize": {"x": 0, "y": 0, "w": w, "h": h},
               "sourceSize": {"w": w, "h": h}, "duration": int(d)} for i, d in enumerate(duracoes)]
    return {"frames": frames,
            "meta": {"app": "horys-pixel vfx (efeito do pixelfx)", "version": "1", "image": imagem,
                     "format": "RGBA8888", "size": {"w": w * len(duracoes), "h": h}, "scale": "1",
                     "frameTags": [{"name": nome, "from": 0, "to": len(duracoes) - 1, "direction": "forward"}],
                     "horys": extra}}


# ---------------------------------------------------------------- render pelo pixelfx

@dataclass
class Folha:
    quadros: list[np.ndarray]
    duracoes: list[int]
    meta: dict


def renderizar(efeito: str, rampa: list[str] | None = None, seed: int | None = None) -> Folha:
    """Chama `node tools/render.mjs <efeito> --sheet --bg none` e corta a folha em quadros RGBA."""
    if not _ID.match(efeito or ""):
        raise ErroVfx(f"efeito inválido: {efeito!r} (use categoria/nome, ex.: fire/campfire)")
    opts = {}
    if rampa:
        opts["palette"] = ["#%02x%02x%02x" % hex_rgb(c) for c in rampa]
    if seed is not None:
        opts["seed"] = int(seed)
    with tempfile.TemporaryDirectory(prefix="horys_vfx_") as tmp:
        args = ["tools/render.mjs", efeito, "--sheet", "--bg", "none", "--out", tmp]
        if opts:
            args += ["--opts", json.dumps(opts)]
        _rodar(args)
        nome = efeito.split("/")[1]
        pasta = Path(tmp, *efeito.split("/"))
        arq_json, arq_png = pasta / f"{nome}.json", pasta / f"{nome}.png"
        if not arq_json.is_file() or not arq_png.is_file():
            raise ErroVfx(f"pixelfx não gravou a folha de {efeito}")
        dados = json.loads(arq_json.read_text(encoding="utf-8"))
        folha = np.array(Image.open(arq_png).convert("RGBA"))
    quadros, duracoes = [], []
    for f in dados["frames"]:
        r = f["frame"]
        quadros.append(folha[r["y"]:r["y"] + r["h"], r["x"]:r["x"] + r["w"]].copy())
        duracoes.append(int(f.get("duration") or 100))
    if not quadros:
        raise ErroVfx(f"pixelfx devolveu {efeito} sem quadros")
    return Folha(quadros, duracoes, dados.get("meta", {}).get("pixelfx", {}))


@dataclass
class Resultado:
    png: Path
    json: Path
    previa: Path
    quadros: list[np.ndarray]
    duracoes: list[int]
    info: dict = field(default_factory=dict)


def previa(quadros: list[np.ndarray], limite: int = 1400) -> Image.Image:
    from . import pixels
    return pixels.filmstrip(quadros, limite)


def gerar(efeito: str, saida: str | os.PathLike, rampa: list[str], tamanho: int | None = None,
          quadros: int | None = None, seed: int | None = None, alfa_minimo: int = 128,
          paleta_nativa: bool = True, nome: str | None = None) -> Resultado:
    """Gera um VFX do pixelfx recolorido na rampa e grava <nome>.png (tira), <nome>.json e <nome>_previa.png."""
    if not rampa:
        raise ErroVfx("passe a rampa do personagem (lista de hex, do escuro ao claro)")
    folha = renderizar(efeito, rampa if paleta_nativa else None, seed)
    qs, durs = amostrar(folha.quadros, folha.duracoes, quadros)
    qs = recolorir(qs, rampa, alfa_minimo)
    pivo = tuple(folha.meta.get("pivot") or (qs[0].shape[1] // 2, qs[0].shape[0] // 2))
    qs, pivo, esc = ajustar_tamanho(qs, tamanho, pivo)
    vazios = sum(1 for q in qs if not (q[..., 3] > 0).any())
    nome = nome or efeito.replace("/", "_")
    out = Path(saida)
    out.mkdir(parents=True, exist_ok=True)
    h, w = qs[0].shape[:2]
    arq_png, arq_json, arq_prev = out / f"{nome}.png", out / f"{nome}.json", out / f"{nome}_previa.png"
    Image.fromarray(tira(qs), "RGBA").save(arq_png)
    info = {"efeito": efeito, "rampa": list(rampa), "quadros": len(qs), "quadros_pixelfx": len(folha.quadros),
            "tamanho": [w, h], "escala": round(esc, 4), "pivo": list(pivo), "loop": bool(folha.meta.get("loop")),
            "duracao_ms": int(sum(durs)), "quadros_vazios": vazios, "seed": seed, "alfa_minimo": alfa_minimo,
            "credito": CREDITO}
    if esc < 1.0:
        info["aviso"] = f"o efeito foi reduzido a {esc:.0%} para caber em {tamanho} px (detalhe perdido)"
    arq_json.write_text(json.dumps(json_aseprite(nome, arq_png.name, w, h, durs, info), ensure_ascii=False,
                                   indent=1), encoding="utf-8")
    previa(qs).save(arq_prev)
    return Resultado(arq_png, arq_json, arq_prev, qs, durs, info)
