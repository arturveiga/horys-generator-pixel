"""Plano de instalação do kohya (sem baixar nada), caminhos, integração opcional com estilos e a CLI."""

import json
import sys
import types

import numpy as np
import pytest
from PIL import Image

from horys_pixel.treino import ErroTreino, alvo, gpu, kohya
from horys_pixel.treino.__main__ import main


@pytest.fixture(autouse=True)
def casa(tmp_path, monkeypatch):
    monkeypatch.setenv("HORYS_PIXEL_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("HORYS_KOHYA_DIR", raising=False)
    return tmp_path / "home"


def test_caminhos_padrao(casa, monkeypatch, tmp_path):
    assert kohya.raiz() == casa / "kohya"
    assert kohya.pasta_repo() == casa / "kohya" / "sd-scripts"
    assert kohya.python_kohya().parent.parent == casa / "kohya" / "venv"
    assert kohya.script("treino_sd15").name == "train_network.py"
    assert kohya.script("treino_sdxl").name == "sdxl_train_network.py"
    assert kohya.script("gen_img.py") == kohya.pasta_repo() / "gen_img.py"
    monkeypatch.setenv("HORYS_KOHYA_DIR", str(tmp_path / "outro"))
    assert kohya.raiz() == tmp_path / "outro"


def test_script_de_geracao_com_fallback():
    assert kohya.script_geracao("sd15").name == "gen_img.py"  # nada instalado: o nome atual
    kohya.pasta_repo().mkdir(parents=True)
    (kohya.pasta_repo() / "sdxl_gen_img.py").write_text("")
    assert kohya.script_geracao("sdxl").name == "sdxl_gen_img.py"  # sd-scripts antigo
    (kohya.pasta_repo() / "gen_img.py").write_text("")
    assert kohya.script_geracao("sdxl").name == "gen_img.py"
    with pytest.raises(ErroTreino):
        kohya.script_geracao("flux")


def test_plano_de_instalacao_nao_executa(monkeypatch):
    def proibido(*a, **k):
        raise AssertionError("não pode rodar nada sem executar=True")
    monkeypatch.setattr("subprocess.run", proibido)
    monkeypatch.setattr("subprocess.Popen", proibido)
    passos = kohya.instalar(executar=False, python_base="python3.10", cuda="cu124")
    textos = [" ".join(p.comando) for p in passos]
    assert any(t.startswith("git clone https://github.com/kohya-ss/sd-scripts") for t in textos)
    assert any("-m venv" in t and t.startswith("python3.10") for t in textos)
    torch = next(p for p in passos if "torch==" in " ".join(p.comando))
    assert torch.comando[-2:] == ["--index-url", "https://download.pytorch.org/whl/cu124"]
    req = next(p for p in passos if "requirements.txt" in p.comando)
    assert req.cwd == kohya.pasta_repo()
    acc = next(p for p in passos if "accelerate.commands.accelerate_cli" in p.comando)
    assert acc.comando[3:5] == ["config", "default"] and str(kohya.config_accelerate()) in acc.comando
    assert all(p.comando[0] == str(kohya.python_kohya()) for p in passos[4:])
    assert not kohya.raiz().exists()  # nada criado
    assert not kohya.instalado()


def test_plano_pula_o_que_ja_existe():
    (kohya.pasta_repo() / ".git").mkdir(parents=True)
    kohya.python_kohya().parent.mkdir(parents=True)
    kohya.python_kohya().write_text("")
    passos = {p.descricao: p for p in kohya.instalar(python_base="py", cuda="cu118")}
    assert passos["Baixar o sd-scripts (git clone)"].pular
    assert passos["Criar o ambiente Python do kohya (venv)"].pular
    assert not passos["Atualizar referências do repositório"].pular


def test_instalado_exige_marca_python_e_script():
    kohya.pasta_repo().mkdir(parents=True)
    (kohya.pasta_repo() / "train_network.py").write_text("")
    kohya.python_kohya().parent.mkdir(parents=True)
    kohya.python_kohya().write_text("")
    assert not kohya.instalado()
    kohya.marca_instalacao().write_text("{}")
    assert kohya.instalado()


@pytest.mark.parametrize("driver, cuda", [("581.80", "cu124"), ("525.60", "cu124"), ("470.1", "cu118"), (None, "cu124")])
def test_cuda_pelo_driver(driver, cuda):
    assert kohya.cuda_para_driver(driver) == cuda


# ---------------------------------------------------------------- integração com estilos


def test_de_estilo_sem_modulo(monkeypatch):
    import horys_pixel
    monkeypatch.setitem(sys.modules, "horys_pixel.estilos", None)  # import falha
    monkeypatch.delattr(horys_pixel, "estilos", raising=False)
    with pytest.raises(ErroTreino, match="--estilo-dados"):
        alvo.de_estilo("qualquer")


def test_de_estilo_com_modulo(monkeypatch, tmp_path):
    falso = types.ModuleType("horys_pixel.estilos")
    falso.carregar = lambda nome: types.SimpleNamespace(nome=nome, trigger="hpxliso")
    falso.pasta_dados = lambda est, tipo: tmp_path / est.nome / tipo
    monkeypatch.setitem(sys.modules, "horys_pixel.estilos", falso)
    import horys_pixel
    monkeypatch.setattr(horys_pixel, "estilos", falso, raising=False)
    a = alvo.de_estilo("liso")
    assert a.trigger == "hpxliso" and a.gosto == tmp_path / "liso" / "gosto" and a.lora == tmp_path / "liso" / "lora"


def test_trigger_padrao():
    assert alvo.trigger_padrao("Horys Pixel Liso") == "horyspixelliso"
    assert alvo.trigger_padrao("Ação Ótima!") == "acaootima"


# ---------------------------------------------------------------- CLI


def _estilo(tmp_path):
    aprov = tmp_path / "est" / "gosto" / "aprovados"
    aprov.mkdir(parents=True)
    for i in range(2):
        a = np.zeros((12, 12, 4), np.uint8)
        a[2:10, 3:9] = (100 + 50 * i, 40, 40, 255)
        Image.fromarray(a, "RGBA").save(aprov / f"s{i}.png")
        (aprov / f"s{i}.json").write_text(json.dumps({"descricao": f"coisa {i}", "tipo": "prop"}))
    return tmp_path / "est"


def test_cli_gpu_e_perfil(monkeypatch, capsys):
    monkeypatch.setattr(gpu, "listar", lambda *a, **k: [{"nome": "RTX Falsa", "vram_mb": 6144, "driver": "1.0"}])
    monkeypatch.setattr(gpu, "detectar", lambda *a, **k: {"nome": "RTX Falsa", "vram_mb": 6144, "driver": "1.0"})
    assert main(["gpu"]) == 0
    assert "RTX Falsa" in capsys.readouterr().out
    assert main(["perfil"]) == 0
    saida = capsys.readouterr().out
    assert "sd15-6gb" in saida and "train_network.py" in saida
    assert main(["perfil", "--vram", "16384"]) == 0
    assert "sdxl-16gb" in capsys.readouterr().out
    assert main(["perfil", "--todos"]) == 0


def test_cli_sem_gpu(monkeypatch, capsys):
    monkeypatch.setattr(gpu, "listar", lambda *a, **k: [])
    monkeypatch.setattr(gpu, "detectar", lambda *a, **k: None)
    assert main(["gpu"]) == 0
    assert "Nenhuma GPU" in capsys.readouterr().out
    assert main(["perfil"]) == 0
    assert "GPU alugada" in capsys.readouterr().out


def test_cli_instalar_simulado(monkeypatch, capsys):
    monkeypatch.setattr(gpu, "detectar", lambda *a, **k: None)
    assert main(["instalar", "--python", "py310", "--cuda", "cu124"]) == 0
    saida = capsys.readouterr().out
    assert "simulação" in saida and "git clone https://github.com/kohya-ss/sd-scripts" in saida
    assert not kohya.raiz().exists()


def test_cli_fluxo_simulado(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(gpu, "detectar", lambda *a, **k: None)
    est = _estilo(tmp_path)
    minhas = tmp_path / "minhas"
    minhas.mkdir()
    a = np.zeros((8, 8, 4), np.uint8)
    a[1:7, 1:7] = (10, 200, 10, 255)
    Image.fromarray(a, "RGBA").save(minhas / "arbusto.png")

    # sem GPU e sem --perfil/--resolucao: explica e sai com erro
    assert main(["preparar", "--estilo-dados", str(est), "--trigger", "tstx"]) == 2
    assert "GPU" in capsys.readouterr().err
    # imagens sem licença: erro
    assert main(["preparar", "--estilo-dados", str(est), "--trigger", "tstx", "--perfil", "sd15-6gb",
                 "--imagens", str(minhas)]) == 2
    assert "licença" in capsys.readouterr().err

    assert main(["preparar", "--estilo-dados", str(est), "--trigger", "tstx", "--perfil", "sd15-6gb",
                 "--imagens", str(minhas), "--licenca", "minha arte", "--tipo", "prop", "--fundo", "#000000"]) == 0
    saida = capsys.readouterr().out
    assert "3 imagens (2 da memória de gosto, 1 enviadas)" in saida and "minha arte" in saida
    assert (est / "conjunto" / "manifesto.json").is_file()

    modelo = tmp_path / "base.safetensors"
    assert main(["configurar", "--estilo-dados", str(est), "--perfil", "sd15-6gb", "--modelo", str(modelo)]) == 0
    saida = capsys.readouterr().out
    assert "v1 configurada" in saida and "ainda não existe" in saida
    assert (est / "lora" / "v1" / "treino.toml").is_file()

    assert main(["treinar", "--estilo-dados", str(est)]) == 0
    saida = capsys.readouterr().out
    assert "accelerate.commands.launch" in saida and "train_network.py" in saida and "simulação" in saida
    assert not (est / "lora" / "v1" / "treino.log").exists()
    assert main(["treinar", "--estilo-dados", str(est), "--executar"]) == 2
    assert "instalar --executar" in capsys.readouterr().err

    assert main(["avaliar", "--estilo-dados", str(est)]) == 0
    assert "gen_img.py" in capsys.readouterr().out

    assert main(["promover", "--estilo-dados", str(est), "--versao", "v1", "--aprovado"]) == 1
    assert "NÃO foi promovida" in capsys.readouterr().out
    assert main(["gerar", "--estilo-dados", str(est), "--prompt", "a tree"]) == 2
    assert "versão ativa" in capsys.readouterr().err


def test_cli_notas(tmp_path, capsys):
    est = _estilo(tmp_path)
    (est / "lora" / "v1").mkdir(parents=True)
    arq = tmp_path / "notas.json"
    arq.write_text(json.dumps({"silhueta": 80, "paleta": 90}))
    assert main(["notas", "--estilo-dados", str(est), "--versao", "v1", "--notas-json", str(arq), "--revisor", "codex"]) == 0
    assert "85" in capsys.readouterr().out
    assert main(["notas", "--estilo-dados", str(est), "--versao", "1", "--nota", "70"]) == 0
    assert json.loads((est / "lora" / "v1" / "notas.json").read_text(encoding="utf-8"))["nota"] == 70
