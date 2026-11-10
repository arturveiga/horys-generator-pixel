"""Instalação: extensão no Aseprite, MCP no Claude Code e no Codex, skills e (opcional) início com o Windows.

Cada passo é independente e mostra o que faz. `simular=True` só descreve.
"""
from __future__ import annotations

import configparser
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from . import config

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src"
EXT = RAIZ / "extension"
SKILLS = ["horys-pixel", "horys-pixel-review", "horys-pixel-estilo"]
NOME_EXT = "horys-pixel"
ACESSO = 2 | 4 | 8          # gravar | ler | abrir conexão (FileAccessMode do Aseprite)


def pasta_usuario_aseprite() -> Path:
    env = os.environ.get("ASEPRITE_USER_FOLDER")
    if env:
        return Path(env)
    if os.name == "nt":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "Aseprite"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Aseprite"
    return Path.home() / ".config" / "aseprite"


def aseprite_aberto() -> bool:
    try:
        if os.name == "nt":
            out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq aseprite.exe"], capture_output=True, text=True).stdout
            return "aseprite.exe" in out.lower()
        out = subprocess.run(["pgrep", "-i", "aseprite"], capture_output=True, text=True).stdout
        return bool(out.strip())
    except OSError:
        return False


def instalar_extensao(pasta_usuario: Path | None = None, simular: bool = False) -> list[str]:
    base = pasta_usuario or pasta_usuario_aseprite()
    destino = base / "extensions" / NOME_EXT
    log = [f"extensão: {EXT} → {destino}"]
    if simular:
        return log
    if destino.exists():
        pref = destino / "__pref.lua"
        guardado = pref.read_bytes() if pref.exists() else None
        shutil.rmtree(destino)
    else:
        guardado = None
    shutil.copytree(EXT, destino)
    if guardado is not None:
        (destino / "__pref.lua").write_bytes(guardado)
    log.append("ok (reabra o Aseprite para carregar a extensão)")
    return log


def chaves_scripts(pasta_ext: Path) -> list[str]:
    """SHA-1 do caminho de cada script que pede permissão (como o Aseprite calcula), em / e em \\."""
    chaves = []
    for nome in sorted(p.name for p in EXT.glob("*.lua")):   # handlers.lua abre/salva arquivos, plugin.lua conecta...
        p = str(pasta_ext / nome)
        for v in {p, p.replace("/", "\\"), p.replace("\\", "/")}:
            chaves.append(hashlib.sha1(v.encode("utf-8")).hexdigest())
    return chaves


def confiar_scripts(pasta_usuario: Path | None = None, simular: bool = False) -> list[str]:
    """Pré-autoriza a extensão (rede + ler/gravar arquivo) no aseprite.ini — o mesmo que clicar 'Permitir'."""
    base = pasta_usuario or pasta_usuario_aseprite()
    ini = base / "aseprite.ini"
    pasta_ext = base / "extensions" / NOME_EXT
    log = [f"permissões: {ini} [script_access] para {pasta_ext}"]
    if simular:
        return log
    if aseprite_aberto() and pasta_usuario is None:
        log.append("o Aseprite está aberto: ele regrava o aseprite.ini ao fechar. Feche e rode de novo, ou aceite "
                   "o pedido de permissão na primeira conexão.")
        return log
    texto = ini.read_text(encoding="utf-8", errors="replace") if ini.exists() else ""
    linhas = texto.splitlines()
    try:
        i = next(k for k, l in enumerate(linhas) if l.strip().lower() == "[script_access]")
    except StopIteration:
        linhas += ["", "[script_access]"]
        i = len(linhas) - 1
    fim = next((k for k in range(i + 1, len(linhas)) if linhas[k].startswith("[")), len(linhas))
    atuais = {}
    for k in range(i + 1, fim):
        m = re.match(r"\s*([0-9a-f]{40})\s*=\s*(\d+)", linhas[k])
        if m:
            atuais[m.group(1)] = (k, int(m.group(2)))
    novas = []
    for ch in chaves_scripts(pasta_ext):
        if ch in atuais:
            k, v = atuais[ch]
            linhas[k] = f"{ch} = {v | ACESSO}"
        else:
            novas.append(f"{ch} = {ACESSO}")
    linhas[fim:fim] = novas
    ini.parent.mkdir(parents=True, exist_ok=True)
    if ini.exists():
        shutil.copy2(ini, ini.with_suffix(".ini.horys-bak"))
    ini.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    log.append(f"ok ({len(novas)} chaves novas; cópia em {ini.with_suffix('.ini.horys-bak').name})")
    return log


