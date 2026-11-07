"""Gerador de referência do estilo: imagens com a versão ativa do LoRA (``lora/ativo.json``).

A imagem gerada é só referência: passa pelo pipeline normal (conversão com a paleta travada, limpeza,
portão e revisor) e nunca vira asset direto.
"""

from __future__ import annotations

import random
from pathlib import Path

from . import _geracao
from ._comum import ErroTreino, carimbo, formatar_comando, gravar_json, agora_iso, ler_json
from .alvo import resolver
from .config import carregar_plano, perfil_do_plano
from .conjunto import tipo_legenda


def montar_prompt(trigger: str, prompt: str, tipo: str | None = None) -> str:
    """Garante ``<trigger>, pixel art, [tipo,]`` no começo do prompt."""
    texto = _geracao.limpar_prompt(prompt)
    if texto.lower().startswith(trigger.lower()):
        return texto
    partes = [trigger, "pixel art"]
    if tipo:
        partes.append(tipo_legenda(tipo))
    partes.append(texto)
    return ", ".join(partes)


def planejar(
    estilo,
    prompt: str,
    n: int = 3,
    tipo: str | None = None,
    seed: int | None = None,
    pasta_saida: Path | str | None = None,
    python: Path | str | None = None,
) -> dict:
    """Tudo o que a geração vai usar (versão ativa, prompt, seeds, comando, caminhos), sem rodar nada."""
    if n < 1 or n > 32:
        raise ErroTreino("n deve ficar entre 1 e 32")
    alvo = resolver(estilo)
    ativo = ler_json(alvo.ativo)
    if not ativo or not ativo.get("versao"):
        raise ErroTreino(
            "o estilo ainda não tem versão ativa do LoRA. Treine, avalie e promova uma versão "
            "(treinar → avaliar → notas → promover)."
        )
    plano = carregar_plano(alvo, ativo["versao"])
    perfil = perfil_do_plano(plano)
    seed = int(seed) if seed is not None else random.randint(1, 2**31 - 1)
    texto = montar_prompt(plano["trigger"], prompt, tipo)
    pasta = Path(pasta_saida) if pasta_saida else alvo.lora / "referencias" / carimbo()
    arq_prompts = pasta / "prompts.txt"
    lora = ativo.get("arquivo_lora") or plano["arquivo_lora"]
    cmd = _geracao.comando(perfil, plano["modelo_base"], arq_prompts, pasta, lora=lora, python=python)
    return {
        "versao": ativo["versao"],
        "prompt": texto,
        "seeds": [seed + i for i in range(n)],
        "linhas": [_geracao.linha_prompt(texto, seed + i, perfil.resolucao) for i in range(n)],
        "pasta": pasta,
        "arquivo_prompts": arq_prompts,
        "lora": lora,
        "modelo_base": plano["modelo_base"],
        "comando": cmd,
        "comando_texto": formatar_comando(cmd),
        "previstas": [pasta / f"im_{i + 1:06d}.png" for i in range(n)],
    }


def gerar_referencia(
    estilo,
    prompt: str,
    n: int = 3,
    executar: bool = False,
    tipo: str | None = None,
    seed: int | None = None,
    pasta_saida: Path | str | None = None,
    python: Path | str | None = None,
    eco: bool = True,
) -> list[Path]:
    """Gera ``n`` imagens de referência com a versão ativa. Sem ``executar``, devolve os caminhos previstos."""
    p = planejar(estilo, prompt, n=n, tipo=tipo, seed=seed, pasta_saida=pasta_saida, python=python)
    if not executar:
        return p["previstas"]
    if not Path(p["lora"]).is_file():
        raise ErroTreino(f"arquivo do LoRA ativo não encontrado: {p['lora']}")
    if not Path(p["modelo_base"]).is_file():
        raise ErroTreino(f"modelo-base não encontrado: {p['modelo_base']}")
    _geracao.escrever_prompts(p["arquivo_prompts"], p["linhas"])
    imagens = _geracao.rodar(p["comando"], p["pasta"], p["pasta"] / "geracao.log", n, eco=eco)
    gravar_json(p["pasta"] / "referencia.json", {
        "versao": p["versao"], "prompt": p["prompt"], "seeds": p["seeds"],
        "imagens": [str(i) for i in imagens], "criado_em": agora_iso(),
    })
    return imagens
