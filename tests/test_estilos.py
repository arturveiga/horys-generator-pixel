"""Pacotes de estilo: busca, carregar, config do motor, dados, paleta."""
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

R = Path(__file__).resolve().parents[1]
SRC = R / "src"
sys.path.insert(0, str(SRC))

from horys_pixel import estilos as E  # noqa: E402
from horys_pixel.motor import comum as C  # noqa: E402

CFG_SKILL = Path.home() / ".agents" / "skills" / "horys-pixel-liso" / "scripts" / "config.json"
ESTILO_ARTUR = Path.home() / ".horys-pixel" / "estilos" / "horys-pixel-liso"


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.delenv("HORYS_PIXEL_HOME", raising=False)
    monkeypatch.setenv("HORYS_HOME", str(h))
    monkeypatch.delenv("HORYS_MOTOR_CONFIG", raising=False)
    return h


def test_listar_e_carregar_exemplo(home):
    assert "exemplo" in E.listar()
    e = E.carregar("exemplo")
    assert e.nome == "exemplo" and e.licenca == "MIT" and e.no_repo
    assert e.kb is None and e.regua is None and not e.regua_disponivel
    assert e.paleta.is_file() and e.paleta.parent == R / "estilos" / "exemplo"
    assert e.leitura == [R / "estilos" / "exemplo" / "estilo.md"] and e.leitura[0].exists()
    assert e.motor_padrao == "claude" and e.referencia_padrao == "pedir" and e.trigger


def test_paleta_do_exemplo(home):
    p = E.paleta("exemplo")
    assert set(p) == {"rampas", "contorno", "brilho"}
    materiais = {k: v for k, v in p["rampas"].items() if k not in ("contorno", "brilho")}
    assert len(materiais) == 5 and all(len(v) == 3 for v in materiais.values())
    assert p["contorno"] == "#1c1828" and p["brilho"] == "#fbf5e6"
    # rampas ordenadas de sombra para luz
    for v in materiais.values():
        L = [float(C.oklab(np.array(C.hex2rgb(h)))[0]) for h in v]
        assert L == sorted(L)
    pasta = R / "estilos" / "exemplo"
    assert (pasta / "paleta.gpl").exists() and (pasta / "paleta.hex").exists() and (pasta / "estilo.md").exists()
    assert len((pasta / "paleta.hex").read_text(encoding="utf-8").split()) == 17


def test_config_motor_do_exemplo(home, monkeypatch):
    c = E.config_motor("exemplo")
    assert c["estilo"] == "exemplo" and c["kb"] is None and c["regua"] is None
    assert c["regua_por_categoria"] == {}
    assert Path(c["paleta_json"]).is_absolute() and Path(c["paleta_json"]).exists()
    destino = E.escrever_config_motor("exemplo")
    assert destino == home / "motor-exemplo.json" and destino.exists()
    monkeypatch.setenv("HORYS_MOTOR_CONFIG", str(destino))
    cm = C.config()
    assert os.path.samefile(cm["paleta_json"], c["paleta_json"])
    assert cm["chao"] == {"claro": "#78a05e", "escuro": "#5a5870"}
    outro = E.escrever_config_motor(E.carregar("exemplo"), home / "x" / "m.json")
    assert outro.exists()


def test_pasta_dados(home):
    g = E.pasta_dados("exemplo", "gosto")
    assert g == home / "estilos-dados" / "exemplo" / "gosto" and g.is_dir()   # pacote do repo: fora do repo
    assert not (R / "estilos" / "exemplo" / "gosto").exists()
    with pytest.raises(ValueError):
        E.pasta_dados("exemplo", "outra")


def test_usuario_vence_em_conflito(home):
    pasta = home / "estilos" / "exemplo"
    pasta.mkdir(parents=True)
    d = json.loads((R / "estilos" / "exemplo" / "estilo.json").read_text(encoding="utf-8"))
    d["versao"] = "9.9"
    d["paleta"] = str(R / "estilos" / "exemplo" / "paleta.json")
    (pasta / "estilo.json").write_text(json.dumps(d), encoding="utf-8")
    e = E.carregar("exemplo")
    assert e.versao == "9.9" and e.pasta == pasta.resolve() and not e.no_repo
    assert E.pasta_dados(e, "lora") == pasta.resolve() / "lora"
    assert E.listar().count("exemplo") == 1


