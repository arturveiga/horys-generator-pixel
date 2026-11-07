"""Ferramentas de partes: checagem, recorte da referência e extensão de anatomia oculta (fatiamento modular).

A lógica pura vive em horys_pixel.partes (sem Aseprite); aqui só se lê e escreve camadas. Recorte e extensão nunca
mudam a imagem composta: conferem a composição antes e depois e desfazem se ela mudou.
"""
from __future__ import annotations

import json
import hashlib
from pathlib import Path

import numpy as np
from PIL import Image

from .. import config, partes as P, pixels
from .desenho import escrever_rgba, ler_rgba
from .estilo import _estilo, _ficha, _paleta, _partes
from .registro import BOOL, INT, STR, ErroFerramenta, ferramenta, imagem, texto


# ------------------------------------------------------------------ apoio (também usado pelo portão)

def _rgb(hexes) -> set[tuple[int, int, int]]:
    out = set()
    for h in hexes:
        if isinstance(h, str):
            try:
                out.add(pixels.hex_rgba(h)[:3])
            except ValueError:
                pass
    return out


def _cores_linha(f: dict) -> set:
    try:
        pal = _paleta(_estilo(f.get("estilo")))
        c = pal.get("contorno")
        hexes = (c if isinstance(c, list) else [c]) if c else []
    except Exception:
        hexes = []
    return _rgb(hexes + [f.get("cor_contorno")])


def hash_checagem(f: dict, quadros: list[dict], referencias: list[np.ndarray | None]) -> str:
    h = hashlib.sha256()
    contrato = {k: f.get(k) for k in ("modular", "preset_partes", "partes", "juncoes", "partes_oculto",
                                       "componentes_max", "espessura_fina")}
    h.update(json.dumps(contrato, sort_keys=True, ensure_ascii=False).encode())
    for q, ref in zip(quadros, referencias):
        for p in f.get("partes") or []:
            h.update(p.encode()); h.update(np.ascontiguousarray(q[p]).tobytes())
        if ref is not None:
            h.update(np.ascontiguousarray(ref).tobytes())
    return h.hexdigest()


async def ler_quadros(ctx, partes: list[str], indices: list[int], com_referencia: bool = True):
    quadros, refs = [], []
    for q in indices:
        quadros.append({p: await ler_rgba(ctx, p, q) for p in partes})
        refs.append(await ler_rgba(ctx, "referencia", q) if com_referencia else None)
    return quadros, refs


async def checar_asset(ctx, f: dict, st: dict, indices: list[int]):
    """Valida as partes do sprite aberto nos quadros dados. Devolve (relatório, quadros, ordem das partes)."""
    ordem = _partes(f, st)
    _, juncoes, oculto = P.contratos_da_ficha(f)
    quadros, refs = await ler_quadros(ctx, ordem, indices)
    rel = P.checar(f.get("preset_partes") or None, quadros, partes=ordem, juncoes=juncoes, oculto=oculto,
                   referencias=refs, cores_linha=_cores_linha(f), ignorar_linha=f.get("contorno") == "nenhum",
                   componentes_max=f.get("componentes_max"), espessura_fina=f.get("espessura_fina"))
    return rel, quadros, ordem, refs


def escrever_saidas(saida: Path, nome: str, rel: P.Relatorio, quadros: list[dict], ordem: list[str],
                    quadro_vista: int = 0) -> list[Path]:
    """partes_checagem.txt, medidas/partes.json e <nome>_partes.png (vista explodida, ocultos em magenta)."""
    saida.mkdir(parents=True, exist_ok=True)
    (saida / "medidas").mkdir(exist_ok=True)
    txt, js, png = saida / "partes_checagem.txt", saida / "medidas" / "partes.json", saida / f"{nome}_partes.png"
    txt.write_text(rel.texto(500), encoding="utf-8")
    js.write_text(rel.json(), encoding="utf-8")
    vista = P.vista_explodida(quadros[min(quadro_vista, len(quadros) - 1)], ordem)
    Image.fromarray(vista, "RGBA").save(png)
    return [txt, js, png]


def _regiao(a) -> tuple[int, int, int, int]:
    r = a.get("regiao") or a.get("rect")
    if isinstance(r, (list, tuple)) and len(r) >= 4:
        return tuple(int(v) for v in r[:4])
    if isinstance(r, dict) and all(k in r for k in ("x", "y", "w", "h")):
        return int(r["x"]), int(r["y"]), int(r["w"]), int(r["h"])
    raise ErroFerramenta("informe 'regiao': {x, y, w, h} (ou [x, y, w, h])")


