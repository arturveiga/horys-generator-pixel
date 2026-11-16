"""Guia de pose do SpriteKiln (horys_pixel.guia_kiln): classificação pura, spec derivada, encaixe e render real."""
from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from horys_pixel import guia_kiln as G
from horys_pixel import mapa_partes as M

RAIZ = Path(__file__).resolve().parents[1]
SPEC_PIRATA = RAIZ / "art/specs/characters/pirata_anchor_test/pirata_anchor_test.yaml"

PAIS = {"torso_rot": "root", "pelvis": "torso_rot", "head": "pelvis", "shoulder_L": "pelvis",
        "hip_L": "pelvis", "sole_L": "root", "sword": "wrist_R", "sword_edge": "sword"}
IK = {"arm_L": {"start": "shoulder_L", "joint": "elbow_L", "end": "wrist_L"},
      "arm_R": {"start": "shoulder_R", "joint": "elbow_R", "end": "wrist_R"},
      "leg_L": {"start": "hip_L", "joint": "knee_L", "end": "ankle_L"}}


@pytest.mark.parametrize("nome,esperado", [
    ("arm_L", "braco-dir"), ("hand_R", "braco-esq"), ("forearm_L", "braco-dir"),
    ("leg_R", "perna-esq"), ("boot_L", "perna-dir"), ("torso", "tronco"), ("belt", "tronco"), ("hip", "tronco"),
    ("head", "cabeca"), ("eye_L", "cabeca"), ("headband", "cabeca"), ("neck", "cabeca"),
    ("hair_lock_L", "enfeite"), ("bandana_tail", "enfeite"), ("horn_L", "enfeite"), ("cape", "enfeite"),
    ("sword_blade", "arma"), ("sword_grip", "arma"), ("staff", "arma"), ("smear", "arma"),
    ("bracoEsquerdo", "braco-dir"), ("espada", "arma"),
])
def test_classificar_pelo_nome(nome, esperado):
    assert G.classificar(nome)[0] == esperado


def test_classificar_pelos_ossos_e_ik():
    # sem pista no nome: o espaço (wrist_R é o fim da cadeia arm_R) decide categoria e lado
    assert G.classificar("torch", "wrist_R", (), PAIS, IK)[0] == "braco-esq"
    # primitiva que cita @elbow_L
    assert G.classificar("gem", None, ["elbow_L"], PAIS, IK)[0] == "braco-dir"
    # cadeia de pais: sword_edge -> sword
    assert G.classificar("thing", "sword_edge", (), PAIS, IK)[0] == "arma"
    assert G.classificar("pad", "sole_L", (), PAIS, IK)[0] == "perna-dir"
    c, motivo = G.classificar("xyz")
    assert c == "tronco" and "sem pista" in motivo


def test_materiais_guia_lados_opostos_e_cores_do_contrato():
    mats = G.materiais_guia()
    cores = {"#%02x%02x%02x" % c for c in M.CORES.values()}
    for m in mats.values():
        assert m["ramp"][0] == m["ramp"][1] and m["ramp"][0] in cores
        assert m["emissive"] and m["outline"] is False and m["line"] is False
    hexa = lambda n: "#%02x%02x%02x" % M.CORES[n]
    assert mats["guia_braco_dir_L"]["ramp"][0] == hexa("braco-dir")
    assert mats["guia_braco_dir_R"]["ramp"][0] == hexa("braco-esq")   # a gêmea do _L troca de lado
    assert mats["guia_perna_esq_R"]["ramp"][0] == hexa("perna-dir")


def _info():
    parts = {
        "torso": {"material": "cloth", "space": "pelvis", "refs": []},
        "arm_L": {"material": "cloth", "refs": ["shoulder_L", "elbow_L"], "paint": True},
        "arm_R": {"material": "cloth", "refs": ["shoulder_R", "elbow_R"], "mirror": True},
        "smear": {"materials": 3, "space": "fxspace", "refs": []},
        "hair": {"material": "hair", "space": "head", "refs": []},
        "torch": {"material": "wood", "space": "wrist_R", "refs": []},
    }
    return {"parts": parts, "bones": PAIS, "ik": IK, "ramps": {"cloth": ["#000000", "#111111"]},
            "header": {"name": "x", "size": 32, "camera": {"pitch": 38, "scale": 0.07},
                       "render": {"snap": True, "outline": "dark"}}}


def test_montar_spec_derivada(tmp_path):
    orig = tmp_path / "x.yaml"
    orig.write_text("spritekiln: 1\n")
    g = G.montar_spec(orig, _info())
    sp = g["spec"]
    assert sp["extends"] == orig.resolve().as_posix() and sp["name"] == "x_guia"
    assert sp["mirror"] is False and sp["shadow"]["alpha"] == 0
    assert sp["render"] == {"outline": "none", "shading": "flat", "lines": "none", "highlights": False,
                            "dither": "none", "snap": True}
    assert sp["parts"]["arm_L"] == {"material": "guia_braco_dir_L", "paint": []}
    assert "arm_R" not in sp["parts"]                     # gêmea: segue a _L pelo espelhamento
    assert sp["parts"]["smear"] == {"materials": ["guia_arma"] * 3}
    assert g["partes"]["arm_R"] == "braco-esq" and g["partes"]["torch"] == "braco-esq"
    assert g["partes"]["hair"] == "enfeite"
    texto = G.spec_yaml(sp)
    assert texto.startswith("spritekiln: 1\n")
    assert 'camera:\n  "pitch": 38\n  "scale": 0.07\n' in texto
    assert 'extends: "' in texto and "mirror: false" in texto


