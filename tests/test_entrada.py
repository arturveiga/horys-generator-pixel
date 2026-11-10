"""Portão de entrada (tarefa 1.4) com imagens sintéticas: imagem boa, fundo em degradê, figura cortada, sombra no
chão, escala pequena, cor do fundo na figura, degradê na figura e grades (boa, escalas diferentes, chão diferente)."""
import numpy as np
from PIL import Image, ImageDraw

from horys_pixel import entrada
from test_nucleo import _ambiente, _txt, rodar

VERDE = (61, 190, 91)
CONTORNO = (26, 28, 44)


def _figura(d: ImageDraw.ImageDraw, cx: int, topo: int, altura: int, corpo=(150, 110, 200), pele=(230, 180, 140)):
    """Boneco chapado de contorno escuro: cabeça, tronco, braços e duas pernas; pés na linha topo+altura-1."""
    u = altura / 100.0
    w = lambda v: int(round(v * u))  # noqa: E731
    lw = max(2, w(1.2))
    d.ellipse([cx - w(14), topo, cx + w(14), topo + w(26)], fill=pele, outline=CONTORNO, width=lw)
    d.rectangle([cx - w(22), topo + w(24), cx + w(22), topo + w(62)], fill=corpo, outline=CONTORNO, width=lw)
    d.rectangle([cx - w(34), topo + w(26), cx - w(22), topo + w(56)], fill=pele, outline=CONTORNO, width=lw)
    d.rectangle([cx + w(22), topo + w(26), cx + w(34), topo + w(56)], fill=pele, outline=CONTORNO, width=lw)
    pe = topo + altura - 1
    d.rectangle([cx - w(20), topo + w(60), cx - w(4), pe], fill=(90, 70, 60), outline=CONTORNO, width=lw)
    d.rectangle([cx + w(4), topo + w(60), cx + w(20), pe], fill=(90, 70, 60), outline=CONTORNO, width=lw)


def _imagem(tmp_path, nome="img.png", tam=(400, 600), fundo=VERDE, figs=((200, 70, 450),), extra=None):
    im = Image.new("RGB", tam, fundo)
    d = ImageDraw.Draw(im)
    if extra:
        extra(im, d)
    for cx, topo, alt in figs:
        _figura(d, cx, topo, alt)
    p = tmp_path / nome
    im.save(p)
    return p


def _itens(r):
    return [(f["item"], f["texto"]) for f in r["falhas"]]


def _tem(r, item, trecho):
    return any(i == item and trecho in t for i, t in _itens(r))


def test_imagem_boa_aprova_e_grava(tmp_path):
    p = _imagem(tmp_path)
    r = entrada.checar(p, 100)
    assert r["aprovado"], _itens(r)
    m = r["medidas"]
    assert m["figura"]["altura"] == 450 and m["pes_y"] == 519
    assert m["escala"]["razao"] == 4.5
    assert m["chapado"]["degrade"] < 0.05 and m["chapado"]["areas_lisas"] > 0.8
    txt = (tmp_path / "entrada_checagem.txt").read_text(encoding="utf-8")
    assert txt.splitlines()[0] == "PORTÃO DE ENTRADA: APROVADO"
    previa = Image.open(m["previa"])
    assert previa.height == round(600 * 100 / 450)  # figura na altura alvo
    assert previa.width == round(400 * 100 / 450)


def test_fundo_em_degrade_reprova(tmp_path):
    def degrade(im, d):
        a = np.zeros((600, 400, 3), np.uint8)
        t = np.linspace(0, 1, 600)[:, None, None]
        a[:] = (np.array([175, 160, 160]) * (1 - t) + np.array([110, 95, 95]) * t).astype(np.uint8)
        im.paste(Image.fromarray(a))
    r = entrada.checar(_imagem(tmp_path, extra=degrade), 100)
    assert not r["aprovado"]
    assert _tem(r, 10, "Fundo não é liso")
    txt = (tmp_path / "entrada_checagem.txt").read_text(encoding="utf-8")
    assert txt.splitlines()[0] == "PORTÃO DE ENTRADA: REPROVADO"
    assert "item 10" in txt


def test_figura_cortada_reprova(tmp_path):
    r = entrada.checar(_imagem(tmp_path, figs=((385, 70, 450),)), 100, gravar=False)
    assert _tem(r, 10, "cortada")
    assert r["medidas"]["figura"]["margens"]["dir"] == 0
    assert not (tmp_path / "entrada_checagem.txt").exists()


def test_margem_curta_reprova(tmp_path):
    r = entrada.checar(_imagem(tmp_path, figs=((200, 8, 450),)), 100, margem_min=0.05, gravar=False)
    assert _tem(r, 10, "margem curta") and not _tem(r, 10, "cortada")
    assert entrada.checar(_imagem(tmp_path, figs=((200, 8, 450),)), 100, margem_min=0.01,
                          gravar=False)["aprovado"]


def test_sombra_no_chao_reprova(tmp_path):
    def sombra(im, d):
        d.ellipse([90, 495, 310, 540], fill=(35, 120, 55))  # verde do fundo escurecido, achatado, sob os pés
    r = entrada.checar(_imagem(tmp_path, extra=sombra), 100, gravar=False)
    assert _tem(r, 10, "sombra no chão")
    assert r["medidas"]["figura"]["sombra"]["largura"] > 150


def test_sombra_suave_no_fundo_reprova(tmp_path):
    def sombra(im, d):
        a = np.asarray(im).astype(float)
        yy, xx = np.mgrid[:600, :400]
        k = np.clip(1 - (((xx - 200) / 120) ** 2 + ((yy - 520) / 18) ** 2), 0, 1)[..., None]
        im.paste(Image.fromarray((a * (1 - 0.35 * k)).astype(np.uint8)))
    r = entrada.checar(_imagem(tmp_path, extra=sombra), 100, gravar=False)
    assert _tem(r, 10, "sombra no chão")


