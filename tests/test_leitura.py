import numpy as np
import pytest

from horys_pixel import leitura as L

from .conftest import ampliar_irregular


def _vistas_verdade(rgba):
    return L._separar(rgba)


def _acerto(lido: np.ndarray, verdade: np.ndarray) -> float:
    """Fração dos pixels da verdade (opacos) reproduzidos com a mesma cor (±12 por canal) no mesmo lugar."""
    assert lido.shape == verdade.shape, (lido.shape, verdade.shape)
    op = verdade[..., 3] > 0
    ok = (lido[..., 3] > 0) & (np.abs(lido[..., :3].astype(int) - verdade[..., :3].astype(int)).max(-1) <= 12)
    return float((ok & op).sum() / op.sum())


def test_pixel_art_exata_e_lida_sem_mudar(boneco):
    rgb = ampliar_irregular(boneco, bloco=(1, 1), borrar=False, margem=4)
    r = L.ler(rgb, alvo=44)
    assert r.relatorio["modo"] == "exata"
    assert list(r.vistas) == ["frente", "lado", "costas"]
    for lido, verdade in zip(r.vistas.values(), _vistas_verdade(boneco)):
        assert _acerto(lido, verdade) == 1.0


def test_ampliada_por_inteiro_exato(boneco):
    rgba = np.repeat(np.repeat(boneco, 6, 0), 6, 1)
    rgb = ampliar_irregular(rgba, bloco=(1, 1), borrar=False, margem=24)
    r = L.ler(rgb, alvo=44)
    assert r.relatorio["modo"] == "exata" and r.relatorio["escala"] == 6


@pytest.mark.parametrize("bloco,semente", [((11, 15), 0), ((11, 15), 1), ((14, 14), 0), ((20, 30), 2)])
def test_blocos_irregulares_com_borda_suave_voltam_ao_original(boneco, bloco, semente):
    rgb = ampliar_irregular(boneco, bloco=bloco, borrar=True, semente=semente)
    r = L.ler(rgb, alvo=44, contorno=False)
    assert r.relatorio["modo"] == "grade"
    assert r.altura == 44
    for lido, verdade in zip(r.vistas.values(), _vistas_verdade(boneco)):
        assert _acerto(lido, verdade) >= 0.99


def test_olho_de_um_pixel_sobrevive():
    rgba = np.zeros((20, 14, 4), np.uint8)
    rgba[1:19, 1:13] = (200, 160, 120, 255)          # corpo
    rgba[0, :], rgba[-1, :], rgba[:, 0], rgba[:, -1] = (20, 20, 30, 255), (20, 20, 30, 255), (20, 20, 30, 255), (20, 20, 30, 255)
    rgba[5, 4] = (20, 20, 30, 255)                    # olhos de 1 px
    rgba[5, 9] = (20, 20, 30, 255)
    rgb = ampliar_irregular(rgba, bloco=(12, 16), borrar=True, semente=3)
    r = L.ler(rgb, alvo=20)
    f = r.vistas["frente"]
    escuro = (f[..., :3].astype(int).sum(-1) < 150) & (f[..., 3] > 0)
    miolo = escuro[2:-2, 2:-2]
    assert miolo.sum() >= 2, "os dois olhos de 1 px têm que continuar lá"


def test_altura_errada_e_recusada(boneco):
    rgb = ampliar_irregular(boneco, bloco=(11, 15), borrar=True)
    with pytest.raises(L.ErroLeitura, match="Gere a imagem de novo"):
        L.ler(rgb, alvo=32)


def test_paleta_travada_so_usa_as_cores_dela(boneco):
    rgb = ampliar_irregular(boneco, bloco=(11, 15), borrar=True, semente=7)
    pal = ["#161c2e", "#69777f", "#a0b3b6", "#daf3ee"]
    r = L.ler(rgb, alvo=44, paleta=pal)
    usadas = {"#%02x%02x%02x" % tuple(p) for v in r.vistas.values() for p in v[v[..., 3] > 0][:, :3]}
    assert usadas <= set(pal)


def test_folha_alinha_pelo_pe(boneco):
    r = L.ler(ampliar_irregular(boneco, bloco=(1, 1), borrar=False, margem=4), alvo=44)
    f = r.folha
    assert f.shape[0] == 44 + 4
    ult = np.nonzero(f[..., 3].any(1))[0].max()
    assert ult == f.shape[0] - 3
