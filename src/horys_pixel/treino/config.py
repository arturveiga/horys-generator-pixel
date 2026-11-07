"""Configuração do treino: TOML do conjunto (``--dataset_config``) e TOML do treino (``--config_file``).

``configurar`` grava em ``lora/vN/``::

    dataset.toml   pastas, repetições, resolução, legendas
    treino.toml    modelo-base, rede (LoRA), otimizador, precisão, saída — lido por train_network.py
                   (SD 1.5) ou sdxl_train_network.py (SDXL)
    plano.json     perfil, conjunto, modelo-base, nome do arquivo do LoRA, estimativa de tempo
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from ._comum import ErroTreino, agora_iso, gravar_json, ler_json, normalizar_versao, proxima_versao, versoes
from .alvo import AlvoTreino, resolver
from .conjunto import carregar_manifesto
from .perfis import PERFIS, Perfil, estimar

SEED_PADRAO = 42


# ---------------------------------------------------------------- escritor TOML mínimo


def _chave(k: str) -> str:
    return k if k.replace("_", "").replace("-", "").isalnum() else json.dumps(k, ensure_ascii=False)


def _valor(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            raise ValueError("TOML: float não finito")
        return repr(v)
    if isinstance(v, Path):
        v = str(v)
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)  # escapes do JSON são válidos em string básica TOML
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_valor(x) for x in v) + "]"
    raise TypeError(f"TOML: tipo não suportado: {type(v).__name__}")


def _eh_lista_tabelas(v) -> bool:
    return isinstance(v, (list, tuple)) and len(v) > 0 and all(isinstance(x, dict) for x in v)


def _escrever(linhas: list[str], caminho: str, tabela: dict, lista: bool = False) -> None:
    escalares = {k: v for k, v in tabela.items() if v is not None and not isinstance(v, dict) and not _eh_lista_tabelas(v)}
    if caminho:
        linhas.append(f"[[{caminho}]]" if lista else f"[{caminho}]")
    for k, v in escalares.items():
        linhas.append(f"{_chave(k)} = {_valor(v)}")
    linhas.append("")
    for k, v in tabela.items():
        sub = f"{caminho}.{_chave(k)}" if caminho else _chave(k)
        if isinstance(v, dict):
            _escrever(linhas, sub, v)
        elif _eh_lista_tabelas(v):
            for item in v:
                _escrever(linhas, sub, item, lista=True)


def para_toml(dados: dict, cabecalho: str | None = None) -> str:
    linhas: list[str] = []
    if cabecalho:
        linhas += [f"# {l}" if l else "#" for l in cabecalho.splitlines()] + [""]
    _escrever(linhas, "", dados)
    while linhas and linhas[-1] == "":
        linhas.pop()
    return "\n".join(linhas) + "\n"


# ---------------------------------------------------------------- dicionários


def dataset_dict(perfil: Perfil, pasta_imagens: Path | str, repeticoes: int) -> dict:
    return {
        "general": {
            "caption_extension": ".txt",
            "shuffle_caption": False,
            "enable_bucket": False,  # imagens já quadradas na resolução: nada é redimensionado (sem suavizar)
        },
        "datasets": [{
            "resolution": perfil.resolucao,
            "batch_size": perfil.batch_size,
            "subsets": [{"image_dir": str(pasta_imagens), "num_repeats": int(repeticoes)}],
        }],
    }


def treino_dict(
    perfil: Perfil,
    modelo_base: Path | str,
    pasta_saida: Path | str,
    nome_saida: str,
    epocas: int | None = None,
    seed: int = SEED_PADRAO,
    salvar_a_cada: int | None = None,
) -> dict:
    epocas = int(epocas or perfil.max_train_epochs)
    otim = {
        "optimizer_type": perfil.optimizer_type,
        "learning_rate": perfil.learning_rate,
        "unet_lr": perfil.unet_lr,
        "lr_scheduler": "cosine",
        "max_train_epochs": epocas,
        "min_snr_gamma": 5.0,
    }
    if perfil.text_encoder_lr is not None and not perfil.network_train_unet_only:
        otim["text_encoder_lr"] = perfil.text_encoder_lr
    rede = {
        "network_module": "networks.lora",
        "network_dim": perfil.network_dim,
        "network_alpha": perfil.network_alpha,
    }
    if perfil.network_train_unet_only:
        rede["network_train_unet_only"] = True
    desempenho = {
        "mixed_precision": perfil.mixed_precision,
        "gradient_checkpointing": perfil.gradient_checkpointing,
        "cache_latents": perfil.cache_latents,
        "sdpa": True,
        "max_data_loader_n_workers": 1,
    }
    if perfil.cache_text_encoder_outputs:
        desempenho["cache_text_encoder_outputs"] = True
    modelo = {"pretrained_model_name_or_path": str(modelo_base)}
    if perfil.sdxl and perfil.no_half_vae:
        modelo["no_half_vae"] = True
    return {
        "modelo": modelo,
        "rede": rede,
        "otimizador": otim,
        "desempenho": desempenho,
        "saida": {
            "output_dir": str(pasta_saida),
            "output_name": nome_saida,
            "save_model_as": "safetensors",
            "save_precision": "fp16",
            "save_every_n_epochs": int(salvar_a_cada or max(1, epocas // 5)),
            "seed": int(seed),
        },
    }


def argumentos_cli(treino: dict) -> list[str]:
    """O mesmo ``treino.toml`` como argumentos de linha de comando (alternativa ao ``--config_file``)."""
    args: list[str] = []
    for secao in treino.values():
        for k, v in (secao.items() if isinstance(secao, dict) else []):
            if v is None or v is False:
                continue
            args.append(f"--{k}")
            if v is not True:
                args.append(str(v))
    return args


# ---------------------------------------------------------------- configurar uma versão


def gerar(
    perfil: Perfil,
    pasta_conjunto: Path | str,
    modelo_base: Path | str,
    pasta_saida: Path | str,
    nome_saida: str,
    epocas: int | None = None,
    seed: int = SEED_PADRAO,
) -> dict:
    """Grava ``dataset.toml`` e ``treino.toml`` em ``pasta_saida``; devolve caminhos e dicionários."""
    man = carregar_manifesto(pasta_conjunto)
    if int(man.get("resolucao", 0)) != perfil.resolucao:
        raise ErroTreino(
            f"o conjunto foi preparado a {man.get('resolucao')} px, mas o perfil {perfil.nome} treina a "
            f"{perfil.resolucao} px. Prepare de novo com --resolucao {perfil.resolucao} (ou --perfil {perfil.nome})."
        )
    if not man.get("contagem", {}).get("total"):
        raise ErroTreino("o conjunto está vazio; aprove sprites ou mande imagens antes de configurar")
    pasta_saida = Path(pasta_saida)
    pasta_saida.mkdir(parents=True, exist_ok=True)
    ds = dataset_dict(perfil, man["pasta_imagens"], man["repeticoes"])
    tr = treino_dict(perfil, modelo_base, pasta_saida, nome_saida, epocas=epocas, seed=seed)
    cab = f"Gerado pelo horys-pixel em {agora_iso()} — perfil {perfil.nome}."
    arq_ds = pasta_saida / "dataset.toml"
    arq_tr = pasta_saida / "treino.toml"
    arq_ds.write_text(para_toml(ds, cab + "\nUso: --dataset_config dataset.toml"), encoding="utf-8")
    arq_tr.write_text(para_toml(tr, cab + f"\nUso: {perfil.script_treino} --config_file treino.toml"), encoding="utf-8")
    return {"dataset": arq_ds, "treino": arq_tr, "dataset_dict": ds, "treino_dict": tr, "manifesto": man}


def configurar(
    estilo,
    modelo_base: Path | str,
    perfil: Perfil | str,
    versao: str | None = None,
    epocas: int | None = None,
    seed: int = SEED_PADRAO,
) -> dict:
    """Prepara a versão ``vN`` (padrão: a próxima) de um estilo e grava ``plano.json``."""
    alvo: AlvoTreino = resolver(estilo)
    if isinstance(perfil, str):
        if perfil not in PERFIS:
            raise ErroTreino(f"perfil desconhecido: {perfil!r}. Opções: {', '.join(PERFIS)}")
        perfil = PERFIS[perfil]
    versao = normalizar_versao(versao) if versao else proxima_versao(alvo.lora)
    pasta = alvo.pasta_versao(versao)
    if (pasta / "info.json").is_file() and (ler_json(pasta / "info.json", {}) or {}).get("status") == "ok":
        raise ErroTreino(f"{versao} já foi treinada; configure uma versão nova (sem --versao) ou apague {pasta}")
    modelo_base = Path(modelo_base).expanduser()
    if modelo_base.suffix.lower() not in {".safetensors", ".ckpt"}:
        raise ErroTreino(f"modelo-base deve ser .safetensors (ou .ckpt): {modelo_base}")
    trigger = alvo.trigger_efetivo()
    nome_saida = f"{trigger}_{versao}"
    res = gerar(perfil, alvo.conjunto, modelo_base.resolve() if modelo_base.exists() else modelo_base,
                pasta, nome_saida, epocas=epocas, seed=seed)
    man = res["manifesto"]
    plano = {
        "versao": versao,
        "estilo": alvo.nome,
        "trigger": trigger,
        "perfil": perfil.como_dict(),
        "modelo_base": str(modelo_base.resolve() if modelo_base.exists() else modelo_base),
        "modelo_base_existe": modelo_base.is_file(),
        "conjunto": {
            "pasta": str(alvo.conjunto),
            "manifesto": str(alvo.manifesto),
            "assinatura": man.get("assinatura"),
            "contagem": man.get("contagem"),
            "repeticoes": man.get("repeticoes"),
            "licencas": man.get("licencas"),
        },
        "dataset_toml": str(res["dataset"]),
        "treino_toml": str(res["treino"]),
        "nome_saida": nome_saida,
        "arquivo_lora": str(pasta / f"{nome_saida}.safetensors"),
        "seed": seed,
        "estimativa": estimar(perfil, man["contagem"]["total"], man["repeticoes"], epocas),
        "criado_em": agora_iso(),
    }
    gravar_json(pasta / "plano.json", plano)
    return plano


def carregar_plano(estilo, versao: str | None = None) -> dict:
    """``plano.json`` de uma versão; sem versão, a mais nova que tiver plano."""
    alvo = resolver(estilo)
    if versao:
        versao = normalizar_versao(versao)
        plano = ler_json(alvo.pasta_versao(versao) / "plano.json")
    else:
        plano = None
        for v in reversed(versoes(alvo.lora)):
            plano = ler_json(alvo.pasta_versao(v) / "plano.json")
            if plano:
                break
    if not plano:
        alvo_txt = versao or "nenhuma versão"
        raise ErroTreino(f"{alvo_txt}: sem plano.json em {alvo.lora}. Rode o comando configurar antes.")
    return plano


def perfil_do_plano(plano: dict) -> Perfil:
    nome = plano["perfil"]["nome"]
    if nome in PERFIS:
        return PERFIS[nome]
    raise ErroTreino(f"perfil {nome!r} do plano não existe mais")
