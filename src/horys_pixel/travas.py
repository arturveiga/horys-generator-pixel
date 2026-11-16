"""Travas de passo (perfeicao.md, seção 13, item C6): o processo vira trava de ferramenta, não texto.

- Aprovação de arquivo: <arquivo>.aprovado.json ao lado do PNG, com o sha256 do arquivo no momento do sim. Se o
  arquivo mudar depois, a aprovação deixa de valer (o que foi aprovado é aquele pixel, não aquele nome).
- A/B do revisor: <pasta>/ab.json com as rodadas A/B cegas (qual venceu e por quê). A entrega recusa pasta sem A/B.

Quem passa: vestir exige base aprovada; animar exige vista aprovada; entrega exige A/B registrado.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

QUEM = ("artur", "revisor")


class Travado(Exception):
    """O passo anterior não foi cumprido. Mensagem curta, em português, dizendo o que falta."""


def _sha(caminho: Path) -> str:
    return hashlib.sha256(Path(caminho).read_bytes()).hexdigest()


def _lateral(caminho: str | Path) -> Path:
    p = Path(caminho)
    return p.with_name(p.name + ".aprovado.json")


def aprovar(caminho: str | Path, quem: str = "artur", comentario: str = "", origem: str = "") -> dict:
    p = Path(caminho)
    if not p.is_file():
        raise FileNotFoundError(f"arquivo não encontrado: {p}")
    if quem not in QUEM:
        raise ValueError(f"quem: {' | '.join(QUEM)}")
    reg = {"arquivo": p.name, "sha256": _sha(p), "quem": quem, "comentario": comentario, "origem": origem,
           "quando": time.strftime("%Y-%m-%d %H:%M:%S")}
    _lateral(p).write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")
    return reg


def aprovacao(caminho: str | Path) -> dict | None:
    """O registro de aprovação, se ainda vale (mesmo sha256); senão None."""
    lat = _lateral(caminho)
    if not lat.is_file() or not Path(caminho).is_file():
        return None
    try:
        reg = json.loads(lat.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return reg if reg.get("sha256") == _sha(Path(caminho)) else None


def exigir_aprovado(caminho: str | Path, o_que: str = "arquivo", quem: str = "artur") -> dict:
    reg = aprovacao(caminho)
    if reg is None:
        motivo = "mudou depois da aprovação" if _lateral(caminho).is_file() else "não foi aprovado"
        raise Travado(f"{o_que} {Path(caminho).name} {motivo}. Mostre ao Artur (horys_aprovar) e, com o sim dele, "
                      f"registre com horys_aprovar_arquivo. Nada de vestir/animar sobre forma não aprovada.")
    if quem == "artur" and reg.get("quem") != "artur":
        raise Travado(f"{o_que} {Path(caminho).name} foi aprovado por '{reg.get('quem')}', não pelo Artur.")
    return reg


# ------------------------------------------------------------------ A/B do revisor


def registrar_ab(pasta: str | Path, a: str, b: str, vencedor: str, motivo: str = "", revisor: str = "") -> dict:
    """Uma rodada A/B cega: a = antes, b = depois da correção. A correção só fica se b vencer."""
    vencedor = vencedor.strip().upper()
    if vencedor not in ("A", "B", "EMPATE"):
        raise ValueError("vencedor: A | B | EMPATE")
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    arq = pasta / "ab.json"
    hist = json.loads(arq.read_text(encoding="utf-8")) if arq.is_file() else {"rodadas": []}
    rod = {"a": str(a), "b": str(b), "vencedor": vencedor, "motivo": motivo, "revisor": revisor,
           "quando": time.strftime("%Y-%m-%d %H:%M:%S"), "fica": "b" if vencedor == "B" else "a"}
    hist["rodadas"].append(rod)
    arq.write_text(json.dumps(hist, ensure_ascii=False, indent=2), encoding="utf-8")
    return rod


def exigir_ab(pasta: str | Path) -> dict:
    arq = Path(pasta) / "ab.json"
    if not arq.is_file():
        raise Travado(f"sem A/B do revisor em {pasta}: rode o revisor em A/B cego (antes × depois) e registre com "
                      "horys_ab_registrar antes de entregar.")
    hist = json.loads(arq.read_text(encoding="utf-8"))
    if not hist.get("rodadas"):
        raise Travado(f"ab.json em {pasta} está vazio")
    return hist