def _junction(origem: Path, destino: Path):
    if destino.exists() or destino.is_symlink():
        return False
    destino.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        import _winapi
        _winapi.CreateJunction(str(origem), str(destino))
    else:
        destino.symlink_to(origem, target_is_directory=True)
    return True


def instalar_skills_codex(simular: bool = False) -> list[str]:
    base = Path.home() / ".codex" / "skills"
    log = []
    for s in SKILLS:
        dest = base / s
        log.append(f"skill do Codex: {dest} → {RAIZ / 'skills' / s}")
        if not simular:
            log.append("ok" if _junction(RAIZ / "skills" / s, dest) else "já existe (mantido)")
    return log


def registrar_codex(simular: bool = False) -> list[str]:
    arq = Path.home() / ".codex" / "config.toml"
    py = sys.executable.replace("\\", "/")
    bloco = (f'\n[mcp_servers.horys]\ncommand = "{py}"\nargs = ["-m", "horys_pixel.mcp_ponte"]\n'
             f'tool_timeout_sec = 600\n\n[mcp_servers.horys.env]\nPYTHONPATH = "{str(SRC).replace(chr(92), "/")}"\n')
    # o Codex aprova ferramenta MCP por ferramenta: sem isto, `codex exec` pode parar pedindo aprovação
    from .ferramentas import registro
    registro.carregar_todas()
    for nome in registro.REGISTRO:
        bloco += f'\n[mcp_servers.horys.tools.{nome}]\napproval_mode = "approve"\n'
    log = [f"Codex: [mcp_servers.horys] em {arq}"]
    if simular:
        return log
    atual = arq.read_text(encoding="utf-8") if arq.exists() else ""
    if "[mcp_servers.horys]" in atual:
        log.append("já registrado (mantido)")
        return log
    arq.parent.mkdir(parents=True, exist_ok=True)
    if arq.exists():
        shutil.copy2(arq, arq.with_suffix(".toml.horys-bak"))
    with open(arq, "a", encoding="utf-8") as f:
        f.write(bloco)
    log.append("ok")
    return log


def registrar_claude(simular: bool = False) -> list[str]:
    """Plugin do Claude Code (MCP + skills + agente) a partir da pasta do repo (marketplace local)."""
    claude = shutil.which("claude")
    cmds = [[claude or "claude", "plugin", "marketplace", "add", str(RAIZ)],
            [claude or "claude", "plugin", "install", "horys-pixel@horys-pixel", "--scope", "user"]]
    log = ["Claude Code: " + " && ".join(" ".join(c[1:]) for c in cmds)]
    if simular:
        return log
    if not claude:
        log.append("não achei o 'claude' no PATH")
        return log
    for c in cmds:
        r = subprocess.run(c, capture_output=True, text=True, encoding="utf-8", errors="replace")
        saida = (r.stdout + r.stderr).strip().splitlines()
        log.append(f"$ {' '.join(c[1:])} → {r.returncode}: {saida[-1] if saida else ''}")
    return log


def inicio_windows(simular: bool = False) -> list[str]:
    """Atalho na pasta Inicializar: o horysd sobe com o Windows (o botão Gerar funciona sem terminal aberto)."""
    if os.name != "nt":
        return ["início automático: só no Windows por enquanto"]
    pasta = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    arq = pasta / "horysd.cmd"
    pw = Path(sys.executable).with_name("pythonw.exe")
    exe = pw if pw.exists() else Path(sys.executable)
    conteudo = f'@echo off\r\nset PYTHONPATH={SRC}\r\nstart "" "{exe}" -m horys_pixel.daemon.servidor\r\n'
    log = [f"início com o Windows: {arq}"]
    if not simular:
        arq.write_text(conteudo, encoding="utf-8")
        log.append("ok")
    return log


def tudo(simular: bool = False, confiar: bool = False, inicializacao: bool = False, codex: bool = False) -> list[str]:
    """Instala tudo, SEM o Codex por padrão (ele é opcional: codex=True / `horys instalar --tudo --codex`)."""
    log = []
    config.token()
    log += instalar_extensao(simular=simular)
    if confiar:
        log += confiar_scripts(simular=simular)
    log += registrar_claude(simular=simular)
    if codex:
        log += registrar_codex(simular=simular)
        log += instalar_skills_codex(simular=simular)
    if inicializacao:
        log += inicio_windows(simular=simular)
    return log
