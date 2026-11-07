"""Onde ficam os dados de treino de um estilo (gosto/, conjunto/, lora/) e qual é o trigger.

O módulo não depende de ``horys_pixel.estilos``: recebe a pasta do estilo diretamente. Se o módulo de
estilos existir, ``de_estilo(nome)`` usa a API dele (``estilos.carregar`` e ``estilos.pasta_dados``).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, replace
from pathlib import Path

from ._comum import ErroTreino, ler_json

_RE_TRIGGER = re.compile(r"^[a-z0-9][a-z0-9_\-]{1,63}$")


def trigger_padrao(nome: str) -> str:
    """Trigger derivado do nome: minúsculas ASCII sem espaços (ex.: "Horys Pixel Liso" → "horyspixelliso")."""
    texto = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii").lower()
    texto = re.sub(r"[^a-z0-9]+", "", texto)
    return texto or "estilo"


def validar_trigger(trigger: str) -> str:
    t = (trigger or "").strip().lower()
    if not _RE_TRIGGER.match(t):
        raise ErroTreino(
            f"trigger inválido: {trigger!r}. Use uma palavra rara, só letras minúsculas, números, _ ou - "
            "(ex.: hpxliso). Ela vira nome de pasta e a palavra que ativa o LoRA."
        )
    return t


@dataclass(frozen=True)
class AlvoTreino:
    """Pastas de dados de treino de um estilo."""

    nome: str
    gosto: Path
    conjunto: Path
    lora: Path
    trigger: str | None = None

    @property
    def manifesto(self) -> Path:
        return self.conjunto / "manifesto.json"

    @property
    def ativo(self) -> Path:
        return self.lora / "ativo.json"

    def pasta_versao(self, versao: str) -> Path:
        return self.lora / versao

    def trigger_efetivo(self) -> str:
        """Trigger explícito, senão o do manifesto do conjunto, senão derivado do nome."""
        if self.trigger:
            return validar_trigger(self.trigger)
        man = ler_json(self.manifesto, {}) or {}
        if man.get("trigger"):
            return validar_trigger(man["trigger"])
        return trigger_padrao(self.nome)

    def com_trigger(self, trigger: str | None) -> "AlvoTreino":
        return replace(self, trigger=trigger) if trigger else self


def de_pasta(pasta: Path | str, trigger: str | None = None, nome: str | None = None) -> AlvoTreino:
    """Alvo a partir da pasta do estilo (a que contém ``gosto/``, ``conjunto/`` e ``lora/``)."""
    raiz = Path(pasta).expanduser().resolve()
    info = ler_json(raiz / "estilo.json", {}) or {}
    return AlvoTreino(
        nome=nome or info.get("nome") or raiz.name,
        gosto=raiz / "gosto",
        conjunto=raiz / "conjunto",
        lora=raiz / "lora",
        trigger=trigger or info.get("trigger"),
    )


def de_estilo(nome: str, trigger: str | None = None) -> AlvoTreino:
    """Alvo a partir do nome do estilo, usando ``horys_pixel.estilos`` se ele existir."""
    try:
        from horys_pixel import estilos  # import tardio: o módulo pode ainda não existir
    except ImportError as e:
        raise ErroTreino(
            "o módulo de estilos (horys_pixel.estilos) não está disponível; "
            "use --estilo-dados <pasta do estilo> em vez de --estilo."
        ) from e
    try:
        est = estilos.carregar(nome)
        return AlvoTreino(
            nome=getattr(est, "nome", nome),
            gosto=Path(estilos.pasta_dados(est, "gosto")),
            conjunto=Path(estilos.pasta_dados(est, "conjunto")),
            lora=Path(estilos.pasta_dados(est, "lora")),
            trigger=trigger or getattr(est, "trigger", None),
        )
    except ErroTreino:
        raise
    except Exception as e:  # API externa: qualquer falha vira mensagem clara
        raise ErroTreino(f"não consegui carregar o estilo {nome!r}: {e}") from e


def resolver(estilo, trigger: str | None = None) -> AlvoTreino:
    """Aceita um ``AlvoTreino``, a pasta do estilo ou o nome de um estilo instalado."""
    if isinstance(estilo, AlvoTreino):
        return estilo.com_trigger(trigger)
    caminho = Path(str(estilo)).expanduser()
    if caminho.is_dir():
        return de_pasta(caminho, trigger=trigger)
    return de_estilo(str(estilo), trigger=trigger)
