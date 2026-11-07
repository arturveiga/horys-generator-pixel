"""Fase 0 do TODO: gosto não aprende com resposta automática."""
from horys_pixel.ferramentas import gosto


def test_gosto_ignora_pendente_usuario(casa_temp):
    dados = {"estilo": "exemplo", "etapa": "conceito", "tipo": "personagem", "descricao": "x"}
    gosto.registrar_aprovacao(dados, {"aprovado": True, "comentario": "", "pendente_usuario": True})
    assert gosto.ler_registros("exemplo") == []
    gosto.registrar_aprovacao(dados, {"aprovado": True, "comentario": "bom"})
    regs = gosto.ler_registros("exemplo")
    assert len(regs) == 1 and regs[0]["aprovado"] is True


import asyncio

import pytest

from horys_pixel.ferramentas import estilo, registro
from horys_pixel.ferramentas.registro import ErroFerramenta


def test_revisar_recusa_portao_reprovado(casa_temp, tmp_path):
    registro.carregar_todas()
    (tmp_path / "idle_checagem.txt").write_text("# checagem idle\n\nPORTÃO DE MEDIDAS: REPROVADO — corrija\n",
                                                encoding="utf-8")
    with pytest.raises(ErroFerramenta, match="REPROVADO"):
        asyncio.run(registro.REGISTRO["horys_revisar"].funcao(None, {"pasta": str(tmp_path)}))
    assert estilo._portao_reprovado(tmp_path) == ["idle_checagem.txt"]


def _versao_falsa(tmp_path, codigo):
    saida = tmp_path / "v01"
    saida.mkdir(exist_ok=True)
    (saida / "boneco.png").write_bytes(b"png")

    async def gerar(ctx, a):
        return {"saida": saida, "versao": "v01", "codigo": codigo}
    return gerar, saida


def test_exportar_recusa_portao_reprovado(casa_temp, tmp_path, monkeypatch):
    registro.carregar_todas()
    gerar, saida = _versao_falsa(tmp_path, 1)
    monkeypatch.setattr(estilo, "gerar_versao", gerar)
    dest = tmp_path / "entrega"
    monkeypatch.setattr(estilo.config, "caminho_permitido", lambda p: True)
    with pytest.raises(ErroFerramenta, match="REPROVADO"):
        asyncio.run(estilo.exportar(None, {"destino": str(dest)}))
    assert not dest.exists()
    with pytest.raises(ErroFerramenta):   # forcar sem motivo não basta
        asyncio.run(estilo.exportar(None, {"destino": str(dest), "forcar": True}))
    r = asyncio.run(estilo.exportar(None, {"destino": str(dest), "forcar": True, "motivo": "usuário pediu"}))
    assert (dest / "boneco.png").exists() and "FORÇADO" in r[0]["text"]
    assert (saida / "entrega.json").exists()


def test_exportar_aprovado_copia(casa_temp, tmp_path, monkeypatch):
    registro.carregar_todas()
    gerar, _ = _versao_falsa(tmp_path, 0)
    monkeypatch.setattr(estilo, "gerar_versao", gerar)
    monkeypatch.setattr(estilo.config, "caminho_permitido", lambda p: True)
    dest = tmp_path / "entrega"
    asyncio.run(estilo.exportar(None, {"destino": str(dest)}))
    assert (dest / "boneco.png").exists()


def test_prompt_pedido_entrega_skill(tmp_path):
    from horys_pixel.daemon import pedidos
    t = pedidos.prompt_pedido({"id": "p1", "descricao": "aldeão idle", "estilo": "exemplo", "pasta": str(tmp_path)})
    assert "Briefing" in t and "5b" in t and "Portão" in t
    cabeca = t.split("SKILL horys-pixel")[0]
    assert "NÃO tente ler" not in cabeca and "humanoide-ferreiro'" not in cabeca
    assert "praticas.md" in t and str(tmp_path) in t
    assert not t.split("SKILL horys-pixel")[1].lstrip("= \n").startswith("---")


def test_parte_desconexa_gera_texto():
    """Regressão (e2e 2026-11-07): os pontos da parte desconexa iam para 'juncao' e quebravam o relatório."""
    import numpy as np
    from horys_pixel import partes as P
    base = np.zeros((16, 16, 4), np.uint8)
    base[2:5, 2:5] = (200, 60, 60, 255)
    base[10:13, 10:13] = (200, 60, 60, 255)
    rel = P.checar(None, [{"base": base}], partes=["base"], juncoes=[])
    p = [x for x in rel.problemas if x.codigo == "parte-desconexa"][0]
    assert p.juncao is None and p.pontos
    assert "parte-desconexa" in rel.texto(500)
