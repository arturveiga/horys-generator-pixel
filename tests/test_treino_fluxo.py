"""Fluxo configurar → treinar → avaliar → notas → promover → gerar, com um sd-scripts FALSO.

Os scripts falsos (train_network.py, gen_img.py) só leem os argumentos e escrevem arquivos; nada de GPU ou rede.
"""

import hashlib
import json
import sys
import textwrap
import tomllib

import numpy as np
import pytest
from PIL import Image

from horys_pixel.treino import ErroTreino, avaliar, config, conjunto, de_pasta, executar, gerar, kohya, perfis

TREINO_FALSO = textwrap.dedent('''
    import argparse, pathlib, tomllib
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset_config"); ap.add_argument("--config_file")
    a = ap.parse_args()
    cfg = tomllib.loads(pathlib.Path(a.config_file).read_text(encoding="utf-8"))
    ds = tomllib.loads(pathlib.Path(a.dataset_config).read_text(encoding="utf-8"))
    saida = cfg["saida"]
    print("passos: ok", ds["datasets"][0]["resolution"])
    pathlib.Path(saida["output_dir"], saida["output_name"] + ".safetensors").write_bytes(b"lora")
''')

GERACAO_FALSA = textwrap.dedent('''
    import argparse, pathlib, zlib
    from PIL import Image
    ap = argparse.ArgumentParser()
    for opt in ["--ckpt", "--outdir", "--from_file", "--images_per_prompt", "--sampler", "--steps", "--scale",
                "--W", "--H", "--batch_size", "--network_module", "--network_weights", "--network_mul"]:
        ap.add_argument(opt)
    for flag in ["--sequential_file_name", "--sdpa", "--fp16", "--bf16", "--sdxl", "--no_half_vae"]:
        ap.add_argument(flag, action="store_true")
    a = ap.parse_args()
    linhas = [l for l in pathlib.Path(a.from_file).read_text(encoding="utf-8").splitlines() if l.strip()]
    out = pathlib.Path(a.outdir); out.mkdir(parents=True, exist_ok=True)
    for i, l in enumerate(linhas, 1):
        cor = zlib.crc32((l + str(a.network_weights)).encode()) & 0xFFFFFF
        Image.new("RGB", (int(a.W), int(a.H)), (cor >> 16, (cor >> 8) & 255, cor & 255)).save(out / f"im_{i:06d}.png")
''')