def test_paleta_relativa_a_kb_e_regua(home, tmp_path):
    kb = tmp_path / "kb"
    (kb / "estilo").mkdir(parents=True)
    (kb / "estilo" / "pal.json").write_text((R / "estilos" / "exemplo" / "paleta.json").read_text(encoding="utf-8"),
                                            encoding="utf-8")
    (kb / "nota.md").write_text("x", encoding="utf-8")
    regua = tmp_path / "regua"
    regua.mkdir()
    pasta = home / "estilos" / "meu"
    pasta.mkdir(parents=True)
    (pasta / "estilo.json").write_text(json.dumps({
        "nome": "meu", "kb": str(kb), "paleta": "estilo/pal.json", "leitura": ["nota.md"],
        "regua": {"pasta": str(regua), "nome": "Ref", "por_categoria": {"idle": ["a.png", 64]}},
        "brilho_regua": "#ffffff", "motor": {"limite_imagem": 777}}), encoding="utf-8")
    e = E.carregar("meu")
    assert e.paleta == kb / "estilo" / "pal.json" and e.leitura == [kb / "nota.md"]
    assert e.regua_disponivel and e.brilho_regua == ["#ffffff"]
    c = E.config_motor(e)
    assert c["regua"] == str(regua) and c["regua_nome"] == "Ref" and c["regua_por_categoria"]["idle"] == ["a.png", 64]
    assert c["limite_imagem"] == 777


def test_estilo_inexistente(home):
    with pytest.raises(E.EstiloNaoEncontrado):
        E.carregar("nao-existe-mesmo")


def test_exportar_paleta(tmp_path):
    pal = {"nome": "t", "rampas": {"a": ["#000001", "#808080"], "b": ["#808080", "#ffffff"]}}
    gpl, hx = E.exportar_paleta(pal, tmp_path / "p")
    assert gpl.read_text(encoding="utf-8").startswith("GIMP Palette")
    assert hx.read_text(encoding="utf-8").split() == ["000001", "808080", "ffffff"]


def test_modelo_do_artur_no_repo_e_valido():
    d = json.loads((R / "estilos" / "horys-pixel-liso.exemplo.json").read_text(encoding="utf-8"))
    for k in ("nome", "versao", "autor", "licenca", "descricao", "kb", "paleta", "regua", "chao", "contorno_regua",
              "brilho_regua", "metas", "leitura", "motor_padrao", "referencia_padrao", "trigger"):
        assert k in d, k
    assert set(d["regua"]) == {"pasta", "nome", "por_categoria"}
    # nenhuma imagem de terceiros no repo
    assert not list((R / "estilos").rglob("*.png"))


def test_grade_com_estilo_exemplo(home, tmp_path):
    """O motor roda com a config gerada do pacote exemplo: contorno da paleta, nada fora da paleta."""
    from test_motor import GRADE
    cfg = E.escrever_config_motor("exemplo")
    g = tmp_path / "boneco.grade"
    g.write_text(GRADE, encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=str(SRC), HORYS_MOTOR_CONFIG=str(cfg), HORYS_HOME=str(home),
               PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "-m", "horys_pixel.motor.grade", "gerar", str(g), "--saida", str(tmp_path / "s")],
                       capture_output=True, text=True, encoding="utf-8", env=env, cwd=str(R))
    assert r.returncode in (0, 1), r.stdout + r.stderr
    chec = (tmp_path / "s" / "boneco_boneco_checagem.txt").read_text(encoding="utf-8")
    assert "fora da paleta" not in chec and "régua não configurada" in chec
    im = np.array(Image.open(tmp_path / "s" / "boneco_boneco.png").convert("RGBA"))
    assert (np.all(im[..., :3] == C.hex2rgb("#1c1828"), axis=-1) & (im[..., 3] == 255)).any()


@pytest.mark.skipif(not (ESTILO_ARTUR / "estilo.json").exists() or not CFG_SKILL.exists(),
                    reason="pacote horys-pixel-liso do Artur ou a skill ausentes nesta máquina")
def test_estilo_do_artur_reproduz_config_da_skill(home):
    e = E.carregar(str(ESTILO_ARTUR))
    assert e.nome == "horys-pixel-liso" and not e.no_repo
    c = E.config_motor(e)
    s = json.loads(CFG_SKILL.read_text(encoding="utf-8"))
    for k, v in s.items():
        if k in ("kb", "regua", "trabalho", "aseprite"):
            assert os.path.normpath(c[k]) == os.path.normpath(v), k
        elif k == "paleta_json":
            assert os.path.samefile(c[k], os.path.join(s["kb"], v))
        else:
            assert c[k] == v, k
    assert c["regua_nome"] == "Tiny"
    assert all(p.exists() for p in e.leitura)
    modelo = json.loads((R / "estilos" / "horys-pixel-liso.exemplo.json").read_text(encoding="utf-8"))
    assert modelo == e.dados
