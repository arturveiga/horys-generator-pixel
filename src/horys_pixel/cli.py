"""horys: linha de comando do horys-pixel.

  horys daemon                    sobe o horysd (normalmente a ponte MCP já sobe sozinha)
  horys status                    horysd, Aseprite e sprite ativo
  horys token [--novo]            mostra (ou troca) o token de pareamento — não cole em chat
  horys instalar [--tudo] [--simular] [--extensao] [--confiar] [--claude] [--codex] [--skills] [--inicializacao]
  horys estilos [nome]            pacotes de estilo
  horys estilo-novo NOME IMG...   cria um pacote analisando imagens (o assistente completo roda pelo Aseprite)
  horys ferramenta NOME [JSON]    chama qualquer ferramenta MCP (para testar)
  horys pedido "DESCRIÇÃO" [--motor claude|codex] [--estilo E] [--tipo T] [--estados idle,andar]
  horys extensao                  gera dist/horys-pixel.aseprite-extension
  horys treino ...                repassa para python -m horys_pixel.treino
"""
from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path

from . import config


def _chamar(nome: str, args: dict) -> int:
    from .mcp_ponte import Daemon

    async def ir():
        d = Daemon()
        try:
            r = await d.enviar({"t": "chamar", "ferramenta": nome, "args": args})
        finally:
            await d.fechar()
        for c in r.get("conteudo") or []:
            if c.get("type") == "text":
                print(c["text"])
            elif c.get("type") == "image":
                print(f"[imagem PNG, {len(c['data']) * 3 // 4} bytes]")
        return 1 if r.get("erro") else 0
    return asyncio.run(ir())


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["treino"]:
        return subprocess.call([sys.executable, "-m", "horys_pixel.treino", *argv[1:]])
    ap = argparse.ArgumentParser(prog="horys", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("daemon")
    p.add_argument("--porta", type=int, default=0)
    sub.add_parser("status")
    p = sub.add_parser("token")
    p.add_argument("--novo", action="store_true")
    p = sub.add_parser("instalar")
    for f in ("tudo", "simular", "extensao", "confiar", "claude", "codex", "skills", "inicializacao"):
        p.add_argument(f"--{f}", action="store_true")
    p.add_argument("--pasta-aseprite", default="", help="pasta de usuário do Aseprite (padrão: a do sistema)")
    p = sub.add_parser("estilos")
    p.add_argument("nome", nargs="?")
    p = sub.add_parser("estilo-novo")
    p.add_argument("nome")
    p.add_argument("imagens", nargs="+")
    p.add_argument("--autor", default="")
    p.add_argument("--licenca", default="", help="licença/origem das imagens (obrigatório para treinar depois)")
    p = sub.add_parser("ferramenta")
    p.add_argument("nome")
    p.add_argument("json", nargs="?", default="{}")
    p = sub.add_parser("pedido")
    p.add_argument("descricao")
    p.add_argument("--motor", default="")
    p.add_argument("--estilo", default="")
    p.add_argument("--tipo", default="")
    p.add_argument("--estados", default="")
    p.add_argument("--referencia", default="")
    sub.add_parser("extensao")
    a = ap.parse_args(argv)

    if a.cmd == "daemon":
        from .daemon import servidor
        return servidor.main(["--porta", str(a.porta)] if a.porta else [])
    if a.cmd == "token":
        print(config.token(novo=a.novo))
        print(f"(arquivo: {config.arquivo_token()}; a extensão lê esse arquivo sozinha)", file=sys.stderr)
        return 0
    if a.cmd == "status":
        try:
            return _chamar("horys_status", {})
        except Exception as e:
            print(f"horysd fora do ar ou recusou: {e}")
            return 2
    if a.cmd == "instalar":
        from . import instalar as I
        base = Path(a.pasta_aseprite) if a.pasta_aseprite else None
        if a.tudo:
            log = I.tudo(a.simular, a.confiar, a.inicializacao, a.codex)
        else:
            log = []
            if a.extensao:
                log += I.instalar_extensao(base, a.simular)
            if a.confiar:
                log += I.confiar_scripts(base, a.simular)
            if a.claude:
                log += I.registrar_claude(a.simular)
            if a.codex:
                log += I.registrar_codex(a.simular)
            if a.skills:
                log += I.instalar_skills_codex(a.simular)
            if a.inicializacao:
                log += I.inicio_windows(a.simular)
            if not log:
                log = ["nada escolhido: use --tudo ou as opções (veja horys instalar -h)"]
        print("\n".join(log))
        return 0
    if a.cmd == "estilos":
        from . import estilos
        if not a.nome:
            print("\n".join(estilos.listar()))
            return 0
        e = estilos.carregar(a.nome)
        print(json.dumps(e.dados, ensure_ascii=False, indent=1))
        return 0
    if a.cmd == "estilo-novo":
        from . import analise_estilo
        p = analise_estilo.criar_pacote(a.nome, a.imagens, autor=a.autor, licenca_imagens=a.licenca)
        print(f"pacote criado em {p}\nrevise o estilo.md (itens 'a confirmar') e a paleta.")
        return 0
    if a.cmd == "ferramenta":
        return _chamar(a.nome, json.loads(a.json))
    if a.cmd == "pedido":
        args = {"descricao": a.descricao}
        for k in ("motor", "estilo", "tipo", "referencia"):
            if getattr(a, k):
                args[k] = getattr(a, k)
        if a.estados:
            args["estados"] = [x.strip() for x in a.estados.split(",") if x.strip()]
        return _chamar("horys_pedido_novo", args)
    if a.cmd == "extensao":
        raiz = Path(__file__).resolve().parents[2]
        return subprocess.call([sys.executable, str(raiz / "scripts" / "build_extension.py")])
    return 0


if __name__ == "__main__":
    sys.exit(main())