def test_mapeamento_vence_e_gemea_troca_de_lado(tmp_path):
    orig = tmp_path / "x.yaml"
    orig.write_text("spritekiln: 1\n")
    g = G.montar_spec(orig, _info(), {"arm_L": "braco-esq", "hair": "cabeca", "arm_R": "arma", "nada": "arma"})
    assert g["spec"]["parts"]["arm_L"]["material"] == "guia_braco_esq_L"
    assert g["partes"]["arm_R"] == "braco-dir"
    assert g["spec"]["parts"]["hair"]["material"] == "guia_cabeca"
    assert any("gêmea" in a for a in g["avisos"]) and any("não existe" in a for a in g["avisos"])
    with pytest.raises(ValueError):
        G.montar_spec(orig, _info(), {"torso": "pescoço"})


def test_encaixar_e_rotulos():
    q = np.zeros((4, 4, 4), np.uint8)
    q[0, 0] = (10, 250, 240, 255)        # quase ciano
    q[1, 1] = (250, 135, 5, 200)         # quase laranja
    q[2, 2] = (90, 90, 90, 255)          # longe de tudo
    q[3, 3] = (255, 0, 0, 60)            # alfa baixo: some
    out, fora = G.encaixar(q)
    assert tuple(out[0, 0]) == (*M.CORES["cabeca"], 255)
    assert tuple(out[1, 1]) == (*M.CORES["tronco"], 255)
    assert out[3, 3, 3] == 0 and fora == 1
    rot = M.rotulos(out)
    assert (rot >= 0).all() and (rot[out[..., 3] > 0] > 0).all()


# ------------------------------------------------------------------ render real (precisa do spritekiln)

precisa_kiln = pytest.mark.skipif(not (G.spritekiln_disponivel() and SPEC_PIRATA.is_file()),
                                  reason="spritekiln não instalado ou spec de teste ausente")


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


@precisa_kiln
def test_render_real_humanoide(tmp_path):
    antes = _sha(SPEC_PIRATA)
    r = G.renderizar(SPEC_PIRATA, tmp_path / "guia", anims=["idle"], dirs="s,e,n")
    assert _sha(SPEC_PIRATA) == antes                     # original intacta
    assert Path(r["spec_guia"]).is_relative_to(tmp_path)  # spec derivada e render só na pasta de saída
    idx = json.loads((tmp_path / "guia" / "guia.json").read_text(encoding="utf-8"))
    assert set(idx["animacoes"]["idle"]) == {"s", "e", "n"}
    assert r["fora_do_contrato"] == 0                     # o render já sai chapado
    q = np.array(Image.open(tmp_path / "guia" / "idle_s_00.png").convert("RGBA"))
    rot = M.rotulos(q)
    op = q[..., 3] > 0
    assert (rot[op] > 0).all()                            # todo pixel opaco é uma parte do contrato
    presentes = {M.NOMES[i - 1] for i in np.unique(rot[op])}
    assert {"cabeca", "tronco", "braco-esq", "braco-dir", "perna-esq", "perna-dir"} <= presentes
    # convenção: na vista de frente, braco-dir (parte _L do spec) fica à direita da imagem
    xs = lambda n: np.nonzero(rot == M.NOMES.index(n) + 1)[1].mean()
    assert xs("braco-dir") > xs("braco-esq") and xs("perna-dir") > xs("perna-esq")
    # costas: os lados trocam na imagem, a cor fica presa à parte
    qn = M.rotulos(np.array(Image.open(tmp_path / "guia" / "idle_n_00.png").convert("RGBA")))
    xn = lambda n: np.nonzero(qn == M.NOMES.index(n) + 1)[1].mean()
    assert xn("braco-dir") < xn("braco-esq")


@precisa_kiln
def test_ferramenta_guia_kiln(tmp_path):
    from horys_pixel.ferramentas import guia_kiln as _  # noqa: F401  (registra)
    from horys_pixel.ferramentas import registro
    out = asyncio.run(registro.REGISTRO["horys_guia_kiln"].funcao(
        None, {"spec": str(SPEC_PIRATA), "saida": str(tmp_path / "g"), "anims": ["idle"], "dirs": ["s"]}))
    assert out[0]["type"] == "text" and "quadros" in out[0]["text"]
    assert out[1]["type"] == "image"
    assert (tmp_path / "g" / "idle_s_00.png").is_file()
    with pytest.raises(registro.ErroFerramenta):
        asyncio.run(registro.REGISTRO["horys_guia_kiln"].funcao(None, {"spec": "nao/existe.yaml", "saida": "x"}))
