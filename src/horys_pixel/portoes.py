"""Portões da animação: medidas que BLOQUEIAM a entrega quando falham (sem flag para contornar).

- NAO_CABE / JUNTA_FORA vindos do render;
- cintilação (pixels que piscam A->B->A) acima do limite;
- no idle: altura e linha do pé variando mais que o permitido (andando, o pé que vem para a câmera desce na tela:
  em top-down isso é certo, então andar/correr não entram nesta regra);
- mudança média por quadro fora da faixa da ação (andar que só desliza; idle que ferve);
- parado: altura entre as direções variando mais de 20%.
Avisos (não bloqueiam): peça com menos de 2 px de espessura; emenda do ciclo com pop (pula mais de 'emenda_pop'
vezes um passo) ou trava (menos de 'emenda_trava' de um passo). A emenda é aviso até ser medida nos assets reais.
Na prévia (4 quadros por ação) só valem NAO_CABE, JUNTA_FORA e o parado: as medidas de ciclo precisam de todos os
quadros.
"""
from __future__ import annotations

CICLOS = ("idle", "andar", "correr", "flutuar")
FIXOS = ("idle",)
GOLPES = ("soco", "ataque", "dano", "morte")


def avaliar(rel: dict, jogo: dict, previa: bool = False) -> dict:
    g = jogo["portoes"]
    falhas, avisos = [], []
    for a in rel.get("avisos", []):
        (falhas if a.startswith(("NAO_CABE", "JUNTA_FORA")) else avisos).append(a)
    alturas_parado = {}
    for est, e in rel.get("estados", {}).items():
        if e["tipo"] == "parado" and e["altura_px"]:
            alturas_parado[e["direcao"]] = e["altura_px"][0]
        if previa:
            continue
        lim = g.get("pisca_max_golpe", g["pisca_max"]) if e["tipo"] in GOLPES else g["pisca_max"]
        if e["pisca"] > lim:
            falhas.append(f"{est}: {e['pisca']:.1%} dos pixels piscam (máximo {lim:.1%})")
        if e["tipo"] in FIXOS and e["altura_px"] and e["quadros"] > 1:
            var = e["altura_px"][1] - e["altura_px"][0]
            if var > g["altura_var_max_px"]:
                falhas.append(f"{est}: a altura varia {var} px no ciclo (máximo {g['altura_var_max_px']})")
        if e["tipo"] in FIXOS and e["pe_linha"] and e["quadros"] > 1:
            var = e["pe_linha"][1] - e["pe_linha"][0]
            if var > g["pe_var_max_px"]:
                falhas.append(f"{est}: a linha do pé varia {var} px (máximo {g['pe_var_max_px']}): o pé descola")
        faixa = g.get("mudanca", {}).get(e["tipo"])
        if faixa and e["quadros"] > 1:
            lo, hi = faixa
            if not lo <= e["mudanca_media"] <= hi:
                falhas.append(f"{est}: muda {e['mudanca_media']:.0%} por quadro (faixa {lo:.0%}–{hi:.0%})")
        em = e.get("emenda")
        if em and em["razao"] is not None and e["tipo"] in CICLOS:
            if em["razao"] > g.get("emenda_pop", 2.0):
                avisos.append(f"{est}: a emenda do loop muda {em['razao']}x um passo (pop no último->primeiro)")
            elif em["razao"] < g.get("emenda_trava", 0.25):
                avisos.append(f"{est}: a emenda do loop quase não muda ({em['razao']}x um passo): quadro repetido")
    if len(alturas_parado) > 1:
        lo, hi = min(alturas_parado.values()), max(alturas_parado.values())
        if hi > 1.2 * lo:
            falhas.append(f"parado: altura entre direções vai de {lo} a {hi} px (máximo 20%)")
    for est, partes in rel.get("detalhe_fino", {}).items():
        avisos.append(f"{est}: peça com menos de {g.get('detalhe_min_px', 2)} px de espessura: {', '.join(partes)}")
    return {"ok": not falhas, "falhas": falhas, "avisos": avisos}
