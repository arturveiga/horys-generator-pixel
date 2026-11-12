"""Render 3D com câmera fixa → motor de sequência: registro 'fixa', manifesto, validação objetiva e folha Godot."""
import json

import numpy as np
import pytest
from PIL import Image

from horys_pixel import sequencia as S
from horys_pixel.sequencia import entradas, registro, spritesheet, validar

PAL = ["#18122c", "#6a5a4a", "#a08c70", "#ff9a2a"]
RGB = {h: tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) for h in PAL}


def _golem(t: int, n: int = 8, W=64, H=64, quique=True, olho=True, dx=0):
    """Boneco sintético de câmera fixa: corpo, cabeça com olho laranja, pernas que alternam. 'quique' sobe o corpo
    na passagem (movimento deliberado que o registro não pode apagar)."""
    q = np.zeros((H, W, 4), np.uint8)
    fase = np.sin(2 * np.pi * t / n)
    sobe = int(round(abs(fase) * 2)) if quique else 0
    cx = 32 + dx
    def ret(x0, y0, x1, y1, cor):
        q[max(0, y0):y1, max(0, x0):x1] = (*RGB[cor], 255)
    ret(cx - 10, 22 - sobe, cx + 10, 44 - sobe, "#6a5a4a")          # corpo
    ret(cx - 6, 10 - sobe, cx + 6, 22 - sobe, "#a08c70")            # cabeça
    if olho:
        ret(cx - 3, 14 - sobe, cx - 1, 16 - sobe, "#ff9a2a")
        ret(cx + 1, 14 - sobe, cx + 3, 16 - sobe, "#ff9a2a")
    pe = int(round(fase * 4))
    ret(cx - 8 + pe, 44 - sobe, cx - 3 + pe, 56, "#18122c")         # perna E (pé no chão em 56)
    ret(cx + 3 - pe, 44 - sobe, cx + 8 - pe, 56, "#18122c")         # perna D
    return q


