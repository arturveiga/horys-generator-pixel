"""Pipeline Blender (perfeicao.md §14): paleta (passo 0), pós-render, recolor e o render de ponta a ponta no robô."""
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from horys_pixel.blender import paleta as BP
from horys_pixel.blender import pos

ROBO_BLEND = Path("C:/Users/artur/Documents/Codex/2026-11-14/veja-o-perfeicao-md/outputs/Robo-suavizado.blend")
ROBO_CFG = Path(__file__).resolve().parents[1] / "art-src" / "robo" / "blender" / "robo.json"


def test_rampa_mantem_a_base_e_vai_do_escuro_ao_claro():
    from horys_pixel import paleta_ops as PO
    r3 = BP.rampa_material("#2c4fc7", 3)
    assert r3[1] == "#2c4fc7" and len(r3) == 3
    assert PO.luminancia(r3[0]) < PO.luminancia(r3[1]) < PO.luminancia(r3[2])
    r2 = BP.rampa_material("#c9a050", 2)
    assert r2[1] == "#c9a050" and PO.luminancia(r2[0]) < PO.luminancia(r2[1])


def test_montar_paleta_confere_limites():
    fams = [{"nome": f"f{i}", "base": b, "tons": 3} for i, b in
            enumerate(["#2c4fc7", "#c9b4b4", "#3c3d62", "#c9a050", "#8a5cd0", "#3fbf5f", "#bf3f3f"])]
    pal = BP.montar(fams)
    assert len(pal["cores"]) == 22
    assert any("máximo 20" in a for a in pal["avisos"])
    assert pal["tinta"] in pal["cores"]
    pal2 = BP.montar([{"nome": "luz", "tipo": "emissivo", "rampa": ["#3fe6ee"]}, {"nome": "a", "base": "#2c4fc7"}],
                     tinta="#131a33")
    assert pal2["familias"]["luz"]["rampa"] == ["#3fe6ee"] and not [a for a in pal2["avisos"] if "máximo" in a]


def test_propor_ignora_o_fundo():
    im = np.zeros((40, 40, 3), np.uint8)
    im[:] = (200, 200, 205)
    im[10:30, 10:30] = (40, 70, 200)
    im[15:20, 15:20] = (240, 220, 150)
    prop = BP.propor(im, 2)
    assert {p["base"] for p in prop} == {"#2846c8", "#f0dc96"}


def test_duracoes_somam_o_tempo():
    ms = pos.duracoes(8, 6)
    assert sum(ms) == 1330 and all(m % 10 == 0 for m in ms)
    assert pos.duracoes(3, 12) == [80, 90, 80]


def test_limpar_soltos_e_contorno():
    fam = ["a", "a", "b", "_tinta"]
    idx = np.full((7, 7), -1)
    idx[1:6, 1:6] = 0
    idx[3, 3] = 1          # tom isolado da mesma família
    out, n = pos.limpar_soltos(idx, fam, set(), tinta=3)
    assert n == 1 and out[3, 3] == 0
    idx[3, 3] = 2          # outra família: precisa de 6 vizinhos (tem 8)
    out, n = pos.limpar_soltos(idx, fam, {2}, tinta=3)
    assert out[3, 3] == 0
    c = pos.contorno(out, 3, "fora")
    assert c[0, 3] == 3 and c[0, 0] == -1 and c[1, 1] == 0
    d = pos.contorno(out, 3, "dentro")
    assert d[1, 3] == 3 and d[0, 3] == -1


def test_mapa_recolor_por_posicao_na_rampa():
    velha = {"familias": {"azul": {"rampa": ["#000011", "#000022", "#000033"]}}, "tinta": "#010101"}
    nova = {"familias": {"azul": {"rampa": ["#110000", "#000022", "#330000"]}}, "tinta": "#020202"}
    assert pos.mapa_recolor(velha, nova) == {"#000011": "#110000", "#000033": "#330000", "#010101": "#020202"}


def test_render_exige_paleta_aprovada(tmp_path):
    import asyncio
    from horys_pixel.ferramentas import registro
    from horys_pixel.ferramentas.registro import ErroFerramenta
    registro.carregar_todas()
    pal = BP.montar([{"nome": "a", "base": "#2c4fc7"}])
    (tmp_path / "paleta.json").write_text(json.dumps(pal), encoding="utf-8")
    cfg = {"blend": "x.blend", "paleta": "paleta.json", "rig": {}, "papeis": {}, "camera": {}}
    (tmp_path / "c.json").write_text(json.dumps(cfg), encoding="utf-8")
    with pytest.raises(ErroFerramenta, match="TRAVADO"):
        asyncio.run(registro.REGISTRO["horys_blender_render"].funcao(None, {"config": str(tmp_path / "c.json"),
                                                                             "saida": str(tmp_path / "o")}))


@pytest.mark.skipif(not ROBO_BLEND.exists() or not ROBO_CFG.exists(), reason="sem o .blend do robô")
def test_render_previa_do_robo_de_ponta_a_ponta(tmp_path):
    from horys_pixel import blender as B
    if not B.achar_blender():
        pytest.skip("sem Blender")
    cfg = B.ler_config(ROBO_CFG)
    cfg["acoes"] = {"andar": {"tipo": "andar", "quadros": 8, "fps": 6}}
    cfg["direcoes"] = {"sul": 0, "leste": 90}
    cfg["camera"] = {**cfg["camera"], "quadro": 64, "altura_px": 44}
    pal = json.loads(Path(cfg["paleta"]).read_text(encoding="utf-8"))
    r = B.rodar(cfg, pal, tmp_path, previa=True)
    assert r["ok"], r["log"]
    rel = pos.processar(tmp_path, pal, cfg)
    sul = np.asarray(Image.open(tmp_path / "andar_sul.png").convert("RGBA"))
    cores = {"#%02x%02x%02x" % tuple(c[:3]) for c in sul.reshape(-1, 4) if c[3]}
    assert cores <= set(pal["cores"])                       # nenhuma cor fora da paleta
    assert set(np.unique(sul[..., 3])) <= {0, 255}          # alfa binário
    assert rel["acoes"]["andar_sul"]["pe_linha"][1] < 64    # o pé não sai do quadro
    partes = list((tmp_path / "partes" / "andar").glob("sul_*.png"))
    assert partes
