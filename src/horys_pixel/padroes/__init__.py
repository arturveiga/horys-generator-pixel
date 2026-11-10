"""Padrões de entrada por tipo de asset (números das fichas do cofre; o texto e a justificativa ficam lá)."""
from __future__ import annotations

import json
from pathlib import Path

PASTA = Path(__file__).parent
TIPOS = ("personagem", "criatura-pequena", "criatura-grande", "boss", "prop", "arvore", "predio", "tile", "icone",
         "retrato", "efeito")
CAMPOS = ("quadro", "pivo", "altura_alvo", "detalhe_min_frac", "vista", "camera", "proporcao", "canvas_geracao",
          "ocupacao", "linha_chao_frac", "cores_max", "contorno", "luz", "remover", "animacao")
ALIAS = {"humanoide": "personagem", "npc": "personagem", "heroi": "personagem", "inimigo": "personagem",
         "criatura": "criatura-pequena", "animal": "criatura-pequena", "elite": "criatura-grande",
         "recurso": "prop", "item": "prop", "ui": "icone", "predios": "predio", "árvore": "arvore", "ícone": "icone"}


def tipo_de(nome: str | None) -> str | None:
    n = (nome or "").strip().lower()
    n = ALIAS.get(n, n)
    return n if n in TIPOS else None


def carregar(tipo: str) -> dict:
    t = tipo_de(tipo)
    if not t:
        raise ValueError(f"tipo sem padrão: {tipo!r} (use um de {', '.join(TIPOS)})")
    return json.loads((PASTA / f"{t}.json").read_text(encoding="utf-8"))


def validar(p: dict) -> list[str]:
    erros = [f"falta '{c}'" for c in CAMPOS if c not in p]
    if not erros and not (0 < p["detalhe_min_frac"] < 1):
        erros.append("detalhe_min_frac fora de (0,1)")
    return erros


def detalhe_min_px(p: dict, altura_alvo: int) -> float:
    """px mínimo no jogo = detalhe_min_frac × altura alvo."""
    return p["detalhe_min_frac"] * altura_alvo
