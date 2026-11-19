"""Aprovações do Artur, presas ao conteúdo do arquivo (sha256). Arquivo mudou = aprovação perdida.

<asset>/aprovado.json = {etapa: {"arquivo": relativo ao asset, "sha256", "quem", "comentario", "quando"}}
Etapas usadas: "arte" (arte/folha.png), "paleta" (paleta.json), "final" (saida/portoes.json).
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

ARQ = "aprovado.json"


class Travado(Exception):
    pass


def sha(caminho: str | Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def _ler(asset: Path) -> dict:
    p = asset / ARQ
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def aprovar(asset: str | Path, etapa: str, arquivo: str | Path, quem: str = "artur", comentario: str = "") -> dict:
    asset = Path(asset)
    arq = (asset / arquivo) if not Path(arquivo).is_absolute() else Path(arquivo)
    if not arq.exists():
        raise FileNotFoundError(f"não existe: {arq}")
    dados = _ler(asset)
    dados[etapa] = {"arquivo": str(arq.resolve().relative_to(asset.resolve())).replace("\\", "/"),
                    "sha256": sha(arq), "quem": quem, "comentario": comentario,
                    "quando": time.strftime("%Y-%m-%d %H:%M:%S")}
    (asset / ARQ).write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    return dados[etapa]


def estado(asset: str | Path) -> dict:
    """{etapa: {"ok": bool, ...}}: ok = o arquivo ainda é o aprovado."""
    asset = Path(asset)
    out = {}
    for etapa, d in _ler(asset).items():
        arq = asset / d["arquivo"]
        out[etapa] = {**d, "ok": arq.exists() and sha(arq) == d["sha256"]}
    return out


def exigir(asset: str | Path, etapa: str) -> None:
    e = estado(asset).get(etapa)
    if not e:
        raise Travado(f"falta aprovar '{etapa}': rode `horys aprovar {Path(asset).name} {etapa}` depois que o Artur "
                      "disser sim")
    if not e["ok"]:
        raise Travado(f"'{e['arquivo']}' mudou depois da aprovação de '{etapa}': o Artur precisa aprovar de novo")
