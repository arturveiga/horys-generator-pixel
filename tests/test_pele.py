"""Base + Pele: leitura na grade da base, separação da pele e propagação por parte (dados sintéticos, sem arte)."""
import numpy as np
import pytest

from horys_pixel import pele as P

CHAVE = (255, 0, 255)
CINZA = (128, 128, 128, 255)
ESCURO = (30, 30, 40, 255)
VERMELHO = (200, 40, 40, 255)


def _base():
    b = np.zeros((20, 12, 4), np.uint8)
    b[2:8, 3:9] = CINZA      # cabeça
    b[8:15, 4:8] = CINZA     # tronco
    b[15:19, 4:6] = ESCURO   # perna esq.
    b[15:19, 6:8] = ESCURO   # perna dir.
    return b


def _ampliar(rgba, k, ox, oy, tam=(400, 300)):
    """Ampliação inteira sobre a chave, deslocada (o que o Codex devolveria num caso ideal)."""
    H, W = tam
    img = np.zeros((H, W, 3), np.uint8)
    img[:] = CHAVE
    big = np.repeat(np.repeat(rgba, k, 0), k, 1)
    m = big[..., 3] > 0
    sub = img[oy:oy + big.shape[0], ox:ox + big.shape[1]]
    sub[m] = big[m][:, :3]
    return img


def test_vestir_separa_so_as_celulas_que_mudaram():
    base = _base()
    vestida = base.copy()
    vestida[9:13, 4:8] = VERMELHO          # camisa sobre o tronco
    vestida[1, 3:9] = VERMELHO             # chapéu acima da cabeça (fora da base)
    img = _ampliar(vestida, 14, ox=37, oy=21)
    v = P.vestir(base, img, "#ff00ff")
    assert v.grade.celula == pytest.approx(14, abs=0.2)
    assert v.grade.acerto > 0.75   # a camisa cobre 16 das 80 células da base: não dá 100%
    esperado = np.zeros(base.shape[:2], bool)
    esperado[9:13, 4:8] = True
    esperado[1, 3:9] = True
    assert (v.mudou == esperado).all()
    assert (v.pele[esperado][:, :3] == VERMELHO[:3]).all()
    assert (v.pele[~esperado][:, 3] == 0).all()
    assert v.removidos == 0 and not v.avisos
    assert (P.compor(base, v.pele) == v.lido).all()


def test_vestir_tira_celula_solta_e_avisa_imagem_que_nao_e_a_base():
    base = _base()
    vestida = base.copy()
    vestida[10, 5] = VERMELHO               # um pixel solto: ruído
    v = P.vestir(base, _ampliar(vestida, 12, 10, 10), "#ff00ff")
    assert v.isolados_tirados == 1 and not v.mudou.any()
    outra = np.zeros_like(base)
    outra[0:20, 0:12] = VERMELHO            # nada a ver com a base
    v2 = P.vestir(base, _ampliar(outra, 12, 10, 10), "#ff00ff")
    assert v2.avisos


def test_vestir_encaixa_na_paleta_dada():
    base = _base()
    vestida = base.copy()
    vestida[9:13, 4:8] = (205, 45, 38, 255)  # quase vermelho
    v = P.vestir(base, _ampliar(vestida, 10, 5, 5), "#ff00ff", paleta=["#c82828", "#2828c8"])
    assert v.cores_pele == ["#c82828"]


def test_propagar_leva_a_pele_com_a_parte():
    p0 = np.zeros((20, 12), int)
    p0[2:8, 3:9] = 1      # cabeça
    p0[8:15, 4:8] = 2     # tronco
    pn = np.zeros_like(p0)
    pn[3:9, 3:9] = 1      # cabeça desce 1
    pn[9:16, 5:9] = 2     # tronco desce 1 e anda 1
    pele = np.zeros((20, 12, 4), np.uint8)
    pele[1, 3:9] = VERMELHO     # chapéu: fora da base, vai para a parte mais próxima (cabeça)
    pele[10:12, 4:8] = VERMELHO  # camisa (tronco)
    r = P.propagar(pele, p0, pn)
    assert r.por_parte[1]["dx"] == 0 and r.por_parte[1]["dy"] == 1
    assert r.por_parte[2]["dx"] == 1 and r.por_parte[2]["dy"] == 1
    assert (r.pele[2, 3:9, 3] == 255).all()
    assert (r.pele[11:13, 5:9, 3] == 255).all()
    assert not r.avisos


def test_propagar_avisa_parte_que_muda_de_forma():
    p0 = np.zeros((20, 12), int)
    p0[8:15, 4:8] = 1
    pn = np.zeros_like(p0)
    pn[12:14, 1:11] = 1   # a parte deitou: não é só deslocamento
    pele = np.zeros((20, 12, 4), np.uint8)
    pele[9:13, 4:8] = VERMELHO
    r = P.propagar(pele, p0, pn)
    assert r.avisos


