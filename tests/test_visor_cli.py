import json
import threading
import urllib.request

import numpy as np
from PIL import Image

from horys_pixel import cli
from horys_pixel.visor import servidor

from .conftest import ampliar_irregular


def _projeto(tmp_path, boneco):
    (tmp_path / "assets").mkdir()
    (tmp_path / "jogo.json").write_text("{}", encoding="utf-8")
    return tmp_path


def test_cli_do_novo_ate_a_paleta(tmp_path, boneco, monkeypatch, capsys):
    p = _projeto(tmp_path, boneco)
    monkeypatch.chdir(p)
    assert cli.main(["novo", "boneco", "--altura", "44", "--descricao", "boneco cinza"]) == 0
    assert cli.main(["prompt", "boneco"]) == 0
    assert "exatamente 44 pixels" in (p / "assets" / "boneco" / "prompt.txt").read_text(encoding="utf-8")
    Image.fromarray(ampliar_irregular(boneco, bloco=(11, 15))).save(p / "assets" / "boneco" / "gerada.png")
    assert cli.main(["ler", "boneco"]) == 0
    for v in ("frente", "lado", "costas"):
        assert (p / "assets" / "boneco" / "arte" / f"{v}.png").exists()
    assert cli.main(["paleta", "boneco", "--materiais", "2"]) == 0
    assert cli.main(["gabarito", "boneco"]) == 1          # sem aprovação: recusa
    assert "falta aprovar" in capsys.readouterr().err
    assert cli.main(["aprovar", "boneco", "arte"]) == 0
    assert cli.main(["aprovar", "boneco", "paleta"]) == 0
    assert cli.main(["estado", "boneco"]) == 0
    assert cli.main(["exportar", "boneco", str(tmp_path / "jogo")]) == 1   # sem portões: recusa


def test_cli_ler_recusa_altura_errada(tmp_path, boneco, monkeypatch, capsys):
    p = _projeto(tmp_path, boneco)
    monkeypatch.chdir(p)
    cli.main(["novo", "b", "--altura", "30"])
    Image.fromarray(ampliar_irregular(boneco, bloco=(11, 15))).save(p / "assets" / "b" / "gerada.png")
    assert cli.main(["ler", "b"]) == 1
    assert "Gere a imagem de novo" in capsys.readouterr().err


def test_visor_lista_e_serve_arquivos(tmp_path, boneco, monkeypatch):
    p = _projeto(tmp_path, boneco)
    monkeypatch.chdir(p)
    cli.main(["novo", "boneco", "--altura", "44"])
    Image.fromarray(np.ascontiguousarray(boneco)).save(p / "assets" / "boneco" / "gerada.png")
    cli.main(["ler", "boneco"])
    srv = servidor.criar(p, 0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        dados = json.loads(urllib.request.urlopen(base + "/api/assets").read())
        a = dados["assets"][0]
        assert a["nome"] == "boneco" and set(a["arte"]) == {"frente", "lado", "costas"}
        png = urllib.request.urlopen(f"{base}/arq/boneco/{a['arte']['frente']}").read()
        assert png[:4] == b"\x89PNG"
        assert b"horys" in urllib.request.urlopen(base + "/").read()
        try:
            urllib.request.urlopen(base + "/arq/boneco/../../jogo.json")
            assert False, "não pode sair de assets/"
        except urllib.error.HTTPError as e:
            assert e.code == 404
    finally:
        srv.shutdown()
        srv.server_close()
