"""horys_revisar: se o motor cruzado falhar (ex.: sem cota), revisa com o de reserva e avisa."""
import asyncio
import json

from horys_pixel.daemon import motores
from horys_pixel.daemon.contexto import Contexto
from horys_pixel.ferramentas import registro


def test_revisor_cai_para_o_reserva(casa_temp, tmp_path, monkeypatch):
    chamados = []

    async def falso(motor, prompt, pasta, nome_log="motor", timeout=None, ao_iniciar=None):
        chamados.append(motor)
        if motor == "codex":
            return {"codigo": 1, "texto": "ERROR: You've hit your usage limit", "log": "x", "segundos": 1}
        return {"codigo": 0, "texto": 'ok\n{"veredito": "NAO_PASSA", "aceitacao": 54}', "log": "y", "segundos": 2}

    monkeypatch.setattr(motores, "rodar", falso)
    registro.carregar_todas()

    async def corpo():
        ctx = Contexto()
        r = await registro.REGISTRO["horys_revisar"].funcao(ctx, {"pasta": str(tmp_path), "quem_desenhou": "claude"})
        i = r[0]["text"].split("id: ")[1].split()[0]
        res = await ctx.pend.aguardar(i, 5)
        return res
    res = asyncio.run(corpo())
    assert chamados == ["codex", "claude"]
    assert res["resposta"]["json"]["aceitacao"] == 54 and "NÃO foi cruzado" in res["resposta"]["aviso"]
