"""Auto-ajuste ranqueado: roda o motor com várias alturas-alvo e ordena os candidatos que CABEM no quadro.
Nunca aplica sozinho: devolve até 'max_candidatos' para o Artur (ou o revisor) escolher. Critérios, nesta ordem:
1. cabe no quadro com a margem pedida (quem não cabe sai);
2. altura neutra perto da 'altura_neutra' da ficha (dentro da tolerância conta como empate);
3. validação sem graves;
4. mais detalhe retido (pixels opacos por altura² — menos borrão da redução);
5. menos cintilação depois da anti-cintilação;
6. altura-alvo mais perto da pedida."""
from __future__ import annotations

import numpy as np


def caixa_uniao(quadros: list[np.ndarray]) -> tuple[int, int, int, int] | None:
    op = np.zeros(quadros[0].shape[:2], bool)
    for q in quadros:
        op |= q[..., 3] >= 128
    if not op.any():
        return None
    ys, xs = np.nonzero(op)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def _altura(q: np.ndarray) -> int:
    linhas = np.nonzero((q[..., 3] >= 128).any(1))[0]
    return int(linhas[-1] - linhas[0] + 1) if len(linhas) else 0


def medir(quadros: list[np.ndarray], W: int, H: int, margem: int = 0) -> dict:
    cx = caixa_uniao(quadros)
    if cx is None:
        return {"cabe": False, "altura": 0, "detalhe": 0.0}
    x0, y0, x1, y1 = cx
    # o registro corta o que passa do quadro: encostar na borda de cima ou dos lados = foi cortado, não cabe
    m = max(1, margem)
    cabe = x0 >= m and y0 >= m and x1 <= W - m and y1 <= H
    neutra = int(np.median([_altura(q) for q in quadros]))
    opacos = float(np.mean([(q[..., 3] >= 128).sum() for q in quadros]))
    return {"cabe": bool(cabe), "altura": neutra, "detalhe": round(opacos / max(1, neutra) ** 2, 4)}


def autoajustar(processar, fonte, paleta_hex: list[str], alturas: list[int], quadro: tuple[int, int],
                pivo: tuple[float, int], altura_neutra: int | None = None, tolerancia: int = 1, margem: int = 0,
                max_candidatos: int = 3, **kw) -> dict:
    """'processar' = sequencia.processar (injetado para não haver import circular). Devolve
    {candidatos: [{altura_alvo, cabe, altura, detalhe, graves, pisca, resultado}], descartados: [...]}."""
    W, H = int(quadro[0]), int(quadro[1])
    alvo = altura_neutra if altura_neutra is not None else max(alturas)
    todos = []
    for a in sorted({int(x) for x in alturas}, reverse=True):
        try:
            r = processar(fonte, paleta_hex, a, quadro, pivo, **kw)
        except ValueError as e:
            todos.append({"altura_alvo": a, "cabe": False, "erro": str(e)})
            continue
        val = r["relatorio"]["validacao"]
        todos.append({"altura_alvo": a, **medir(r["quadros"], W, H, margem), "graves": int(val.get("graves", 0)),
                      "pisca": r["relatorio"]["pisca_depois"], "resultado": r})

    def chave(c):
        d = abs(c["altura"] - alvo)
        fora = d > tolerancia
        return (fora, d if fora else 0, c["graves"] > 0, -c["detalhe"], c["pisca"], abs(c["altura_alvo"] - alvo))

    bons = sorted((c for c in todos if c.get("cabe")), key=chave)
    return {"candidatos": bons[:max_candidatos],
            "descartados": [{k: v for k, v in c.items() if k != "resultado"} for c in todos if not c.get("cabe")]}
