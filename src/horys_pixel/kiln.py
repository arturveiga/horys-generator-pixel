"""Ponte com o SpriteKiln (MIT, dependência opcional): lê o atlas que o `spritekiln render` grava, gera a paleta
do estilo no formato de rampas dele e limpa a sequência de quadros sem criar boil.

Módulo puro (NumPy/SciPy/Pillow); nada aqui fala com o Aseprite. O pacote `spritekiln` roda num subprocesso (o venv dele) em
`mascaras_por_parte`, então o Horys funciona sem ele instalado.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

DIRECOES = ("s", "se", "e", "ne", "n", "nw", "w", "sw")


@dataclass
class Atlas:
    quadros: list[np.ndarray]                       # RGBA uint8, um por quadro, na ordem das tags
    duracoes_ms: list[int]
    tags: list[tuple[str, int, int]]                # (nome, de, ate) inclusivo
    tamanho: tuple[int, int]                        # (w, h) do quadro
    pivo: tuple[float, float] | None = None
    eventos: dict[int, list[str]] = field(default_factory=dict)
    sha256: str = ""
    nome: str = ""
    loops: dict[str, bool] = field(default_factory=dict)


def _dividir_tag(nome: str) -> tuple[str, str | None]:
    """'attack_e' -> ('attack', 'e'); sem sufixo de direção -> (nome, None)."""
    base, _, suf = nome.rpartition("_")
    if base and suf in DIRECOES:
        return base, suf
    return nome, None


def ler_atlas(caminho_json: str | Path) -> Atlas:
    caminho = Path(caminho_json)
    if not caminho.exists():
        raise ValueError(f"JSON do SpriteKiln não existe: {caminho}")
    bruto = caminho.read_bytes()
    d = json.loads(bruto.decode("utf-8"))
    meta = d.get("meta") or {}
    frames = d.get("frames")
    if not isinstance(frames, dict) or not frames:
        raise ValueError("JSON sem 'frames' no formato hash do Aseprite (use o JSON do `spritekiln render`)")
    img_path = caminho.parent / (meta.get("image") or caminho.with_suffix(".png").name)
    if not img_path.exists():
        raise ValueError(f"atlas PNG não existe: {img_path}")
    at = np.array(Image.open(img_path).convert("RGBA"))
    nomes = list(frames)
    quadros, dur = [], []
    w0 = h0 = None
    for n in nomes:
        r = frames[n]["frame"]
        x, y, w, h = int(r["x"]), int(r["y"]), int(r["w"]), int(r["h"])
        if w0 is None:
            w0, h0 = w, h
        elif (w, h) != (w0, h0):
            raise ValueError(f"quadros de tamanhos diferentes no atlas ({n}: {w}x{h}, esperado {w0}x{h0})")
        quadros.append(at[y:y + h, x:x + w].copy())
        dur.append(int(frames[n].get("duration", 100)))
    tags = [(t["name"], int(t["from"]), int(t["to"])) for t in meta.get("frameTags") or []]
    if not tags:
        tags = [("quadros", 0, len(quadros) - 1)]
    sk = d.get("spritekiln") or {}
    pv = sk.get("pivot")
    pivo = (float(pv["x"]), float(pv["y"])) if pv else None
    eventos: dict[int, list[str]] = {}
    loops: dict[str, bool] = {}
    idx = {n: i for i, n in enumerate(nomes)}
    for anim, info in (sk.get("animations") or {}).items():
        loops[anim] = bool(info.get("loop", True))
        for _dir, dd in (info.get("directions") or {}).items():
            fr = dd.get("frames") or []
            for k, evs in (dd.get("events") or {}).items():
                i = int(k)
                if i < len(fr) and fr[i] in idx:
                    eventos.setdefault(idx[fr[i]], []).extend(evs)
    return Atlas(quadros, dur, tags, (w0, h0), pivo, eventos, hashlib.sha256(bruto).hexdigest(),
                 sk.get("name") or caminho.stem, loops)


def direcoes(atlas: Atlas) -> list[str]:
    vistas = []
    for nome, _, _ in atlas.tags:
        _, d = _dividir_tag(nome)
        if d and d not in vistas:
            vistas.append(d)
    return vistas


def filtrar(atlas: Atlas, tags: list[str] | None = None, direcao: str | None = None) -> Atlas:
    """Só as tags (estados) pedidas e só uma direção; renomeia 'idle_e' para 'idle' e reindexa os quadros."""
    vistas = direcoes(atlas)
    if direcao is None and vistas:
        direcao = vistas[0]
    if direcao is not None and vistas and direcao not in vistas:
        raise ValueError(f"direção '{direcao}' não está no atlas (tem: {', '.join(vistas)})")
    quer = set(tags) if tags else None
    q, dur, novas, evs = [], [], [], {}
    achadas = set()
    for nome, de, ate in atlas.tags:
        base, d = _dividir_tag(nome)
        if d is not None and d != direcao:
            continue
        if quer is not None and base not in quer and nome not in quer:
            continue
        achadas.add(base)
        ini = len(q)
        for i in range(de, ate + 1):
            if i in atlas.eventos:
                evs[len(q)] = list(atlas.eventos[i])
            q.append(atlas.quadros[i])
            dur.append(atlas.duracoes_ms[i])
        novas.append((base, ini, len(q) - 1))
    if quer is not None:
        faltam = sorted(t for t in quer if t not in achadas and not any(t == n for n, _, _ in atlas.tags))
        if faltam:
            disp = sorted({_dividir_tag(n)[0] for n, _, _ in atlas.tags})
            raise ValueError(f"tags não encontradas: {', '.join(faltam)} (tem: {', '.join(disp)})")
    if not q:
        raise ValueError("nenhum quadro sobrou depois do filtro")
    return Atlas(q, dur, novas, atlas.tamanho, atlas.pivo, evs, atlas.sha256, atlas.nome, atlas.loops)


# ------------------------------------------------------------------ paleta

def rampas_do_estilo(paleta: dict) -> dict[str, list[str]]:
    """Rampas no formato do SpriteKiln a partir da paleta de um estilo Horys: índice 0 = contorno, depois
    sombra -> base -> luz. Rampas de uma cor só (contorno, brilho) ficam de fora."""
    contorno = paleta.get("contorno") or "#000000"
    out = {}
    for nome, cores in (paleta.get("rampas") or {}).items():
        cores = [c.lower() for c in cores]
        if len(cores) < 2 or nome in ("contorno", "brilho"):
            continue
        out[nome] = [contorno.lower(), *cores]
    if not out:
        raise ValueError("a paleta do estilo não tem rampas de 2+ cores")
    return out


def yaml_paleta_kiln(paleta: dict) -> str:
    """Texto YAML de um arquivo de paleta do SpriteKiln (um mapa nome -> lista de hex)."""
    linhas = [f"# gerado pelo horys a partir da paleta '{paleta.get('nome', '')}'", "ramps:"]
    for nome, cores in rampas_do_estilo(paleta).items():
        linhas.append(f"  {json.dumps(nome, ensure_ascii=False)}: [{', '.join(json.dumps(c) for c in cores)}]")
    return "\n".join(linhas) + "\n"


# ------------------------------------------------------------------ limpeza da sequência

def _chave(rgba: np.ndarray) -> np.ndarray:
    a = rgba.astype(np.uint32)
    return (a[..., 0] << 24) | (a[..., 1] << 16) | (a[..., 2] << 8) | a[..., 3]


def limpar_quadro(rgba: np.ndarray, min_px: int, proteger: set[tuple[int, int, int]] | None = None) -> np.ndarray:
    """Funde cada mancha (4-conexa, mesma cor) menor que `min_px` na cor vizinha mais frequente. Não toca no
    alfa: só recolore pixels opacos com cores de vizinhos opacos."""
    out = rgba.copy()
    if min_px <= 1:
        return out
    ch = _chave(out)
    opaco = out[..., 3] > 0
    for _ in range(3):  # poucas passadas: manchas vizinhas pequenas se resolvem em cadeia
        mudou = False
        for cor in np.unique(ch[opaco]):
            m = (ch == cor) & opaco
            r, g, b, _a = ((int(cor) >> 24) & 255, (int(cor) >> 16) & 255, (int(cor) >> 8) & 255, int(cor) & 255)
            if proteger and (r, g, b) in proteger:
                continue
            lab, n = ndimage.label(m)
            if n == 0:
                continue
            tam = np.bincount(lab.ravel())
            for i in np.nonzero(tam < min_px)[0]:
                if i == 0:
                    continue
                pedaco = lab == i
                borda = ndimage.binary_dilation(pedaco) & ~pedaco & opaco
                if not borda.any():
                    continue
                viz, cont = np.unique(ch[borda], return_counts=True)
                nova = viz[np.argmax(cont)]
                ys, xs = np.nonzero(borda & (ch == nova))
                out[pedaco] = out[ys[0], xs[0]]
                ch[pedaco] = nova
                mudou = True
        if not mudou:
            break
    return out


def limpar_sequencia(quadros: list[np.ndarray], min_px: int,
                     proteger: set[tuple[int, int, int]] | None = None) -> list[np.ndarray]:
    """Limpa cada quadro e, onde o original não mudou em relação ao quadro anterior, repete a decisão do anterior
    (pixel parado recebe a mesma cor nos dois quadros: a limpeza não cria boil)."""
    out = []
    for i, q in enumerate(quadros):
        limpo = limpar_quadro(q, min_px, proteger)
        if i > 0 and quadros[i - 1].shape == q.shape:
            parado = np.all(quadros[i - 1] == q, axis=-1)
            limpo[parado] = out[-1][parado]
        out.append(limpo)
    return out


# ------------------------------------------------------------------ partes (usa o spritekiln, opcional)

# Roda DENTRO do Python do SpriteKiln (ele costuma ficar isolado num venv do uv/pipx). Usa a função interna
# pipeline.parts_mask do 0.3.x: o render guarda, por pixel, o id da parte que ficou na frente.
_SCRIPT_MASCARAS = r"""
import json, sys
import numpy as np
from spritekiln import spec as specmod
from spritekiln.api import pose_env, _checked
from spritekiln.pipeline import parts_mask, render_buffers
pedido = json.loads(sys.argv[1])
sp = _checked(specmod.load(pedido["spec"]))
yaw = dict(sp["directions"]).get(pedido["direcao"])
if yaw is None:
    yaw = {"s": 0, "se": 45, "e": 90, "ne": 135, "n": 180, "nw": -135, "w": -90, "sw": -45}[pedido["direcao"]]