def test_escala_pequena_reprova(tmp_path):
    r = entrada.checar(_imagem(tmp_path), 200, gravar=False)
    assert _tem(r, 1, "pequena demais")
    assert r["medidas"]["escala"]["razao"] == 2.25


def test_cor_do_fundo_na_figura_reprova(tmp_path):
    p = _imagem(tmp_path)
    im = Image.open(p)
    ImageDraw.Draw(im).rectangle([170, 200, 230, 260], fill=(75, 170, 100))  # verde parecido com o fundo (ΔE 0.06)
    im.save(p)
    r = entrada.checar(p, 100, gravar=False)
    assert _tem(r, 10, "aparece dentro da figura")


def test_degrade_na_figura_reprova(tmp_path):
    p = _imagem(tmp_path)
    a = np.asarray(Image.open(p)).copy()
    y0, y1, x0, x1 = 186, 345, 154, 247  # miolo do tronco
    t = np.linspace(0, 1, y1 - y0)[:, None, None]
    a[y0:y1, x0:x1] = (np.array([220, 120, 120]) * (1 - t) + np.array([60, 60, 170]) * t).astype(np.uint8)
    Image.fromarray(a).save(p)
    r = entrada.checar(p, 100, gravar=False)
    assert _tem(r, 9, "degradê"), _itens(r)


def test_grade_boa_aprova(tmp_path):
    figs = tuple((150 + 300 * i, 60, 360) for i in range(3))
    r = entrada.checar(_imagem(tmp_path, tam=(900, 520), figs=figs), 100, grade=(1, 3))
    assert r["aprovado"], _itens(r)
    g = r["medidas"]["grade"]
    assert g["alturas"] == [360, 360, 360] and g["desvio_altura_max"] == 0
    assert Image.open(r["medidas"]["previa"]).height == round(520 * 100 / 360)


def test_grade_com_escalas_diferentes_reprova(tmp_path):
    figs = ((150, 60, 360), (450, 96, 324), (750, 60, 360))  # a do meio 10% menor, mesmo chão
    r = entrada.checar(_imagem(tmp_path, tam=(900, 520), figs=figs), 100, grade=(1, 3), gravar=False)
    assert _tem(r, 10, "alturas diferentes")
    assert not _tem(r, 10, "mesmo chão")


def test_grade_com_chao_diferente_reprova(tmp_path):
    figs = ((150, 60, 360), (450, 30, 360), (750, 60, 360))  # mesma altura, pés 30 px acima
    r = entrada.checar(_imagem(tmp_path, tam=(900, 520), figs=figs), 100, grade=(1, 3), gravar=False)
    assert _tem(r, 10, "mesmo chão") and not _tem(r, 10, "alturas diferentes")


def test_grade_celula_vazia_e_duas_figuras(tmp_path):
    figs = ((75, 219, 200), (225, 219, 200), (750, 60, 360))  # duas na 1ª célula, nenhuma na 2ª
    r = entrada.checar(_imagem(tmp_path, tam=(900, 520), figs=figs), 100, grade=(1, 3), gravar=False)
    assert _tem(r, 1, "vazia") and _tem(r, 1, "figuras grandes separadas")


def test_ferramenta_portao_entrada(ambiente, tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    boa = _imagem(tmp_path / "a")
    ruim = _imagem(tmp_path / "b", figs=((385, 70, 450),))

    async def corpo():
        ctx, ase, chamar, fim = await _ambiente(ambiente)
        try:
            r = await chamar("horys_portao_entrada", imagem=str(boa), altura=100)
            assert not r["erro"], _txt(r)
            assert _txt(r).startswith("PORTÃO DE ENTRADA: APROVADO")
            assert any(c["type"] == "image" for c in r["conteudo"])
            r = await chamar("horys_portao_entrada", imagem=str(ruim), altura=100, margem_min=0.05)
            assert _txt(r).startswith("PORTÃO DE ENTRADA: REPROVADO") and "item 10" in _txt(r)
            r = await chamar("horys_portao_entrada", imagem=str(tmp_path / "nao.png"), altura=100)
            assert r["erro"]
        finally:
            await fim()
    rodar(corpo())


def test_converter_recusa_entrada_reprovada(tmp_path):
    from horys_pixel.ferramentas.estilo import entrada_reprovada
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    boa = _imagem(tmp_path / "a")
    ruim = _imagem(tmp_path / "b", figs=((385, 70, 450),))
    assert entrada_reprovada(boa) and "falta" in entrada_reprovada(boa)
    assert entrada.checar(boa, 100)["aprovado"]
    assert entrada_reprovada(boa) is None
    outra = tmp_path / "a" / "outra.png"
    outra.write_bytes(boa.read_bytes())
    assert "não é da imagem" in entrada_reprovada(outra)
    assert not entrada.checar(ruim, 100, margem_min=0.05)["aprovado"]
    assert "reprovou" in entrada_reprovada(ruim)


def test_medir_pe_no_vao_entre_os_pes():
    from horys_pixel.motor.medir import medir_quadro
    f = np.zeros((80, 80, 4), np.uint8)
    f[10:60, 25:55] = (120, 80, 60, 255)      # tronco e tanga (acaba em y=59 no centro)
    f[60:70, 25:33] = (120, 80, 60, 255)      # pé esquerdo
    f[60:70, 47:55] = (120, 80, 60, 255)      # pé direito; vão no centro
    r, _ = medir_quadro(f, {"contorno": (0, 0, 0), "brilho": [], "chao_L": {}})
    assert r["pe"] == 69
