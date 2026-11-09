"""Ponte SpriteKiln: leitura do atlas, filtro, paleta, limpeza sem boil e importação no Aseprite falso."""
import json

import numpy as np
import pytest
from PIL import Image

from horys_pixel import kiln
from test_nucleo import _ambiente, _txt, rodar

VERM = (200, 60, 60, 255)
AZUL = (60, 60, 200, 255)


def _atlas(tmp_path, n_idle=2, n_atk=1, lado=8, dirs=("e",)):
    """Atlas sintético no formato do `spritekiln render`: uma linha por clipe, quadros lado a lado."""
    clipes = [("idle", n_idle), ("attack", n_atk)]
    linhas = [(c, d, n) for c, n in clipes for d in dirs]
    larg = max(n for _, _, n in linhas) * lado
    at = np.zeros((len(linhas) * lado, larg, 4), np.uint8)
    frames, tags, anims, k = {}, [], {}, 0
    for row, (c, d, n) in enumerate(linhas):
        nomes = []
        for i in range(n):
            x, y = i * lado, row * lado
            at[y + 1:y + 1 + i + 2, x + 2:x + 4] = VERM if c == "idle" else AZUL   # muda a cada quadro
            nome = f"{c}_{d}_{i}"
            frames[nome] = {"frame": {"x": x, "y": y, "w": lado, "h": lado}, "duration": 100 + 10 * i}
            nomes.append(nome)
        tags.append({"name": f"{c}_{d}", "from": k, "to": k + n - 1, "direction": "forward"})
        anims.setdefault(c, {"loop": c == "idle", "directions": {}})["directions"][d] = {
            "row": row, "frames": nomes, "events": {"0": ["hit"]} if c == "attack" else {}}
        k += n
    Image.fromarray(at, "RGBA").save(tmp_path / "boneco.png")
    d = {"frames": frames, "meta": {"app": "spritekiln", "image": "boneco.png", "frameTags": tags},
         "spritekiln": {"name": "boneco", "frame_size": lado, "pivot": {"x": 4, "y": 7}, "animations": anims}}
    p = tmp_path / "boneco.json"
    p.write_text(json.dumps(d), encoding="utf-8")
    return p, at


def test_ler_atlas_sintetico(tmp_path):
    p, at = _atlas(tmp_path)
    a = kiln.ler_atlas(p)
    assert len(a.quadros) == 3 and a.tamanho == (8, 8)
    assert a.duracoes_ms == [100, 110, 100]
    assert a.tags == [("idle_e", 0, 1), ("attack_e", 2, 2)]
    assert np.array_equal(a.quadros[1], at[0:8, 8:16])
    assert a.eventos == {2: ["hit"]} and a.pivo == (4.0, 7.0) and len(a.sha256) == 64


def test_filtrar_direcao_e_tags(tmp_path):
    p, _ = _atlas(tmp_path, dirs=("e", "w"))
    a = kiln.ler_atlas(p)
    assert kiln.direcoes(a) == ["e", "w"]
    f = kiln.filtrar(a, direcao="w")
    assert [t[0] for t in f.tags] == ["idle", "attack"] and len(f.quadros) == 3
    f = kiln.filtrar(a, tags=["attack"], direcao="e")
    assert f.tags == [("attack", 0, 0)] and f.eventos == {0: ["hit"]}
    with pytest.raises(ValueError, match="direção"):
        kiln.filtrar(a, direcao="n")
    with pytest.raises(ValueError, match="run"):
        kiln.filtrar(a, tags=["run"])


def test_rampas_do_estilo_padrao():
    pal = json.loads(open(kiln.Path(kiln.__file__).parent / "motor" / "paleta_padrao.json", encoding="utf-8").read())
    r = kiln.rampas_do_estilo(pal)
    todas = {c.lower() for v in pal["rampas"].values() for c in v}
    assert "contorno" not in r and "brilho" not in r and r
    for cores in r.values():
        assert cores[0] == pal["contorno"].lower() and set(cores) <= todas
    assert kiln.yaml_paleta_kiln(pal).splitlines()[1] == "ramps:"


def test_limpar_quadro_funde_mancha_pequena():
    q = np.zeros((6, 6, 4), np.uint8)
    q[:, :] = VERM
    q[2, 2] = AZUL                                    # órfão
    out = kiln.limpar_quadro(q, 3)
    assert tuple(out[2, 2]) == VERM
    assert tuple(kiln.limpar_quadro(q, 3, {AZUL[:3]})[2, 2]) == AZUL   # protegido


def test_limpar_sequencia_sem_boil():
    base = np.zeros((8, 8, 4), np.uint8)
    base[:, :4] = VERM
    base[:, 4:] = AZUL
    base[3, 3] = AZUL   # pixel na fronteira: a decisão de limpeza poderia oscilar entre quadros
    qs = [base.copy() for _ in range(3)]
    qs[1][7, 7] = VERM  # muda só um canto longe
    out = kiln.limpar_sequencia(qs, 3)
    parado = np.all(qs[0] == qs[2], axis=-1)
    assert np.array_equal(out[0][parado], out[2][parado])
    assert np.array_equal(out[0][3, 3], out[1][3, 3])


def test_distribuir_posse_unica():
    comp = np.zeros((4, 4, 4), np.uint8)
    comp[:, :] = VERM
    m = {"topo": np.zeros((4, 4), bool)}
    m["topo"][0:2] = True
    d = kiln.distribuir(comp, m, ["base", "topo"])
    assert (d["base"][..., 3] > 0).sum() == 8 and (d["topo"][..., 3] > 0).sum() == 8
    assert not ((d["base"][..., 3] > 0) & (d["topo"][..., 3] > 0)).any()