saida = {}
nomes = set()
for q in pedido["quadros"]:
    env = pose_env(sp, pedido["anim"], q, yaw)
    env2 = dict(env, yaw=float(yaw), dir=specmod.direction_name(yaw))
    _gb, groups, _a, _b = render_buffers(sp, env2, yaw)
    nomes |= {g.name.split(":")[0] for g in groups}
    for parte, alvo in pedido["grupos"].items():
        saida[f"{q}|{parte}"] = parts_mask(sp, env, yaw, set(alvo))
np.savez_compressed(pedido["saida"], **saida)
print(json.dumps(sorted(nomes)))
"""


def python_do_kiln() -> str:
    """O Python que enxerga o pacote spritekiln: HORYS_KILN_PYTHON, o venv do uv/pipx ou o Python atual."""
    import os
    import sys
    if os.environ.get("HORYS_KILN_PYTHON"):
        return os.environ["HORYS_KILN_PYTHON"]
    casa = Path.home()
    for c in (casa / "AppData/Roaming/uv/tools/spritekiln/Scripts/python.exe",
              casa / ".local/share/uv/tools/spritekiln/bin/python",
              casa / "pipx/venvs/spritekiln/Scripts/python.exe",
              casa / ".local/pipx/venvs/spritekiln/bin/python",
              casa / ".local/share/pipx/venvs/spritekiln/bin/python"):
        if c.exists():
            return str(c)
    return sys.executable


def mascaras_por_parte(spec_path: str | Path, anim: str | None, quadros: list[int], direcao: str,
                       grupos: dict[str, list[str]], python: str | None = None
                       ) -> tuple[dict[int, dict[str, np.ndarray]], list[str]]:
    """Máscaras dos pixels VISÍVEIS de cada parte do Horys (grupo de partes do spec) em cada quadro.
    Devolve ({quadro: {parte: máscara}}, nomes de partes que o spec tem). Precisa do spritekiln 0.3.x."""
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        saida = Path(tmp) / "m.npz"
        pedido = {"spec": str(spec_path), "anim": anim, "quadros": list(quadros), "direcao": direcao,
                  "grupos": grupos, "saida": str(saida)}
        r = subprocess.run([python or python_do_kiln(), "-c", _SCRIPT_MASCARAS, json.dumps(pedido)],
                           capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            raise RuntimeError("spritekiln não conseguiu separar as partes (instalado? versão 0.3.x?): "
                               + (r.stderr or r.stdout)[-1500:])
        nomes = json.loads(r.stdout.strip().splitlines()[-1])
        out: dict[int, dict[str, np.ndarray]] = {}
        with np.load(saida) as dados:
            for k in dados.files:
                q, parte = k.split("|", 1)
                out.setdefault(int(q), {})[parte] = dados[k].astype(bool)
    return out, nomes


def distribuir(composto: np.ndarray, mascaras: dict[str, np.ndarray], ordem: list[str],
               resto: str | None = None) -> dict[str, np.ndarray]:
    """Divide um quadro composto entre as partes: cada pixel visível vai para exatamente uma parte. Máscaras que se
    sobrepõem ficam com a parte mais alta em `ordem` (de baixo para cima); pixels sem dono vão para `resto`."""
    H, W = composto.shape[:2]
    dono = np.full((H, W), -1, int)
    for i, p in enumerate(ordem):
        m = mascaras.get(p)
        if m is not None:
            dono[m] = i
    visivel = composto[..., 3] > 0
    r = ordem.index(resto) if resto in ordem else 0
    dono[visivel & (dono < 0)] = r
    out = {}
    for i, p in enumerate(ordem):
        img = np.zeros_like(composto)
        sel = visivel & (dono == i)
        img[sel] = composto[sel]
        out[p] = img
    return out