async def _aplicar_sem_mudar_composicao(ctx, camada: str, q: int, original: np.ndarray, novo: np.ndarray) -> int:
    """Escreve `novo` na camada e confere a composição inteira; se mudou, desfaz e aborta."""
    masc = np.any(novo != original, axis=-1)
    if not masc.any():
        return 0
    antes = await ler_rgba(ctx, None, q)
    await escrever_rgba(ctx, camada, q, 0, 0, novo, masc.astype(np.uint8))
    depois = await ler_rgba(ctx, None, q)
    if not np.array_equal(antes, depois):
        await escrever_rgba(ctx, camada, q, 0, 0, original, masc.astype(np.uint8))
        revisto = await ler_rgba(ctx, None, q)
        extra = "" if np.array_equal(antes, revisto) else " ATENÇÃO: a composição NÃO voltou ao estado anterior; " \
                                                         "use horys_desfazer"
        n = int(np.any(antes != depois, axis=-1).sum())
        raise ErroFerramenta(f"abortado e revertido: a imagem composta mudaria em {n} px (quadro {q}, '{camada}').{extra}")
    return int(masc.sum())


def _quadros_alvo(a: dict, st: dict, padrao_ativo: bool = True) -> list[int]:
    s = st["sprite"]
    n = len(s["quadros"])
    if a.get("quadros"):
        idx = [int(i) for i in a["quadros"]]
    elif "quadro" in a:
        idx = [int(a["quadro"])]
    else:
        idx = [int(s.get("quadro_ativo") or 0)] if padrao_ativo else list(range(n))
    ruins = [i for i in idx if not 0 <= i < n]
    if ruins:
        raise ErroFerramenta(f"quadro(s) fora do sprite: {ruins} (há {n})")
    return idx


# ------------------------------------------------------------------ ferramentas

@ferramenta("horys_partes_checar", """Valida o fatiamento em PARTES do sprite modular (ficha com modular/preset_partes):
parte vazia ou desconexa, partes que não se tocam, inferior ao menos 1 px sob a superior (erro; aviso se < 2 px),
buraco ao deslocar a parte móvel 1 px (erro) ou 2 px (aviso) nas 8 direções, linha interna entre as partes e cobertura
mínima de 90% da anatomia oculta e da camada 'referencia'. Camada faltando é erro. Devolve o diagnóstico e a VISTA
EXPLODIDA (cada parte numa célula, pixels ocultos em MAGENTA). 'quadros' (padrão: todos); 'quadro' escolhe o da
vista; 'salvar': pasta onde gravar partes_checagem.txt, medidas/partes.json e <nome>_partes.png.""",
            {"quadros": {"type": "array", "items": INT}, "quadro": INT, "salvar": STR})
async def partes_checar(ctx, a):
    chave, f, st = await _ficha(ctx)
    if not f.get("modular"):
        raise ErroFerramenta("este asset não é modular (ficha sem 'modular'). Crie com horys_asset_novo "
                             "preset_partes='humanoide-ferreiro' ou defina modular/partes/juncoes com horys_ficha")
    indices = [int(i) for i in a["quadros"]] if a.get("quadros") else list(range(len(st["sprite"]["quadros"])))
    rel, quadros, ordem, refs = await checar_asset(ctx, f, st, indices)
    if len(indices) == len(st["sprite"]["quadros"]):          # só a checagem de todos os quadros libera a etapa
        f["partes_checagem"] = {"ok": rel.ok, "erros": len(rel.erros), "avisos": len(rel.avisos),
                                "n_quadros": len(indices), "hash": hash_checagem(f, quadros, refs)}
        ctx.salvar_ficha(chave, f)
    vista_q = int(a.get("quadro", indices[0]))
    pos = indices.index(vista_q) if vista_q in indices else 0
    saida = ""
    if a.get("salvar"):
        pasta = Path(a["salvar"])
        if not config.caminho_permitido(pasta):
            raise ErroFerramenta(f"pasta não permitida: {pasta}")
        escrever_saidas(pasta, f.get("nome") or "asset", rel, quadros, ordem, pos)
        saida = f"\ngravado em {pasta}"
    vistas = [P.vista_explodida(quadros[pos], ordem, escala=e) for e in (4, 3, 2, 1)]
    arr = next((v for v in vistas if max(v.shape[:2]) <= 900), vistas[-1])
    im = Image.fromarray(arr, "RGBA")
    img = imagem(pixels.png_b64(im))
    return [texto(rel.texto() + f"vista explodida do quadro {indices[pos]} (magenta = pixel oculto sob parte de cima)"
                  + saida), img]


