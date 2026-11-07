"""GPU (saída simulada do nvidia-smi) e escolha de perfil por VRAM."""

import subprocess
from types import SimpleNamespace

import pytest

from horys_pixel.treino import ErroTreino, gpu, perfis


def _rodar(stdout="", returncode=0, erro=None):
    def rodar(cmd, **kw):
        assert cmd[0] == "nvidia-smi"
        assert "--query-gpu=name,memory.total,driver_version" in cmd
        if erro:
            raise erro
        return SimpleNamespace(stdout=stdout, returncode=returncode)
    return rodar


def test_detectar_uma_placa():
    g = gpu.detectar(_rodar("NVIDIA GeForce RTX 3060 Laptop GPU, 6144, 581.80\n"))
    assert g == {"nome": "NVIDIA GeForce RTX 3060 Laptop GPU", "vram_mb": 6144, "driver": "581.80"}


def test_detectar_varias_placas_escolhe_maior_vram():
    saida = "NVIDIA GeForce GTX 1650, 4096, 551.23\nNVIDIA GeForce RTX 4090, 24564, 551.23\n\n"
    assert gpu.detectar(_rodar(saida))["vram_mb"] == 24564
    assert len(gpu.listar(_rodar(saida))) == 2


def test_nome_com_virgula_e_memoria_na():
    lista = gpu.interpretar("Placa, Edição X, 8192, 560.1\nOutra, [N/A], 560.1\n")
    assert lista[0] == {"nome": "Placa, Edição X", "vram_mb": 8192, "driver": "560.1"}
    assert lista[1]["vram_mb"] is None
    assert gpu.detectar(_rodar("Outra, [N/A], 560.1\n")) is None


@pytest.mark.parametrize("rodar", [
    _rodar(erro=FileNotFoundError("nvidia-smi")),
    _rodar(erro=subprocess.TimeoutExpired("nvidia-smi", 15)),
    _rodar(stdout="", returncode=9),
    _rodar(stdout="NVIDIA-SMI has failed because it couldn't communicate with the driver.", returncode=0),
])
def test_detectar_sem_gpu(rodar):
    assert gpu.detectar(rodar) is None


def test_descrever():
    assert "6144 MB" in gpu.descrever({"nome": "X", "vram_mb": 6144, "driver": "1"})
    assert "Nenhuma GPU" in gpu.descrever(None)


@pytest.mark.parametrize("vram, nome", [
    (6144, "sd15-6gb"),
    (6000, "sd15-6gb"),
    (7168, "sd15-6gb"),
    (8192, "sdxl-8gb"),
    (8188, "sdxl-8gb"),
    (10240, "sdxl-12gb"),
    (12288, "sdxl-12gb"),
    (16376, "sdxl-16gb"),
    (24564, "sdxl-16gb"),
])
def test_escolher_por_faixa(vram, nome):
    assert perfis.escolher(vram).nome == nome


def test_perfil_6gb_conforme_docs():
    p = perfis.escolher(6144)
    assert (p.familia, p.resolucao, p.network_dim, p.optimizer_type, p.mixed_precision, p.batch_size) == \
        ("sd15", 512, 16, "AdamW8bit", "fp16", 1)
    assert p.gradient_checkpointing and p.cache_latents
    assert p.script_treino == "train_network.py"


def test_perfis_sdxl():
    p8, p12, p16 = perfis.escolher(8192), perfis.escolher(12288), perfis.escolher(16384)
    assert p8.resolucao == 768 and p12.resolucao == 1024 and p16.resolucao == 1024
    assert all(p.sdxl and p.script_treino == "sdxl_train_network.py" for p in (p8, p12, p16))
    assert p8.cache_text_encoder_outputs and p8.network_train_unet_only and p8.gradient_checkpointing
    assert not p16.network_train_unet_only


@pytest.mark.parametrize("vram", [None, 0, 2048, 4096])
def test_sem_gpu_ou_pouca_vram(vram):
    assert perfis.escolher(vram) is None
    texto = perfis.explicar(vram)
    assert "GPU alugada" in texto


def test_forcar_perfil():
    assert perfis.escolher(None, "sdxl-8gb").nome == "sdxl-8gb"
    assert perfis.escolher(6144, forcar="sdxl-12gb").nome == "sdxl-12gb"
    with pytest.raises(ErroTreino):
        perfis.escolher(6144, forcar="inexistente")


def test_estimar():
    est = perfis.estimar(perfis.SD15_6GB, 20, 10, 10)
    assert est["passos"] == 2000 and est["passos_por_epoca"] == 200
    assert 0 < est["minutos_min"] < est["minutos_max"]