def test_preencher_ocultos_mantem_composto_e_respeita_limite():
    base = np.zeros((9, 9, 4), np.uint8)
    topo = np.zeros_like(base)
    base[4, 1:4] = VERM
    topo[3:6, 4:8] = AZUL
    isolada = np.zeros_like(base)
    isolada[4, 1:9] = VERM
    antes = kiln.distribuir(base + topo, {"topo": topo[..., 3] > 0}, ["base", "topo"])
    cheio = kiln.preencher_ocultos(antes, {"base": isolada}, ["base", "topo"], 2)
    # Só dois pixels entram sob o topo; o terceiro está além do limite.
    assert cheio["base"][4, 4:6, 3].tolist() == [255, 255]
    assert cheio["base"][4, 6, 3] == 0
    from horys_pixel import partes as P
    assert np.array_equal(P.compor(antes, ["base", "topo"]), P.compor(cheio, ["base", "topo"]))


def test_preencher_ocultos_limite_por_parte():
    baixo = np.zeros((5, 7, 4), np.uint8)
    cima = np.zeros_like(baixo)
    baixo[2, 1] = VERM
    cima[1:4, 2:6] = AZUL
    iso = np.zeros_like(baixo)
    iso[2, 1:6] = VERM
    out = kiln.preencher_ocultos({"baixo": baixo, "cima": cima}, {"baixo": iso}, ["baixo", "cima"], {"baixo": 1})
    assert out["baixo"][2, 2, 3] == 255 and out["baixo"][2, 3, 3] == 0


def test_preencher_ocultos_completa_junta_que_o_render_termina_rente():
    baixo = np.zeros((5, 7, 4), np.uint8)
    cima = np.zeros_like(baixo)
    baixo[2, 1:3] = VERM
    cima[1:4, 3:6] = AZUL
    # O render isolado também termina rente, mas a junta precisa continuar sob a camada móvel.
    out = kiln.preencher_ocultos({"baixo": baixo, "cima": cima}, {"baixo": baixo.copy()},
                                 ["baixo", "cima"], 2)
    assert np.all(out["baixo"][2, 3:5] == VERM)


def test_importar_kiln_no_falso(ambiente, tmp_path):
    p, at = _atlas(tmp_path)

    async def corpo():
        ctx, ase, chamar, fim = await _ambiente(ambiente)
        try:
            r = await chamar("horys_asset_novo", estilo="exemplo", nome="boneco", tipo="prop", quadro=8,
                             modular=True, partes=["base", "topo"],
                             juncoes=[{"nome": "j", "inferior": "base", "superior": "topo", "movel": "topo"}],
                             contorno="nenhum", pasta=str(tmp_path / "b"),
                             estados=[{"nome": "idle", "quadros": 1, "ms": 100}])
            assert not r["erro"], _txt(r)
            r = await chamar("horys_importar_kiln", json=str(p))
            assert not r["erro"], _txt(r)
            s = ase.atual
            assert len(s.quadros) == 3 and [q["ms"] for q in s.quadros] == [100, 110, 100]
            assert np.array_equal(s.img("referencia", 1), at[0:8, 8:16])
            assert {"nome": "attack", "de": 2, "ate": 2} in s.tags
            assert sum(t["nome"] == "idle" for t in s.tags) == 1
            f = ctx.ficha(s.arquivo)
            assert f["kiln"]["sha256"] and f["kiln"]["tags"] == ["idle", "attack"]
        finally:
            await fim()
    rodar(corpo())


def test_importar_kiln_tamanho_errado(ambiente, tmp_path):
    p, _ = _atlas(tmp_path, lado=8)

    async def corpo():
        ctx, ase, chamar, fim = await _ambiente(ambiente)
        try:
            r = await chamar("horys_asset_novo", estilo="exemplo", nome="b", tipo="prop", quadro=16,
                             modular=True, partes=["base", "topo"],
                             juncoes=[{"nome": "j", "inferior": "base", "superior": "topo", "movel": "topo"}],
                             contorno="nenhum", pasta=str(tmp_path / "b"))
            assert not r["erro"], _txt(r)
            r = await chamar("horys_importar_kiln", json=str(p))
            assert r["erro"] and "8x8" in _txt(r)
        finally:
            await fim()
    rodar(corpo())


def test_paleta_kiln_grava_yaml(ambiente, tmp_path):
    async def corpo():
        ctx, ase, chamar, fim = await _ambiente(ambiente)
        try:
            r = await chamar("horys_paleta_kiln", estilo="exemplo", destino=str(tmp_path / "pal.yaml"))
            assert not r["erro"], _txt(r)
            assert (tmp_path / "pal.yaml").read_text(encoding="utf-8").splitlines()[1] == "ramps:"
        finally:
            await fim()
    rodar(corpo())


def test_mascaras_por_parte_no_spritekiln_real():
    """Só roda com o spritekiln 0.3.x instalado (venv do uv/pipx ou HORYS_KILN_PYTHON) e o spec de teste local."""
    import subprocess
    py = kiln.python_do_kiln()
    if subprocess.run([py, "-c", "import spritekiln"], capture_output=True).returncode != 0:
        pytest.skip("spritekiln não instalado")
    spec = kiln.Path(__file__).resolve().parents[1] / "tmp-kiln/art/specs/characters/aldeao/aldeao_horys.yaml"
    if not spec.exists():
        pytest.skip("spec de teste local ausente (tmp-kiln)")
    ms, nomes = kiln.mascaras_por_parte(spec, "idle", [0], "e",
                                        {"corpo": ["torso", "coat", "belt", "neck"], "cabeca": ["head", "hair"]})
    assert "torso" in nomes
    a, b = ms[0]["corpo"], ms[0]["cabeca"]
    assert a.any() and b.any() and not (a & b).any()
