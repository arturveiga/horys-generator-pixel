"""Ponte com o Blender (headless). O Blender é obrigatório para animar; a arte parada não precisa dele.

rodar(): renderiza ações × direções de um asset com dentro.py, na câmera e na escala do contrato do jogo.
inspecionar(): lista coleções, peças, materiais e caixas de um .blend e sugere os pivôs do rig.
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
from pathlib import Path
from shutil import which

DENTRO = Path(__file__).with_name("dentro.py")
INSPECIONAR = Path(__file__).with_name("inspecionar.py")
CASCO = Path(__file__).with_name("casco_blender.py")

# contrato das cores do mapa de partes (uma cor chapada por parte)
CORES_PARTES = {
    "cabeca": "#00ffff", "tronco": "#ff8c00", "braco-esq": "#00c800", "braco-dir": "#a000ff",
    "perna-esq": "#ffe600", "perna-dir": "#ff0000", "arma": "#ff00a0", "enfeite": "#ffffff",
}


class ErroBlender(RuntimeError):
    pass


def achar_blender() -> str | None:
    if os.environ.get("BLENDER") and Path(os.environ["BLENDER"]).is_file():
        return os.environ["BLENDER"]
    cands = sorted(glob.glob(r"C:\Program Files\Blender Foundation\Blender *\blender.exe"))
    if cands:
        return cands[-1]
    for c in ("/Applications/Blender.app/Contents/MacOS/Blender",):
        if Path(c).exists():
            return c
    return which("blender")


def _exe() -> str:
    exe = achar_blender()
    if not exe:
        raise ErroBlender("Blender não encontrado: instale o Blender 4+ ou defina a variável BLENDER")
    return exe


def rodar(cfg: dict, blend: Path, jogo: dict, paleta: dict, saida: str | Path, acoes: dict, direcoes: dict, *,
          previa: bool = False, timeout: int = 3600, projecao: dict | None = None) -> dict:
    """Devolve {ok, codigo, log, manifesto}. Os quadros crus ficam em <saida>/_render e <saida>/_partes."""
    if not Path(blend).exists():
        raise ErroBlender(f"o .blend não existe: {blend}")
    saida = Path(saida).resolve()
    (saida / "_render").mkdir(parents=True, exist_ok=True)
    trab = {"config": cfg, "jogo": jogo, "paleta": paleta, "saida": str(saida), "previa": previa,
            "acoes": acoes, "direcoes": direcoes, "cores_partes": CORES_PARTES, "projecao": projecao,
            "cor_por_direcao": cfg.get("cor_por_direcao")}
    tj = saida / "_render" / "trabalho.json"
    tj.write_text(json.dumps(trab, ensure_ascii=False, indent=1), encoding="utf-8")
    r = subprocess.run([_exe(), "-b", str(blend), "--python", str(DENTRO), "--", str(tj)], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=timeout)
    log = (r.stdout or "") + "\n" + (r.stderr or "")
    (saida / "_render" / "blender.log").write_text(log, encoding="utf-8")
    mani = saida / "_render" / "manifesto.json"
    ok = r.returncode == 0 and "[horys] ok" in log and mani.exists()
    return {"codigo": r.returncode, "ok": ok, "log": log[-4000:],
            "manifesto": json.loads(mani.read_text(encoding="utf-8")) if ok else None}


def inspecionar(blend: str | Path, timeout: int = 300) -> dict:
    blend = Path(blend).resolve()
    saida = blend.with_name(f"_{blend.stem}_inspecao.json")
    r = subprocess.run([_exe(), "-b", str(blend), "--python", str(INSPECIONAR), "--", str(saida)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    if r.returncode != 0 or not saida.exists():
        raise ErroBlender("a inspeção falhou:\n" + ((r.stdout or "") + (r.stderr or ""))[-2000:])
    dados = json.loads(saida.read_text(encoding="utf-8"))
    saida.unlink()
    dados["pivos_sugeridos"] = sugerir_pivos(dados.get("caixas", {}))
    return dados


def sugerir_pivos(caixas: dict) -> dict:
    """Pivô sugerido por coleção, pela caixa das peças: membros giram no topo (ombro, quadril), cabeça e tronco na
    base. É ponto de partida: confira e escreva em asset.json (rig.segmentos)."""
    out = {}
    for nome, c in caixas.items():
        (x0, y0, z0), (x1, y1, z1) = c
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        n = nome.lower()
        if any(k in n for k in ("braço", "braco", "perna", "arm", "leg")):
            z = z1 - 0.08 * (z1 - z0)
        else:
            z = z0
        out[nome] = [round(cx, 3), round(cy, 3), round(z, 3)]
    return out


def construir_casco(casco_json: str | Path, blend: str | Path, timeout: int = 600) -> None:
    """Monta o .blend do casco visual (casco_blender.py) a partir do JSON de peças."""
    blend = Path(blend).resolve()
    blend.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([_exe(), "-b", "--python", str(CASCO), "--", str(Path(casco_json).resolve()), str(blend)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    log = (r.stdout or "") + (r.stderr or "")
    if r.returncode != 0 or "[horys] ok" not in log or not blend.exists():
        raise ErroBlender("o casco falhou no Blender:\n" + log[-2000:])