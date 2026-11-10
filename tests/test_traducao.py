from horys_pixel import padroes, traducao

PALETA = {"rampas": {"pelo": ["#3f3c56", "#55556e", "#72768d"], "pedra": ["#616177", "#918fa7", "#c3bdaf"]},
          "contorno": "#18122c", "brilho": "#fdbe45"}


def test_prompt_traducao_parado(tmp_path):
    r = traducao.escrever(tmp_path, tipo="boss", descricao="gorila de pedra", paleta=PALETA, nome_estilo="golem",
                          altura=198, referencia=str(tmp_path / "macaco.png"), referencia_propria=False)
    t = r["texto"]
    for i in range(1, 12):
        assert f"\n{i}. " in t or f"\n 1{i-10}. " in t or f"{i}. " in t
    for h in traducao.todos_hex(PALETA):
        assert h in t
    assert "2%" in t and "só se a imagem for sua" in t
    assert (tmp_path / "traducao" / "paleta-golem.png").exists()


def test_prompt_traducao_poses(tmp_path):
    t = traducao.gerar("boss", "gorila", PALETA, altura=198, modo="poses", poses=["contato", "passagem"],
                       base_aprovada="v19.png")
    assert "1. contato" in t and "2. passagem" in t and "v19.png" in t and "grade 1×2" in t


def test_padroes_detalhe_em_pixels():
    p = padroes.carregar("personagem")
    assert round(padroes.detalhe_min_px(p, 70)) == 3


def test_revisor_classe_e_estado_de_entrega():
    from horys_pixel import entrega
    js = {"aceitacao": 85, "redesenhar_forma": False, "criterios": [
        {"id": "L3", "resultado": "falha", "severidade": "leve", "classe": "acabamento"},
        {"id": "L2", "resultado": "passa", "severidade": "grave"}]}
    r = entrega.avaliar(js)
    assert r["pronto"] and len(r["acabamento"]) == 1 and not r["estruturais"]
    js["criterios"].append({"id": "L1", "resultado": "falha", "severidade": "grave", "classe": "estrutural"})
    assert not entrega.avaliar(js)["pronto"]
    assert not entrega.avaliar({"aceitacao": 90, "redesenhar_forma": True, "criterios": []})["pronto"]
    assert not entrega.avaliar({"aceitacao": 70, "criterios": []})["pronto"]


def test_padroes_carregam_e_validam():
    for t in padroes.TIPOS:
        p = padroes.carregar(t)
        assert padroes.validar(p) == [], (t, padroes.validar(p))
        lo, hi = p["altura_alvo"]
        assert 0 < lo <= hi, t
        # detalhe_min_frac = px mínimo ÷ altura alvo: no alvo mínimo dá pelo menos ~1 px
        assert padroes.detalhe_min_px(p, lo) >= 0.9, t
    assert padroes.tipo_de("npc") == "personagem" and padroes.tipo_de("xyz") is None


def test_prompt_poses_grade_cabe_todas_e_subpaleta():
    from horys_pixel import traducao
    assert traducao.layout_poses(6, [1, 2]) == (2, 3)
    assert traducao.layout_poses(2, [1, 2]) == (1, 2)
    assert traducao.layout_poses(8, [1, 2]) == (2, 4)
    pal = {"rampas": {"pedra": ["#111111", "#222222", "#333333"], "fogo": ["#aa0000", "#ff0000"],
                      "agua": ["#0000aa", "#0000ff", "#00ffff"]}, "contorno": "#000000"}
    sub = traducao.subpaleta(pal, ["pedra", "fogo"])
    assert list(sub["rampas"]) == ["pedra", "fogo"] and "#0000ff" not in traducao.todos_hex(sub)
    import pytest
    with pytest.raises(ValueError):
        traducao.subpaleta(pal, ["lava"])


def test_subpaleta_aceita_texto():
    from horys_pixel import traducao
    pal = {"rampas": {"pedra lilás": ["#111111"], "fogo": ["#aa0000"], "agua": ["#0000aa"]}, "contorno": "#000000"}
    assert list(traducao.subpaleta(pal, '["pedra lilás", "fogo"]')["rampas"]) == ["pedra lilás", "fogo"]
    assert list(traducao.subpaleta(pal, "pedra lilás, fogo")["rampas"]) == ["pedra lilás", "fogo"]
