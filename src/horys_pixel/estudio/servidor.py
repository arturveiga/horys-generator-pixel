"""Horys Estúdio: interface local (estilo Noct) para ver tudo agrupado, riscar na imagem, mandar pedidos ao chat,
aprovar/reprovar, ajustar a paleta (recolor) e disparar o render do Blender.

Servidor só com a biblioteca padrão, em 127.0.0.1, com token por sessão (toda chamada /api e /arquivo exige o token;
a página recebe o token pela URL). Lê e serve só arquivos dentro das raízes (preferência 'estudio_raizes' ou o
padrão: art-src, saida e comparacao do repo, a pasta de aprovados e os pedidos do Estúdio).

uso: horys estudio [--porta 8765] [--sem-navegador] [--app]
"""
from __future__ import annotations

import json
import mimetypes
import os
import secrets
import threading
import time
import traceback
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .. import config
from . import pedidos as PD

WEB = Path(__file__).with_name("web")
REPO = Path(__file__).resolve().parents[3]
IMAGENS = {".png", ".gif", ".jpg", ".jpeg", ".webp"}
MODELOS = {".glb", ".gltf"}
mimetypes.add_type("model/gltf-binary", ".glb")
mimetypes.add_type("model/gltf+json", ".gltf")
IGNORAR = {".git", "__pycache__", ".venv", "node_modules", "_aseprite", "_calibrar"}
TOKEN = secrets.token_urlsafe(18)
JOBS: dict[str, dict] = {}


def raizes() -> list[Path]:
    from .. import aprovados
    pref = config.preferencias().get("estudio_raizes")
    if pref:
        base = [Path(p) for p in pref]
    else:
        base = [REPO / "art-src", REPO / "saida", REPO / "comparacao", aprovados.pasta(), PD.pasta()]
    return [p.resolve() for p in base if p.exists()]


def seguro(caminho: str) -> Path:
    p = Path(caminho).resolve()
    for r in raizes():
        try:
            p.relative_to(r)
            return p
        except ValueError:
            continue
    raise PermissionError(f"fora das raízes do Estúdio: {caminho}")


# ------------------------------------------------------------------ catálogo


def _conta(p: Path) -> int:
    try:
        return sum(1 for f in p.iterdir() if f.suffix.lower() in IMAGENS | MODELOS)
    except OSError:
        return 0


def arvore(p: Path, prof: int = 0) -> dict:
    filhos = []
    if prof < 6:
        try:
            for d in sorted(p.iterdir(), key=lambda x: x.name.lower()):
                if d.is_dir() and d.name not in IGNORAR and not d.name.startswith("."):
                    n = arvore(d, prof + 1)
                    if n["total"] > 0:
                        filhos.append(n)
        except OSError:
            pass
    n_aqui = _conta(p)
    tipo = "blender" if (p / "_render" / "manifesto.json").exists() else ("pedido" if (p / "pedido.json").exists() else "pasta")
    return {"nome": p.name, "caminho": str(p), "imagens": n_aqui, "total": n_aqui + sum(f["total"] for f in filhos),
            "filhos": filhos, "tipo": tipo, "mtime": _mtime(p)}


