import asyncio
import os
import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def porta_livre() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


@pytest.fixture
def casa_temp(tmp_path, monkeypatch):
    monkeypatch.setenv("HORYS_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("HORYS_TOKEN", raising=False)
    return tmp_path / "home"


@pytest.fixture
def ambiente(casa_temp, monkeypatch):
    """horysd rodando no loop do teste + um Aseprite falso conectado. Devolve (ctx, aseprite, chamar)."""
    porta = porta_livre()
    monkeypatch.setenv("HORYS_PORTA", str(porta))
    return porta