def _manifesto(tmp_path, quadros, nome="walk"):
    pasta = tmp_path / nome
    pasta.mkdir()
    arqs = []
    for i, q in enumerate(quadros):
        Image.fromarray(q, "RGBA").save(pasta / f"{i:04d}.png")
        arqs.append(f"{i:04d}.png")
    m = {"versao": 1, "fonte": "blender", "acao": nome, "fps": 8, "canvas": [64, 64], "pivo": [32, 56],
         "camera": {"pitch": 32, "yaw": 0, "ortho_scale": 3.0}, "loop": True, "quadros": arqs}
    (pasta / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
    return pasta / "manifest.json"


def test_manifesto_carrega_e_recusa_canvas_diferente(tmp_path):
    man = _manifesto(tmp_path, [_golem(t) for t in range(8)])
    assert entradas.eh_manifesto(man) and entradas.eh_manifesto(man.parent)
    qs = entradas.carregar(man.parent)
    assert len(qs) == 8 and all(q.shape == (64, 64, 4) for q in qs)
    Image.fromarray(np.zeros((70, 64, 4), np.uint8)).save(man.parent / "0003.png")
    with pytest.raises(entradas.ErroEntrada, match="câmera mudou"):
        entradas.carregar(man)


def test_manifesto_versao_errada(tmp_path):
    man = _manifesto(tmp_path, [_golem(0)])
    d = json.loads(man.read_text())
    d["versao"] = 2
    man.write_text(json.dumps(d))
    with pytest.raises(entradas.ErroEntrada, match="versao"):
        entradas.ler_manifesto(man)


def test_registro_fixa_preserva_quique():
    qs = [_golem(t) for t in range(8)]
    topos = lambda fr: [registro.caixa(q)[1] for q in fr]
    fixa = registro.registrar(qs, 49, (64, 64), (32, 56), "fixa")   # 49 = altura máx.: escala 1
    orig = topos(qs)
    assert max(orig) - min(orig) == 2
    assert max(topos(fixa)) - min(topos(fixa)) == 2          # o corpo ainda sobe e desce
    # câmera fixa: mesma transformação → o deslocamento entre quadros é idêntico ao original
    assert np.diff(topos(fixa)).tolist() == np.diff(orig).tolist()
    pes = [registro.caixa(q)[3] for q in fixa]
    assert len(set(pes)) == 1 and pes[0] == 56


def test_registro_escala_invalida():
    with pytest.raises(ValueError, match="escala"):
        registro.registrar([_golem(0)], 40, (64, 64), (32, 56), "nenhuma")


def test_validar_aprova_ciclo_bom():
    qs = [_golem(t) for t in range(8)]
    rel = validar.validar(qs, PAL, pivo=(32, 56))
    falhas = [c for c in rel["checagens"] if not c["ok"]]
    assert rel["aprovado"], validar.resumo(rel)
    assert all(not c["grave"] for c in falhas)


@pytest.mark.parametrize("estrago,checagem", [
    ("canvas", "V01"), ("alpha", "V02"), ("paleta", "V03"), ("deriva", "V06"), ("repetido", "V10"),
    ("olho", "V13"), ("cabeca", "V05"), ("pisca", "V09"), ("loop", "V11"),
])
def test_validar_reprova_cada_defeito(estrago, checagem):
    qs = [_golem(t) for t in range(8)]
    if estrago == "canvas":
        qs[3] = np.zeros((65, 64, 4), np.uint8)
    elif estrago == "alpha":
        qs[2] = qs[2].copy()
        qs[2][30, 30, 3] = 128
    elif estrago == "paleta":
        qs[1] = qs[1].copy()
        qs[1][30, 30, :3] = (1, 2, 3)
    elif estrago == "deriva":
        qs = [_golem(t, dx=t) for t in range(8)]
    elif estrago == "repetido":
        qs[4] = qs[3].copy()
    elif estrago == "olho":
        qs[5] = _golem(5, olho=False)
    elif estrago == "cabeca":
        qs[6] = qs[6].copy()
        qs[6][0:10, 26:38] = (*RGB["#a08c70"], 255)               # cabeça "cresce" 10 px
    elif estrago == "pisca":
        qs = [_golem(0)] * 8                                       # boil: pose parada, pixels soltos piscando
        qs = [q.copy() for q in qs]
        for i in (1, 3, 5, 7):
            for y in range(24, 42, 3):
                for x in range(24, 41, 3):
                    qs[i][y, x, :3] = RGB["#a08c70"]
            qs[i][12, 32, :3] = RGB["#6a5a4a"]                      # evita quadro idêntico disfarçado
    elif estrago == "loop":
        qs = [_golem(t, n=16) for t in range(8)]                  # meio ciclo: o último não volta ao primeiro
    rel = validar.validar(qs, PAL)
    falhou = {c["id"] for c in rel["checagens"] if not c["ok"]}
    assert checagem in falhou, validar.resumo(rel)
    assert not rel["aprovado"]


def test_processar_manifesto_liga_render3d_e_preserva_olho(tmp_path):
    man = _manifesto(tmp_path, [_golem(t) for t in range(8)])
    r = S.processar(str(man), PAL, 46, (64, 64), (32, 56), fator=2, proteger={RGB["#ff9a2a"]})
    rel = r["relatorio"]
    assert rel["preset"] == "render3d" and rel["escala"] == "fixa"
    assert len(r["quadros"]) == 8
    laranja = np.array(RGB["#ff9a2a"])
    assert all(np.all(q[..., :3] == laranja, -1).any() for q in r["quadros"])   # brilho do olho sobrevive
    v = rel["validacao"]
    assert {"V01", "V02", "V03", "V10"} <= {c["id"] for c in v["checagens"] if c["ok"]}
    topos = [registro.caixa(q)[1] for q in r["quadros"]]
    assert max(topos) - min(topos) >= 1                               # quique sobreviveu ao motor inteiro


def test_preset_invalido():
    with pytest.raises(ValueError, match="preset"):
        S.processar([_golem(0)], PAL, 40, (64, 64), (32, 56), preset="xyz")


def test_folha_godot(tmp_path):
    qs = [_golem(t) for t in range(8)]
    arqs = spritesheet.salvar(qs, tmp_path / "out", "golem_walk", 125, "walk", (32, 56))
    im = Image.open(arqs["png"])
    assert im.size == (64 * 8, 64) and im.mode == "RGBA"
    d = json.loads(open(arqs["json"], encoding="utf-8").read())
    assert len(d["frames"]) == 8 and d["meta"]["frameTags"][0] == {
        "name": "walk", "from": 0, "to": 7, "direction": "forward", "repeat": "0"}
    assert all(f["duration"] == 125 for f in d["frames"].values())
    assert d["meta"]["horys"]["pivo"] == [32, 56]
    assert Image.open(arqs["gif"]).n_frames == 8
    with pytest.raises(ValueError):
        spritesheet.salvar([qs[0], np.zeros((10, 10, 4), np.uint8)], tmp_path, "x")


def test_quantizacao_direta_preserva_degrade():
    """Render 3D: pelo escuro e pedra clara no mesmo quadro não podem cair no mesmo tom médio."""
    from horys_pixel.sequencia import quantizacao
    q = np.zeros((4, 64, 4), np.uint8)
    q[..., 3] = 255
    for x in range(64):                                   # degradê contínuo do escuro ao claro
        q[:, x, :3] = (40 + 3 * x, 30 + 3 * x, 35 + 2 * x)
    pal = ["#2a2531", "#5f4e42", "#8e7560", "#d8b898"]
    direta = quantizacao.quantizar([q], pal, direto=True)[0]
    assert set(direta[0].tolist()) == {0, 1, 2, 3}       # as 4 cores aparecem, em ordem
    assert list(direta[0]) == sorted(direta[0])
