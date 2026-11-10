"""Registro das ferramentas MCP. Cada ferramenta é uma função async (ctx, args) -> lista de conteúdo MCP."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable


class ErroFerramenta(Exception):
    """Erro mostrado ao motor como resultado com isError (mensagem curta, em português)."""


@dataclass
class Ferramenta:
    nome: str
    descricao: str
    esquema: dict
    funcao: Callable[[Any, dict], Awaitable[list]]


REGISTRO: dict[str, Ferramenta] = {}


def ferramenta(nome: str, descricao: str, propriedades: dict | None = None, obrigatorios: list | None = None):
    esquema = {"type": "object", "properties": propriedades or {}, "additionalProperties": True}
    if obrigatorios:
        esquema["required"] = obrigatorios

    def deco(fn):
        REGISTRO[nome] = Ferramenta(nome, descricao.strip(), esquema, fn)
        return fn
    return deco


def texto(s: str) -> dict:
    return {"type": "text", "text": s}


def imagem(png_b64: str) -> dict:
    return {"type": "image", "data": png_b64, "mimeType": "image/png"}


def listar() -> list[dict]:
    carregar_todas()
    return [{"name": f.nome, "description": f.descricao, "inputSchema": f.esquema} for f in REGISTRO.values()]


_carregadas = False


def carregar_todas():
    global _carregadas
    if _carregadas:
        return
    from . import desenho, conversa, estilo, partes, pedidos, gosto, treino, kiln, sequencia, entrega  # noqa: F401  (registram ao importar)
    _carregadas = True


# esquemas reutilizados
INT = {"type": "integer"}
STR = {"type": "string"}
BOOL = {"type": "boolean"}
OBJ = {"type": "object"}
LISTA_STR = {"type": "array", "items": {"type": "string"}}
