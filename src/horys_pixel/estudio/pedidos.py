"""Caixa de entrada do Estúdio: o que o Artur risca e escreve na interface vira um pedido em disco, que o agente lê
(horys_estudio_pedidos) e responde (horys_estudio_responder). A resposta aparece na interface.

~/.horys-pixel/estudio/pedidos/<id>/pedido.json + anotado.png (a imagem com os riscos) + original.png
"""
from __future__ import annotations

import base64
import json
import time
import uuid
from pathlib import Path

from .. import config

ESTADOS = ("pendente", "em_andamento", "feito", "descartado")


def pasta() -> Path:
    p = config.pasta("estudio") / "pedidos"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _png_de_dataurl(d: str) -> bytes:
    if not d.startswith("data:image/png;base64,"):
        raise ValueError("imagem precisa ser data:image/png;base64")
    return base64.b64decode(d.split(",", 1)[1])


def criar(nota: str, asset: str = "", quadro: int | None = None, marcas: list | None = None,
          anotado: str | None = None, original: str | None = None, extra: dict | None = None,
          vistas: list[str] | None = None) -> dict:
    if not (nota or "").strip() and not marcas:
        raise ValueError("escreva o que mudar ou risque na imagem")
    i = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
    d = pasta() / i
    d.mkdir()
    p = {"id": i, "criado": time.strftime("%Y-%m-%d %H:%M:%S"), "estado": "pendente", "nota": (nota or "").strip(),
         "asset": asset, "quadro": quadro, "marcas": marcas or [], "respostas": [], **(extra or {})}
    if anotado:
        (d / "anotado.png").write_bytes(_png_de_dataurl(anotado))
        p["anotado"] = str(d / "anotado.png")
    if original:
        (d / "original.png").write_bytes(_png_de_dataurl(original))
        p["original"] = str(d / "original.png")
    if vistas:
        p["vistas"] = []
        for k, v in enumerate(vistas[:24], 1):          # 3D: uma foto por defeito apontado
            arq = d / f"vista_{k:02d}.png"
            arq.write_bytes(_png_de_dataurl(v))
            p["vistas"].append(str(arq))
    _gravar(p)
    return p


def _gravar(p: dict):
    (pasta() / p["id"] / "pedido.json").write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")


def ler(i: str) -> dict:
    arq = pasta() / i / "pedido.json"
    if not arq.is_file() or "/" in i or "\\" in i or ".." in i:
        raise KeyError(f"pedido {i} não existe")
    return json.loads(arq.read_text(encoding="utf-8"))


def listar(estado: str | None = None) -> list[dict]:
    out = []
    for arq in sorted(pasta().glob("*/pedido.json"), reverse=True):
        try:
            p = json.loads(arq.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if estado in (None, "", "todos") or p.get("estado") == estado:
            out.append(p)
    return out


def responder(i: str, texto: str, estado: str = "feito", imagem: str | None = None) -> dict:
    if estado not in ESTADOS:
        raise ValueError(f"estado: {' | '.join(ESTADOS)}")
    p = ler(i)
    r = {"quando": time.strftime("%Y-%m-%d %H:%M:%S"), "texto": texto, "estado": estado}
    if imagem:
        r["imagem"] = imagem
    p["respostas"].append(r)
    p["estado"] = estado
    _gravar(p)
    return p


def resumo_para_hook(max_n: int = 5) -> str:
    """Texto curto dos pedidos pendentes (para um hook UserPromptSubmit injetar no contexto do chat)."""
    pend = listar("pendente")[:max_n]
    if not pend:
        return ""
    linhas = [f"Pedidos do Horys Estúdio pendentes ({len(pend)}): leia com horys_estudio_pedidos."]
    for p in pend:
        linhas.append(f"- {p['id']}: {p['nota'][:120]} ({p.get('asset') or 'sem asset'})")
    return "\n".join(linhas)
