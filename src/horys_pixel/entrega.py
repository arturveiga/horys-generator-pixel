"""Estado de entrega do revisor: estrutural × acabamento.

Estrutural = o que o usuário não deveria ter que consertar (forma, silhueta, leitura, técnica quebrada, forma a
redesenhar). Acabamento = o que o usuário finaliza no Aseprite (brilho, pelo, dedos, facetas, rosto fino) e que vai
marcado na camada 'revisao'. Pronto para entrega = zero estrutural E aceitação >= limite (padrão 80)."""
from __future__ import annotations

LIMITE_PADRAO = 80
CLASSES = ("estrutural", "acabamento")


def classe_de(defeito: dict) -> str:
    """'classe' do JSON do revisor; sem ela, grave = estrutural e leve = acabamento (compatível com o formato antigo)."""
    c = str(defeito.get("classe") or "").strip().lower()
    if c in CLASSES:
        return c
    return "estrutural" if str(defeito.get("severidade") or "grave").lower() == "grave" else "acabamento"


def avaliar(js: dict | None, limite: int = LIMITE_PADRAO) -> dict:
    """Calcula o estado de entrega a partir do JSON do revisor."""
    if not isinstance(js, dict):
        return {"pronto": False, "motivo": "sem JSON do revisor", "estruturais": [], "acabamento": []}
    estruturais, acabamento = [], []
    for d in js.get("criterios") or []:
        if str(d.get("resultado") or "falha").lower() == "passa":
            continue
        (estruturais if classe_de(d) == "estrutural" else acabamento).append(d)
    if js.get("redesenhar_forma"):
        estruturais.append({"id": "L3", "classe": "estrutural", "resultado": "falha", "severidade": "grave",
                            "onde": "forma geral", "correcao": "redesenhar a forma (revisor marcou redesenhar_forma)"})
    try:
        aceitacao = int(js.get("aceitacao") or 0)
    except (TypeError, ValueError):
        aceitacao = 0
    pronto = not estruturais and aceitacao >= limite
    if estruturais:
        motivo = f"{len(estruturais)} defeito(s) estrutural(is)"
    elif aceitacao < limite:
        motivo = f"aceitação {aceitacao} < {limite}"
    else:
        motivo = "zero estrutural e aceitação ok"
    return {"pronto": pronto, "motivo": motivo, "aceitacao": aceitacao, "limite": limite,
            "estruturais": estruturais, "acabamento": acabamento}
