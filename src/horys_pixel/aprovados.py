"""Régua do Artur: o que ele aprova (ou reprova) vira registro com as palavras dele (perfeicao.md F8).

Aprovar = copiar o arquivo para <aprovados>/<grupo>/, gravar a trava (sha256, travas.aprovar) e uma linha em
aprovados.json. Reprovar = só a linha (com o motivo), para o revisor e o gosto aprenderem. A pasta vem da preferência
'aprovados' (padrão ~/Documents/pixel-liso/_aprovados).
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from . import config
from . import travas as T


def pasta() -> Path:
    p = Path(config.preferencias().get("aprovados") or (Path.home() / "Documents" / "pixel-liso" / "_aprovados"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def _registro() -> Path:
    return pasta() / "aprovados.json"


def listar() -> list[dict]:
    r = _registro()
    if not r.exists():
        return []
    try:
        return json.loads(r.read_text(encoding="utf-8"))
    except ValueError:
        return []


def _gravar(lista: list[dict]):
    _registro().write_text(json.dumps(lista, ensure_ascii=False, indent=1), encoding="utf-8")


def _grupo(arquivo: Path) -> str:
    partes = [p for p in arquivo.parent.parts if p not in ("", "\\", "/")]
    for nome in ("art-src", "saida", "comparacao"):
        if nome in partes:
            i = partes.index(nome)
            return partes[i + 1] if i + 1 < len(partes) else arquivo.parent.name
    return arquivo.parent.name


def registrar(arquivo: str | Path, veredito: str = "aprovado", comentario: str = "", origem: str = "estudio",
              grupo: str | None = None) -> dict:
    arquivo = Path(arquivo).resolve()
    if not arquivo.is_file():
        raise FileNotFoundError(f"arquivo não encontrado: {arquivo}")
    if veredito not in ("aprovado", "reprovado"):
        raise ValueError("veredito: aprovado | reprovado")
    g = grupo or _grupo(arquivo)
    item = {"quando": time.strftime("%Y-%m-%d %H:%M:%S"), "veredito": veredito, "arquivo": str(arquivo),
            "grupo": g, "comentario": comentario, "origem": origem}
    if veredito == "aprovado":
        T.aprovar(arquivo, "artur", comentario, origem)
        if arquivo.suffix.lower() in (".glb", ".gltf"):        # o 3D aprovado é o .blend de onde ele saiu
            blend = arquivo.with_suffix(".blend")
            if not blend.exists():                               # centa_andar.glb -> centa.blend
                blend = arquivo.with_name(arquivo.stem.split("_")[0] + ".blend")
            if blend.exists():
                T.aprovar(blend, "artur", comentario, origem + " (via " + arquivo.name + ")")
                item["blend"] = str(blend)
        destino = pasta() / g
        destino.mkdir(parents=True, exist_ok=True)
        copia = destino / f"{arquivo.parent.name}__{arquivo.name}"
        shutil.copy2(arquivo, copia)
        item["copia"] = str(copia)
        js = arquivo.with_suffix(".json")
        if js.exists():
            shutil.copy2(js, copia.with_suffix(".json"))
    lista = listar()
    lista.append(item)
    _gravar(lista)
    return item


def estado(arquivo: str | Path) -> str | None:
    """'aprovado' (com a trava valendo), 'reprovado' ou None, pelo último registro do arquivo."""
    a = str(Path(arquivo).resolve())
    ult = None
    for it in listar():
        if it["arquivo"] == a:
            ult = it["veredito"]
    if ult == "aprovado" and T.aprovacao(a) is None:
        return "mudou"
    return ult
