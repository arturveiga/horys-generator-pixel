"""Ferramentas de estilo com o Aseprite falso: asset_novo, pixel_map, contorno, portão, limpeza, marcação, medição.

A prova principal: uma .grade real do Artur entra no 'Aseprite' como camadas, o horys_portao exporta de volta e o
PNG da folha sai IDÊNTICO ao do grade.py rodado direto na .grade original.
"""
import asyncio
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from horys_pixel import config, grade_io
from test_nucleo import _ambiente, _txt, rodar

SRC = Path(__file__).resolve().parents[1] / "src"
GRADE_REAL = Path(r"D:\godot\games\hunvix\art-src\pixel-liso\construtor\v03\idle_base_v03.grade")
CONFIG_ARTUR = Path.home() / ".horys-pixel" / "motor-horys-pixel-liso.json"
ESTILO_ARTUR = Path.home() / ".horys-pixel" / "estilos" / "horys-pixel-liso" / "estilo.json"


def test_fluxo_estilo_exemplo(ambiente, tmp_path):
    async def corpo():
        ctx, ase, chamar, fim = await _ambiente(ambiente)
        try:
            r = await chamar("horys_estilos")
            assert "exemplo" in _txt(r)
            r = await chamar("horys_asset_novo", estilo="exemplo", nome="bloco", tipo="prop", quadro=64,
                             partes=["corpo", "topo"], estados=[{"nome": "idle", "quadros": 2, "ms": 100}],
                             pasta=str(tmp_path / "bloco"))
            assert not r["erro"], _txt(r)
            letras = json.loads(_txt(r).split("letras no horys_pixel_map): ")[1])
            nomes = [c["nome"] for c in ase.atual.camadas]
            assert nomes == ["sombra", "contorno", "corpo", "topo", "revisao"]
            assert ase.atual.camadas[0]["opacidade"] == 77 and not ase.atual.camadas[-1]["visivel"]
            assert ase.atual.tags == [{"nome": "idle", "de": 0, "ate": 1}]
            # desenha uma forma simples (pé no pivô (32, 42) do quadro 64)
            k = list(letras)
            linhas = [k[1] * 12] * 10 + [k[2] * 12] * 6
            for q in (0, 1):
                r = await chamar("horys_pixel_map", paleta={c: letras[c] for c in k[:3]}, linhas=linhas,
                                 x=26, y=27 + q, camada="corpo", quadro=q)
                assert not r["erro"], _txt(r)
            r = await chamar("horys_contorno")
            assert not r["erro"], _txt(r)
            cont = ase.atual.img("contorno", 0)
            assert (cont[..., 3] > 0).sum() > 40          # anel de 2 px em volta
            # (a elipse da sombra fica escondida sob um bloco largo; a real é conferida no teste de equivalência)
            r = await chamar("horys_portao")
            t = _txt(r)
            assert "PORTÃO" in t and "v01" in t, t
            v01 = tmp_path / "bloco" / "v01"
            assert (v01 / "idle.grade").exists() and list(v01.glob("*.png"))
            r = await chamar("horys_marcar", pontos=[[30, 30]], retangulos=[[26, 27, 12, 16]])
            assert not r["erro"] and ase.atual.camadas[-1]["visivel"]
            r = await chamar("horys_medir_arquivo", estilo="exemplo")
            assert not r["erro"], _txt(r)
            r = await chamar("horys_limpar", camada="corpo", quadro=0, min=2)
            assert not r["erro"], _txt(r)
            r = await chamar("horys_afinar", camada="corpo", quadro=0)
            assert not r["erro"], _txt(r)
            r = await chamar("horys_paleta_estilo", verificar=True)
            assert "todas as cores" in _txt(r), _txt(r)
        finally:
            await fim()
    rodar(corpo())


@pytest.mark.skipif(not (GRADE_REAL.exists() and CONFIG_ARTUR.exists() and ESTILO_ARTUR.exists()),
                    reason="precisa da .grade real e do pacote do Artur")
def test_equivalencia_portao_com_grade_real(ambiente, tmp_path, monkeypatch):
    """A .grade real vira camadas no Aseprite falso; o portão reexporta; a folha tem que ser idêntica."""
    # o pacote do Artur mora em ~/.horys-pixel; o teste usa HORYS_HOME temporário: copia o pacote para lá
    destino = Path(os.environ["HORYS_HOME"]) / "estilos" / "horys-pixel-liso"
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ESTILO_ARTUR.parent, destino)
    from horys_pixel.motor import grade as G
    meta, cores, quadros, erros = G.ler(str(GRADE_REAL))
    assert not erros
    Q = meta["quadro"]
    # referência: grade.py direto na .grade original
    ref = tmp_path / "ref"
    env = dict(os.environ, PYTHONPATH=str(SRC), HORYS_MOTOR_CONFIG=str(CONFIG_ARTUR), PYTHONIOENCODING="utf-8")
    subprocess.run([sys.executable, "-m", "horys_pixel.motor.grade", "gerar", str(GRADE_REAL), "--saida", str(ref)],
                   env=env, capture_output=True)
    png_ref = ref / f"{meta['nome']}_{meta['estado']}.png"
    assert png_ref.exists(), list(ref.iterdir())

    async def corpo():
        ctx, ase, chamar, fim = await _ambiente(ambiente)
        try:
            partes = meta.get("camadas") or ["desenho"]
            r = await chamar("horys_asset_novo", estilo="horys-pixel-liso", nome=meta["nome"], tipo=meta["tipo"],
                             quadro=Q, partes=partes, contorno=meta["contorno"], sombra=meta["sombra"] == "sim",
                             estados=[{"nome": meta["estado"], "quadros": len(quadros), "ms": meta["ms"]}],
                             pasta=str(tmp_path / "novo"),
                             **({"cor_contorno": meta["cor_contorno"]} if meta.get("cor_contorno") else {}))
            assert not r["erro"], _txt(r)
            for k, q in enumerate(quadros):
                img, _ = G.montar(meta, cores, q)
                for nome, im, _op in G.camadas_rgba(meta, cores, q, img)[2:] if "camadas" in q else \
                        [("desenho", None, 255)]:
                    if im is None:   # sem camadas: as letras inteiras numa camada
                        im = grade_io.rgba_de_letras(q["linhas"], cores, Q, meta["pivo"])
                    ase.atual.img(nome, k)[:] = im
            r = await chamar("horys_portao")
            assert "PORTÃO" in _txt(r), _txt(r)
        finally:
            await fim()
    rodar(corpo())
    novo = tmp_path / "novo" / "v01" / f"{meta['nome']}_{meta['estado']}.png"
    assert novo.exists(), list((tmp_path / "novo" / "v01").iterdir())
    a = np.array(Image.open(png_ref).convert("RGBA"))
    b = np.array(Image.open(novo).convert("RGBA"))
    assert a.shape == b.shape and np.array_equal(a, b), "a folha reexportada do Aseprite difere da original"
