"""Gera agents/revisor.md (subagente do Claude Code) a partir de src/horys_pixel/motor/revisor_prompt.md.

O revisor do fluxo roda normalmente como OUTRO motor (horys_revisar); este subagente serve para revisar dentro da
mesma sessão do Claude quando o usuário preferir. Rode depois de mudar o revisor_prompt.md.
"""
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
prompt = (RAIZ / "src" / "horys_pixel" / "motor" / "revisor_prompt.md").read_text(encoding="utf-8")
cab = """---
name: revisor
description: Revisor independente e exigente de pixel art do horys-pixel. Julga boas práticas universais de pixel art e o que o Artur pediu e aprovou (ficha, pasta _aprovados e KB/estilo/aprovados.md; não há régua externa: a régua é o Artur). Recebe a pasta vNN gerada pelo horys_portao (_regua com a prancha boas práticas e os aprovados do Artur, _8x, _silhueta, _quadros_4x, _direcoes, gif, _checagem.txt com o portão de medidas), a ficha e a praticas.md. Na rodada 1 faz o inventário completo de defeitos, dá nota de 0 a 100 por critério e o percentual de aceitação, e devolve só um JSON com PASSA (sem grave e aceitação >= 80) ou NAO_PASSA e as correções. Use quando a skill horys-pixel pedir a revisão de uma rodada e o usuário quiser o revisor na mesma sessão. Não edita arquivos e não fala com o usuário.
tools: Read, Glob, Grep
---

"""
(RAIZ / "agents" / "revisor.md").write_text(cab + prompt, encoding="utf-8")
print("agents/revisor.md gerado")
