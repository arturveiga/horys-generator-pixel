"""Empacota extension/ em dist/horys-pixel.aseprite-extension (um zip com o conteúdo na raiz).

Uso: python scripts/build_extension.py [destino]
Para instalar: Aseprite › Editar › Preferências › Extensões › Adicionar extensão.
"""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
EXT = RAIZ / "extension"
PADRAO = RAIZ / "dist" / "horys-pixel.aseprite-extension"

# o que vai no pacote (nada de cache, rascunho ou arquivo oculto)
INCLUIR = {".lua", ".json", ".md", ".txt", ".png"}


def arquivos() -> list[Path]:
    lista = []
    for p in sorted(EXT.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(EXT)
        if any(parte.startswith(".") for parte in rel.parts):
            continue
        if p.suffix.lower() in INCLUIR:
            lista.append(p)
    return lista


def construir(destino: Path | str = PADRAO) -> Path:
    destino = Path(destino)
    pacote = EXT / "package.json"
    if not pacote.is_file():
        raise SystemExit("extension/package.json não existe")
    dados = json.loads(pacote.read_text(encoding="utf-8"))
    for s in dados.get("contributes", {}).get("scripts", []):
        if not (EXT / s["path"]).resolve().is_file():
            raise SystemExit(f"package.json aponta para {s['path']}, que não existe")
    destino.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for p in arquivos():
            z.write(p, p.relative_to(EXT).as_posix())
    return destino


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    destino = construir(Path(argv[0]) if argv else PADRAO)
    with zipfile.ZipFile(destino) as z:
        nomes = z.namelist()
    print(f"{destino} ({len(nomes)} arquivos): {', '.join(nomes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
