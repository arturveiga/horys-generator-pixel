import numpy as np
from PIL import Image

from horys_pixel import sequencia as S
from horys_pixel.sequencia import anticintilacao, entradas, escolha, identidade, quantizacao, registro


def _fig(h, x, y, W=200, H=200, cor=(200, 80, 60, 255)):
    q = np.zeros((H, W, 4), np.uint8)
    w = max(2, h // 3)
    q[y - h + 1:y + 1, x - w // 2:x + w // 2 + 1] = cor
    return q


def test_sequencia_entradas(tmp_path):
    qs = [_fig(60, 50 + i, 150) for i in range(4)]
    pasta = tmp_path / "p"
    pasta.mkdir()
    for i, q in enumerate(qs):
        Image.fromarray(q, "RGBA").save(pasta / f"{i:02d}.png")
    grade = np.concatenate([np.concatenate(qs[:2], 1), np.concatenate(qs[2:], 1)], 0)
    Image.fromarray(grade, "RGBA").save(tmp_path / "g.png")
    a = entradas.carregar(pasta)
    b = entradas.carregar(tmp_path / "g.png", 2, 2)
    assert len(a) == len(b) == 4
    for x, y in zip(a, b):
        assert x.shape == y.shape and x.dtype == np.uint8 and x.shape[-1] == 4
        assert np.array_equal(x, y)


def test_registro_deriva_ate_1px():
    qs = [_fig(100, 80, 150), _fig(120, 100, 160), _fig(90, 70, 140), _fig(110, 95, 155)]
    r = registro.registrar(qs, 100, (200, 200), (100, 180))
    d = registro.deriva(r)
    assert d["pes"] <= 1 and d["x"] <= 1 and d["altura"] <= 1


def test_escolher_andar_pega_os_contatos():
    quadros = []
    for i in range(16):
        q = np.zeros((60, 60, 4), np.uint8)
        abre = 2 + int(round(10 * abs(np.cos(np.pi * i / 4))))   # contatos em i = 0, 4, 8, 12
        q[10:50, 28:32] = 255
        q[48:50, 30 - abre:30 + abre] = 255
        quadros.append(q)
    esc = escolha.escolher_andar(quadros, 8)
    assert len(esc) == 8
    assert {4, 8}.issubset(set(esc))


def test_quantizacao_conjunta_estavel():
    rng = np.random.default_rng(1)
    qs = []
    for _ in range(5):
        q = np.zeros((40, 40, 4), np.uint8)
        ruido = rng.integers(-3, 4, (30, 30, 3))
        q[5:35, 5:35, :3] = np.clip(np.array([120, 90, 70]) + ruido, 0, 255)
        q[5:35, 5:35, 3] = 255
        qs.append(q)
    idx = quantizacao.quantizar(qs, ["#785a46", "#202020", "#f0f0f0"])
    assert all(np.array_equal(idx[0], m) for m in idx)
    assert len(set(idx[0][idx[0] >= 0].tolist())) == 1


def test_anticintilacao_zera_o_pisca():
    base = np.zeros((20, 20), np.int16)
    base[5:15, 5:15] = 2
    fr = [base.copy() for _ in range(6)]
    for i in (1, 3):
        fr[i][8, 8] = 3
    assert anticintilacao.pisca(fr) > 0
    assert anticintilacao.pisca(anticintilacao.aplicar(fr)) == 0


def test_identidade_acha_peca_deslocada_3px():
    base = np.zeros((40, 40, 4), np.uint8)
    base[10:16, 10:16] = (255, 0, 0, 255)
    base[12, 12] = (0, 255, 0, 255)
    q = np.zeros((40, 40, 4), np.uint8)
    q[13:19, 13:19] = (255, 0, 0, 255)
    q[15, 15] = (0, 0, 255, 255)
    out, rel = identidade.travar([q], base, [{"nome": "olho", "rect": [10, 10, 6, 6], "busca": 5}])
    assert rel[0]["colou"] and (rel[0]["x"], rel[0]["y"]) == (13, 13)
    assert tuple(out[0][15, 15]) == (0, 255, 0, 255)
    assert tuple(out[0][12, 12]) == (0, 0, 0, 0)       # sem borda nem retângulo fora da peça


def test_processar_ponta_a_ponta():
    qs = [_fig(100 + 4 * i, 80 + 3 * i, 150 + i) for i in range(4)]
    r = S.processar(qs, ["#c8503c", "#202020"], 50, (80, 80), (40, 70), fator=2, limpar_min=1, regularizar=False)
    assert len(r["quadros"]) == 4 and all(q.shape == (80, 80, 4) for q in r["quadros"])
    assert r["relatorio"]["pisca_depois"] == 0.0


def test_registro_andar_nao_pula_de_pe_em_pe():
    """No andar um pé fica mais baixo: o registro centraliza pelo corpo, não pelo pé da frente."""
    import numpy as np
    from horys_pixel.sequencia import registro
    def fig(pe_baixo_esq):
        q = np.zeros((120, 120, 4), np.uint8)
        q[20:90, 40:80] = 255                              # corpo
        e, d = (100, 94) if pe_baixo_esq else (94, 100)
        q[90:e, 42:52] = 255                               # pé esquerdo
        q[90:d, 68:78] = 255                               # pé direito
        return q
    out = registro.registrar([fig(True), fig(False)], 60, (100, 100), (50, 90), "comum")
    cx = [registro.caixa(q) for q in out]
    centros = [(b[0] + b[2]) / 2 for b in cx]
    assert abs(centros[0] - centros[1]) <= 1
