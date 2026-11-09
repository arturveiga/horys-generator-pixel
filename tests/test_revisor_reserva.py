"""horys_revisar: revisor Claude por padrão; Codex só com preferência e no PATH; reserva avisa quando não cruza."""
import asyncio

from horys_pixel import config
from horys_pixel.daemon import motores
from horys_pixel.daemon.contexto import Contexto
from horys_pixel.ferramentas import registro


def _revisar(tmp_path, chamados, monkeypatch):
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
        return await ctx.pend.aguardar(i, 5)
    return asyncio.run(corpo())


def test_revisor_padrao_claude(casa_temp, tmp_path, monkeypatch):
    assert config.PREFERENCIAS_PADRAO["revisor"] == "claude"
    monkeypatch.setattr(motores, "executavel", lambda m: None)     # sem Codex instalado
    chamados = []
    res = _revisar(tmp_path, chamados, monkeypatch)
    assert chamados == ["claude"]
    assert res["resposta"]["json"]["aceitacao"] == 54 and "aviso" not in res["resposta"]


def test_revisor_padrao_nao_chama_codex_mesmo_instalado(casa_temp, tmp_path, monkeypatch):
    monkeypatch.setattr(motores, "executavel", lambda m: m)
    chamados = []
    _revisar(tmp_path, chamados, monkeypatch)
    assert chamados == ["claude"]


def test_revisor_cruzado_sem_codex_no_path_usa_claude(casa_temp, tmp_path, monkeypatch):
    config.salvar_preferencias({"revisor": "cruzado"})
    monkeypatch.setattr(motores, "executavel", lambda m: None if m == "codex" else m)
    chamados = []
    _revisar(tmp_path, chamados, monkeypatch)
    assert chamados == ["claude"]


def test_revisor_cai_para_o_reserva(casa_temp, tmp_path, monkeypatch):
    config.salvar_preferencias({"revisor": "cruzado"})
    monkeypatch.setattr(motores, "executavel", lambda m: m)
    chamados = []
    res = _revisar(tmp_path, chamados, monkeypatch)
    assert chamados == ["codex", "claude"]
    assert res["resposta"]["json"]["aceitacao"] == 54 and "NÃO foi cruzado" in res["resposta"]["aviso"]
