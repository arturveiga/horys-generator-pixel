"""Preparo do conjunto de treino de um estilo, no formato que o sd-scripts espera.

Entradas:
- aprovados da memória de gosto: ``gosto/aprovados/*.png`` com ``.json`` ao lado (``descricao``, ``tipo``);
- imagens enviadas pela pessoa, em lotes com licença declarada (guardados em ``conjunto/lotes.json``
  para entrarem de novo nos próximos preparos).

Saída (``conjunto/``)::

    img/<repeticoes>_<trigger>/0001_gosto_xxx.png   imagem quadrada, fundo liso, ampliada sem suavizar
    img/<repeticoes>_<trigger>/0001_gosto_xxx.txt   legenda "<trigger>, pixel art, <tipo>, <descricao>"
    manifesto.json                                  origem/licença de cada imagem, contagem, duplicadas
    lotes.json                                      lotes enviados pela pessoa

Cada imagem: alfa binarizado (sem semitransparência → sem cores novas), escala nativa detectada (uma
cópia ampliada 4× vira 1×), dedupe por hash dos pixels, recorte do transparente com margem, fundo liso,
quadrado com padding e ampliação por vizinho mais próximo (fator inteiro) até a resolução do perfil.
"""

from __future__ import annotations

import hashlib
import math
import re
import shutil
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
from PIL import Image

from ._comum import ErroTreino, agora_iso, gravar_json, ler_json
from .alvo import validar_trigger

EXTENSOES = {".png", ".gif", ".bmp", ".webp", ".jpg", ".jpeg"}
LICENCA_GOSTO = "própria (aprovada na memória de gosto do horys)"
TIPO_PADRAO = "sprite"
COR_FUNDO_PADRAO = (255, 255, 255)

# O codificador de texto do SD entende inglês; os tipos conhecidos vão traduzidos na legenda.
TIPOS_EN = {
    "personagem": "character", "heroi": "hero", "herói": "hero", "npc": "npc", "inimigo": "enemy",
    "chefe": "boss", "boss": "boss", "criatura": "creature", "monstro": "monster", "item": "item",
    "icone": "icon", "ícone": "icon", "arma": "weapon", "prop": "prop", "objeto": "object",
    "tile": "tile", "tileset": "tileset", "cenario": "scenery", "cenário": "scenery",
    "predio": "building", "prédio": "building", "construcao": "building", "construção": "building",
    "efeito": "effect", "vfx": "effect", "ui": "ui", "interface": "ui", "retrato": "portrait",
    "carta": "card",
}


# ---------------------------------------------------------------- operações de imagem


def carregar_rgba(caminho: Path) -> np.ndarray:
    with Image.open(caminho) as im:
        im.seek(0)
        return np.array(im.convert("RGBA"), dtype=np.uint8)


def binarizar_alfa(arr: np.ndarray, limiar: int = 128) -> np.ndarray:
    """Alfa vira 0 ou 255; pixels transparentes ficam RGB=0 (para o hash não depender do lixo invisível)."""
    out = arr.copy()
    opaco = out[..., 3] >= limiar
    out[..., 3] = np.where(opaco, 255, 0)
    out[~opaco, :3] = 0
    return out


def fundo_por_bordas(arr: np.ndarray) -> np.ndarray:
    """Imagem sem transparência cuja borda inteira é de uma cor só: o fundo ligado às bordas vira transparente.

    Exigir a borda inteira (e não só os cantos) protege tiles e cenários, que vão até a beirada.
    """
    if (arr[..., 3] < 255).any() or min(arr.shape[:2]) < 3:
        return arr
    cor = arr[0, 0, :3]
    mesma = (arr[..., :3] == cor).all(axis=-1)
    if not (mesma[0].all() and mesma[-1].all() and mesma[:, 0].all() and mesma[:, -1].all()):
        return arr
    try:
        from scipy import ndimage

        rotulos, _ = ndimage.label(mesma)
        bordas = np.concatenate([rotulos[0], rotulos[-1], rotulos[:, 0], rotulos[:, -1]])
        ids = np.unique(bordas[bordas > 0])
        fundo = np.isin(rotulos, ids)
    except ImportError:  # sem scipy: preenchimento iterativo a partir das bordas
        fundo = np.zeros_like(mesma)
        fundo[0], fundo[-1], fundo[:, 0], fundo[:, -1] = mesma[0], mesma[-1], mesma[:, 0], mesma[:, -1]
        while True:
            viz = fundo.copy()
            viz[1:] |= fundo[:-1]
            viz[:-1] |= fundo[1:]
            viz[:, 1:] |= fundo[:, :-1]
            viz[:, :-1] |= fundo[:, 1:]
            novo = viz & mesma
            if (novo == fundo).all():
                break
            fundo = novo
    out = arr.copy()
    out[fundo] = 0
    return out


