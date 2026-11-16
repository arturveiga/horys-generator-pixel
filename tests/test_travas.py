"""Travas de passo (C6): aprovação presa ao sha256 do arquivo e A/B obrigatório na entrega."""
import json

import numpy as np
import pytest
from PIL import Image

from horys_pixel import travas as T


def _png(p, v=0):
    a = np.zeros((4, 4, 4), np.uint8)
    a[1, 1] = (v, 0, 0, 255)
    Image.fromarray(a).save(p)


def test_aprovacao_cai_quando_o_arquivo_muda(tmp_path):
    f = tmp_path / "vista.png"
    _png(f)
    with pytest.raises(T.Travado, match="não foi aprovado"):
        T.exigir_aprovado(f)
    T.aprovar(f, "artur", "gostei")
    assert T.exigir_aprovado(f)["comentario"] == "gostei"
    _png(f, 200)
    with pytest.raises(T.Travado, match="mudou depois"):
        T.exigir_aprovado(f)


def test_aprovado_pelo_revisor_nao_vale_como_artur(tmp_path):
    f = tmp_path / "x.png"
    _png(f)
    T.aprovar(f, "revisor")
    with pytest.raises(T.Travado, match="revisor"):
        T.exigir_aprovado(f)
    assert T.exigir_aprovado(f, quem="revisor")


def test_ab(tmp_path):
    with pytest.raises(T.Travado):
        T.exigir_ab(tmp_path)
    r = T.registrar_ab(tmp_path, "a.png", "b.png", "a", "b perdeu o rosto")
    assert r["fica"] == "a"
    assert len(json.loads((tmp_path / "ab.json").read_text(encoding="utf-8"))["rodadas"]) == 1
    with pytest.raises(ValueError):
        T.registrar_ab(tmp_path, "a", "b", "talvez")


def test_animar_recusa_vista_nao_aprovada(tmp_path):
    import asyncio
    from horys_pixel import mapa_partes as M
    from horys_pixel.ferramentas import registro
    from horys_pixel.ferramentas.registro import ErroFerramenta
    registro.carregar_todas()
    chamar = lambda nome, **a: asyncio.run(registro.REGISTRO[nome].funcao(None, a))
    v = np.zeros((8, 4, 4), np.uint8)
    v[0:3, 1:3] = (200, 150, 120, 255)
    v[3:8, 0:4] = (40, 60, 160, 255)
    Image.fromarray(v).save(tmp_path / "v.png")
    rot = M.mapa_regioes(v, [{"parte": "cabeca", "rect": [0, 0, 4, 3]}, {"parte": "tronco", "rect": [0, 3, 4, 8]}])
    Image.fromarray(M.pintar(rot)).save(tmp_path / "m.png")
    with pytest.raises(ErroFerramenta, match="TRAVADO"):
        chamar("horys_animar_tabela", vista=str(tmp_path / "v.png"), mapa=str(tmp_path / "m.png"), tabela="idle",
               saida=str(tmp_path / "o"))
    with pytest.raises(ErroFerramenta):
        chamar("horys_aprovar_arquivo", arquivo=str(tmp_path / "v.png"))      # sem id nem chat
    chamar("horys_aprovar_arquivo", arquivo=str(tmp_path / "v.png"), chat=True, comentario="ok, anima")
    r = chamar("horys_animar_tabela", vista=str(tmp_path / "v.png"), mapa=str(tmp_path / "m.png"), tabela="idle",
               saida=str(tmp_path / "o"))
    assert "4 quadros" in r[0]["text"]
