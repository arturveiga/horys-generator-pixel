"""Configuração local do horys-pixel: pasta de dados, token, porta e preferências.

Tudo fica em ~/.horys-pixel (ou HORYS_HOME). Nada aqui vai para o repositório.
"""
from __future__ import annotations

import json
import os
import secrets
from pathlib import Path

PORTA_PADRAO = 9140

PREFERENCIAS_PADRAO = {
    "motor_padrao": "claude",          # claude | codex
    "revisor": "claude",               # claude | cruzado | codex (Codex é opcional)
    "estilo_padrao": "horys-cozy",
    "pastas_permitidas": [],           # além da pasta home do usuário e de ~/.horys-pixel
    "aseprite": None,                  # caminho do aseprite.exe (para modo batch); None = procura
    "claude": "claude",
    "codex": "codex",
    "tempo_max_motor_s": 3 * 3600,
}


def casa() -> Path:
    p = Path(os.environ.get("HORYS_HOME") or (Path.home() / ".horys-pixel"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def porta() -> int:
    v = os.environ.get("HORYS_PORTA")
    if v:
        return int(v)
    return int(preferencias().get("porta", PORTA_PADRAO))


def arquivo_token() -> Path:
    return casa() / "token"


def token(novo: bool = False) -> str:
    """Lê o token; cria na primeira vez (ou troca, com novo=True). Nunca imprima o token em log."""
    env = os.environ.get("HORYS_TOKEN")
    if env and not novo:
        return env.strip()
    arq = arquivo_token()
    if novo or not arq.exists():
        t = secrets.token_hex(24)
        arq.write_text(t, encoding="ascii")
        try:
            os.chmod(arq, 0o600)
        except OSError:
            pass
        return t
    return arq.read_text(encoding="ascii").strip()


def arquivo_preferencias() -> Path:
    return casa() / "preferencias.json"


def preferencias() -> dict:
    p = dict(PREFERENCIAS_PADRAO)
    arq = arquivo_preferencias()
    if arq.exists():
        try:
            p.update(json.loads(arq.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            pass
    return p


def salvar_preferencias(mudancas: dict) -> dict:
    p = preferencias()
    p.update(mudancas)
    arquivo_preferencias().write_text(json.dumps(p, indent=2, ensure_ascii=False), encoding="utf-8")
    return p


def pasta(nome: str) -> Path:
    """Subpasta de dados (pedidos, logs, temp, backups...)."""
    p = casa() / nome
    p.mkdir(parents=True, exist_ok=True)
    return p


def pastas_permitidas() -> list[Path]:
    base = [Path.home(), casa()]
    for x in preferencias().get("pastas_permitidas", []):
        base.append(Path(x))
    tmp = os.environ.get("TEMP") or os.environ.get("TMP")
    if tmp:
        base.append(Path(tmp))
    return [b.resolve() for b in base]


def caminho_permitido(caminho: str | os.PathLike) -> bool:
    try:
        alvo = Path(caminho).resolve()
    except OSError:
        return False
    for b in pastas_permitidas():
        try:
            alvo.relative_to(b)
            return True
        except ValueError:
            continue
    return False


def achar_aseprite() -> str | None:
    pref = preferencias().get("aseprite")
    candidatos = [pref] if pref else []
    candidatos += [
        os.environ.get("ASEPRITE"),
        str(Path.home() / "Documents" / "aseprite" / "aseprite.exe"),
        r"C:\Program Files\Aseprite\Aseprite.exe",
        r"C:\Program Files (x86)\Steam\steamapps\common\Aseprite\Aseprite.exe",
        "/Applications/Aseprite.app/Contents/MacOS/aseprite",
        "/usr/bin/aseprite",
    ]
    for c in candidatos:
        if c and Path(c).exists():
            return str(c)
    return None
