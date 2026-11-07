"""Perfis de treino por VRAM (ver ``docs/treino.md``).

| VRAM           | perfil       | modelo-base | resolução |
|----------------|--------------|-------------|-----------|
| < 5 GB         | —            | —           | não treina localmente |
| 5 a ~7,3 GB    | sd15-6gb     | SD 1.5      | 512 |
| ~7,3 a ~10 GB  | sdxl-8gb     | SDXL        | 768 (otimizações pesadas) |
| ~10 a ~15 GB   | sdxl-12gb    | SDXL        | 1024 (otimizações ligadas) |
| ≥ ~15 GB       | sdxl-16gb    | SDXL        | 1024 (padrão) |

Os limites são em MB reportados pelo nvidia-smi (uma placa "de 6 GB" reporta 6144; "de 8 GB", 8192).
As estimativas de tempo são grosseiras e servem só para dar uma ideia antes de treinar.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Perfil:
    nome: str
    familia: str  # "sd15" ou "sdxl"
    descricao: str
    vram_min_mb: int
    resolucao: int
    network_dim: int
    network_alpha: int
    optimizer_type: str
    mixed_precision: str
    gradient_checkpointing: bool
    cache_latents: bool
    cache_text_encoder_outputs: bool
    network_train_unet_only: bool
    no_half_vae: bool
    batch_size: int
    learning_rate: float
    unet_lr: float
    text_encoder_lr: float | None
    max_train_epochs: int
    segundos_por_passo: tuple[float, float]  # (otimista, pessimista) — estimativa
    observacoes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def sdxl(self) -> bool:
        return self.familia == "sdxl"

    @property
    def script_treino(self) -> str:
        return "sdxl_train_network.py" if self.sdxl else "train_network.py"

    def como_dict(self) -> dict:
        d = asdict(self)
        d["segundos_por_passo"] = list(self.segundos_por_passo)
        d["observacoes"] = list(self.observacoes)
        d["script_treino"] = self.script_treino
        return d


SD15_6GB = Perfil(
    nome="sd15-6gb",
    familia="sd15",
    descricao="SD 1.5 a 512 px, para placas de ~6 GB (ex.: RTX 3060 Laptop)",
    vram_min_mb=5000,
    resolucao=512,
    network_dim=16,
    network_alpha=8,
    optimizer_type="AdamW8bit",
    mixed_precision="fp16",
    gradient_checkpointing=True,
    cache_latents=True,
    cache_text_encoder_outputs=False,
    network_train_unet_only=False,
    no_half_vae=False,
    batch_size=1,
    learning_rate=1e-4,
    unet_lr=1e-4,
    text_encoder_lr=5e-5,
    max_train_epochs=10,
    segundos_por_passo=(0.6, 1.5),
    observacoes=(
        "SDXL em 6 GB só forçando --perfil sdxl-8gb: muito lento e pode faltar memória.",
        "Feche jogos, navegador com vídeo e o Aseprite pesado durante o treino.",
    ),
)

SDXL_8GB = Perfil(
    nome="sdxl-8gb",
    familia="sdxl",
    descricao="SDXL a 768 px com otimizações pesadas, para placas de 8 a 10 GB",
    vram_min_mb=7300,
    resolucao=768,
    network_dim=16,
    network_alpha=8,
    optimizer_type="AdamW8bit",
    mixed_precision="fp16",
    gradient_checkpointing=True,
    cache_latents=True,
    cache_text_encoder_outputs=True,
    network_train_unet_only=True,
    no_half_vae=True,
    batch_size=1,
    learning_rate=1e-4,
    unet_lr=1e-4,
    text_encoder_lr=None,
    max_train_epochs=10,
    segundos_por_passo=(1.5, 3.5),
    observacoes=("Treina só a U-Net e guarda as saídas do codificador de texto em cache para caber na memória.",),
)

SDXL_12GB = Perfil(
    nome="sdxl-12gb",
    familia="sdxl",
    descricao="SDXL a 1024 px com otimizações ligadas, para placas de 10 a 15 GB",
    vram_min_mb=10000,
    resolucao=1024,
    network_dim=16,
    network_alpha=8,
    optimizer_type="AdamW8bit",
    mixed_precision="fp16",
    gradient_checkpointing=True,
    cache_latents=True,
    cache_text_encoder_outputs=True,
    network_train_unet_only=True,
    no_half_vae=True,
    batch_size=1,
    learning_rate=1e-4,
    unet_lr=1e-4,
    text_encoder_lr=None,
    max_train_epochs=10,
    segundos_por_passo=(1.5, 3.0),
)

SDXL_16GB = Perfil(
    nome="sdxl-16gb",
    familia="sdxl",
    descricao="SDXL a 1024 px, configuração padrão, para placas de 16 GB ou mais",
    vram_min_mb=15000,
    resolucao=1024,
    network_dim=32,
    network_alpha=16,
    optimizer_type="AdamW8bit",
    mixed_precision="bf16",
    gradient_checkpointing=True,
    cache_latents=True,
    cache_text_encoder_outputs=False,
    network_train_unet_only=False,
    no_half_vae=True,
    batch_size=2,
    learning_rate=1e-4,
    unet_lr=1e-4,
    text_encoder_lr=1e-5,
    max_train_epochs=10,
    segundos_por_passo=(1.0, 2.5),
    observacoes=("bf16 exige placa RTX 30xx ou mais nova; em placa antiga, force fp16 editando o treino.toml.",),
)

PERFIS: dict[str, Perfil] = {p.nome: p for p in (SD15_6GB, SDXL_8GB, SDXL_12GB, SDXL_16GB)}


def escolher(vram_mb: int | None, forcar: str | None = None) -> Perfil | None:
    """Perfil para a VRAM informada; ``forcar`` escolhe pelo nome. ``None`` = não dá para treinar aqui."""
    if forcar:
        try:
            return PERFIS[forcar]
        except KeyError:
            from ._comum import ErroTreino

            raise ErroTreino(f"perfil desconhecido: {forcar!r}. Opções: {', '.join(PERFIS)}") from None
    if not vram_mb or vram_mb < SD15_6GB.vram_min_mb:
        return None
    for perfil in sorted(PERFIS.values(), key=lambda p: p.vram_min_mb, reverse=True):
        if vram_mb >= perfil.vram_min_mb:
            return perfil
    return None  # inalcançável


def explicar(vram_mb: int | None, forcar: str | None = None) -> str:
    """Por que este perfil (ou por que nenhum), em pt-BR."""
    if forcar:
        p = escolher(vram_mb, forcar)
        return f"Perfil forçado: {p.nome} — {p.descricao}."
    if not vram_mb:
        return (
            "Sem GPU NVIDIA: não dá para treinar nesta máquina. Use só a memória de gosto, ou treine numa GPU "
            "alugada (o horys gera o conjunto e os TOML; rode lá e traga o .safetensors para lora/vN/)."
        )
    p = escolher(vram_mb)
    if p is None:
        return (
            f"{vram_mb} MB de VRAM é pouco para treinar LoRA com segurança (mínimo ~{SD15_6GB.vram_min_mb} MB). "
            "Use a memória de gosto, ou treine numa GPU alugada e traga o LoRA."
        )
    return f"{vram_mb} MB de VRAM → {p.nome}: {p.descricao}."


def estimar(perfil: Perfil, n_imagens: int, repeticoes: int, epocas: int | None = None) -> dict:
    """Passos totais e tempo estimado (minutos), com folga de ~5 min para carregar modelo e cache."""
    epocas = epocas or perfil.max_train_epochs
    passos_epoca = math.ceil(max(0, n_imagens) * max(1, repeticoes) / max(1, perfil.batch_size))
    passos = passos_epoca * epocas
    rapido, lento = perfil.segundos_por_passo
    return {
        "passos": passos,
        "passos_por_epoca": passos_epoca,
        "epocas": epocas,
        "minutos_min": round(passos * rapido / 60 + 3),
        "minutos_max": round(passos * lento / 60 + 8),
    }
