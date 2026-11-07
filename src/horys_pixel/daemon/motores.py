"""Motores: Claude Code (`claude -p`) e Codex (`codex exec`) rodando sem terminal, com o MCP do horys."""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import time
from pathlib import Path

from .. import config

RAIZ_REPO = Path(__file__).resolve().parents[3]          # .../horys-generator-pixel
SRC = Path(__file__).resolve().parents[2]                # .../src
MOTORES = ("claude", "codex")

FERRAMENTAS_CLAUDE = ["mcp__horys__*", "Read", "Write", "Edit", "Glob", "Grep", "WebSearch", "WebFetch"]


def _barra(p) -> str:
    return str(p).replace("\\", "/")


def arquivo_mcp_json() -> Path:
    """Configuração MCP só com o servidor horys (para `claude --mcp-config ... --strict-mcp-config`)."""
    arq = config.casa() / "mcp-horys.json"
    dados = {"mcpServers": {"horys": {"command": sys.executable, "args": ["-m", "horys_pixel.mcp_ponte"],
                                      "env": {"PYTHONPATH": str(SRC)}}}}
    arq.write_text(json.dumps(dados, indent=2), encoding="utf-8")
    return arq


def outro(motor: str) -> str:
    return "codex" if motor == "claude" else "claude"


def executavel(motor: str) -> str | None:
    nome = config.preferencias().get(motor) or motor
    return shutil.which(nome) or (nome if Path(nome).exists() else None)


def comando(motor: str, prompt: str, pasta: Path, ultima_msg: Path) -> list[str]:
    exe = executavel(motor)
    if not exe:
        raise FileNotFoundError(f"não achei o '{motor}' no PATH (preferências: '{motor}')")
    if motor == "claude":
        # o prompt vai pela entrada padrão (no Windows o .CMD limita a linha de comando a ~8 mil caracteres)
        return [exe, "-p", "--mcp-config", str(arquivo_mcp_json()), "--strict-mcp-config",
                "--allowedTools", ",".join(FERRAMENTAS_CLAUDE), "--permission-mode", "acceptEdits",
                "--output-format", "json"]
    if motor == "codex":
        py = _barra(sys.executable)
        from ..ferramentas import registro
        registro.carregar_todas()
        aprovacoes = []
        for nome in registro.REGISTRO:   # o Codex aprova ferramenta MCP por ferramenta
            aprovacoes += ["-c", f'mcp_servers.horys.tools.{nome}.approval_mode="approve"']
        return [exe, "exec", "--skip-git-repo-check", "-s", "workspace-write", "-C", str(pasta), *aprovacoes,
                "-c", 'approval_policy="never"',
                "-c", f'mcp_servers.horys.command="{py}"',
                "-c", 'mcp_servers.horys.args=["-m","horys_pixel.mcp_ponte"]',
                "-c", f'mcp_servers.horys.env={{PYTHONPATH="{_barra(SRC)}"}}',
                "-c", "mcp_servers.horys.tool_timeout_sec=600",
                "--output-last-message", str(ultima_msg), "-"]       # "-": prompt pela entrada padrão
    raise ValueError(f"motor desconhecido: {motor}")


def _flags_sem_janela() -> dict:
    if os.name == "nt":
        return {"creationflags": 0x08000000}  # CREATE_NO_WINDOW
    return {}


async def rodar(motor: str, prompt: str, pasta: Path, nome_log: str = "motor",
                timeout: float | None = None, ao_iniciar=None) -> dict:
    """Roda o motor e devolve {"codigo","texto","log"}; 'texto' é a mensagem final do motor."""
    pasta = pasta.resolve()
    pasta.mkdir(parents=True, exist_ok=True)
    ultima = pasta / f"{nome_log}_ultima.txt"
    log = pasta / f"{nome_log}.log"
    cmd = comando(motor, prompt, pasta, ultima)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    t0 = time.time()
    with open(log, "wb") as f:
        f.write(("$ " + " ".join(c if len(c) < 200 else c[:200] + "…" for c in cmd) + "\n\n").encode("utf-8"))
        f.write(("[prompt pela entrada padrão]\n" + prompt + "\n\n").encode("utf-8"))
        proc = await asyncio.create_subprocess_exec(*cmd, cwd=str(pasta), stdin=asyncio.subprocess.PIPE,
                                                    stdout=asyncio.subprocess.PIPE, stderr=f, env=env,
                                                    **_flags_sem_janela())
        if ao_iniciar:
            ao_iniciar(proc)
        try:
            out, _ = await asyncio.wait_for(proc.communicate(prompt.encode("utf-8")),
                                            timeout or config.preferencias().get("tempo_max_motor_s", 10800))
        except asyncio.TimeoutError:
            proc.kill()
            out = b""
            f.write(b"\n[horys] tempo esgotado: motor encerrado\n")
        f.write(b"\n--- stdout ---\n" + (out or b""))
    texto = ""
    saida = (out or b"").decode("utf-8", "replace")
    if motor == "claude":
        try:
            texto = json.loads(saida).get("result") or ""
        except (json.JSONDecodeError, AttributeError):
            texto = saida
    else:
        texto = ultima.read_text(encoding="utf-8", errors="replace") if ultima.exists() else saida
    return {"codigo": proc.returncode, "texto": texto.strip(), "log": str(log), "segundos": round(time.time() - t0)}


def extrair_json(texto: str):
    """O último objeto JSON {...} do texto (revisor devolve um JSON no fim)."""
    fim = texto.rfind("}")
    while fim != -1:
        ini = texto.rfind("{", 0, fim)
        while ini != -1:
            try:
                return json.loads(texto[ini:fim + 1])
            except json.JSONDecodeError:
                ini = texto.rfind("{", 0, ini)
        fim = texto.rfind("}", 0, fim)
    return None
