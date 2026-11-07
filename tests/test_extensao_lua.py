"""Testes da extensão do Aseprite (extension/), rodando o Aseprite de verdade em modo batch.

Pula se o executável não existir. Caminho: variável ASEPRITE ou os lugares de costume.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
EXT = RAIZ / "extension"
LUA = RAIZ / "tests" / "lua"

CANDIDATOS = [
    os.environ.get("ASEPRITE"),
    r"C:/Users/artur/Documents/aseprite/aseprite.exe",
    r"C:/Program Files/Aseprite/Aseprite.exe",
    r"C:/Program Files (x86)/Steam/steamapps/common/Aseprite/Aseprite.exe",
    shutil.which("aseprite"),
]


def _aseprite() -> str | None:
    for c in CANDIDATOS:
        if c and Path(c).is_file():
            return c
    return None


ASEPRITE = _aseprite()
precisa_aseprite = pytest.mark.skipif(ASEPRITE is None, reason="Aseprite não encontrado (defina ASEPRITE)")


def _rodar(script: Path, **params: str) -> subprocess.CompletedProcess:
    args = [ASEPRITE, "-b"]
    for k, v in {"ext": str(EXT), **params}.items():
        args += ["--script-param", f"{k}={v}"]
    args += ["--script", str(script)]
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)


@precisa_aseprite
def test_handlers_no_aseprite():
    r = _rodar(LUA / "test_handlers.lua")
    saida = (r.stdout or "") + (r.stderr or "")
    linhas = [l for l in saida.splitlines() if l.strip()]
    assert not any(l.startswith("FALHA") for l in linhas), saida
    assert linhas and linhas[-1].startswith("OK "), saida
    assert int(linhas[-1].split()[1]) >= 25, saida
    assert r.returncode == 0, saida


@precisa_aseprite
@pytest.mark.parametrize("rodada", range(3))
def test_hmac_igual_ao_python(rodada):
    token = secrets.token_hex(24)  # 48 hex, como o horysd gera
    nonce = secrets.token_hex(16)
    r = _rodar(LUA / "hmac_cli.lua", token=token, nonce=nonce)
    saida = (r.stdout or "") + (r.stderr or "")
    esperado = hmac.new(token.encode("ascii"), nonce.encode("ascii"), hashlib.sha256).hexdigest()
    linhas = {l.split(" ", 1)[0]: l.split(" ", 1)[1] for l in saida.splitlines() if " " in l}
    assert linhas.get("HMAC") == esperado, saida
    ola = json.loads(linhas["OLA"])
    assert ola["t"] == "ola" and ola["papel"] == "aseprite"
    assert ola["prova"] == esperado
    assert len(ola["nonce"]) == 32 and int(ola["nonce"], 16) >= 0


@precisa_aseprite
def test_hmac_confere_com_o_auth_do_servidor():
    """A prova da extensão bate com horys_pixel.auth (se o módulo existir)."""
    auth = pytest.importorskip("horys_pixel.auth")
    token, nonce = secrets.token_hex(24), auth.nonce()
    r = _rodar(LUA / "hmac_cli.lua", token=token, nonce=nonce)
    hmac_lua = next(l.split(" ", 1)[1] for l in r.stdout.splitlines() if l.startswith("HMAC "))
    assert auth.confere(token, nonce, hmac_lua)


@precisa_aseprite
def test_token_lido_do_arquivo_sem_espacos(tmp_path):
    # (o Aseprite não abre com outro USERPROFILE; o caminho padrão é testado no Lua)
    arquivo = tmp_path / "token"
    token = secrets.token_hex(24)
    arquivo.write_bytes(f"  {token}".encode("ascii") + bytes([13, 10]))  # termina em CRLF
    r = _rodar(LUA / "hmac_cli.lua", token="x", nonce="y", arquivo_token=str(arquivo))
    assert f"TOKEN_ARQUIVO {token}" in r.stdout, r.stdout + r.stderr
    r = _rodar(LUA / "hmac_cli.lua", token="x", nonce="y", arquivo_token=str(tmp_path / "nao-existe"))
    assert "TOKEN_ARQUIVO nil" in r.stdout, r.stdout + r.stderr


def test_build_gera_zip_com_package_json_na_raiz(tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location("build_extension", RAIZ / "scripts" / "build_extension.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    destino = mod.construir(tmp_path / "horys-pixel.aseprite-extension")
    with zipfile.ZipFile(destino) as z:
        nomes = z.namelist()
        assert "package.json" in nomes
        assert "plugin.lua" in nomes
        assert not any(n.startswith("extension/") for n in nomes)
        pacote = json.loads(z.read("package.json"))
    assert pacote["contributes"]["scripts"][0]["path"] == "./plugin.lua"
    # todo .lua carregado por modulos.lua está no zip
    for nome in ("modulos", "jsonx", "base64", "sha256", "logica", "arquivos", "handlers", "cliente", "ui"):
        assert f"{nome}.lua" in nomes


@precisa_aseprite
def test_imagem_rgba_sem_arquivo():
    """A aprovação manda RGBA cru; a extensão monta a Image sem gravar arquivo (sem pedido de permissão)."""
    import base64
    import numpy as np
    im = np.zeros((2, 3, 4), np.uint8)
    im[0, 0] = (10, 20, 30, 255)
    im[1, 2] = (200, 100, 50, 128)
    r = _rodar(LUA / "imagem_rgba.lua", rgba=base64.b64encode(im.tobytes()).decode(), w="3", h="2")
    saida = (r.stdout or "") + (r.stderr or "")
    assert "TAM 3x2" in saida and "P00 10,20,30,255" in saida and "P21 200,100,50,128" in saida, saida
    assert "NORM 3x2" in saida, saida
