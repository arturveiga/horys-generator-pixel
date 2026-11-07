"""Roda o treino de uma versão (``lora/vN/``) com o Python do venv do kohya.

Sem ``executar=True`` só monta e devolve o comando. Com ele, roda com log em ``lora/vN/treino.log`` e
grava ``lora/vN/info.json`` (perfil, conjunto, hash do modelo-base, datas, duração, resultado).
"""

from __future__ import annotations

import time
from pathlib import Path

from . import kohya
from ._comum import ErroTreino, agora_iso, env_kohya, formatar_comando, gravar_json, sha256_com_cache, rodar_com_log
from .alvo import resolver
from .config import carregar_plano, perfil_do_plano


def montar_comando(plano: dict, python: Path | str | None = None, usar_accelerate: bool = True) -> list[str]:
    """``accelerate launch`` (ou python direto) + script de treino + ``--dataset_config`` + ``--config_file``."""
    perfil = perfil_do_plano(plano)
    py = str(python or kohya.python_kohya())
    script = str(kohya.script(perfil.script_treino))
    if usar_accelerate:
        cmd = [py, "-m", "accelerate.commands.launch"]
        if kohya.config_accelerate().is_file():
            cmd += ["--config_file", str(kohya.config_accelerate())]
        cmd += ["--num_cpu_threads_per_process", "1", script]
    else:
        cmd = [py, script]
    cmd += ["--dataset_config", plano["dataset_toml"], "--config_file", plano["treino_toml"]]
    return cmd


def treinar(
    estilo,
    versao: str | None = None,
    executar: bool = False,
    python: Path | str | None = None,
    usar_accelerate: bool = True,
    eco: bool = True,
) -> dict:
    """Treina a versão configurada (padrão: a mais nova com ``plano.json``)."""
    alvo = resolver(estilo)
    plano = carregar_plano(alvo, versao)
    versao = plano["versao"]
    pasta = alvo.pasta_versao(versao)
    comando = montar_comando(plano, python=python, usar_accelerate=usar_accelerate)
    resultado = {
        "versao": versao,
        "comando": comando,
        "comando_texto": formatar_comando(comando),
        "cwd": str(kohya.pasta_repo()),
        "log": str(pasta / "treino.log"),
        "info": str(pasta / "info.json"),
        "arquivo_lora": plano["arquivo_lora"],
        "estimativa": plano.get("estimativa"),
        "executado": False,
    }
    if not executar:
        return resultado

    if python is None and not kohya.instalado():
        raise ErroTreino("o kohya (sd-scripts) não está instalado. Rode: python -m horys_pixel.treino instalar --executar")
    modelo = Path(plano["modelo_base"])
    if not modelo.is_file():
        raise ErroTreino(f"modelo-base não encontrado: {modelo}. Baixe o .safetensors e rode configurar de novo.")
    if not Path(plano["dataset_toml"]).is_file() or not Path(plano["treino_toml"]).is_file():
        raise ErroTreino(f"TOML da {versao} sumiu; rode configurar de novo.")

    if eco:
        print(f"Calculando o hash do modelo-base ({modelo.name})...", flush=True)
    hash_modelo = sha256_com_cache(modelo)
    info = {
        "versao": versao,
        "status": "treinando",
        "perfil": plano["perfil"],
        "conjunto": plano["conjunto"],
        "modelo_base": {"caminho": str(modelo), "sha256": hash_modelo, "tamanho": modelo.stat().st_size},
        "comando": comando,
        "inicio": agora_iso(),
    }
    gravar_json(pasta / "info.json", info)
    t0 = time.monotonic()
    cwd = kohya.pasta_repo() if kohya.pasta_repo().is_dir() else None
    codigo = rodar_com_log(comando, pasta / "treino.log", cwd=cwd, env=env_kohya(), eco=eco)
    duracao = time.monotonic() - t0
    arquivo = Path(plano["arquivo_lora"])
    ok = codigo == 0 and arquivo.is_file()
    info.update({
        "status": "ok" if ok else "falhou",
        "codigo_saida": codigo,
        "fim": agora_iso(),
        "duracao_s": round(duracao, 1),
        "arquivo_lora": str(arquivo) if arquivo.is_file() else None,
    })
    gravar_json(pasta / "info.json", info)
    resultado.update({"executado": True, "codigo": codigo, "status": info["status"], "duracao_s": info["duracao_s"]})
    if not ok:
        motivo = f"código {codigo}" if codigo else "o arquivo do LoRA não foi criado"
        raise ErroTreino(f"o treino da {versao} falhou ({motivo}). Veja o log: {pasta / 'treino.log'}")
    return resultado
