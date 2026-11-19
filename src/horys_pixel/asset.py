"""Um asset = uma pasta em assets/<nome>/ com tudo dele.

assets/<nome>/
  asset.json      ficha: tipo, altura_px (alvo da arte), blend, rig, papeis, acoes, materiais, esconder
  gerada.png      imagem do gerador (ver prompt.md); referencia.png é opcional (só para consulta)
  arte/           frente.png, lado.png, costas.png (1x), folha.png, folha_8x.png, leitura.json
  paleta.json     famílias + tinta (paleta.png = amostra)
  aprovado.json   aprovações do Artur (sha256)
  blender/        o .blend do modelo e scripts de modelagem
  saida/          render: gabarito/, animacao/ (folhas, prancha, pos.json, portoes.json)
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from . import jogo as J

MODELO = {
    "nome": "",
    "tipo": "humanoide",
    "altura_px": None,
    "descricao": "",
    "blend": "blender/modelo.blend",
    "esconder": [],
    "materiais": {"padrao": "auto", "regras": []},
    "rig": {"ancora": "", "segmentos": []},
    "papeis": {"tronco": "", "cabeca": "", "bracos": [], "pernas": []},
    "acoes": {
        "idle": {"tipo": "idle", "quadros": 8, "fps": 8},
        "andar": {"tipo": "andar", "quadros": 8, "fps": 10},
    },
}


@dataclass
class Asset:
    nome: str
    pasta: Path
    cfg: dict

    @property
    def arte(self) -> Path:
        return self.pasta / "arte"

    @property
    def saida(self) -> Path:
        return self.pasta / "saida"

    @property
    def paleta(self) -> Path:
        return self.pasta / "paleta.json"

    @property
    def blend(self) -> Path:
        return (self.pasta / self.cfg["blend"]).resolve()

    def alvo_px(self, jogo: dict) -> int:
        return int(self.cfg.get("altura_px") or jogo["altura_humano_px"])

    def salvar_cfg(self) -> None:
        (self.pasta / "asset.json").write_text(json.dumps(self.cfg, ensure_ascii=False, indent=1), encoding="utf-8")


def pasta_assets(raiz: str | Path | None = None) -> Path:
    return J.raiz(raiz) / "assets"


def abrir(nome: str, raiz: str | Path | None = None) -> Asset:
    p = Path(nome)
    pasta = p if p.is_dir() and (p / "asset.json").exists() else pasta_assets(raiz) / nome
    arq = pasta / "asset.json"
    if not arq.exists():
        raise FileNotFoundError(f"asset '{nome}' não existe ({arq}). Crie com: horys novo {nome}")
    cfg = json.loads(arq.read_text(encoding="utf-8"))
    return Asset(cfg.get("nome") or pasta.name, pasta.resolve(), cfg)


def novo(nome: str, raiz: str | Path | None = None, tipo: str = "humanoide", altura_px: int | None = None,
         descricao: str = "") -> Asset:
    pasta = pasta_assets(raiz) / nome
    if (pasta / "asset.json").exists():
        raise FileExistsError(f"o asset '{nome}' já existe")
    for sub in ("arte", "blender", "saida"):
        (pasta / sub).mkdir(parents=True, exist_ok=True)
    cfg = json.loads(json.dumps(MODELO))
    cfg.update({"nome": nome, "tipo": tipo, "altura_px": altura_px, "descricao": descricao})
    a = Asset(nome, pasta.resolve(), cfg)
    a.salvar_cfg()
    return a


def listar(raiz: str | Path | None = None) -> list[str]:
    base = pasta_assets(raiz)
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir() if (p / "asset.json").exists())
