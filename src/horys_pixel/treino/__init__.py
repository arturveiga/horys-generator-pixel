"""Treino do estilo: LoRA com kohya-ss/sd-scripts (fase 6).

Fluxo: ``gpu`` → ``perfis`` → ``kohya`` (instalação) → ``conjunto`` (preparo) → ``config`` (TOML)
→ ``executar`` (treino) → ``avaliar`` (lote fixo, prancha, notas, promoção) → ``gerar`` (referência).

Nada aqui baixa, instala ou treina sem ``executar=True``; sem isso, as funções só devolvem o plano
(comandos, caminhos e configurações). Ver ``docs/treino.md`` e ``docs/treino-uso.md``.
"""

from ._comum import ErroTreino
from .alvo import AlvoTreino, de_estilo, de_pasta, resolver

__all__ = ["AlvoTreino", "ErroTreino", "de_estilo", "de_pasta", "resolver"]
