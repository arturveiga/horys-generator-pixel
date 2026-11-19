"""Contrato do jogo: os números que valem para TODOS os assets (escala, câmera, luz, contorno, direções, portões).

Fica em jogo.json na raiz do projeto. Nenhum asset sobrescreve estes números: é isso que mantém goblin e ogro na
mesma escala, com a mesma luz e o mesmo ângulo.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

PADRAO = {
    "quadro": 96,                 # px do quadro de cada sprite
    "px_por_metro": 26.6,         # escala única do jogo (1 m no plano da câmera = N px)
    "altura_humano_px": 44,       # altura de um humano adulto na tela; alvo da arte parada de humanoides
    "angulo": 43,                 # inclinação da câmera top-down 3/4 (graus acima do horizonte)
    "base_px": 4,                 # linha do pé: px acima da borda de baixo do quadro
    "margem_px": 2,
    "luz": {"direcao": [-0.52, -0.53, 0.67], "faceta": 0.73, "sol": 3.0, "ambiente": 0.25},
    "contorno": "fora",           # fora | dentro | nenhum (1 px com a tinta da paleta)
    "max_cores": 20,
    "direcoes": {"sul": 0, "sudeste": 45, "leste": 90, "nordeste": 135, "norte": 180,
                 "noroeste": -135, "oeste": -90, "sudoeste": -45},
    "vistas": {"frente": "sul", "lado": "leste", "costas": "norte"},
    "portoes": {
        "pisca_max": 0.02,                      # fração de pixels que piscam (A->B->A) depois da anticintilação
        "pisca_max_golpe": 0.03,                # idem para ações de um tiro (soco, ataque, dano, morte)
        "altura_var_max_px": 2,                 # variação da altura num ciclo de idle/andar/correr
        "pe_var_max_px": 1,                     # variação da linha do pé num ciclo de idle/andar/correr
        "mudanca": {"idle": [0.0, 0.35], "andar": [0.05, 0.65], "correr": [0.05, 0.75]},
        "gabarito": {"iou_min": 0.85, "familia_min": 0.75, "altura_tol": 0.08},
        "detalhe_min_px": 2,
    },
}

ARQUIVO = "jogo.json"


def _mesclar(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict) and k != "direcoes":
            out[k] = _mesclar(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def raiz(inicio: str | Path | None = None) -> Path:
    """Pasta do projeto: a primeira, subindo de 'inicio', que tem jogo.json (ou a pasta 'assets'); senão o cwd."""
    p = Path(inicio or Path.cwd()).resolve()
    if p.is_file():
        p = p.parent
    for d in [p, *p.parents]:
        if (d / ARQUIVO).exists() or (d / "assets").is_dir():
            return d
    return Path.cwd().resolve()


def carregar(inicio: str | Path | None = None) -> dict:
    arq = raiz(inicio) / ARQUIVO
    extra = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {}
    j = _mesclar(PADRAO, extra)
    if float(j["px_por_metro"]) <= 0:
        raise ValueError("jogo.json: px_por_metro precisa ser > 0")
    if not j["direcoes"]:
        raise ValueError("jogo.json: nenhuma direção")
    for nome, d in j["vistas"].items():
        if d not in j["direcoes"]:
            raise ValueError(f"jogo.json: a vista '{nome}' usa a direção '{d}', que não está em 'direcoes'")
    return j


PROIBIDO_NO_ASSET = ("camera", "luz", "contorno", "direcoes", "quadro", "px_por_metro", "angulo")


def checar_asset(cfg: dict) -> list[str]:
    """Campos do asset que tentam mudar o contrato do jogo (são ignorados; a lista vira aviso)."""
    return [k for k in PROIBIDO_NO_ASSET if k in cfg]
