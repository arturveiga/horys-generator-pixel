"""Motor de sequência: recebe N quadros de QUALQUER fonte (render 3D com câmera fixa, grade de poses, vídeo, pasta
de PNGs, atlas do Kiln) e devolve pixel art animada e consistente. Trata a sequência como um todo (o acabamento de
uma imagem só cria cintilação): registro → escolha de quadros → quantização conjunta → redução por moda →
anti-cintilação → trava de identidade → limpeza → validação. Puro (numpy/PIL/scipy), sem Aseprite."""
from __future__ import annotations

import numpy as np

from . import (anticintilacao, autoajuste, colagem, entradas, escolha, fundo, identidade, limpeza, quantizacao, registro,
               snapper, spritesheet, validar)

__all__ = ["processar", "PRESETS", "entradas", "fundo", "registro", "escolha", "quantizacao", "identidade",
           "anticintilacao", "colagem", "limpeza", "validar", "spritesheet", "snapper", "autoajuste", "autoajustar"]

# Padrões por tipo de fonte. 'render3d': a câmera já é fixa e a geometria é a mesma em todos os quadros, então o
# motor NÃO reenquadra quadro a quadro (escala e deslocamento únicos), não regulariza a borda por quadro (cada
# quadro ganharia degraus diferentes = contorno tremendo), limpa só órfãos de 1 px e NÃO roda a anti-cintilação:
# o render é determinístico (não há ruído para tirar) e peças internas se movem sem mudar a silhueta (braço na
# frente do corpo), então herdar a cor do quadro anterior deixa rastro (medido no golem, 2026-11-11). E quantiza
# cada pixel direto na paleta (o agrupamento guloso juntava o pelo escuro e a pedra clara num tom médio).
PRESETS = {
    "render3d": {"escala": "fixa", "regularizar": False, "limpar_min": 2, "anticintilar": False,
                 "quant_direta": True},
    "grade": {"escala": "comum", "regularizar": True, "limpar_min": 3, "anticintilar": True, "quant_direta": False},
    "video": {"escala": "por_quadro", "regularizar": True, "limpar_min": 3, "anticintilar": True,
              "quant_direta": False},
}


def processar(fonte, paleta_hex: list[str], altura_alvo: int, quadro: tuple[int, int], pivo: tuple[float, int],
              linhas: int | None = None, colunas: int | None = None, fps: float | None = None,
              cor_fundo: str = "auto", plano: str | None = None, n: int | None = None, escala: str | None = None,
              fator: int = 4, base: np.ndarray | None = None, decalques: list[dict] | None = None,
              limpar_min: int | None = None, regularizar: bool | None = None, proteger: set | None = None,
              preset: str | None = None, loop: bool = True, anticintilar: bool | None = None,
              prancha: bool = False, franja: bool = True) -> dict:
    """Roda o motor inteiro. 'quadro' = (W, H) final; 'pivo' = (x, y dos pés) final; 'fator' = quanto o espaço de
    trabalho é maior que o final (a redução por moda volta ao tamanho final). 'plano' = 'andar' | 'golpe' | None
    (com n = quantos quadros ficar). 'base' (RGBA no tamanho final) + 'decalques' ligam a trava de identidade.
    'preset' = render3d | grade | video (padrões de escala/limpeza; um manifest.json de render 3D liga 'render3d'
    sozinho); argumentos explícitos ganham do preset. 'proteger' = cores RGB que PODEM mudar sem a forma mudar
    (brilho do olho, runa pulsando): a anti-cintilação e a limpeza não mexem nelas.
    'prancha' = PNG com poses soltas (achadas por componentes, sem grade); 'franja' = tira o anel quase-fundo.
    Devolve {quadros: [RGBA], indices: [int], relatorio: {...}} com a validação objetiva em relatorio['validacao']."""
    if preset is None and not isinstance(fonte, list) and entradas.eh_manifesto(fonte):
        preset = "render3d"
    if preset is not None and preset not in PRESETS:
        raise ValueError(f"preset '{preset}' inválido: use {', '.join(PRESETS)}")
    pad = PRESETS.get(preset, PRESETS["grade"])
    escala = escala or pad["escala"]
    regularizar = pad["regularizar"] if regularizar is None else regularizar
    limpar_min = pad["limpar_min"] if limpar_min is None else limpar_min
    anticintilar = pad["anticintilar"] if anticintilar is None else anticintilar

    W, H = int(quadro[0]), int(quadro[1])
    f = max(1, int(fator))
    quadros = entradas.carregar(fonte, linhas, colunas, fps, prancha, cor_fundo) if not isinstance(fonte, list) else list(fonte)
    quadros = fundo.tirar_fundo(quadros, cor_fundo, franja=franja)
    grande = registro.registrar(quadros, altura_alvo * f, (W * f, H * f), (pivo[0] * f, pivo[1] * f), escala)
    indices = list(range(len(grande)))
    if plano and n:
        pick = escolha.escolher_andar(grande, n) if plano == "andar" else escolha.escolher_golpe(grande, n)
        indices = pick
        grande = [grande[i] for i in pick]
    idx = quantizacao.quantizar(grande, paleta_hex, direto=pad["quant_direta"])
    pequenos = [quantizacao.reduzir_moda(m, (W, H)) for m in idx]
    pisca_antes = anticintilacao.pisca(pequenos, ciclo=loop)
    mascaras = None
    if proteger:
        pal = quantizacao.hex_para_rgb(paleta_hex)
        livres = [i for i, c in enumerate(pal) if tuple(int(v) for v in c) in proteger]
        mascaras = [np.isin(m, livres) for m in pequenos] if livres else None
    if anticintilar:
        pequenos = anticintilacao.aplicar(pequenos, proteger=mascaras)
    pisca_depois = anticintilacao.pisca(pequenos, ciclo=loop)
    rgba = [quantizacao.para_rgba(m, paleta_hex) for m in pequenos]
    rel_id = []
    if base is not None and decalques:
        rgba, rel_id = identidade.travar(rgba, base, decalques)
    rgba = limpeza.limpar(rgba, limpar_min, proteger, regularizar)
    val = validar.validar(rgba, paleta_hex, loop=loop)
    return {"quadros": rgba, "indices": indices,
            "relatorio": {"quadros": len(rgba), "preset": preset, "escala": escala, "anticintilar": anticintilar,
                          "pisca_antes": round(pisca_antes, 4), "pisca_depois": round(pisca_depois, 4),
                          "deriva": registro.deriva(grande), "identidade": rel_id, "validacao": val}}


def autoajustar(fonte, paleta_hex: list[str], alturas: list[int], quadro: tuple[int, int], pivo: tuple[float, int],
                **kw) -> dict:
    """Roda processar com cada altura de 'alturas' e ranqueia os que cabem (ver autoajuste.py). Não aplica nada."""
    return autoajuste.autoajustar(processar, fonte, paleta_hex, alturas, quadro, pivo, **kw)