@pytest.fixture
def kohya_falso(tmp_path, monkeypatch):
    monkeypatch.setenv("HORYS_PIXEL_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("HORYS_KOHYA_DIR", raising=False)
    repo = kohya.pasta_repo()
    repo.mkdir(parents=True)
    (repo / "train_network.py").write_text(TREINO_FALSO, encoding="utf-8")
    (repo / "sdxl_train_network.py").write_text(TREINO_FALSO, encoding="utf-8")
    (repo / "gen_img.py").write_text(GERACAO_FALSA, encoding="utf-8")
    return repo


@pytest.fixture
def estilo(tmp_path):
    raiz = tmp_path / "meu-estilo"
    aprov = raiz / "gosto" / "aprovados"
    aprov.mkdir(parents=True)
    for i, cor in enumerate([(200, 40, 50), (40, 60, 200), (30, 160, 60)]):
        a = np.zeros((16, 16, 4), np.uint8)
        a[3:13, 4:12] = (*cor, 255)
        a[5 + i, 6] = (10, 10, 10, 255)
        Image.fromarray(a, "RGBA").save(aprov / f"s{i}.png")
        (aprov / f"s{i}.json").write_text(json.dumps({"descricao": f"sprite {i}", "tipo": "item"}), encoding="utf-8")
    (raiz / "estilo.json").write_text(json.dumps({"nome": "Meu Estilo", "trigger": "meuestilo"}), encoding="utf-8")
    alvo = de_pasta(raiz)
    conjunto.preparar(alvo.conjunto, alvo.trigger_efetivo(), pasta_gosto=alvo.gosto, resolucao=512, repeticoes=5)
    modelo = tmp_path / "modelos" / "sd15 base.safetensors"
    modelo.parent.mkdir()
    modelo.write_bytes(b"pesos falsos " * 100)
    return alvo, modelo


# ---------------------------------------------------------------- config / TOML


def test_toml_parseavel_e_com_argumentos_certos(estilo):
    alvo, modelo = estilo
    plano = config.configurar(alvo, modelo, "sd15-6gb")
    assert plano["versao"] == "v1" and plano["nome_saida"] == "meuestilo_v1"
    ds = tomllib.loads(open(plano["dataset_toml"], encoding="utf-8").read())
    tr = tomllib.loads(open(plano["treino_toml"], encoding="utf-8").read())
    sub = ds["datasets"][0]["subsets"][0]
    assert sub["num_repeats"] == 5 and sub["image_dir"].endswith("5_meuestilo")
    assert ds["datasets"][0]["resolution"] == 512 and ds["general"]["caption_extension"] == ".txt"
    assert ds["general"]["enable_bucket"] is False
    plano_tr = {k: v for secao in tr.values() for k, v in secao.items()}
    esperado = {
        "pretrained_model_name_or_path": str(modelo.resolve()),
        "network_module": "networks.lora", "network_dim": 16, "network_alpha": 8,
        "save_model_as": "safetensors", "mixed_precision": "fp16", "sdpa": True,
        "optimizer_type": "AdamW8bit", "gradient_checkpointing": True, "cache_latents": True,
        "max_train_epochs": 10, "learning_rate": 1e-4, "seed": 42, "output_name": "meuestilo_v1",
        "output_dir": str(alvo.pasta_versao("v1")),
    }
    for k, v in esperado.items():
        assert plano_tr[k] == v, k
    assert "text_encoder_lr" in plano_tr and "network_train_unet_only" not in plano_tr
    assert plano["estimativa"]["passos"] == 3 * 5 * 10


def test_toml_sdxl(estilo):
    alvo, modelo = estilo
    conjunto.preparar(alvo.conjunto, "meuestilo", pasta_gosto=alvo.gosto, resolucao=768)
    plano = config.configurar(alvo, modelo, perfis.escolher(8192))
    tr = tomllib.loads(open(plano["treino_toml"], encoding="utf-8").read())
    plano_tr = {k: v for secao in tr.values() for k, v in secao.items()}
    assert plano_tr["no_half_vae"] and plano_tr["cache_text_encoder_outputs"] and plano_tr["network_train_unet_only"]
    assert "text_encoder_lr" not in plano_tr
    assert next(c for c in executar.montar_comando(plano) if c.endswith(".py")).endswith("sdxl_train_network.py")


def test_resolucao_do_conjunto_tem_que_bater(estilo):
    alvo, modelo = estilo
    with pytest.raises(ErroTreino, match="768"):
        config.configurar(alvo, modelo, "sdxl-8gb")


def test_toml_escapa_caminhos_windows():
    texto = config.para_toml({"a": {"p": r"C:\Users\fulano\x \"y\".safetensors", "l": [1, 2], "f": 0.0001, "b": False}})
    assert tomllib.loads(texto)["a"] == {"p": r"C:\Users\fulano\x \"y\".safetensors", "l": [1, 2], "f": 0.0001, "b": False}


def test_argumentos_cli():
    tr = config.treino_dict(perfis.SD15_6GB, "m.safetensors", "out", "x_v1")
    args = config.argumentos_cli(tr)
    assert args[args.index("--network_module") + 1] == "networks.lora"
    assert "--gradient_checkpointing" in args and "--sdpa" in args


def test_versoes_sucessivas(estilo):
    alvo, modelo = estilo
    assert config.configurar(alvo, modelo, "sd15-6gb")["versao"] == "v1"
    assert config.configurar(alvo, modelo, "sd15-6gb")["versao"] == "v2"
    assert config.carregar_plano(alvo)["versao"] == "v2"


# ---------------------------------------------------------------- treinar


def test_comando_de_treino_simulado(estilo, kohya_falso):
    alvo, modelo = estilo
    plano = config.configurar(alvo, modelo, "sd15-6gb")
    r = executar.treinar(alvo, executar=False)
    cmd = r["comando"]
    assert cmd[0] == str(kohya.python_kohya())
    assert cmd[1:3] == ["-m", "accelerate.commands.launch"]
    assert "--num_cpu_threads_per_process" in cmd
    script = next(c for c in cmd if c.endswith(".py"))
    assert script == str(kohya_falso / "train_network.py")
    assert cmd[cmd.index("--dataset_config") + 1] == plano["dataset_toml"]
    assert cmd[-2:] == ["--config_file", plano["treino_toml"]]
    assert not r["executado"]
    assert not (alvo.pasta_versao("v1") / "treino.log").exists()
    assert not (alvo.pasta_versao("v1") / "info.json").exists()


def test_comando_usa_config_do_accelerate_se_existir(estilo, kohya_falso):
    alvo, modelo = estilo
    plano = config.configurar(alvo, modelo, "sd15-6gb")
    kohya.config_accelerate().write_text("compute_environment: LOCAL_MACHINE\n", encoding="utf-8")
    cmd = executar.montar_comando(plano)
    assert cmd[3:5] == ["--config_file", str(kohya.config_accelerate())]
    assert executar.montar_comando(plano, usar_accelerate=False)[1].endswith("train_network.py")


def test_treinar_exige_kohya_instalado(estilo, kohya_falso):
    alvo, modelo = estilo
    config.configurar(alvo, modelo, "sd15-6gb")
    with pytest.raises(ErroTreino, match="instalar"):
        executar.treinar(alvo, executar=True, eco=False)


def test_treinar_de_verdade_com_script_falso(estilo, kohya_falso):
    alvo, modelo = estilo
    plano = config.configurar(alvo, modelo, "sd15-6gb")
    r = executar.treinar(alvo, "v1", executar=True, python=sys.executable, usar_accelerate=False, eco=False)
    assert r["status"] == "ok"
    pasta = alvo.pasta_versao("v1")
    assert "passos: ok 512" in (pasta / "treino.log").read_text(encoding="utf-8")
    info = json.loads((pasta / "info.json").read_text(encoding="utf-8"))
    assert info["status"] == "ok" and info["perfil"]["nome"] == "sd15-6gb"
    assert info["modelo_base"]["sha256"] == hashlib.sha256(modelo.read_bytes()).hexdigest()
    assert info["conjunto"]["contagem"]["total"] == 3 and info["duracao_s"] >= 0
    assert info["arquivo_lora"] == plano["arquivo_lora"]
    with pytest.raises(ErroTreino, match="já foi treinada"):
        config.configurar(alvo, modelo, "sd15-6gb", versao="v1")


def test_treino_que_falha_grava_info(estilo, kohya_falso):
    alvo, modelo = estilo
    config.configurar(alvo, modelo, "sd15-6gb")
    (kohya_falso / "train_network.py").write_text("import sys; print('CUDA out of memory'); sys.exit(1)\n")
    with pytest.raises(ErroTreino, match="falhou"):
        executar.treinar(alvo, executar=True, python=sys.executable, usar_accelerate=False, eco=False)
    info = json.loads((alvo.pasta_versao("v1") / "info.json").read_text(encoding="utf-8"))
    assert info["status"] == "falhou" and info["codigo_saida"] == 1


# ---------------------------------------------------------------- avaliar / notas / promover / gerar


def _treinar(alvo, modelo, versao=None):
    plano = config.configurar(alvo, modelo, "sd15-6gb", versao=versao)
    executar.treinar(alvo, plano["versao"], executar=True, python=sys.executable, usar_accelerate=False, eco=False)
    return plano


def test_comando_de_geracao(estilo, kohya_falso):
    alvo, modelo = estilo
    plano = config.configurar(alvo, modelo, "sd15-6gb")
    r = avaliar.avaliar(alvo, executar=False)
    assert r["contra"] == "base" and not r["executado"]
    base, nova = r["colunas"]
    assert "--network_weights" not in base["comando"]
    cmd = nova["comando"]
    assert cmd[1] == str(kohya_falso / "gen_img.py") and "--sdxl" not in cmd
    assert cmd[cmd.index("--network_weights") + 1] == plano["arquivo_lora"]
    assert cmd[cmd.index("--ckpt") + 1] == plano["modelo_base"] and "--sequential_file_name" in cmd
    assert len(nova["itens"]) == len(avaliar.LOTE_TESTE)
    assert all(it["prompt"].startswith("meuestilo, pixel art, ") for it in nova["itens"])
    assert {it["seed"] for it in nova["itens"]} == {it["seed"] for it in avaliar.LOTE_TESTE}
    assert "--d 1001 --w 512 --h 512" in nova["itens"][0]["linha"]


def test_avaliar_gera_prancha_e_json(estilo, kohya_falso):
    alvo, modelo = estilo
    _treinar(alvo, modelo)
    r = avaliar.avaliar(alvo, "v1", executar=True, python=sys.executable, eco=False)
    assert r["executado"] and r["contra"] == "base"
    with Image.open(r["prancha"]) as im:
        n = len(avaliar.LOTE_TESTE)
        assert im.size[1] > n * 192 and im.size[0] > 2 * 192
    aval = json.loads((alvo.pasta_versao("v1") / "avaliacao.json").read_text(encoding="utf-8"))
    assert set(aval["imagens"]) == {"base", "v1"} and len(aval["imagens"]["v1"]) == len(avaliar.LOTE_TESTE)
    # segunda versão compara com a anterior treinada e reaproveita as imagens já geradas da v1
    _treinar(alvo, modelo)
    r2 = avaliar.avaliar(alvo, "v2", executar=True, python=sys.executable, eco=False)
    assert r2["contra"] == "v1"
    assert r2["colunas"][0]["reaproveitado"] and not r2["colunas"][1]["reaproveitado"]


def test_prancha_lado_a_lado(tmp_path):
    caminhos = {}
    for rot, cor in (("v1", (255, 0, 0)), ("v2", (0, 0, 255))):
        caminhos[rot] = []
        for i in range(2):
            p = tmp_path / f"{rot}_{i}.png"
            Image.new("RGB", (64, 64), cor).save(p)
            caminhos[rot].append(p)
    saida = avaliar.prancha([("v1", caminhos["v1"]), ("v2", caminhos["v2"])], ["a", "b"], tmp_path / "p.png", celula=50)
    with Image.open(saida) as im:
        assert im.getpixel((120 + 8 + 25, 28 + 8 + 25)) == (255, 0, 0)
        assert im.getpixel((120 + 8 + 58 + 25, 28 + 8 + 25)) == (0, 0, 255)
    with pytest.raises(ErroTreino):
        avaliar.prancha([("v1", caminhos["v1"][:1])], ["a", "b"], tmp_path / "x.png")


def test_promocao_respeita_nota_e_aprovacao(estilo, kohya_falso):
    alvo, modelo = estilo
    _treinar(alvo, modelo)
    # sem nota: não promove
    assert not avaliar.promover(alvo, "v1", True)["promovido"]
    avaliar.registrar_notas(alvo, "v1", {"leitura": 70, "paleta": 80}, revisor="codex")
    assert json.loads((alvo.pasta_versao("v1") / "notas.json").read_text(encoding="utf-8"))["nota"] == 75
    # com nota mas sem o sim: não promove
    r = avaliar.promover(alvo, "v1", False)
    assert not r["promovido"] and any("sim" in m for m in r["motivos"])
    assert not alvo.ativo.exists()
    # primeira versão com nota e sim: promove
    assert avaliar.promover(alvo, "v1", True)["promovido"]
    assert json.loads(alvo.ativo.read_text(encoding="utf-8"))["versao"] == "v1"

    _treinar(alvo, modelo)
    avaliar.registrar_notas(alvo, "v2", 75)  # empate: não é MAIOR
    r = avaliar.promover(alvo, "v2", True)
    assert not r["promovido"] and any("não é maior" in m for m in r["motivos"])
    avaliar.registrar_notas(alvo, "v2", {"nota": 82})
    assert not avaliar.promover(alvo, "v2", False)["promovido"]  # maior, mas sem o sim
    r = avaliar.promover(alvo, "v2", True)
    assert r["promovido"]
    ativo = json.loads(alvo.ativo.read_text(encoding="utf-8"))
    assert ativo["versao"] == "v2" and ativo["nota"] == 82 and ativo["historico"][0]["versao"] == "v1"
    assert not avaliar.promover(alvo, "v2", True)["promovido"]  # já é a ativa


def test_notas_invalidas(estilo, kohya_falso):
    alvo, modelo = estilo
    _treinar(alvo, modelo)
    for ruim in (120, -1, "boa", {"x": "y"}):
        with pytest.raises(ErroTreino):
            avaliar.registrar_notas(alvo, "v1", ruim)
    with pytest.raises(ErroTreino):
        avaliar.registrar_notas(alvo, "v9", 50)


def test_gerar_referencia(estilo, kohya_falso):
    alvo, modelo = estilo
    with pytest.raises(ErroTreino, match="versão ativa"):
        gerar.gerar_referencia(alvo, "a red potion")
    _treinar(alvo, modelo)
    avaliar.registrar_notas(alvo, "v1", 80)
    assert avaliar.promover(alvo, "v1", True)["promovido"]

    previstas = gerar.gerar_referencia(alvo, "a red potion", n=2, seed=7, tipo="item")
    assert len(previstas) == 2 and not previstas[0].exists()
    p = gerar.planejar(alvo, "a red potion", n=2, seed=7, tipo="item")
    assert p["prompt"] == "meuestilo, pixel art, item, a red potion" and p["seeds"] == [7, 8]
    assert "--network_weights" in p["comando"]

    feitas = gerar.gerar_referencia(alvo, "meuestilo, pixel art, sword -- bad", n=3, executar=True, seed=7,
                                    pasta_saida=alvo.lora / "ref", python=sys.executable, eco=False)
    assert len(feitas) == 3 and all(f.is_file() for f in feitas)
    linhas = (alvo.lora / "ref" / "prompts.txt").read_text(encoding="utf-8").splitlines()
    assert linhas[0].startswith("meuestilo, pixel art, sword - bad --n ")
    assert "--d 9 " in linhas[2]


def test_comando_de_geracao_sdxl(kohya_falso):
    from horys_pixel.treino import _geracao

    cmd = _geracao.comando(perfis.SDXL_12GB, "xl.safetensors", "p.txt", "out", lora="l.safetensors")
    assert "--sdxl" in cmd and "--no_half_vae" in cmd and cmd[cmd.index("--W") + 1] == "1024"
    cmd15 = _geracao.comando(perfis.SD15_6GB, "sd.safetensors", "p.txt", "out")
    assert "--sdxl" not in cmd15 and "--no_half_vae" not in cmd15 and "--network_module" not in cmd15
