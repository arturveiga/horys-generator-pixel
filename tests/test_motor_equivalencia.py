"""Prova de equivalência: o motor portado faz o mesmo que a skill horys-pixel-liso original.

Só roda na máquina que tem a skill, a régua (Tiny Swords), a KB e os .grade do Hunvix; senão, skip.
A calibração completa leva ~1,5 min: pule com HORYS_PULAR_LENTOS=1.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

R = Path(__file__).resolve().parents[1]
SRC = R / "src"
SKILL = Path.home() / ".agents" / "skills" / "horys-pixel-liso" / "scripts"
CFG_SKILL = SKILL / "config.json"
HUNVIX = Path("D:/godot/games/hunvix/art-src/pixel-liso")
ESTILO_ARTUR = Path.home() / ".horys-pixel" / "estilos" / "horys-pixel-liso"
GRADES = ["construtor/v04/idle_base.grade", "medico/andar.grade", "construtor/v03/idle_base_v03.grade"]


def _cfg_ok():
    if not CFG_SKILL.exists():
        return False
    c = json.loads(CFG_SKILL.read_text(encoding="utf-8"))
    return Path(c["regua"]).is_dir() and Path(c["kb"]).is_dir()


tem_skill = pytest.mark.skipif(not _cfg_ok(), reason="skill horys-pixel-liso, régua ou KB ausentes nesta máquina")


def rodar(args, env, cwd):
    return subprocess.run([sys.executable] + args, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=env, cwd=str(cwd))


def env_novo(cfg):
    e = dict(os.environ, PYTHONPATH=str(SRC), HORYS_MOTOR_CONFIG=str(cfg), PYTHONIOENCODING="utf-8")
    return e


def copia_da_skill(destino: Path) -> Path:
    """Cópia isolada da skill original (não toca nos arquivos dela, nem no __pycache__)."""
    destino.mkdir(parents=True, exist_ok=True)
    for nome in ("comum.py", "grade.py", "medir.py", "config.json", "exportar_aseprite.lua"):
        shutil.copy2(SKILL / nome, destino / nome)
    return destino


def _sem_caminho(med):
    for f in med["folhas"].values():
        f.pop("arquivo", None)
    return med


def comparar_saidas(so: Path, sn: Path, base: str, ignorar_rotulo_regua: bool):
    a = np.array(Image.open(so / f"{base}.png").convert("RGBA"))
    b = np.array(Image.open(sn / f"{base}.png").convert("RGBA"))
    assert a.shape == b.shape and np.array_equal(a, b), "folha PNG diferente"
    for suf in ("_8x.png", "_silhueta.png", "_regua.png"):
        if (so / (base + suf)).exists():
            assert np.array_equal(np.array(Image.open(so / (base + suf))), np.array(Image.open(sn / (base + suf)))), suf
    if not ignorar_rotulo_regua and (so / f"{base}_regua_anim.png").exists():
        assert np.array_equal(np.array(Image.open(so / f"{base}_regua_anim.png")),
                              np.array(Image.open(sn / f"{base}_regua_anim.png")))
    A = (so / f"{base}_checagem.txt").read_text(encoding="utf-8").splitlines()
    B = (sn / f"{base}_checagem.txt").read_text(encoding="utf-8").splitlines()
    assert len(A) == len(B)
    for x, y in zip(A, B):
        if x == y or "medidas.json" in x:      # a linha do caminho da pasta de saída muda
            continue
        if ignorar_rotulo_regua and "régua animada" in x:
            assert x.replace("vs Tiny", "vs régua") == y
            continue
        assert x == y
    estado = next(p for p in (so / "medidas").iterdir())
    mo = _sem_caminho(json.loads((estado / "medidas.json").read_text(encoding="utf-8")))
    mn = _sem_caminho(json.loads((sn / "medidas" / estado.name / "medidas.json").read_text(encoding="utf-8")))
    assert mo == mn


@tem_skill
@pytest.mark.parametrize("grade", GRADES)
def test_grade_igual_a_skill(grade, tmp_path):
    g = HUNVIX / grade
    if not g.exists():
        pytest.skip(f"{g} não existe")
    orig = copia_da_skill(tmp_path / "skill")
    so, sn = tmp_path / "orig", tmp_path / "novo"
    env_o = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    ro = rodar([str(orig / "grade.py"), "gerar", str(g), "--saida", str(so)], env_o, orig)
    rn = rodar(["-m", "horys_pixel.motor.grade", "gerar", str(g), "--saida", str(sn)], env_novo(CFG_SKILL), R)
    assert ro.returncode in (0, 1), ro.stdout + ro.stderr
    assert rn.returncode == ro.returncode, rn.stdout + rn.stderr
    base = next(p.stem for p in so.glob("*_checagem.txt")).removesuffix("_checagem")
    # com o config.json da skill tal como está, só o rótulo da régua muda ("Tiny" vira "régua": não há regua_nome)
    comparar_saidas(so, sn, base, ignorar_rotulo_regua=True)
    # com a config gerada do pacote de estilo do Artur, tudo igual (inclusive o rótulo)
    if (ESTILO_ARTUR / "estilo.json").exists():
        from horys_pixel import estilos as E
        cfg = E.escrever_config_motor(E.carregar(str(ESTILO_ARTUR)), tmp_path / "motor-horys.json")
        sn2 = tmp_path / "novo_estilo"
        rn2 = rodar(["-m", "horys_pixel.motor.grade", "gerar", str(g), "--saida", str(sn2)], env_novo(cfg), R)
        assert rn2.returncode == ro.returncode
        comparar_saidas(so, sn2, base, ignorar_rotulo_regua=False)


@tem_skill
@pytest.mark.skipif(os.environ.get("HORYS_PULAR_LENTOS") == "1", reason="HORYS_PULAR_LENTOS=1")
def test_calibracao_46_bons_19_estragados(tmp_path):
    cfg = json.loads(CFG_SKILL.read_text(encoding="utf-8"))
    cfg["pasta_calibracao"] = str(tmp_path / "cal")          # a única chave a mais: a saída vai para o temp
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    env = env_novo(p)
    r1 = rodar(["-m", "horys_pixel.motor.calibrar", "mutacoes"], env, R)
    assert r1.returncode == 0, r1.stdout + r1.stderr
    casos = json.loads((tmp_path / "cal" / "casos.json").read_text(encoding="utf-8"))
    r2 = rodar(["-m", "horys_pixel.motor.calibrar", "metricas"], env, R)
    assert r2.returncode == 0, r2.stdout + r2.stderr
    bons = sum(1 for c in casos.values() if c["esperado"] == "PASSA")
    ruins = len(casos) - bons
    assert bons == 46 and ruins == 19, (bons, ruins)
    assert "Bons sem falha: 46/46" in r2.stdout
    assert "(ou só visuais): 19/19" in r2.stdout
    assert (tmp_path / "cal" / "relatorio_metricas.md").exists()
    # nada foi gravado dentro do repo nem da skill
    assert not (R / "_calibracao").exists() and not (SKILL / "_calibracao").exists()
