"""Pipeline Blender do horys (perfeicao.md §14): o modelo 3D dá a consistência e o movimento, o horys dá a paleta,
o pixel e o acabamento. Reimplementa o que o Blender Pixel Kit (SouthernShotty, sem licença declarada) e os scripts
do robô do Codex (14/11) faziam à mão; nada do kit é copiado.

Ordem: modelo 3D no Blender -> Estúdio (o Artur gira, risca e APROVA o 3D) -> paleta (aprovada) -> config do personagem (rig por pivôs, famílias de material, câmera,
ações) -> render no Blender headless (dentro.py) -> pós em Python (pos.py) -> recolor quando quiser.
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
from pathlib import Path

from .. import config

DENTRO = Path(__file__).with_name("dentro.py")


def achar_blender() -> str | None:
    pref = config.preferencias().get("blender")
    if pref and Path(pref).is_file():
        return pref
    if os.environ.get("BLENDER") and Path(os.environ["BLENDER"]).is_file():
        return os.environ["BLENDER"]
    cands = sorted(glob.glob(r"C:\Program Files\Blender Foundation\Blender *\blender.exe"))
    if cands:
        return cands[-1]
    from shutil import which
    return which("blender")


def ler_config(caminho: str | Path) -> dict:
    """Config do personagem (JSON). Caminhos relativos ('blend', 'paleta') são relativos ao arquivo."""
    p = Path(caminho)
    cfg = json.loads(p.read_text(encoding="utf-8"))
    for k in ("blend", "paleta"):
        if cfg.get(k) and not Path(cfg[k]).is_absolute():
            cfg[k] = str((p.parent / cfg[k]).resolve())
    for k in ("blend", "rig", "papeis", "camera"):
        if k not in cfg:
            raise ValueError(f"config sem '{k}'")
    return cfg


def rodar(cfg: dict, paleta: dict, saida: str | Path, *, previa: bool = False, timeout: int = 3600) -> dict:
    """Roda dentro.py no Blender headless. Devolve {codigo, log, manifesto}."""
    from .. import mapa_partes as M
    from .. import travas as T
    if not cfg.get("sem_trava_3d"):
        T.exigir_aprovado(cfg["blend"], "o modelo 3D")      # ordem: modelo -> Estúdio -> Artur aprova -> pixel
    exe = achar_blender()
    if not exe:
        raise FileNotFoundError("Blender não encontrado (preferência 'blender' ou variável BLENDER)")
    saida = Path(saida).resolve()       # o Blender resolve caminho relativo a partir de outro lugar
    (saida / "_render").mkdir(parents=True, exist_ok=True)
    trab = {"config": cfg, "paleta": paleta, "saida": str(saida), "previa": previa,
            "cores_partes": {k: "#%02x%02x%02x" % v for k, v in M.CORES.items()}}
    tj = saida / "_render" / "trabalho.json"
    tj.write_text(json.dumps(trab, ensure_ascii=False, indent=1), encoding="utf-8")
    (saida / "_render" / "paleta.json").write_text(json.dumps(paleta, ensure_ascii=False, indent=1), encoding="utf-8")
    r = subprocess.run([exe, "-b", cfg["blend"], "--python", str(DENTRO), "--", str(tj)], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=timeout)
    log = r.stdout + "\n" + r.stderr
    (saida / "_render" / "blender.log").write_text(log, encoding="utf-8")
    mani = saida / "_render" / "manifesto.json"
    ok = r.returncode == 0 and "[horys] ok" in log and mani.exists()
    return {"codigo": r.returncode, "ok": ok, "log": log[-3000:],
            "manifesto": json.loads(mani.read_text(encoding="utf-8")) if ok else None}


def exportar_3d(cfg: dict, saida: str | Path | None = None, timeout: int = 1800) -> dict:
    """Etapa de aprovação: o modelo com as animações (uma .glb por ação) ao lado do .blend, para o Estúdio. Não
    precisa de aprovação (é o que vai ser aprovado). Devolve {ok, arquivos, log}."""
    exe = achar_blender()
    if not exe:
        raise FileNotFoundError("Blender não encontrado (preferência 'blender' ou variável BLENDER)")
    blend = Path(cfg["blend"])
    saida = Path(saida or blend.parent).resolve()
    saida.mkdir(parents=True, exist_ok=True)
    trab = {"config": cfg, "paleta": {}, "saida": str(saida), "modo": "3d", "stem": blend.stem}
    tj = saida / f"_{blend.stem}_3d_trabalho.json"
    tj.write_text(json.dumps(trab, ensure_ascii=False, indent=1), encoding="utf-8")
    r = subprocess.run([exe, "-b", str(blend), "--python", str(DENTRO), "--", str(tj)], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=timeout)
    log = r.stdout + "\n" + r.stderr
    (saida / f"_{blend.stem}_3d.log").write_text(log, encoding="utf-8")
    mani = saida / f"{blend.stem}_3d.json"
    ok = r.returncode == 0 and "[horys] ok" in log and mani.exists()
    return {"ok": ok, "log": log[-3000:],
            "manifesto": json.loads(mani.read_text(encoding="utf-8")) if ok else None}
