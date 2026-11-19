"""Visor web local, só para VER: referência, arte parada, paleta, gabarito e as animações tocando por direção.
Nada é editado por aqui; aprovar é pelo terminal (horys aprovar). Ouve só em 127.0.0.1.

GET /                 a página
GET /api/assets       tudo de cada asset (o que existe, aprovações, relatórios)
GET /api/versao       maior data de modificação em assets/ (a página recarrega quando muda)
GET /arq/<asset>/...  um arquivo de dentro de assets/<asset>/
"""
from __future__ import annotations

import json
import mimetypes
import os
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from .. import aprovacao as AP
from .. import asset as AS
from .. import jogo as J

WEB = Path(__file__).with_name("index.html")


def _json(caminho: Path):
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _rel(a: AS.Asset, p: Path) -> str | None:
    return str(p.relative_to(a.pasta)).replace("\\", "/") if p.exists() else None


def _animacao(a: AS.Asset, sub: str) -> dict | None:
    pasta = a.saida / sub
    pos = _json(pasta / "pos.json")
    if not pos:
        return None
    estados = []
    for est, e in pos.get("estados", {}).items():
        if (pasta / f"{est}.png").exists():
            estados.append({"nome": est, "acao": e["acao"], "direcao": e["direcao"], "quadros": e["quadros"],
                            "ms": e["ms"], "png": f"saida/{sub}/{est}.png"})
    return {"estados": estados, "portoes": _json(pasta / "portoes.json"),
            "prancha": _rel(a, pasta / "prancha.png"), "camera": pos.get("camera")}


def resumo(raiz: Path) -> dict:
    jogo = J.carregar(raiz)
    out = []
    for nome in AS.listar(raiz):
        try:
            a = AS.abrir(nome, raiz)
        except (OSError, ValueError):
            continue
        out.append({
            "nome": a.nome, "tipo": a.cfg.get("tipo"), "descricao": a.cfg.get("descricao"), "alvo_px": a.alvo_px(jogo),
            "gerada": _rel(a, a.pasta / "gerada.png"), "referencia": _rel(a, a.pasta / "referencia.png"),
            "arte": {n: _rel(a, a.arte / f"{n}.png") for n in ("frente", "lado", "costas") if (a.arte / f"{n}.png").exists()},
            "leitura": _json(a.arte / "leitura.json"),
            "paleta": _json(a.paleta), "paleta_png": _rel(a, a.pasta / "paleta.png"),
            "aprovacoes": AP.estado(a.pasta),
            "gabarito": _json(a.saida / "gabarito" / "gabarito.json"),
            "gabarito_png": _rel(a, a.saida / "gabarito" / "gabarito.png"),
            "animacao": _animacao(a, "animacao"), "previa": _animacao(a, "previa"),
        })
    return {"jogo": {k: jogo[k] for k in ("quadro", "px_por_metro", "altura_humano_px", "angulo", "direcoes")},
            "assets": out}


def versao(raiz: Path) -> float:
    base = AS.pasta_assets(raiz)
    m = 0.0
    for d, _, arqs in os.walk(base):
        for f in arqs:
            try:
                m = max(m, os.path.getmtime(os.path.join(d, f)))
            except OSError:
                pass
    return m


def criar(raiz: Path, porta: int = 8770) -> ThreadingHTTPServer:
    raiz = Path(raiz).resolve()
    base = AS.pasta_assets(raiz).resolve()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _envia(self, codigo: int, corpo: bytes, tipo: str):
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def do_GET(self):
            u = urlparse(self.path)
            caminho = unquote(u.path)
            try:
                if caminho in ("/", "/index.html"):
                    return self._envia(200, WEB.read_bytes(), "text/html; charset=utf-8")
                if caminho == "/api/assets":
                    return self._envia(200, json.dumps(resumo(raiz), ensure_ascii=False).encode("utf-8"),
                                       "application/json; charset=utf-8")
                if caminho == "/api/versao":
                    return self._envia(200, json.dumps({"v": versao(raiz)}).encode(), "application/json")
                if caminho.startswith("/arq/"):
                    alvo = (base / caminho[len("/arq/"):]).resolve()
                    if base not in alvo.parents or not alvo.is_file():
                        return self._envia(404, b"nao encontrado", "text/plain")
                    tipo = mimetypes.guess_type(alvo.name)[0] or "application/octet-stream"
                    return self._envia(200, alvo.read_bytes(), tipo)
                return self._envia(404, b"nao encontrado", "text/plain")
            except Exception as e:  # noqa: BLE001  o visor nunca cai por um asset quebrado
                return self._envia(500, str(e).encode("utf-8"), "text/plain; charset=utf-8")

    return ThreadingHTTPServer(("127.0.0.1", porta), H)


def servir(raiz: Path, porta: int = 8770, abrir: bool = True) -> None:
    srv = criar(raiz, porta)
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    print(f"visor em {url}  (Ctrl+C para parar)")
    if abrir:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
