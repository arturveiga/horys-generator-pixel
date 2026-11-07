"""Avaliação de versões do LoRA: lote de teste fixo, prancha comparativa, notas e promoção.

Ciclo (``docs/treino.md``): gera o mesmo lote com a versão anterior (ou o modelo sem LoRA) e a nova →
prancha lado a lado → o revisor dá nota às duas (fora daqui; ``registrar_notas``) → a pessoa escolhe →
``promover`` só troca a versão ativa (``lora/ativo.json``) se a nota for MAIOR que a da ativa E houver o sim.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Sequence

from PIL import Image, ImageDraw, ImageFont

from . import _geracao
from ._comum import ErroTreino, agora_iso, formatar_comando, gravar_json, ler_json, normalizar_versao, numero_versao, versoes
from .alvo import AlvoTreino, resolver
from .config import carregar_plano, perfil_do_plano
from .conjunto import tipo_legenda

# Lote fixo: um prompt por tipo de asset, seed fixo. Descrições em inglês (o codificador de texto do SD é inglês).
LOTE_TESTE: tuple[dict, ...] = (
    {"tipo": "personagem", "descricao": "knight in armor, full body, front view", "seed": 1001},
    {"tipo": "personagem", "descricao": "young mage with a wooden staff, full body, three-quarter view", "seed": 1002},
    {"tipo": "inimigo", "descricao": "green slime monster", "seed": 1003},
    {"tipo": "item", "descricao": "red health potion in a glass bottle", "seed": 1004},
    {"tipo": "prop", "descricao": "closed wooden treasure chest", "seed": 1005},
    {"tipo": "tile", "descricao": "grass ground with small stones, top-down", "seed": 1006},
    {"tipo": "prédio", "descricao": "small village house with red roof", "seed": 1007},
    {"tipo": "efeito", "descricao": "fire explosion", "seed": 1008},
)
ROTULO_BASE = "base"


def lote(trigger: str, resolucao: int, itens: Sequence[dict] = LOTE_TESTE) -> list[dict]:
    saida = []
    for it in itens:
        prompt = f"{trigger}, pixel art, {tipo_legenda(it['tipo'])}, {it['descricao']}"
        saida.append({**it, "prompt": prompt, "linha": _geracao.linha_prompt(prompt, it["seed"], resolucao)})
    return saida


def _assinatura(linhas: Sequence[str], modelo: str, lora: str | None) -> str:
    return hashlib.sha256(json.dumps([list(linhas), modelo, lora]).encode()).hexdigest()


# ---------------------------------------------------------------- estado ativo


def ler_ativo(estilo) -> dict | None:
    alvo = resolver(estilo)
    return ler_json(alvo.ativo)


def ler_notas(alvo: AlvoTreino, versao: str) -> dict | None:
    return ler_json(alvo.pasta_versao(versao) / "notas.json")


def escolher_contra(alvo: AlvoTreino, versao: str) -> str:
    """Com quem comparar: a versão ativa; senão a anterior treinada; senão o modelo sem LoRA."""
    ativo = ler_json(alvo.ativo)
    if ativo and ativo.get("versao") and ativo["versao"] != versao:
        return ativo["versao"]
    n = numero_versao(versao)
    for v in reversed(versoes(alvo.lora)):
        if numero_versao(v) < n and (ler_json(alvo.pasta_versao(v) / "info.json", {}) or {}).get("status") == "ok":
            return v
    return ROTULO_BASE


# ---------------------------------------------------------------- prancha


def _fonte():
    try:
        return ImageFont.load_default(size=14)
    except TypeError:  # Pillow antigo
        return ImageFont.load_default()


def prancha(
    colunas: Sequence[tuple[str, Sequence[Path | str]]],
    rotulos_linhas: Sequence[str],
    saida: Path | str,
    celula: int = 192,
    fundo=(32, 32, 36),
) -> Path:
    """Prancha PNG: uma coluna por versão, uma linha por prompt. Redimensiona por vizinho mais próximo."""
    if not colunas:
        raise ErroTreino("prancha sem colunas")
    n_linhas = len(rotulos_linhas)
    for rotulo, imgs in colunas:
        if len(imgs) != n_linhas:
            raise ErroTreino(f"coluna {rotulo}: {len(imgs)} imagens para {n_linhas} linhas")
    margem, topo, esquerda = 8, 28, 120
    largura = esquerda + len(colunas) * (celula + margem) + margem
    altura = topo + n_linhas * (celula + margem) + margem
    img = Image.new("RGB", (largura, altura), fundo)
    d = ImageDraw.Draw(img)
    fonte = _fonte()
    for c, (rotulo, imgs) in enumerate(colunas):
        x = esquerda + margem + c * (celula + margem)
        d.text((x, 6), str(rotulo), fill=(235, 235, 235), font=fonte)
        for l, caminho in enumerate(imgs):
            y = topo + margem + l * (celula + margem)
            with Image.open(caminho) as im:
                cel = im.convert("RGB").resize((celula, celula), Image.Resampling.NEAREST)
            img.paste(cel, (x, y))
    for l, rot in enumerate(rotulos_linhas):
        y = topo + margem + l * (celula + margem)
        d.text((margem, y + celula // 2 - 8), str(rot)[:16], fill=(200, 200, 200), font=fonte)
    saida = Path(saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    img.save(saida)
    return saida


# ---------------------------------------------------------------- avaliar


def _coluna(alvo: AlvoTreino, rotulo: str, plano_ref: dict, executar: bool, python, eco: bool) -> dict:
    """Plano (e, com executar, as imagens) do lote de teste para uma versão ou para o modelo sem LoRA."""
    if rotulo == ROTULO_BASE:
        plano, lora, pasta = plano_ref, None, alvo.lora / "_base" / "teste"
    else:
        plano = carregar_plano(alvo, rotulo)
        lora, pasta = plano["arquivo_lora"], alvo.pasta_versao(rotulo) / "teste"
    perfil = perfil_do_plano(plano)
    itens = lote(plano["trigger"], perfil.resolucao)
    linhas = [it["linha"] for it in itens]
    arq_prompts = pasta / "prompts.txt"
    cmd = _geracao.comando(perfil, plano["modelo_base"], arq_prompts, pasta, lora=lora, python=python)
    assinatura = _assinatura(linhas, plano["modelo_base"], lora)
    col = {"rotulo": rotulo, "pasta": str(pasta), "comando": cmd, "comando_texto": formatar_comando(cmd),
           "itens": itens, "imagens": [], "reaproveitado": False}
    feito = ler_json(pasta / "lote.json", {}) or {}
    if feito.get("assinatura") == assinatura and all(Path(p).is_file() for p in feito.get("imagens", [])) \
            and len(feito.get("imagens", [])) == len(itens):
        col.update(imagens=feito["imagens"], reaproveitado=True)
        return col
    if not executar:
        return col
    if lora and not Path(lora).is_file():
        raise ErroTreino(f"{rotulo}: arquivo do LoRA não encontrado ({lora}); treine essa versão antes.")
    if not Path(plano["modelo_base"]).is_file():
        raise ErroTreino(f"modelo-base não encontrado: {plano['modelo_base']}")
    _geracao.escrever_prompts(arq_prompts, linhas)
    if eco:
        print(f"\n» Gerando o lote de teste com {rotulo} ({len(itens)} imagens)...", flush=True)
    imagens = _geracao.rodar(cmd, pasta, pasta / "geracao.log", len(itens), eco=eco)
    col["imagens"] = [str(p) for p in imagens]
    gravar_json(pasta / "lote.json", {"assinatura": assinatura, "imagens": col["imagens"],
                                      "itens": itens, "criado_em": agora_iso()})
    return col


def avaliar(
    estilo,
    versao: str | None = None,
    contra: str | None = None,
    executar: bool = False,
    python: Path | str | None = None,
    eco: bool = True,
) -> dict:
    """Gera o lote de teste com ``contra`` e ``versao``, monta a prancha e grava ``lora/vN/avaliacao.json``."""
    alvo = resolver(estilo)
    plano = carregar_plano(alvo, versao)
    versao = plano["versao"]
    contra = contra if contra == ROTULO_BASE else (normalizar_versao(contra) if contra else escolher_contra(alvo, versao))
    if contra == versao:
        raise ErroTreino("compare com outra versão (ou 'base')")
    colunas = [_coluna(alvo, contra, plano, executar, python, eco), _coluna(alvo, versao, plano, executar, python, eco)]
    pasta = alvo.pasta_versao(versao)
    arq_prancha = pasta / "avaliacao" / f"prancha_{contra}_vs_{versao}.png"
    resultado = {
        "versao": versao,
        "contra": contra,
        "colunas": colunas,
        "prancha": str(arq_prancha),
        "avaliacao": str(pasta / "avaliacao.json"),
        "executado": False,
    }
    if not all(c["imagens"] for c in colunas):
        return resultado  # plano apenas (sem executar e sem imagens prontas para reaproveitar)
    rotulos = [it["tipo"] for it in colunas[1]["itens"]]
    prancha([(c["rotulo"], c["imagens"]) for c in colunas], rotulos, arq_prancha)
    anterior = ler_json(pasta / "avaliacao.json", {}) or {}
    gravar_json(pasta / "avaliacao.json", {
        "versao": versao,
        "contra": contra,
        "criado_em": agora_iso(),
        "prancha": str(arq_prancha),
        "lote": [{k: it[k] for k in ("tipo", "descricao", "seed", "prompt")} for it in colunas[1]["itens"]],
        "imagens": {c["rotulo"]: c["imagens"] for c in colunas},
        "notas": anterior.get("notas", {}),
    })
    resultado["executado"] = True
    return resultado


# ---------------------------------------------------------------- notas e promoção


def _nota_de(notas) -> float:
    if isinstance(notas, (int, float)) and not isinstance(notas, bool):
        valor = float(notas)
    elif isinstance(notas, dict):
        if "nota" in notas:
            valor = float(notas["nota"])
        else:
            numeros = [float(v) for v in notas.values() if isinstance(v, (int, float)) and not isinstance(v, bool)]
            if not numeros:
                raise ErroTreino("notas sem valor numérico")
            valor = sum(numeros) / len(numeros)
    else:
        raise ErroTreino("notas: use um número de 0 a 100 ou um dicionário {critério: nota}")
    if not 0 <= valor <= 100:
        raise ErroTreino(f"nota fora de 0–100: {valor}")
    return round(valor, 2)


def registrar_notas(estilo, versao: str, notas, revisor: str | None = None) -> dict:
    """Guarda a nota do revisor para a versão (``lora/vN/notas.json``) e anota em ``avaliacao.json``."""
    alvo = resolver(estilo)
    versao = normalizar_versao(versao)
    pasta = alvo.pasta_versao(versao)
    if not pasta.is_dir():
        raise ErroTreino(f"versão {versao} não existe em {alvo.lora}")
    registro = {"versao": versao, "nota": _nota_de(notas), "detalhes": notas, "revisor": revisor,
                "registrado_em": agora_iso()}
    gravar_json(pasta / "notas.json", registro)
    # a nota também fica nas avaliações em que esta versão aparece
    for v in versoes(alvo.lora):
        arq = alvo.pasta_versao(v) / "avaliacao.json"
        aval = ler_json(arq)
        if aval and versao in (aval.get("versao"), aval.get("contra")):
            aval.setdefault("notas", {})[versao] = registro["nota"]
            gravar_json(arq, aval)
    return registro


def promover(estilo, versao: str, aprovado_pelo_usuario: bool) -> dict:
    """Torna ``versao`` a ativa só se a nota dela for maior que a da ativa E a pessoa tiver aprovado."""
    alvo = resolver(estilo)
    versao = normalizar_versao(versao)
    motivos = []
    notas = ler_notas(alvo, versao)
    if not notas:
        motivos.append(f"{versao} ainda não tem nota do revisor")
    if not aprovado_pelo_usuario:
        motivos.append("falta o sim de quem usa")
    plano = ler_json(alvo.pasta_versao(versao) / "plano.json")
    arquivo = plano.get("arquivo_lora") if plano else None
    if not arquivo or not Path(arquivo).is_file():
        motivos.append(f"o arquivo do LoRA da {versao} não existe (treinou?)")
    ativo = ler_json(alvo.ativo)
    nota_ativa = None
    if ativo and ativo.get("versao"):
        if ativo["versao"] == versao:
            motivos.append(f"{versao} já é a versão ativa")
        atual = ler_notas(alvo, ativo["versao"])
        nota_ativa = atual["nota"] if atual else ativo.get("nota")
        if notas and nota_ativa is not None and notas["nota"] <= nota_ativa:
            motivos.append(f"nota {notas['nota']} não é maior que a da ativa {ativo['versao']} ({nota_ativa})")
    if motivos:
        return {"promovido": False, "versao": versao, "motivos": motivos, "ativo": ativo}
    historico = list((ativo or {}).get("historico", []))
    if ativo and ativo.get("versao"):
        historico.append({"versao": ativo["versao"], "nota": nota_ativa, "ate": agora_iso()})
    novo = {
        "versao": versao,
        "nota": notas["nota"],
        "arquivo_lora": arquivo,
        "modelo_base": plano.get("modelo_base"),
        "perfil": plano.get("perfil", {}).get("nome"),
        "trigger": plano.get("trigger"),
        "promovido_em": agora_iso(),
        "historico": historico,
    }
    gravar_json(alvo.ativo, novo)
    return {"promovido": True, "versao": versao, "motivos": [], "ativo": novo}