def escala_nativa(arr: np.ndarray, maximo: int = 64) -> int:
    """Maior fator inteiro k tal que a imagem é feita de blocos k×k iguais (pixel art já ampliada)."""
    h, w = arr.shape[:2]
    g = math.gcd(h, w)
    for k in range(min(g, maximo), 1, -1):
        if g % k:
            continue
        reduzida = arr[::k, ::k]
        if np.array_equal(np.repeat(np.repeat(reduzida, k, axis=0), k, axis=1), arr):
            return k
    return 1


def recortar(arr: np.ndarray, margem: int = 0) -> np.ndarray | None:
    """Recorta ao retângulo dos pixels opacos e põe ``margem`` pixels transparentes em volta. Vazia → None."""
    opaco = arr[..., 3] > 0
    if not opaco.any():
        return None
    ys, xs = np.nonzero(opaco)
    recorte = arr[ys.min(): ys.max() + 1, xs.min(): xs.max() + 1]
    if margem > 0:
        recorte = np.pad(recorte, ((margem, margem), (margem, margem), (0, 0)), constant_values=0)
    return recorte


def compor_fundo(arr: np.ndarray, cor: Sequence[int]) -> np.ndarray:
    """RGBA (alfa binário) → RGB com fundo liso; nenhuma mistura de cores."""
    rgb = arr[..., :3].copy()
    rgb[arr[..., 3] == 0] = np.array(cor[:3], dtype=np.uint8)
    return rgb


def quadrar(rgb: np.ndarray, cor: Sequence[int]) -> np.ndarray:
    h, w = rgb.shape[:2]
    lado = max(h, w)
    topo, esq = (lado - h) // 2, (lado - w) // 2
    out = np.empty((lado, lado, 3), dtype=np.uint8)
    out[...] = np.array(cor[:3], dtype=np.uint8)
    out[topo: topo + h, esq: esq + w] = rgb
    return out


