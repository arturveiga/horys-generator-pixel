"""Instalação e localização do kohya-ss/sd-scripts, fora do repo, em ``~/.horys-pixel/kohya/``.

Estrutura::

    ~/.horys-pixel/kohya/
      sd-scripts/        git clone de https://github.com/kohya-ss/sd-scripts
      venv/              ambiente Python próprio (torch com CUDA + requirements do sd-scripts)
      accelerate.yaml    config do accelerate gerada sem perguntas (1 GPU, fp16)
      instalar.log       log da instalação
      instalado.json     marca de instalação concluída (ref, commit, torch)

``HORYS_KOHYA_DIR`` muda a pasta; ``HORYS_PIXEL_HOME`` muda a base ``~/.horys-pixel``.
Nada é baixado sem ``instalar(executar=True)``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from . import gpu as _gpu
from ._comum import ErroTreino, agora_iso, formatar_comando, gravar_json, ler_json, pasta_horys, rodar_com_log

REPO_URL = "https://github.com/kohya-ss/sd-scripts"
REF_PADRAO = "main"
# Versões indicadas no README do sd-scripts (ramo main; conferido na 0.12.3, 2026-10-26). Trocáveis por
# parâmetro. O requirements.txt já traz bitsandbytes (AdamW8bit), accelerate etc.; o torch fica de fora dele.
TORCH_VERSAO = "2.6.0"
TORCHVISION_VERSAO = "0.21.0"
INDICE_TORCH = "https://download.pytorch.org/whl/{cuda}"

# Nomes dos scripts do sd-scripts. Geração: ``gen_img.py`` (atual, SD1/2 e SDXL com --sdxl); ``gen_img_diffusers.py``
# (SD1/2) foi removido na 0.12.0 e ``sdxl_gen_img.py`` ainda existe — ficam como reserva para refs antigas.
SCRIPTS = {
    "treino_sd15": "train_network.py",
    "treino_sdxl": "sdxl_train_network.py",
}
SCRIPTS_GERACAO = {
    "sd15": ("gen_img.py", "gen_img_diffusers.py"),
    "sdxl": ("gen_img.py", "sdxl_gen_img.py"),
}


@dataclass
class Passo:
    descricao: str
    comando: list[str]
    cwd: Path | None = None
    pular: bool = False
    motivo: str = ""

    def texto(self) -> str:
        cmd = formatar_comando(self.comando)
        local = f"   (em {self.cwd})" if self.cwd else ""
        marca = f"   [pula: {self.motivo}]" if self.pular else ""
        return f"{self.descricao}\n    {cmd}{local}{marca}"


# ---------------------------------------------------------------- caminhos


def raiz() -> Path:
    env = os.environ.get("HORYS_KOHYA_DIR")
    return Path(env).expanduser() if env else pasta_horys() / "kohya"


def pasta_repo() -> Path:
    return raiz() / "sd-scripts"


def pasta_venv() -> Path:
    return raiz() / "venv"


def python_kohya() -> Path:
    """Python do venv do kohya (pode ainda não existir)."""
    if os.name == "nt":
        return pasta_venv() / "Scripts" / "python.exe"
    return pasta_venv() / "bin" / "python"


def config_accelerate() -> Path:
    return raiz() / "accelerate.yaml"


def log_instalacao() -> Path:
    return raiz() / "instalar.log"


def marca_instalacao() -> Path:
    return raiz() / "instalado.json"


def script(nome: str) -> Path:
    """Caminho de um script do sd-scripts, por nome de arquivo ou apelido (``treino_sd15``, ``treino_sdxl``)."""
    return pasta_repo() / SCRIPTS.get(nome, nome)


def script_geracao(familia: str) -> Path:
    """Script de geração existente para a família (``sd15``/``sdxl``); o atual (gen_img.py) se nada existir."""
    candidatos = SCRIPTS_GERACAO.get(familia)
    if not candidatos:
        raise ErroTreino(f"família desconhecida: {familia!r}")
    for nome in candidatos:
        if (pasta_repo() / nome).is_file():
            return pasta_repo() / nome
    return pasta_repo() / candidatos[0]


def instalado() -> bool:
    return (
        marca_instalacao().is_file()
        and python_kohya().is_file()
        and script("treino_sd15").is_file()
    )


def info_instalacao() -> dict | None:
    return ler_json(marca_instalacao())


# ---------------------------------------------------------------- plano de instalação


def cuda_para_driver(driver: str | None) -> str:
    """Índice de rodas do PyTorch conforme o driver: CUDA 12.4 com driver ≥ 525, senão CUDA 11.8."""
    try:
        principal = int(str(driver).split(".")[0])
    except (TypeError, ValueError):
        return "cu124"
    return "cu124" if principal >= 525 else "cu118"


def python_base_sugerido() -> str:
    """Python para criar o venv: o sd-scripts recomenda 3.10; usa ``py -3.10`` se houver, senão o atual."""
    if os.name == "nt":
        try:
            r = subprocess.run(
                ["py", "-3.10", "-c", "import sys; print(sys.executable)"],
                capture_output=True, text=True, timeout=15,
            )
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    return sys.executable


def instalar(
    executar: bool = False,
    ref: str = REF_PADRAO,
    python_base: str | None = None,
    cuda: str | None = None,
    torch_versao: str = TORCH_VERSAO,
    torchvision_versao: str = TORCHVISION_VERSAO,
    eco: bool = True,
) -> list[Passo]:
    """Passos para instalar o sd-scripts. Sem ``executar``, só devolve os passos; com, roda e registra log."""
    python_base = python_base or python_base_sugerido()
    if cuda is None:
        placa = _gpu.detectar()
        cuda = cuda_para_driver(placa.get("driver") if placa else None)
    repo, venv_py = pasta_repo(), python_kohya()
    indice = INDICE_TORCH.format(cuda=cuda)
    ja_clonado = (repo / ".git").is_dir()
    tem_venv = venv_py.is_file()

    passos = [
        Passo("Baixar o sd-scripts (git clone)", ["git", "clone", REPO_URL, str(repo)],
              pular=ja_clonado, motivo="já clonado"),
        Passo("Atualizar referências do repositório", ["git", "-C", str(repo), "fetch", "--tags", "origin"],
              pular=not ja_clonado, motivo="clone novo já está atualizado"),
        Passo(f"Usar a versão {ref}", ["git", "-C", str(repo), "checkout", ref]),
        Passo("Criar o ambiente Python do kohya (venv)", [python_base, "-m", "venv", str(pasta_venv())],
              pular=tem_venv, motivo="venv já existe"),
        Passo("Atualizar o pip", [str(venv_py), "-m", "pip", "install", "--upgrade", "pip"]),
        Passo(
            f"Instalar torch {torch_versao} com CUDA ({cuda})",
            [str(venv_py), "-m", "pip", "install", f"torch=={torch_versao}",
             f"torchvision=={torchvision_versao}", "--index-url", indice],
        ),
        Passo("Instalar as dependências do sd-scripts",
              [str(venv_py), "-m", "pip", "install", "--upgrade", "-r", "requirements.txt"], cwd=repo),
        Passo(
            "Configurar o accelerate sem perguntas (1 GPU, fp16)",
            [str(venv_py), "-m", "accelerate.commands.accelerate_cli", "config", "default",
             "--config_file", str(config_accelerate()), "--mixed_precision", "fp16"],
        ),
        Passo("Conferir torch e CUDA",
              [str(venv_py), "-c", "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available())"]),
    ]
    if not executar:
        return passos

    raiz().mkdir(parents=True, exist_ok=True)
    log = log_instalacao()
    for passo in passos:
        if passo.pular:
            continue
        if eco:
            print(f"\n» {passo.descricao}", flush=True)
        codigo = rodar_com_log(passo.comando, log, cwd=passo.cwd, eco=eco)
        if codigo != 0:
            raise ErroTreino(f"falhou: {passo.descricao} (código {codigo}). Veja o log: {log}")
    commit = None
    try:
        r = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=15)
        commit = r.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        pass
    gravar_json(marca_instalacao(), {
        "repo": REPO_URL, "ref": ref, "commit": commit, "torch": torch_versao, "cuda": cuda,
        "python_base": python_base, "instalado_em": agora_iso(),
    })
    return passos