def _mtime(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except OSError:
        return 0.0


def _folha(png: Path) -> dict | None:
    js = png.with_suffix(".json")
    if not js.exists():
        return None
    try:
        d = json.loads(js.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    fr = d.get("frames")
    if fr is None:
        return None
    lista = list(fr.values()) if isinstance(fr, dict) else fr
    quadros = []
    for f in lista:
        r = f.get("frame") or {}
        quadros.append({"x": r.get("x", 0), "y": r.get("y", 0), "w": r.get("w", 0), "h": r.get("h", 0),
                        "ms": f.get("duration", 100)})
    tags = (d.get("meta") or {}).get("frameTags") or []
    return {"quadros": quadros, "tags": tags} if quadros else None


def _subir(p: Path, nome: str, niveis: int = 3) -> Path | None:
    for q in [p] + list(p.parents)[:niveis]:
        for c in q.glob(nome):
            return c
    return None


def pasta_info(p: Path) -> dict:
    from .. import aprovados
    from PIL import Image
    itens = []
    for f in sorted(p.iterdir(), key=lambda x: x.name.lower()):
        if f.suffix.lower() not in IMAGENS or not f.is_file():
            continue
        it = {"nome": f.name, "caminho": str(f), "mtime": _mtime(f), "estado": aprovados.estado(f)}
        try:
            with Image.open(f) as im:
                it["w"], it["h"] = im.size
                it["quadros_gif"] = getattr(im, "n_frames", 1)
        except OSError:
            continue
        folha = _folha(f) if f.suffix.lower() == ".png" else None
        if folha:
            it["folha"] = folha
        it["tipo"] = "folha" if folha else ("gif" if f.suffix.lower() == ".gif" else "imagem")
        itens.append(it)
    for f in sorted(p.iterdir(), key=lambda x: x.name.lower()):
        if f.suffix.lower() in MODELOS and f.is_file():
            vistas = next((v for v in (p / "vistas.png", p / (f.stem + "_vistas.png")) if v.exists()), None)
            itens.insert(0, {"nome": f.name, "caminho": str(f), "mtime": _mtime(f), "tipo": "modelo",
                             "estado": aprovados.estado(f), "miniatura": str(vistas) if vistas else None})
    info = {"caminho": str(p), "itens": itens}
    for nome in ("pos.json", "pedido.json", "pasta_praticas.json"):
        if (p / nome).exists():
            try:
                info[nome.split(".")[0]] = json.loads((p / nome).read_text(encoding="utf-8"))
            except ValueError:
                pass
    pal = p / "_render" / "paleta.json"
    if pal.exists():
        info["paleta"] = {"caminho": str(pal), "dados": json.loads(pal.read_text(encoding="utf-8"))}
        info["saida_blender"] = str(p)
    cfg = None
    for c in [p, *list(p.parents)[:3]]:
        for j in c.glob("*.json"):
            try:
                d = json.loads(j.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(d, dict) and "blend" in d and "rig" in d:
                cfg = j
                break
        if cfg:
            break
    if cfg:
        info["config_blender"] = str(cfg)
    return info


# ------------------------------------------------------------------ ações


def _job(nome: str, fn, *args) -> str:
    i = f"{nome}-{int(time.time())}-{secrets.token_hex(2)}"
    JOBS[i] = {"id": i, "nome": nome, "estado": "rodando", "inicio": time.time()}

    def rodar():
        try:
            JOBS[i]["resultado"] = fn(*args)
            JOBS[i]["estado"] = "ok"
        except Exception as e:      # noqa: BLE001
            JOBS[i]["estado"] = "erro"
            JOBS[i]["erro"] = f"{type(e).__name__}: {e}"
            JOBS[i]["trace"] = traceback.format_exc()[-2000:]
        JOBS[i]["fim"] = time.time()
    threading.Thread(target=rodar, daemon=True).start()
    return i


def acao_blender(cfg_path: str, saida: str, previa: bool) -> dict:
    from .. import blender as B
    from .. import travas as T
    from ..blender import pos
    cfg = B.ler_config(cfg_path)
    if not previa:
        T.exigir_aprovado(cfg["paleta"], "a paleta")
    pal = json.loads(Path(cfg["paleta"]).read_text(encoding="utf-8"))
    r = B.rodar(cfg, pal, saida, previa=previa)
    if not r["ok"]:
        raise RuntimeError("o Blender falhou:\n" + r["log"][-1500:])
    rel = pos.processar(saida, pal, cfg)
    return {"saida": saida, "prancha": rel.get("prancha"), "avisos": rel.get("avisos")}


def acao_recolor(saida: str, nova: dict, cfg_path: str | None) -> dict:
    from .. import blender as B
    from ..blender import pos
    s = Path(saida)
    velha = json.loads((s / "_render" / "paleta.json").read_text(encoding="utf-8"))
    cfg = B.ler_config(cfg_path) if cfg_path else {"contorno": "fora"}
    mapa = pos.mapa_recolor(velha, nova)
    (s / "paleta_editada.json").write_text(json.dumps(nova, ensure_ascii=False, indent=1), encoding="utf-8")
    rel = pos.processar(s, velha, cfg, mapa)
    return {"trocadas": len(mapa), "prancha": rel.get("prancha"), "paleta_editada": str(s / "paleta_editada.json")}


def acao_praticas(caminho: str) -> dict:
    """Boas práticas (docs/boas-praticas.md) da imagem ou folha: as da sequência + as do 1º quadro, sem 'onde'."""
    from .. import boas_praticas as BP
    r = BP.checar_caminho(caminho)
    d = json.loads(Path(r["json"]).read_text(encoding="utf-8"))
    res = [x for sq in d.get("sequencias") or [] for x in sq.get("resultados") or []]
    q0 = (d.get("quadros") or [[]])[0]
    vistos = {x["id"] for x in res}
    res += [x for x in (q0 if isinstance(q0, list) else []) if x["id"] not in vistos]
    for x in res:
        x.pop("onde", None)
    res.sort(key=lambda x: (x.get("passa") is not False, x["id"]))
    return {"resultados": res, "overlay": r.get("png"), "resumo": d.get("resumo")}


# ------------------------------------------------------------------ HTTP


class Manipulador(BaseHTTPRequestHandler):
    server_version = "HorysEstudio/1"

    def log_message(self, fmt, *args):
        pass

    def _token_ok(self, q) -> bool:
        t = self.headers.get("X-Horys-Token") or (q.get("t") or [""])[0]
        return secrets.compare_digest(t, TOKEN)

    def _json(self, dados, status=HTTPStatus.OK):
        corpo = json.dumps(dados, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def _arquivo(self, p: Path, tipo: str | None = None):
        dados = p.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", tipo or mimetypes.guess_type(p.name)[0] or "application/octet-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        try:
            if u.path in ("/", "/index.html"):
                if not self._token_ok(q):
                    return self._json({"erro": "abra pela URL com o token (horys estudio)"}, HTTPStatus.FORBIDDEN)
                html = (WEB / "index.html").read_text(encoding="utf-8").replace("__TOKEN__", TOKEN)
                corpo = html.encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                return self.wfile.write(corpo)
            if u.path.startswith("/static/"):
                nome = u.path[len("/static/"):]
                p = (WEB / nome).resolve()
                if p.parent != WEB.resolve() or not p.is_file():
                    return self._json({"erro": "não existe"}, HTTPStatus.NOT_FOUND)
                return self._arquivo(p)
            if not self._token_ok(q):
                return self._json({"erro": "token"}, HTTPStatus.FORBIDDEN)
            if u.path == "/arquivo":
                return self._arquivo(seguro(q["p"][0]))
            if u.path == "/api/arvore":
                return self._json({"raizes": [arvore(r) for r in raizes()]})
            if u.path == "/api/pasta":
                return self._json(pasta_info(seguro(q["p"][0])))
            if u.path == "/api/pedidos":
                return self._json({"pedidos": PD.listar((q.get("estado") or [None])[0])})
            if u.path == "/api/jobs":
                return self._json({"jobs": sorted(JOBS.values(), key=lambda j: -j["inicio"])[:20]})
            if u.path == "/api/aprovados":
                from .. import aprovados
                return self._json({"pasta": str(aprovados.pasta()), "lista": aprovados.listar()[-200:]})
            return self._json({"erro": "rota"}, HTTPStatus.NOT_FOUND)
        except PermissionError as e:
            return self._json({"erro": str(e)}, HTTPStatus.FORBIDDEN)
        except (KeyError, FileNotFoundError, ValueError) as e:
            return self._json({"erro": str(e)}, HTTPStatus.BAD_REQUEST)

    def do_POST(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if not self._token_ok(q):
            return self._json({"erro": "token"}, HTTPStatus.FORBIDDEN)
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if n > 40 * 2 ** 20:
                return self._json({"erro": "grande demais"}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            a = json.loads(self.rfile.read(n) or b"{}")
            if u.path == "/api/pedido":
                if a.get("asset"):
                    seguro(a["asset"])
                p = PD.criar(a.get("nota", ""), a.get("asset", ""), a.get("quadro"), a.get("marcas"),
                             a.get("anotado"), a.get("original"), {"zoom": a.get("zoom"), "modo": a.get("modo", "chat")},
                             a.get("vistas"))
                if a.get("modo") == "motor":
                    p["job"] = _job("motor", rodar_motor, p["id"])
                return self._json(p)
            if u.path == "/api/abrir_blender":
                return self._json(abrir_no_blender(str(seguro(a["caminho"]))))
            if u.path == "/api/veredito":
                from .. import aprovados
                it = aprovados.registrar(seguro(a["caminho"]), a.get("veredito", "aprovado"),
                                         a.get("comentario", ""), "estudio", a.get("grupo") or None)
                return self._json(it)
            if u.path == "/api/pedido/estado":
                return self._json(PD.responder(a["id"], a.get("texto", "(pelo Estúdio)"), a.get("estado", "descartado")))
            if u.path == "/api/blender":
                seguro(a["saida"]) if Path(a["saida"]).exists() else seguro(str(Path(a["saida"]).parent))
                return self._json({"job": _job("blender", acao_blender, str(seguro(a["config"])), a["saida"],
                                               bool(a.get("previa", True)))})
            if u.path == "/api/recolor":
                return self._json({"job": _job("recolor", acao_recolor, str(seguro(a["saida"])), a["paleta"],
                                               a.get("config"))})
            if u.path == "/api/praticas":
                return self._json({"job": _job("praticas", acao_praticas, str(seguro(a["caminho"])))})
            return self._json({"erro": "rota"}, HTTPStatus.NOT_FOUND)
        except PermissionError as e:
            return self._json({"erro": str(e)}, HTTPStatus.FORBIDDEN)
        except (KeyError, FileNotFoundError, ValueError) as e:
            return self._json({"erro": str(e)}, HTTPStatus.BAD_REQUEST)


def blend_do_modelo(caminho: str) -> Path | None:
    p = Path(caminho)
    if p.suffix.lower() == ".blend":
        return p
    cand = p.with_suffix(".blend")
    return cand if cand.exists() else next(iter(sorted(p.parent.glob("*.blend"))), None)


def abrir_no_blender(caminho: str) -> dict:
    """Abre o .blend do modelo (mesmo nome do .glb, ou o .blend da pasta) no Blender com janela."""
    import subprocess
    from .. import blender as B
    blend = blend_do_modelo(caminho)
    if blend is None:
        raise FileNotFoundError("não achei o .blend deste modelo")
    exe = B.achar_blender()
    if not exe:
        raise FileNotFoundError("Blender não encontrado (preferência 'blender')")
    subprocess.Popen([exe, str(blend)])
    return {"blend": str(blend)}


def rodar_motor(pedido_id: str) -> dict:
    """Modo 'motor': o pedido vai direto para o Claude sem terminal (o mesmo motor dos pedidos do Aseprite)."""
    import asyncio
    from ..daemon import motores
    p = PD.ler(pedido_id)
    prompt = (f"Pedido do Horys Estúdio {p['id']} (o Artur riscou e escreveu na interface).\n"
              f"Asset: {p.get('asset')}\nQuadro: {p.get('quadro')}\nNota: {p['nota']}\n"
              f"Imagem com os riscos: {p.get('anotado')}\nMarcas (em pixels do sprite): {json.dumps(p.get('marcas'))}\n"
              "Leia a imagem anotada, faça a mudança pedida seguindo skills/horys-base-e-pele/SKILL.md e as boas "
              "práticas (docs/boas-praticas.md), e no fim chame horys_estudio_responder com o id, um resumo e o "
              "caminho da imagem nova.")
    PD.responder(pedido_id, "motor começou", "em_andamento")
    r = asyncio.run(motores.rodar("claude", prompt, PD.pasta() / pedido_id, nome_log="motor"))
    p = PD.ler(pedido_id)
    if p["estado"] == "em_andamento":
        PD.responder(pedido_id, (r.get("texto") or "motor terminou")[-2000:], "feito" if r["codigo"] == 0 else "pendente")
    return {"codigo": r["codigo"]}


_SERVIDOR: dict = {}


def iniciar(porta: int = 0, em_thread: bool = True) -> str:
    """Sobe o servidor (uma vez por processo) e devolve a URL com o token."""
    if _SERVIDOR.get("url"):
        return _SERVIDOR["url"]
    porta = porta or int(config.preferencias().get("estudio_porta", 8765))
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", porta), Manipulador)
    except OSError:
        srv = ThreadingHTTPServer(("127.0.0.1", 0), Manipulador)
    url = f"http://127.0.0.1:{srv.server_address[1]}/?t={TOKEN}"
    _SERVIDOR.update(url=url, srv=srv)
    (config.pasta("estudio") / "url.txt").write_text(url, encoding="utf-8")
    if em_thread:
        threading.Thread(target=srv.serve_forever, daemon=True).start()
    return url


def abrir_navegador(url: str, app: bool = False):
    if app and os.name == "nt":
        for exe in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                    r"C:\Program Files\Google\Chrome\Application\chrome.exe"):
            if Path(exe).exists():
                import subprocess
                subprocess.Popen([exe, f"--app={url}", "--window-size=1500,950"])
                return
    webbrowser.open(url)


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="horys estudio")
    ap.add_argument("acao", nargs="?", default="abrir", choices=["abrir", "pendentes"])
    ap.add_argument("--porta", type=int, default=0)
    ap.add_argument("--sem-navegador", action="store_true")
    ap.add_argument("--app", action="store_true", help="janela de app (Edge/Chrome --app), sem barra do navegador")
    a = ap.parse_args(argv)
    if a.acao == "pendentes":
        print(PD.resumo_para_hook())
        return 0
    url = iniciar(a.porta, em_thread=False)
    print(f"Horys Estúdio em {url}\n(Ctrl+C para fechar)")
    if not a.sem_navegador:
        abrir_navegador(url, a.app)
    try:
        _SERVIDOR["srv"].serve_forever()
    except KeyboardInterrupt:
        pass
    return 0