def test_ferramentas_pele_por_arquivo(tmp_path):
    """horys_base_ler -> horys_vestir -> horys_propagar_pele só com arquivos (sem Aseprite)."""
    import asyncio
    from PIL import Image
    from horys_pixel.ferramentas import registro
    registro.carregar_todas()
    chamar = lambda nome, **a: asyncio.run(registro.REGISTRO[nome].funcao(None, a))
    base = _base()
    Image.fromarray(_ampliar(base, 12, 30, 30)).save(tmp_path / "ref.png")
    chamar("horys_base_ler", imagem=str(tmp_path / "ref.png"), saida=str(tmp_path / "b"), cores=2, margem=2)
    b1 = np.array(Image.open(tmp_path / "b" / "base.png"))
    assert b1.shape == (17 + 4, 6 + 4, 4)
    vest = b1.copy()
    vest[8:12, 3:7] = VERMELHO
    Image.fromarray(_ampliar(vest, 12, 20, 25)).save(tmp_path / "vest.png")
    import pytest
    from horys_pixel.ferramentas.registro import ErroFerramenta
    with pytest.raises(ErroFerramenta, match="TRAVADO"):
        chamar("horys_vestir", base=str(tmp_path / "b" / "base.png"), imagem=str(tmp_path / "vest.png"),
               saida=str(tmp_path / "v"))
    chamar("horys_aprovar_arquivo", arquivo=str(tmp_path / "b" / "base.png"), chat=True, comentario="pode vestir")
    r = chamar("horys_vestir", base=str(tmp_path / "b" / "base.png"), imagem=str(tmp_path / "vest.png"),
               saida=str(tmp_path / "v"))
    pele = np.array(Image.open(tmp_path / "v" / "pele.png"))
    assert (pele[8:12, 3:7, 3] == 255).all() and pele[..., 3].sum() == 16 * 255
    mapa = np.zeros(b1.shape, np.uint8)
    mapa[b1[..., 3] > 0] = (10, 10, 10, 255)
    Image.fromarray(mapa).save(tmp_path / "p0.png")
    Image.fromarray(np.roll(mapa, 1, 0)).save(tmp_path / "p1.png")
    chamar("horys_propagar_pele", pele=str(tmp_path / "v" / "pele.png"), partes_ref=str(tmp_path / "p0.png"),
           partes=[str(tmp_path / "p1.png")], saida=str(tmp_path / "q"))
    p1 = np.array(Image.open(tmp_path / "q" / "pele_00.png"))
    assert (p1[9:13, 3:7, 3] == 255).all()


def test_grade_propria_blocos_irregulares_e_franja():
    """Blocos de 11 a 14 px (como o gpt-image) e borda borrada com a chave: volta o sprite 1x exato."""
    from scipy import ndimage
    rng = np.random.default_rng(3)
    cores = np.array([(20, 16, 40), (40, 70, 200), (230, 215, 205), (60, 250, 250)], np.uint8)
    spr = np.zeros((14, 10, 4), np.uint8)
    idx = rng.integers(0, 4, (10, 6))
    spr[2:12, 2:8, :3] = cores[idx]
    spr[2:12, 2:8, 3] = 255
    bx = np.cumsum([0] + [int(rng.integers(11, 15)) for _ in range(10)])
    by = np.cumsum([0] + [int(rng.integers(11, 15)) for _ in range(14)])
    img = np.zeros((by[-1], bx[-1], 3), np.uint8)
    img[:] = (255, 0, 255)
    for i in range(14):
        for j in range(10):
            if spr[i, j, 3]:
                img[by[i]:by[i + 1], bx[j]:bx[j + 1]] = spr[i, j, :3]
    img = ndimage.uniform_filter(img.astype(float), size=(3, 3, 1)).astype(np.uint8)   # franja
    out, bloco, _ = P.ler_grade_propria(img, paleta=["#%02x%02x%02x" % tuple(c) for c in cores])
    ys, xs = np.nonzero(out[..., 3])
    lido = out[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    assert lido.shape[:2] == (10, 6)
    assert (lido[..., :3] == spr[2:12, 2:8, :3]).all()
    assert 11 <= bloco <= 14


def test_ler_pose_trava_cabeca_e_tira_halo():
    """Pose do Codex com cabeça redesenhada e halo ciano: sai na grade do master com a cabeça do master."""
    master = np.zeros((12, 6, 4), np.uint8)
    master[0:5, 1:5] = (230, 215, 205, 255)          # cabeça clara
    master[2, 2] = (20, 16, 40, 255)                 # olho
    master[5:12, 0:6] = (40, 70, 200, 255)           # corpo
    pose = master.copy()
    pose[0:5, 1:5] = (40, 70, 200, 255)              # o Codex "redesenhou" a cabeça
    pose[6:12, 0:2] = 0
    pose[6:12, 4:6] = 0                              # pernas mais finas (a pose)
    big = np.zeros((14, 10, 4), np.uint8)
    big[1:13, 2:8] = pose
    k = 16
    img = np.zeros((14 * k, 10 * k, 3), np.uint8)
    img[:] = (255, 0, 255)
    for y in range(14):
        for x in range(10):
            if big[y, x, 3]:
                img[y * k:(y + 1) * k, x * k:(x + 1) * k] = big[y, x, :3]
    # halo ciano de 1 bloco em volta da figura
    fig = np.kron(big[..., 3] > 0, np.ones((k, k), bool))
    from scipy import ndimage as nd
    halo = nd.binary_dilation(fig, iterations=4) & ~fig        # halo fino (1/4 de bloco), como o do Codex
    img[halo] = (90, 250, 250)
    pal = ["#e6d7cd", "#141028", "#2846c8", "#5afafa"]
    r = P.ler_pose(img, master, paleta=pal, cabeca=5)
    assert r.quadro.shape[:2] == (12, 6), r.quadro.shape
    assert (r.quadro[0:5, 1:5, :3] == master[0:5, 1:5, :3]).all()
    assert not ((r.quadro[..., 1] > 200) & (r.quadro[..., 0] < 120) & (r.quadro[..., 3] > 0)).any()
