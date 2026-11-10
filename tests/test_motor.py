"""Testes rápidos do motor (não dependem da máquina do Artur): config, grade mínima, medir, pixel_review, calibrar."""
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
MOTOR = SRC / "horys_pixel" / "motor"
sys.path.insert(0, str(SRC))

from horys_pixel.motor import comum as C  # noqa: E402
from horys_pixel.motor import pixel_review as PR  # noqa: E402

# figura mínima com as cores da paleta padrão do motor (paleta_padrao.json)
GRADE = """# teste sintético
nome boneco
tipo prop
quadro 64
pivo 6 19
ms 120
contorno auto
sombra sim
cores
  p #c98f6b
  P #eec39a
  s #8e5a4a
  f #4f8f4f
  F #9cc26a
  d #2f5d4b
  m #7d5a48
  M #4f3a3f
--- q0
....pppp....
...pPPPpp...
...pPPpps...
...ppppss...
....pps.....
..ffffffff..
.fFFfffffdf.
.fFfffffddf.
.fFffffffdf.
.pfffffffdp.
.pfffffffdp.
..ffffffdd..
..mmmmmmmm..
..mm....mm..
..mm....mm..
..mm....mm..
..mm....mm..
..MM....MM..
.MMM....MMM.
.MMM....MMM.
--- q1
............
....pppp....
...pPPPpp...
...pPPpps...
...ppppss...
..ffffffff..
.fFFfffffdf.
.fFfffffddf.
pfFffffffdfp
pffffffffddp
..ffffffff..
..ffffffdd..
..mmmmmmmm..
..mm....mm..
..mm....mm..
..mm....mm..
..mm....mm..
..MM....MM..
.MMM....MMM.
.MMM....MMM.
"""


