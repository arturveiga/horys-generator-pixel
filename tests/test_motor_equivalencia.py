"""Prova de equivalência: o motor do pacote (horys_pixel.motor, a fonte única) e os scripts da skill
horys-pixel-liso (wrappers finos que chamam o pacote com o config.json da skill) dão a mesma saída.

Só roda na máquina que tem a skill, a KB, o corpus de teste (Eldiran 32x32) e os .grade do Hunvix; senão, skip.
Não há régua externa (a régua é o Artur): o corpus só calibra o portão. A calibração completa leva ~1,5 min:
pule com HORYS_PULAR_LENTOS=1.
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
    return bool(c.get("kb")) and Path(c["kb"]).is_dir() and bool(c.get("corpus_teste")) and Path(c["corpus_teste"]).is_dir()


tem_skill = pytest.mark.skipif(not _cfg_ok(), reason="skill horys-pixel-liso, KB ou corpus de teste ausentes nesta máquina")


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


def comparar_saidas(so: Path, sn: Path, base: str, so_desenho: bool = False):
    """Folha, _8x e _silhueta iguais; sem so_desenho, também _regua (prancha boas práticas), _regua_anim, a
    checagem linha a linha e o medidas.json."""
    a = np.array(Image.open(so / f"{base}.png").convert("RGBA"))
    b = np.array(Image.open(sn / f"{base}.png").convert("RGBA"))
    assert a.shape == b.shape and np.array_equal(a, b), "folha PNG diferente"
    sufs = ("_8x.png", "_silhueta.png") + (() if so_desenho else ("_regua.png", "_regua_anim.png"))
    for suf in sufs:
        if (so / (base + suf)).exists():
            assert np.array_equal(np.array(Image.open(so / (base + suf))), np.array(Image.open(sn / (base + suf)))), suf
    if so_desenho:
        return
    A = (so / f"{base}_checagem.txt").read_text(encoding="utf-8").splitlines()
    B = (sn / f"{base}_checagem.txt").read_text(encoding="utf-8").splitlines()
    assert len(A) == len(B)
    for x, y in zip(A, B):
        if x == y or "medidas.json" in x:      # a linha do caminho da pasta de saída muda
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
    # o script da skill (wrapper, config.json da skill) e o módulo do pacote com a mesma config: tudo igual
    comparar_saidas(so, sn, base)
    # com a config gerada do pacote de estilo do Artur, o desenho é igual (as pranchas de régua podem mudar)
    if (ESTILO_ARTUR / "estilo.json").exists():
        from horys_pixel import estilos as E
        cfg = E.escrever_config_motor(E.carregar(str(ESTILO_ARTUR)), tmp_path / "motor-horys.json")
        sn2 = tmp_path / "novo_estilo"
        rn2 = rodar(["-m", "horys_pixel.motor.grade", "gerar", str(g), "--saida", str(sn2)], env_novo(cfg), R)
        assert rn2.returncode == ro.returncode
        comparar_saidas(so, sn2, base, so_desenho=True)


@tem_skill
@pytest.mark.skipif(os.environ.get("HORYS_PULAR_LENTOS") == "1", reason="HORYS_PULAR_LENTOS=1")
def test_calibracao_32_72_bons_15_estragados(tmp_path):
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
    assert bons == 72 and ruins == 15, (bons, ruins)       # corpus Eldiran 32x32 (perfil 32), sem régua externa
    assert "Bons sem falha: 72/72" in r2.stdout
    assert "(ou só visuais): 15/15" in r2.stdout
    assert (tmp_path / "cal" / "relatorio_metricas.md").exists()
    # nada foi gravado dentro do repo nem da skill
    assert not (R / "_calibracao").exists() and not (SKILL / "_calibracao").exists()
