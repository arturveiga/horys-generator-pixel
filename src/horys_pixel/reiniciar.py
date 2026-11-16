"""Reiniciar o horysd (perfeicao.md, seção 13, item C12): depois de cada mudança no código, o daemon que está no ar
ainda roda o código velho (em 13/11 as ferramentas novas não apareciam por isso).

`horys reiniciar`: para o horysd do horysd.pid (se estiver vivo), espera a porta liberar e sobe um novo em segundo
plano, com o PYTHONPATH deste repo. A extensão do Aseprite reconecta sozinha.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from . import config

SRC = Path(__file__).resolve().parents[1]


def _porta_ocupada(porta: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", porta)) == 0


def _vivo(pid: int) -> bool:
    if os.name == "nt":
        r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        return str(pid) in r.stdout
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def parar(espera: float = 10.0) -> list[str]:
    log = []
    arq = config.casa() / "horysd.pid"
    pid = None
    if arq.is_file():
        try:
            pid = int(arq.read_text().strip())
        except ValueError:
            pid = None
    if pid and _vivo(pid):
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
        else:
            os.kill(pid, 15)
        log.append(f"horysd {pid} parado")
    else:
        log.append("nenhum horysd vivo no horysd.pid")
    porta = config.porta()
    t0 = time.time()
    while _porta_ocupada(porta) and time.time() - t0 < espera:
        time.sleep(0.25)
    if _porta_ocupada(porta):
        log.append(f"a porta {porta} continua ocupada: outro processo a segura (veja `netstat -ano | findstr {porta}`)")
    return log


def subir(espera: float = 10.0) -> list[str]:
    pw = Path(sys.executable).with_name("pythonw.exe")
    exe = str(pw if (os.name == "nt" and pw.exists()) else sys.executable)
    env = {**os.environ, "PYTHONPATH": str(SRC) + os.pathsep + os.environ.get("PYTHONPATH", "")}
    kw = {}
    if os.name == "nt":
        kw["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kw["start_new_session"] = True
    subprocess.Popen([exe, "-m", "horys_pixel.daemon.servidor"], env=env, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kw)
    porta = config.porta()
    t0 = time.time()
    while not _porta_ocupada(porta) and time.time() - t0 < espera:
        time.sleep(0.25)
    return [f"horysd no ar em 127.0.0.1:{porta}" if _porta_ocupada(porta)
            else f"horysd não abriu a porta {porta} em {espera:.0f} s (veja o horysd.log)"]


def main() -> int:
    log = parar() + subir()
    print("\n".join(log))
    return 0 if "no ar" in log[-1] else 1