@pytest.fixture
def amb(tmp_path, monkeypatch):
    """Ambiente isolado: sem HORYS_MOTOR_CONFIG e com ~/.horys-pixel apontando para uma pasta temporária."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.delenv("HORYS_PIXEL_HOME", raising=False)
    monkeypatch.setenv("HORYS_HOME", str(home))
    monkeypatch.delenv("HORYS_MOTOR_CONFIG", raising=False)
    env = dict(os.environ, PYTHONPATH=str(SRC), HORYS_HOME=str(home), PYTHONIOENCODING="utf-8")
    env.pop("HORYS_MOTOR_CONFIG", None)
    return {"home": home, "env": env, "tmp": tmp_path}


def rodar(args, env, cwd=None):
    return subprocess.run([sys.executable] + args, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=env, cwd=cwd or str(R))


def gerar_grade(amb, modo="m", nome="saida"):
    g = amb["tmp"] / "boneco.grade"
    g.write_text(GRADE, encoding="utf-8")
    saida = amb["tmp"] / nome
    if modo == "m":
        r = rodar(["-m", "horys_pixel.motor.grade", "gerar", str(g), "--saida", str(saida)], amb["env"])
    else:  # script direto, de outra pasta
        r = rodar([str(MOTOR / "grade.py"), "gerar", str(g), "--saida", str(saida)], amb["env"], cwd=str(amb["tmp"]))
    return r, saida


# ------------------------------------------------------------------ config

def test_config_padrao_sem_caminhos_pessoais(amb):
    c = C.config()
    assert c["kb"] is None and c["regua"] is None and c["aseprite"] is None
    assert c["_origem"] is None
    assert os.path.samefile(c["paleta_json"], MOTOR / "paleta_padrao.json")
    txt = (MOTOR / "config_padrao.json").read_text(encoding="utf-8").lower()
    assert "artur" not in txt and "c:/" not in txt and "d:/" not in txt
    assert not C.regua_ok(c)
    assert Path(C.pasta_calibracao(c)) == amb["home"] / "calibracao"


def test_config_ordem_env_vence_home(amb, monkeypatch):
    (amb["home"] / "motor.json").write_text(json.dumps({"limite_imagem": 999}), encoding="utf-8")
    c = C.config()
    assert c["limite_imagem"] == 999 and c["fundo_prancha"] == "#8a9290"   # o resto vem do padrão
    outro = amb["tmp"] / "outra" / "cfg.json"
    outro.parent.mkdir()
    pal = amb["tmp"] / "outra" / "minha_paleta.json"
    pal.write_text((MOTOR / "paleta_padrao.json").read_text(encoding="utf-8"), encoding="utf-8")
    outro.write_text(json.dumps({"limite_imagem": 123, "paleta_json": "minha_paleta.json"}), encoding="utf-8")
    monkeypatch.setenv("HORYS_MOTOR_CONFIG", str(outro))
    c = C.config()
    assert c["limite_imagem"] == 123
    assert os.path.samefile(c["paleta_json"], pal)      # sem kb: relativo à pasta do JSON
    assert C.carregar_paleta(c)["contorno"] == C.hex2rgb("#1c1828")


def test_config_env_inexistente(amb, monkeypatch):
    monkeypatch.setenv("HORYS_MOTOR_CONFIG", str(amb["tmp"] / "nao_existe.json"))
    with pytest.raises(SystemExit):
        C.config()


def test_paleta_relativa_a_kb(amb, monkeypatch):
    kb = amb["tmp"] / "kb"
    (kb / "estilo").mkdir(parents=True)
    (kb / "estilo" / "p.json").write_text((MOTOR / "paleta_padrao.json").read_text(encoding="utf-8"), encoding="utf-8")
    cfg = amb["tmp"] / "c.json"
    cfg.write_text(json.dumps({"kb": str(kb), "paleta_json": "estilo/p.json"}), encoding="utf-8")
    monkeypatch.setenv("HORYS_MOTOR_CONFIG", str(cfg))
    c = C.config()
    assert os.path.samefile(C.caminho_paleta(c), kb / "estilo" / "p.json")
    assert len(C.carregar_paleta(c)["rampas"]) == 7


# ------------------------------------------------------------------ grade + portão

def test_grade_minima_gera_folha_sem_regua(amb):
    r, saida = gerar_grade(amb, "m")
    assert r.returncode in (0, 1), r.stdout + r.stderr
    folha = saida / "boneco_boneco.png"
    assert folha.exists()
    im = np.array(Image.open(folha).convert("RGBA"))
    assert im.shape == (64, 128, 4)
    contorno = np.all(im[..., :3] == C.hex2rgb("#1c1828"), axis=-1) & (im[..., 3] == 255)
    assert contorno.sum() > 50                          # contorno auto de 2 px na cor da paleta
    assert ((im[..., 3] > 0) & (im[..., 3] < 255)).any()   # sombra no chão
    for suf in ("_8x.png", "_silhueta.png", ".gif", "_quadros_4x.png", "_checagem.txt"):
        assert (saida / ("boneco_boneco" + suf)).exists(), suf
    assert not (saida / "boneco_boneco_regua.png").exists()
    assert not (saida / "boneco_boneco_regua_anim.png").exists()
    chec = (saida / "boneco_boneco_checagem.txt").read_text(encoding="utf-8")
    assert "PORTÃO DE MEDIDAS" in chec
    assert "régua não configurada" in chec
    assert ".aseprite não gerado" in chec
    assert "fora da paleta" not in chec
    med = json.loads((saida / "medidas" / "boneco" / "medidas.json").read_text(encoding="utf-8"))
    assert med["tipo"] == "prop" and "boneco" in med["folhas"]
    assert (saida / "medidas" / "boneco" / "overlay_boneco.png").exists()
    assert r.returncode == (1 if med["falhas"] or "ERRO" in chec else 0)


def test_grade_script_direto_igual_ao_modulo(amb):
    r1, s1 = gerar_grade(amb, "m", "a")
    r2, s2 = gerar_grade(amb, "script", "b")
    assert r1.returncode == r2.returncode, r2.stdout + r2.stderr
    a = np.array(Image.open(s1 / "boneco_boneco.png"))
    b = np.array(Image.open(s2 / "boneco_boneco.png"))
    assert np.array_equal(a, b)


def test_grade_numerar(amb):
    g = amb["tmp"] / "boneco.grade"
    g.write_text(GRADE, encoding="utf-8")
    r = rodar(["-m", "horys_pixel.motor.grade", "numerar", str(g), "--quadro", "1"], amb["env"])
    assert r.returncode == 0 and "<pivô" in r.stdout


def test_grade_com_erro_de_letra(amb):
    g = amb["tmp"] / "ruim.grade"
    g.write_text(GRADE.replace("..ffffffff..\n.fFFf", "..ffffZfff..\n.fFFf", 1), encoding="utf-8")
    r = rodar(["-m", "horys_pixel.motor.grade", "gerar", str(g), "--saida", str(amb["tmp"] / "x")], amb["env"])
    assert r.returncode == 1 and "sem cor na legenda" in r.stdout


def test_medir_direto_e_cor_fora_da_paleta(amb):
    _, saida = gerar_grade(amb, "m")
    folha = saida / "boneco_boneco.png"
    r = rodar(["-m", "horys_pixel.motor.medir", "--tipo", "prop", "--quadro", "64", "--folha", f"idle={folha}",
               "--saida", str(amb["tmp"] / "med")], amb["env"])
    assert r.returncode in (0, 1)
    med = json.loads((amb["tmp"] / "med" / "medidas.json").read_text(encoding="utf-8"))
    assert med["folhas"]["idle"]["M01_px_fora"] == 0
    # uma cor fora da paleta reprova no M01
    im = np.array(Image.open(folha).convert("RGBA"))
    ys, xs = np.nonzero(im[..., 3] == 255)
    im[ys[:20], xs[:20], :3] = (1, 250, 3)
    ruim = amb["tmp"] / "ruim.png"
    Image.fromarray(im).save(ruim)
    r = rodar([str(MOTOR / "medir.py"), "--tipo", "prop", "--quadro", "64", "--folha", f"idle={ruim}",
               "--saida", str(amb["tmp"] / "med2")], amb["env"])
    assert r.returncode == 1
    med = json.loads((amb["tmp"] / "med2" / "medidas.json").read_text(encoding="utf-8"))
    assert "M01" in {f["id"] for f in med["falhas"]}


# ------------------------------------------------------------------ pixel_review

def test_pixel_review_medir_arquivo(amb):
    _, saida = gerar_grade(amb, "m")
    folha = saida / "boneco_boneco.png"
    out = amb["tmp"] / "rev"
    res = PR.medir_arquivo(folha, paleta=MOTOR / "paleta_padrao.json", fundo="#78a05e", quadros=2, saida=out)
    assert res["modo"] == "sprite" and len(res["arquivos"]) == 1
    q = res["arquivos"][0]["quadros"]
    assert len(q) == 2 and q[0]["contorno"] == "#1C1828"
    assert all(Path(p).exists() for p in res["overlays"] + res["folhas"])
    assert isinstance(res["erros"], list) and isinstance(res["avisos"], list)
    assert not any("fora da paleta" in e for e in res["erros"])
    json.dumps(res)  # serializável (vai virar resposta de ferramenta MCP)
    # paleta dada como lista de hex, sem a cor de pele: acusa fora da paleta
    so_verde = ["#4f8f4f", "#9cc26a", "#2f5d4b", "#1c1828"]
    res2 = PR.medir_arquivo([folha], paleta=so_verde, quadros=2, saida=out)
    assert not res2["ok"] and any("fora da paleta" in e for e in res2["erros"])
    assert res2["arquivos"][0]["quadros"][0]["marcas"]["fora_paleta"] > 0
    mock = PR.medir_arquivo(folha, mockup=True)
    assert mock["modo"] == "mockup" and mock["arquivos"][0]["cores_unicas"] > 0


def test_pixel_review_cli_json(amb):
    _, saida = gerar_grade(amb, "m")
    r = rodar(["-m", "horys_pixel.motor.pixel_review", str(saida / "boneco_boneco.png"), "--frames", "2",
               "--out", str(amb["tmp"] / "rev"), "--json"], amb["env"])
    assert r.returncode == 0, r.stderr
    d = json.loads(r.stdout)
    assert len(d["arquivos"][0]["quadros"]) == 2


# ------------------------------------------------------------------ calibrar e conceito

def test_calibrar_sem_regua_avisa(amb):
    r = rodar(["-m", "horys_pixel.motor.calibrar", "mutacoes"], amb["env"])
    assert r.returncode != 0 and "regua" in (r.stdout + r.stderr)


def test_conceito_limpar(amb):
    g = amb["tmp"] / "boneco.grade"
    g.write_text(GRADE, encoding="utf-8")
    out = amb["tmp"] / "limpa.grade"
    r = rodar(["-m", "horys_pixel.motor.conceito", "limpar", str(g), "--saida", str(out), "--min", "3"], amb["env"])
    assert r.returncode == 0, r.stderr
    assert out.exists() and "--- q0" in out.read_text(encoding="utf-8")


def test_arquivos_do_motor_presentes():
    for nome in ("comum.py", "grade.py", "medir.py", "conceito.py", "calibrar.py", "pixel_review.py",
                 "exportar_aseprite.lua", "revisor_prompt.md", "config_padrao.json", "paleta_padrao.json"):
        assert (MOTOR / nome).exists(), nome
    assert not (MOTOR / "config.json").exists()   # nada de config pessoal dentro do pacote


def test_conceito_pivo_no_centro_dos_pes(amb):
    """1.8: figura frontal com um pé mais baixo que o outro; o pivô fica no centro dos pés, não dentro do pé baixo."""
    img = Image.new("RGB", (120, 200), "#ff00ff")
    px = img.load()
    for y in range(40, 170):
        for x in range(40, 80):                      # corpo centrado em x=59,5
            px[x, y] = (0xc9, 0x8f, 0x6b)
    for y in range(160, 191):
        for x in range(30, 52):                      # pé esquerdo, chega em y=190
            px[x, y] = (0x4f, 0x3a, 0x3f)
    for y in range(160, 188):
        for x in range(68, 90):                      # pé direito, 3 px mais alto
            px[x, y] = (0x4f, 0x3a, 0x3f)
    arq = amb["tmp"] / "frontal.png"
    img.save(arq)
    leg = amb["tmp"] / "leg.grade"
    leg.write_text(GRADE, encoding="utf-8")
    out = amb["tmp"] / "conv.grade"
    r = rodar(["-m", "horys_pixel.motor.conceito", "converter", str(arq), "--legenda", str(leg), "--altura", "100",
               "--saida", str(out), "--modo", "moda", "--fundo", "#ff00ff"], amb["env"])
    assert r.returncode == 0, r.stderr
    texto = out.read_text(encoding="utf-8").splitlines()
    pivo_x = next(int(l.split()[1]) for l in texto if l.startswith("pivo"))
    linhas = texto[[i for i, l in enumerate(texto) if l.startswith("---")][0] + 1:]
    cols = [j for l in linhas for j, c in enumerate(l) if c != "."]
    centro = (min(cols) + max(cols)) / 2
    assert abs(pivo_x - centro) <= 1, (pivo_x, centro)


def test_sombra_cobre_figura_mais_larga_que_os_pes():
    """1.9: boss com punhos mais largos que os pés: a sombra tem >= 0,75 da largura da figura (régua do medir)."""
    from horys_pixel.motor import grade as G
    linhas = ["." * 4 + "p" * 32 + "." * 4] * 20 + ["." * 12 + "p" * 16 + "." * 12] * 10
    meta = {"quadro": 64, "pivo": (20, len(linhas) - 1), "contorno": "suave", "sombra": "sim", "tipo": "boss"}
    img, mask = G.montar(meta, {"p": "#c98f6b"}, {"nome": "q0", "linhas": linhas})
    semi = (img[..., 3] > 0) & (img[..., 3] < 255)
    sx = np.nonzero(semi.any(axis=0))[0]
    fx = np.nonzero((img[..., 3] == 255).any(axis=0))[0]
    assert (sx.max() - sx.min() + 1) / (fx.max() - fx.min() + 1) >= 0.75
