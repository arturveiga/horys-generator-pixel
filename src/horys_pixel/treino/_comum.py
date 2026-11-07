"""Utilitários compartilhados do módulo de treino (JSON, versões, comandos com log)."""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import shlex
import subprocess
from pathlib import Path
from typing import Sequence


class ErroTreino(RuntimeError):
    """Erro esperado do fluxo de treino; a mensagem já é para a pessoa ler (pt-BR)."""


# ---------------------------------------------------------------- pastas


def pasta_horys() -> Path:
    """Pasta de dados do horys na máquina (``~/.horys-pixel``; ``HORYS_PIXEL_HOME`` muda)."""
    env = os.environ.get("HORYS_HOME") or os.environ.get("HORYS_PIXEL_HOME")
    return Path(env).expanduser() if env else Path.home() / ".horys-pixel"


# ---------------------------------------------------------------- tempo / json


def agora_iso() -> str:
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


def carimbo() -> str:
    return _dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def ler_json(caminho: Path | str, padrao=None):
    p = Path(caminho)
    if not p.is_file():
        return padrao
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return padrao


def gravar_json(caminho: Path | str, dados) -> Path:
    p = Path(caminho)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    os.replace(tmp, p)
    return p


# ---------------------------------------------------------------- versões (v1, v2, ...)

_RE_VERSAO = re.compile(r"^v(\d+)$")


def normalizar_versao(versao: str | int) -> str:
    texto = str(versao).strip().lower()
    if texto.isdigit():
        texto = "v" + texto
    m = _RE_VERSAO.match(texto)
    if not m or int(m.group(1)) < 1:
        raise ErroTreino(f"versão inválida: {versao!r} (use v1, v2, ...)")
    return f"v{int(m.group(1))}"


def numero_versao(versao: str | int) -> int:
    return int(normalizar_versao(versao)[1:])


def versoes(pasta_lora: Path) -> list[str]:
    """Versões existentes em ``lora/`` (pastas vN), em ordem crescente."""
    if not Path(pasta_lora).is_dir():
        return []
    achadas = [p.name for p in Path(pasta_lora).iterdir() if p.is_dir() and _RE_VERSAO.match(p.name)]
    return sorted(achadas, key=lambda v: int(v[1:]))


def proxima_versao(pasta_lora: Path) -> str:
    existentes = versoes(pasta_lora)
    return f"v{int(existentes[-1][1:]) + 1}" if existentes else "v1"


# ---------------------------------------------------------------- comandos


def formatar_comando(comando: Sequence) -> str:
    partes = [str(c) for c in comando]
    if os.name == "nt":
        return subprocess.list2cmdline(partes)
    return shlex.join(partes)


def env_kohya() -> dict:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def rodar_com_log(
    comando: Sequence,
    log: Path,
    cwd: Path | None = None,
    env: dict | None = None,
    eco: bool = True,
) -> int:
    """Roda ``comando`` acrescentando a saída (stdout+stderr) em ``log``. Devolve o código de saída."""
    log = Path(log)
    log.parent.mkdir(parents=True, exist_ok=True)
    partes = [str(c) for c in comando]
    with open(log, "a", encoding="utf-8") as f:
        f.write(f"\n=== {agora_iso()} ===\n$ {formatar_comando(partes)}\n")
        f.flush()
        try:
            proc = subprocess.Popen(
                partes,
                cwd=str(cwd) if cwd else None,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except OSError as e:
            msg = f"ERRO ao iniciar o comando: {e}\n"
            f.write(msg)
            if eco:
                print(msg, end="")
            return 127
        assert proc.stdout is not None
        for linha in proc.stdout:
            f.write(linha)
            f.flush()
            if eco:
                print(linha, end="", flush=True)
        codigo = proc.wait()
        f.write(f"=== fim (código {codigo}) {agora_iso()} ===\n")
    return codigo


# ---------------------------------------------------------------- hash


def sha256_arquivo(caminho: Path, bloco: int = 4 << 20) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for pedaco in iter(lambda: f.read(bloco), b""):
            h.update(pedaco)
    return h.hexdigest()


def sha256_com_cache(caminho: Path) -> str:
    """SHA-256 de arquivo grande (modelo-base), com cache por caminho+tamanho+data em ``~/.horys-pixel``."""
    caminho = Path(caminho).resolve()
    st = caminho.stat()
    chave = f"{caminho}|{st.st_size}|{int(st.st_mtime)}"
    cache_arq = pasta_horys() / "hashes.json"
    cache = ler_json(cache_arq, {}) or {}
    if chave in cache:
        return cache[chave]
    valor = sha256_arquivo(caminho)
    cache[chave] = valor
    try:
        gravar_json(cache_arq, cache)
    except OSError:
        pass
    return valor


def listar_pngs(pasta: Path) -> list[Path]:
    pasta = Path(pasta)
    if not pasta.is_dir():
        return []
    return sorted(p for p in pasta.iterdir() if p.suffix.lower() == ".png" and p.is_file())