def _par(f: dict, a: dict, ordem: list[str]) -> tuple[str, str, str]:
    """(nome, inferior, superior) pela junção nomeada ou por inferior+superior."""
    _, juncoes, _ = P.contratos_da_ficha(f)
    if a.get("juncao"):
        j = next((x for x in juncoes if x.nome == a["juncao"]), None)
        if j is None:
            raise ErroFerramenta(f"junção '{a['juncao']}' não existe (há: {', '.join(x.nome for x in juncoes)})")
        return j.nome, j.inferior, j.superior
    if a.get("inferior") and a.get("superior"):
        return f"{a['inferior']}+{a['superior']}", a["inferior"], a["superior"]
    raise ErroFerramenta("informe 'juncao' (nome do contrato) ou 'inferior' e 'superior'")


@ferramenta("horys_partes_recortar", """Copia uma 'regiao' {x,y,w,h} da camada OCULTA 'referencia' para uma 'parte', no
'quadro' (padrão o ativo; 'quadro_ref' se a referência estiver em outro). Só escreve onde a imagem composta final NÃO
muda (pixel coberto por parte de cima ou da mesma cor que a composição já mostra); o resto é recusado e contado.
Confere a composição depois e desfaz se mudou. 'sobrescrever': troca também pixels já existentes na parte.""",
            {"parte": STR, "regiao": {"type": "object"}, "quadro": INT, "quadro_ref": INT, "sobrescrever": BOOL},
            ["parte", "regiao"])
async def partes_recortar(ctx, a):
    chave, f, st = await _ficha(ctx)
    ordem = _partes(f, st)
    parte = a["parte"]
    if parte not in ordem:
        raise ErroFerramenta(f"'{parte}' não é parte do asset (partes: {', '.join(ordem)})")
    q = _quadros_alvo(a, st)[0]
    qr = int(a.get("quadro_ref", q))
    regiao = _regiao(a)
    atual = {p: await ler_rgba(ctx, p, q) for p in ordem}
    ref = await ler_rgba(ctx, "referencia", qr)
    r = P.recortar(atual, ordem, parte, ref, regiao, bool(a.get("sobrescrever")))
    n = await _aplicar_sem_mudar_composicao(ctx, parte, q, atual[parte], r.novo)
    return [texto(f"recorte da referência (quadro {qr}) em '{parte}' quadro {q}: {n} px copiados, {r.recusados} px "
                  "recusados por mudar a imagem composta. A composição ficou idêntica. Rode horys_partes_checar.")]


@ferramenta("horys_partes_estender", """Estende a parte INFERIOR de 1 a 2 px por baixo da SUPERIOR (anatomia oculta,
com a cor do vizinho mais próximo), pela 'juncao' (nome do contrato) ou por 'inferior'+'superior'. 'px' 1–2 (padrão 2);
'quadros' (padrão: o ativo; 'todos': true para todos). Só toca pixels cobertos pela superior; se a imagem composta
mudasse, ABORTA e REVERTE.""",
            {"juncao": STR, "inferior": STR, "superior": STR, "px": INT, "quadro": INT,
             "quadros": {"type": "array", "items": INT}, "todos": BOOL})
async def partes_estender(ctx, a):
    chave, f, st = await _ficha(ctx)
    ordem = _partes(f, st)
    nome, inf, sup = _par(f, a, ordem)
    for p in (inf, sup):
        if p not in ordem:
            raise ErroFerramenta(f"'{p}' não é parte do asset (partes: {', '.join(ordem)})")
    px = int(a.get("px", 2))
    if px not in (1, 2):
        raise ErroFerramenta("px tem que ser 1 ou 2")
    indices = list(range(len(st["sprite"]["quadros"]))) if a.get("todos") else _quadros_alvo(a, st)
    feitos, linhas = [], []
    for q in indices:
        atual = {p: await ler_rgba(ctx, p, q) for p in ordem}
        if not (atual[inf][..., 3] > 0).any() or not (atual[sup][..., 3] > 0).any():
            linhas.append(f"quadro {q}: parte vazia, nada a estender")
            continue
        r = P.estender(atual, ordem, inf, sup, px)
        try:
            n = await _aplicar_sem_mudar_composicao(ctx, inf, q, atual[inf], r.novo)
        except ErroFerramenta as e:
            if feitos:
                linhas.append(f"(quadros já estendidos: {feitos})")
            raise ErroFerramenta(f"{e} {' '.join(linhas)}")
        feitos.append(q)
        linhas.append(f"quadro {q}: +{n} px em '{inf}' sob '{sup}'" + (f" ({r.recusados} recusados)" if r.recusados else ""))
    return [texto(f"{nome}: " + "; ".join(linhas) + ". A composição ficou idêntica.")]