def ampliar(rgb: np.ndarray, resolucao: int, cor: Sequence[int]) -> tuple[np.ndarray, int]:
    """Amplia por vizinho mais próximo com fator inteiro e completa até ``resolucao`` com o fundo.

    Imagem maior que a resolução é reduzida por vizinho mais próximo (raro em pixel art; avisado no manifesto).
    Devolve (imagem, fator); fator 0 indica redução.
    """
    lado = rgb.shape[0]
    if lado > resolucao:
        im = Image.fromarray(rgb).resize((resolucao, resolucao), Image.Resampling.NEAREST)
        return np.array(im), 0
    k = max(1, resolucao // lado)
    grande = np.repeat(np.repeat(rgb, k, axis=0), k, axis=1)
    return quadrar_em(grande, resolucao, cor), k


def quadrar_em(rgb: np.ndarray, resolucao: int, cor: Sequence[int]) -> np.ndarray:
    h, w = rgb.shape[:2]
    out = np.empty((resolucao, resolucao, 3), dtype=np.uint8)
    out[...] = np.array(cor[:3], dtype=np.uint8)
    topo, esq = (resolucao - h) // 2, (resolucao - w) // 2
    out[topo: topo + h, esq: esq + w] = rgb
    return out


def hash_pixels(arr: np.ndarray) -> str:
    h = hashlib.sha256()
    h.update(f"{arr.shape[0]}x{arr.shape[1]}".encode())
    h.update(np.ascontiguousarray(arr).tobytes())
    return h.hexdigest()


def normalizar(arr: np.ndarray) -> tuple[np.ndarray | None, int]:
    """Alfa binário, fundo das bordas removido, escala nativa e recorte justo. Devolve (sprite, escala)."""
    arr = binarizar_alfa(fundo_por_bordas(binarizar_alfa(arr)))
    recorte = recortar(arr, 0)  # recorta antes: a margem original pode não seguir a grade da ampliação
    if recorte is None:
        return None, 1
    k = escala_nativa(recorte)
    return (recorte[::k, ::k] if k > 1 else recorte), k


# ---------------------------------------------------------------- legendas e cores


def cor_hex(texto: str | Sequence[int]) -> tuple[int, int, int]:
    if not isinstance(texto, str):
        r, g, b = list(texto)[:3]
        return int(r), int(g), int(b)
    t = texto.strip().lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", t):
        raise ErroTreino(f"cor inválida: {texto!r} (use #RRGGBB)")
    return int(t[0:2], 16), int(t[2:4], 16), int(t[4:6], 16)


def tipo_legenda(tipo: str | None) -> str:
    t = (tipo or TIPO_PADRAO).strip()
    return TIPOS_EN.get(t.lower(), t)


def legenda(trigger: str, tipo: str | None, descricao: str | None, traduzir_tipo: bool = True) -> str:
    partes = [trigger, "pixel art", tipo_legenda(tipo) if traduzir_tipo else (tipo or TIPO_PADRAO)]
    desc = re.sub(r"\s+", " ", (descricao or "").replace("\n", " ")).strip(" ,")
    if desc:
        partes.append(desc)
    return ", ".join(p.strip() for p in partes if p and p.strip())


def repeticoes_sugeridas(n_imagens: int, passos_por_epoca: int = 200, maximo: int = 20) -> int:
    """Repetições para ~200 passos por época (com 10 épocas, ~2000 passos no total)."""
    if n_imagens <= 0:
        return 1
    return max(1, min(maximo, math.ceil(passos_por_epoca / n_imagens)))


def _descricao_do_nome(caminho: Path) -> str:
    return re.sub(r"[_\-]+", " ", caminho.stem).strip()


def _metadados(caminho: Path) -> dict:
    meta = ler_json(caminho.with_suffix(".json"), None)
    if isinstance(meta, dict):
        return meta
    txt = caminho.with_suffix(".txt")
    if txt.is_file():
        return {"descricao": txt.read_text(encoding="utf-8", errors="replace").strip()}
    return {}


def _slug(texto: str, limite: int = 40) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", texto).strip("-").lower()
    return (s or "img")[:limite]


def expandir(caminhos: Iterable[Path | str]) -> list[Path]:
    """Arquivos de imagem (pastas são varridas, sem recursão), em ordem."""
    saida: list[Path] = []
    for c in caminhos:
        p = Path(c).expanduser()
        if p.is_dir():
            saida += sorted(f for f in p.iterdir() if f.is_file() and f.suffix.lower() in EXTENSOES)
        else:
            saida.append(p)
    return saida


# ---------------------------------------------------------------- lotes


def registrar_lote(pasta_conjunto: Path, imagens: Sequence[Path | str], licenca: str,
                   tipo: str | None = None, descricao: str | None = None) -> dict:
    """Guarda um lote de imagens da pessoa (com licença) em ``conjunto/lotes.json``."""
    if not licenca or not licenca.strip():
        raise ErroTreino(
            "declare a licença das imagens (--licenca), ex.: \"minha arte\", \"CC0\", "
            "\"comprada com licença que permite treino\". Sem isso elas não entram no conjunto."
        )
    arquivos = expandir(imagens)
    if not arquivos:
        raise ErroTreino("nenhuma imagem encontrada nos caminhos informados")
    lote = {
        "imagens": [str(p.resolve()) for p in arquivos],
        "licenca": licenca.strip(),
        "tipo": tipo,
        "descricao": descricao,
        "adicionado_em": agora_iso(),
    }
    arq = Path(pasta_conjunto) / "lotes.json"
    lotes = ler_json(arq, []) or []
    lotes.append(lote)
    gravar_json(arq, lotes)
    return lote


def _entradas(pasta_gosto: Path | None, lotes: list[dict]) -> list[dict]:
    entradas = []
    if pasta_gosto:
        aprovados = Path(pasta_gosto) / "aprovados"
        if aprovados.is_dir():
            for png in sorted(aprovados.glob("*.png")):
                meta = _metadados(png)
                entradas.append({
                    "fonte": png, "origem": "gosto", "licenca": LICENCA_GOSTO,
                    "tipo": meta.get("tipo"), "descricao": meta.get("descricao") or "",
                })
    for lote in lotes:
        for caminho in lote.get("imagens", []):
            p = Path(caminho)
            meta = _metadados(p) if p.exists() else {}
            entradas.append({
                "fonte": p, "origem": "usuario", "licenca": lote.get("licenca"),
                "tipo": meta.get("tipo") or lote.get("tipo"),
                "descricao": meta.get("descricao") or lote.get("descricao") or _descricao_do_nome(p),
            })
    return entradas


# ---------------------------------------------------------------- preparo


def preparar(
    pasta_conjunto: Path | str,
    trigger: str,
    pasta_gosto: Path | str | None = None,
    imagens: Sequence[Path | str] = (),
    licenca: str | None = None,
    tipo: str | None = None,
    resolucao: int = 512,
    cor_fundo: str | Sequence[int] = COR_FUNDO_PADRAO,
    margem: int = 2,
    repeticoes: int | None = None,
    traduzir_tipo: bool = True,
) -> dict:
    """Monta ``conjunto/img/<repeticoes>_<trigger>/`` com imagens + legendas e grava ``manifesto.json``.

    ``imagens`` (com ``licenca``) é um lote novo da pessoa; os lotes anteriores (``lotes.json``) entram sempre.
    A pasta ``img/`` é refeita do zero a cada preparo; ``lotes.json`` é preservado.
    """
    trigger = validar_trigger(trigger)
    cor = cor_hex(cor_fundo)
    if resolucao < 64:
        raise ErroTreino("resolução muito pequena (mínimo 64)")
    pasta_conjunto = Path(pasta_conjunto)
    pasta_conjunto.mkdir(parents=True, exist_ok=True)
    if imagens:
        registrar_lote(pasta_conjunto, imagens, licenca or "", tipo=tipo)
    lotes = ler_json(pasta_conjunto / "lotes.json", []) or []

    vistos: dict[str, str] = {}
    aceitas: list[dict] = []
    duplicadas: list[dict] = []
    ignoradas: list[dict] = []
    for ent in _entradas(Path(pasta_gosto) if pasta_gosto else None, lotes):
        fonte: Path = ent["fonte"]
        if not fonte.is_file():
            ignoradas.append({"fonte": str(fonte), "motivo": "arquivo não encontrado"})
            continue
        try:
            arr = carregar_rgba(fonte)
        except Exception as e:  # imagem corrompida ou formato não suportado
            ignoradas.append({"fonte": str(fonte), "motivo": f"não abriu: {e}"})
            continue
        sprite, escala = normalizar(arr)
        if sprite is None:
            ignoradas.append({"fonte": str(fonte), "motivo": "imagem toda transparente"})
            continue
        h = hash_pixels(sprite)
        if h in vistos:
            duplicadas.append({"fonte": str(fonte), "igual_a": vistos[h]})
            continue
        vistos[h] = str(fonte)
        aceitas.append({**ent, "sprite": sprite, "hash": h, "escala": escala, "tamanho_original": arr.shape[1::-1]})

    rep = repeticoes or repeticoes_sugeridas(len(aceitas))
    pasta_img = pasta_conjunto / "img"
    if pasta_img.exists():
        shutil.rmtree(pasta_img)
    pasta_sub = pasta_img / f"{rep}_{trigger}"
    pasta_sub.mkdir(parents=True)

    registros = []
    for i, ent in enumerate(aceitas, start=1):
        sprite = recortar(ent["sprite"], margem)
        rgb = quadrar(compor_fundo(sprite, cor), cor)
        final, fator = ampliar(rgb, resolucao, cor)
        base = f"{i:04d}_{ent['origem']}_{_slug(ent['fonte'].stem)}"
        Image.fromarray(final, "RGB").save(pasta_sub / f"{base}.png")
        texto = legenda(trigger, ent["tipo"], ent["descricao"], traduzir_tipo)
        (pasta_sub / f"{base}.txt").write_text(texto + "\n", encoding="utf-8")
        reg = {
            "arquivo": f"{base}.png",
            "origem": ent["origem"],
            "fonte": str(ent["fonte"]),
            "licenca": ent["licenca"],
            "tipo": ent["tipo"] or TIPO_PADRAO,
            "descricao": ent["descricao"],
            "legenda": texto,
            "hash": ent["hash"],
            "tamanho_original": list(ent["tamanho_original"]),
            "escala_nativa": ent["escala"],
            "tamanho_sprite": [int(ent["sprite"].shape[1]), int(ent["sprite"].shape[0])],
            "fator_ampliacao": fator,
        }
        if fator == 0:
            reg["aviso"] = "maior que a resolução: reduzida por vizinho mais próximo"
        registros.append(reg)

    contagem = {
        "total": len(registros),
        "gosto": sum(r["origem"] == "gosto" for r in registros),
        "usuario": sum(r["origem"] == "usuario" for r in registros),
        "duplicadas": len(duplicadas),
        "ignoradas": len(ignoradas),
    }
    avisos = []
    if contagem["total"] < 10:
        avisos.append(f"só {contagem['total']} imagens; o ideal é 15 a 100 para um LoRA de estilo.")
    assinatura = hashlib.sha256("".join(sorted(r["hash"] for r in registros)).encode()).hexdigest()
    manifesto = {
        "trigger": trigger,
        "resolucao": resolucao,
        "cor_fundo": "#%02x%02x%02x" % cor,
        "margem": margem,
        "repeticoes": rep,
        "pasta_imagens": str(pasta_sub.resolve()),
        "criado_em": agora_iso(),
        "assinatura": assinatura,
        "contagem": contagem,
        "licencas": sorted({r["licenca"] for r in registros}),
        "imagens": registros,
        "duplicadas": duplicadas,
        "ignoradas": ignoradas,
        "avisos": avisos,
    }
    gravar_json(pasta_conjunto / "manifesto.json", manifesto)
    return manifesto


def carregar_manifesto(pasta_conjunto: Path | str) -> dict:
    man = ler_json(Path(pasta_conjunto) / "manifesto.json")
    if not man:
        raise ErroTreino(f"conjunto não preparado em {pasta_conjunto} (rode o comando preparar)")
    return man
