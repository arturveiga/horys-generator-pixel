"""Motor de sequência: recebe N quadros de QUALQUER fonte (grade de poses, vídeo, pasta de PNGs, atlas do Kiln) e
devolve pixel art animada e consistente. Trata a sequência como um todo (o acabamento de uma imagem só cria
cintilação): registro → escolha de quadros → quantização conjunta → redução por moda → anti-cintilação → trava de
identidade → limpeza. Puro (numpy/PIL/scipy), sem Aseprite."""
from __future__ import annotations

import numpy as np

from . import anticintilacao, entradas, escolha, fundo, identidade, limpeza, quantizacao, registro

__all__ = ["processar", "entradas", "fundo", "registro", "escolha", "quantizacao", "identidade", "anticintilacao",
           "limpeza"]


def processar(fonte, paleta_hex: list[str], altura_alvo: int, quadro: tuple[int, int], pivo: tuple[float, int],
              linhas: int | None = None, colunas: int | None = None, fps: float | None = None,
              cor_fundo: str = "auto", plano: str | None = None, n: int | None = None, escala: str = "por_quadro",
              fator: int = 4, base: np.ndarray | None = None, decalques: list[dict] | None = None,
              limpar_min: int = 3, regularizar: bool = True, proteger: set | None = None) -> dict:
    """Roda o motor inteiro. 'quadro' = (W, H) final; 'pivo' = (x, y dos pés) final; 'fator' = quanto o espaço de
    trabalho é maior que o final (a redução por moda volta ao tamanho final). 'plano' = 'andar' | 'golpe' | None
    (com n = quantos quadros ficar). 'base' (RGBA no tamanho final) + 'decalques' ligam a trava de identidade.
    Devolve {quadros: [RGBA], indices: [int], relatorio: {...}}."""
    W, H = int(quadro[0]), int(quadro[1])
    f = max(1, int(fator))
    quadros = entradas.carregar(fonte, linhas, colunas, fps) if not isinstance(fonte, list) else list(fonte)
    quadros = fundo.tirar_fundo(quadros, cor_fundo)
    grande = registro.registrar(quadros, altura_alvo * f, (W * f, H * f), (pivo[0] * f, pivo[1] * f), escala)
    indices = list(range(len(grande)))
    if plano and n:
        pick = escolha.escolher_andar(grande, n) if plano == "andar" else escolha.escolher_golpe(grande, n)
        indices = pick
        grande = [grande[i] for i in pick]
    idx = quantizacao.quantizar(grande, paleta_hex)
    pisca_antes = anticintilacao.pisca([quantizacao.reduzir_moda(m, (W, H)) for m in idx])
    pequenos = [quantizacao.reduzir_moda(m, (W, H)) for m in idx]
    pequenos = anticintilacao.aplicar(pequenos)
    pisca_depois = anticintilacao.pisca(pequenos)
    rgba = [quantizacao.para_rgba(m, paleta_hex) for m in pequenos]
    rel_id = []
    if base is not None and decalques:
        rgba, rel_id = identidade.travar(rgba, base, decalques)
    rgba = limpeza.limpar(rgba, limpar_min, proteger, regularizar)
    return {"quadros": rgba, "indices": indices,
            "relatorio": {"quadros": len(rgba), "pisca_antes": round(pisca_antes, 4),
                          "pisca_depois": round(pisca_depois, 4), "deriva": registro.deriva(grande),
                          "identidade": rel_id}}
