import asyncio
import json
import sys
from pathlib import Path

import pytest

from horys_pixel import config
from horys_pixel.daemon import motores
from horys_pixel.daemon.ponte import Ponte
from horys_pixel.ferramentas import desenho
from horys_pixel.ferramentas.registro import ErroFerramenta


def test_motor_pasta_relativa(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    def comando(motor, prompt, pasta, ultima):
        return [sys.executable, '-c',
                'import pathlib,sys; pathlib.Path(sys.argv[1]).write_text("ok", encoding="utf-8")', str(ultima)]
    monkeypatch.setattr(motores, 'comando', comando)
    r = asyncio.run(motores.rodar('codex', 'teste', Path('relativa'), timeout=5))
    assert r['codigo'] == 0
    assert r['texto'] == 'ok'


def test_json_revisor_preserva_objeto_externo():
    esperado = {'veredito': 'NAO_PASSA', 'correcoes': [{'onde': {'x': 3}}]}
    assert motores.extrair_json('texto\n' + json.dumps(esperado)) == esperado
    assert motores.extrair_json('antes {"antigo":true}\n' + json.dumps(esperado)) == esperado


def test_salvar_sem_arquivo_verifica_destino(tmp_path, monkeypatch):
    alvo = tmp_path / 'original.aseprite'
    alvo.write_bytes(b'original')
    class Ctx:
        async def sprite_atual(self):
            return {'sprite': {'arquivo': str(alvo)}}
        async def aseprite(self, *args):
            pytest.fail('não deve enviar salvar ao editor')
    monkeypatch.setattr(config, 'caminho_permitido', lambda p: False)
    with pytest.raises(ErroFerramenta, match='permitida'):
        asyncio.run(desenho.salvar(Ctx(), {}))
    monkeypatch.setattr(config, 'caminho_permitido', lambda p: True)
    with pytest.raises(ErroFerramenta, match='existe'):
        asyncio.run(desenho.salvar(Ctx(), {}))


def test_ponte_limpa_espera_apos_falha_de_envio():
    class Socket:
        async def send(self, msg):
            raise ConnectionError('desconectou')
    async def caso():
        p = Ponte()
        p.ligar(Socket(), 'teste')
        with pytest.raises(ConnectionError):
            await p.pedir('status')
        assert p._espera == {}
    asyncio.run(caso())


def test_pasta_asset_rejeita_destino_antes_de_criar(tmp_path, monkeypatch):
    from horys_pixel.ferramentas.estilo import _pasta_asset
    alvo = tmp_path / 'nao-permitida'
    monkeypatch.setattr(config, 'caminho_permitido', lambda p: False)
    with pytest.raises(ErroFerramenta, match='permitida'):
        _pasta_asset({'pasta': str(alvo)})
    assert not alvo.exists()


@pytest.mark.parametrize('flag', ['--executar', '--exec', '--e'])
def test_treino_args_nao_contorna_executar_false(monkeypatch, flag):
    from horys_pixel.ferramentas import treino
    async def falso(args, timeout):
        assert '--executar' not in args
        return 0, 'simulação'
    monkeypatch.setattr(treino, 'rodar_cli', falso)
    with pytest.raises(ErroFerramenta, match='executar'):
        asyncio.run(treino.treino(None, {'comando': 'instalar', 'args': [flag], 'executar': False}))


def test_instrucoes_mcp_so_citam_ferramentas_existentes():
    import re
    from horys_pixel.mcp_ponte import INSTRUCOES
    from horys_pixel.ferramentas import registro
    registro.carregar_todas()
    assert set(re.findall(r'horys_[a-z_]+', INSTRUCOES)) <= set(registro.REGISTRO)
