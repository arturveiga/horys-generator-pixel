"""analise_estilo com imagens sintéticas geradas aqui: escala, rampas, contorno, fundo, dithering e o pacote."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from scipy import ndimage

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / "src"))

from horys_pixel import analise_estilo as A  # noqa: E402
from horys_pixel import estilos as E  # noqa: E402

RAMPAS = {"vermelho": ["#7a2333", "#b8413f", "#e8836a"], "verde": ["#24553f", "#3f8a4a", "#8cc46a"],
          "azul": ["#28306b", "#3f63a8", "#7fb0dd"]}
CONT = "#151020"


def h2r(h):
    return tuple(int(h.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))


def sprite32(contorno=True):
    """Sprite 32x32: elipse em 3 faixas de material (3 rampas de 3 tons, luz da esquerda) e contorno de 1 px."""
    im = np.zeros((32, 32, 4), np.uint8)
    yy, xx = np.mgrid[0:32, 0:32]
    corpo = ((xx - 15.5) / 11) ** 2 + ((yy - 16) / 14) ** 2 <= 1
    if contorno:
        corpo &= ~ndimage.binary_dilation(~corpo)          # deixa espaço para o contorno dentro do quadro
    for (y0, y1), r in zip(((0, 12), (12, 21), (21, 32)), RAMPAS.values()):
        faixa = corpo & (yy >= y0) & (yy < y1)
        for x in range(32):
            t = 2 if x < 12 else (1 if x < 20 else 0)
            im[faixa[:, x], x] = (*h2r(r[t]), 255)
    if contorno:
        op = im[..., 3] > 0
        im[ndimage.binary_dilation(op) & ~op] = (*h2r(CONT), 255)
    return im


def ampliar(im, k, pad=(13, 9), tam=None):
    big = np.array(Image.fromarray(im).resize((im.shape[1] * k, im.shape[0] * k), Image.NEAREST))
    H, W = tam or (big.shape[0] + 2 * pad[0] + 3, big.shape[1] + 2 * pad[1] + 1)
    out = np.zeros((H, W, 4), np.uint8)
    out[pad[0]:pad[0] + big.shape[0], pad[1]:pad[1] + big.shape[1]] = big
    return out


def salvar(arr, p):
    Image.fromarray(arr).save(p)
    return p


def test_escala_rampas_e_contorno_4x(tmp_path):
    p = salvar(ampliar(sprite32(), 4), tmp_path / "s4.png")
    a = A.analisar_imagens([p])
    assert a["escala"]["mais_comum"] == 4
    assert a["imagens"][0]["tamanho_real"][0] < 50          # voltou para a grade real
    assert a["contorno"]["tem_contorno"] and a["contorno"]["cor"] == CONT
    assert a["rampas"]["quantas"] == 3
    assert a["paleta"]["contorno"] == CONT
    materiais = {k: v for k, v in a["paleta"]["rampas"].items() if k not in ("contorno", "brilho")}
    assert sorted(sorted(v) for v in materiais.values()) == sorted(sorted(v) for v in RAMPAS.values())
    assert set(materiais) == {"vermelho", "verde", "azul"}
    assert a["tons_por_material"] == 3.0
    assert a["sprites"]["quantos"] == 1
    ys, xs = np.nonzero(sprite32()[..., 3])
    assert a["sprites"]["altura_mediana"] == ys.max() - ys.min() + 1       # medido na grade real, não na ampliada
    assert a["sprites"]["largura_mediana"] == xs.max() - xs.min() + 1
    assert not a["dithering"]["tem"] and not a["antialiasing"]["tem"]
    assert a["luz"]["x"] < -0.25                                 # luz da esquerda, como desenhado
    assert a["pixel_art"]


@pytest.mark.parametrize("k", [1, 2, 3, 5])
def test_escala_com_fase(tmp_path, k):
    p = salvar(ampliar(sprite32(), k, pad=(7, 5)), tmp_path / f"s{k}.png")
    a = A.analisar_imagens([p])
    assert a["escala"]["mais_comum"] == k
    assert a["rampas"]["quantas"] == 3 and a["contorno"]["cor"] == CONT


def test_fundo_opaco_e_jpg(tmp_path):
    im = ampliar(sprite32(), 4)
    fundo = np.zeros_like(im)
    fundo[...] = (200, 210, 190, 255)
    op = im[..., 3] == 255
    fundo[op] = im[op]
    p = salvar(fundo, tmp_path / "op.png")
    a = A.analisar_imagens([p])
    assert a["imagens"][0]["fundo_removido"]
    assert a["escala"]["mais_comum"] == 4 and a["rampas"]["quantas"] == 3 and a["contorno"]["cor"] == CONT
    j = tmp_path / "op.jpg"
    Image.fromarray(fundo[..., :3]).save(j, quality=95)
    b = A.analisar_imagens([j])
    assert b["escala"]["mais_comum"] == 4
    assert b["contorno"]["tem_contorno"]
    assert b["rampas"]["quantas"] == 3


def test_sem_contorno(tmp_path):
    p = salvar(ampliar(sprite32(contorno=False), 2), tmp_path / "sc.png")
    a = A.analisar_imagens([p])
    assert not a["contorno"]["tem_contorno"]


def test_dithering(tmp_path):
    im = sprite32()
    yy, xx = np.mgrid[0:32, 0:32]
    verde = np.all(im[..., :3] == h2r(RAMPAS["verde"][1]), axis=-1)
    im[verde & ((xx + yy) % 2 == 0), :3] = h2r(RAMPAS["verde"][0])
    a = A.analisar_imagens([salvar(ampliar(im, 3), tmp_path / "d.png")])
    assert a["dithering"]["tem"]


def test_imagem_comum_limita_cores(tmp_path):
    yy, xx = np.mgrid[0:200, 0:300]
    rgb = np.stack([xx * 255 // 299, yy * 255 // 199, (xx + yy) * 255 // 498], -1).astype(np.uint8)
    p = tmp_path / "grad.png"
    Image.fromarray(rgb).save(p)
    a = A.analisar_imagens([p])
    cores = {c for v in a["paleta"]["rampas"].values() for c in v}
    assert len(cores) <= 33
    assert all(2 <= len(v) <= 4 or k in ("contorno", "brilho") or len(v) == 1
               for k, v in a["paleta"]["rampas"].items())
    assert a["antialiasing"]["tem"]          # gradiente: vizinhos quase iguais


def test_criar_pacote(tmp_path, monkeypatch):
    monkeypatch.delenv("HORYS_PIXEL_HOME", raising=False)
    monkeypatch.setenv("HORYS_HOME", str(tmp_path / "home"))
    imgs = [salvar(ampliar(sprite32(), 4), tmp_path / "a.png"), salvar(ampliar(sprite32(), 2), tmp_path / "b.png")]
    pasta = A.criar_pacote("Meu Estilo", imgs, autor="Fulano", licenca_imagens="CC0")
    assert pasta == tmp_path / "home" / "estilos" / "meu-estilo"
    for n in ("estilo.json", "paleta.json", "paleta.gpl", "paleta.hex", "analise.json", "estilo.md",
              "referencias/a.png", "referencias/b.png", "referencias/origem.json"):
        assert (pasta / n).exists(), n
    origem = json.loads((pasta / "referencias" / "origem.json").read_text(encoding="utf-8"))
    assert origem["licenca"] == "CC0" and len(origem["arquivos"]) == 2
    md = (pasta / "estilo.md").read_text(encoding="utf-8")
    for i in range(1, 16):
        assert f"| {i} |" in md
    assert "a confirmar" in md and CONT in md
    # o pacote criado é um pacote de estilo válido e o motor aceita a config dele
    assert "meu-estilo" in E.listar()
    e = E.carregar("meu-estilo")
    assert e.autor == "Fulano" and not e.no_repo
    p = E.paleta(e)
    assert p["contorno"] == CONT and len([k for k in p["rampas"] if k not in ("contorno", "brilho")]) == 3
    c = E.config_motor(e)
    assert Path(c["paleta_json"]).exists() and c["regua"] is None
    assert E.pasta_dados(e, "conjunto") == pasta / "conjunto"
