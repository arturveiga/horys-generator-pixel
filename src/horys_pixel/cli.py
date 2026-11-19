"""horys: linha de comando do fluxo. A ordem é a do comousar.md.

  horys novo <asset> [--tipo humanoide] [--altura 40] [--descricao "..."]
  horys prompt <asset>                  texto para o gerador de imagem (salva em assets/<asset>/prompt.txt)
  horys ler <asset> [--imagem x.png]    imagem do gerador -> arte parada 1x
  horys paleta <asset> [--materiais 5]  propõe a paleta a partir da arte
  horys aprovar <asset> arte|paleta [--comentario "..."]
  horys inspecionar <asset>             peças, caixas e pivôs sugeridos do .blend
  horys modelar <asset>                 modelo 3D esculpido das vistas aprovadas (casco visual)
horys gabarito <asset>                render parado do 3D x arte aprovada
  horys animar <asset> [--previa]       ações × direções -> pós -> portões
  horys exportar <asset> <pasta>        folhas para o jogo (só com portões ok)
  horys visor [--porta 8770]            página local só para ver
  horys estado [<asset>]                o que falta em cada asset
"""
from __future__ import annotations

import argparse
import json
import sys

from . import aprovacao as AP
from . import asset as AS
from . import blender as B
from . import fluxo as F
from . import jogo as J
from . import leitura as L
from . import prompt as PR


def _imprimir_lista(titulo: str, itens: list[str]) -> None:
    if itens:
        print(titulo)
        for i in itens:
            print("  -", i)


def cmd_novo(a):
    x = AS.novo(a.asset, tipo=a.tipo, altura_px=a.altura, descricao=a.descricao or "")
    print(f"criado {x.pasta}. Próximo: horys prompt {x.nome}")


def cmd_prompt(a):
    x = AS.abrir(a.asset)
    txt = PR.gerar(x, J.carregar(x.pasta))
    (x.pasta / "prompt.txt").write_text(txt, encoding="utf-8")
    print(txt)
    print(f"\n(salvo em {x.pasta / 'prompt.txt'}; a imagem gerada vai para {x.pasta / 'gerada.png'})")


def cmd_ler(a):
    x = AS.abrir(a.asset)
    rel = F.ler_arte(x, a.imagem, vista=a.vista)
    print(f"arte lida: {rel['altura']} px de altura ({rel['modo']}, bloco {rel['bloco']}), vistas {rel['vistas']}, "
          f"{len(rel['cores'])} cores. Veja no visor e, se o Artur aprovar: horys aprovar {x.nome} arte")
    _imprimir_lista("avisos:", rel.get("avisos", []))


def cmd_paleta(a):
    x = AS.abrir(a.asset)
    pal = F.propor_paleta(x, a.materiais)
    print(f"paleta: {len(pal['cores'])} cores, tinta {pal['tinta']}, famílias {list(pal['familias'])} -> "
          f"{x.paleta}. Renomeie as famílias se quiser e aprove: horys aprovar {x.nome} paleta")
    _imprimir_lista("avisos:", pal.get("avisos", []))


def cmd_aprovar(a):
    x = AS.abrir(a.asset)
    arquivos = {"arte": "arte/folha.png", "paleta": "paleta.json"}
    if a.etapa not in arquivos:
        raise SystemExit("etapa: arte | paleta")
    d = AP.aprovar(x.pasta, a.etapa, arquivos[a.etapa], comentario=a.comentario or "")
    print(f"{a.etapa} aprovada ({d['arquivo']}, {d['quando']})")


def cmd_inspecionar(a):
    x = AS.abrir(a.asset)
    print(json.dumps(B.inspecionar(x.blend), ensure_ascii=False, indent=1))


def cmd_modelar(a):
    x = AS.abrir(a.asset)
    r = F.modelar(x)
    print(f"modelo do casco: {r['voxels']} voxels, {r['pecas']} peças -> {r['blend']}")
    print("silhueta do casco x arte:", ", ".join(f"{k} {v:.0%}" for k, v in r["iou"].items()))
    print(f"Próximo: horys gabarito {a.asset}")


def cmd_gabarito(a):
    x = AS.abrir(a.asset)
    g = F.gabarito(x)
    for v, r in g["vistas"].items():
        print(f"  {v}: silhueta {r['iou']:.0%}, materiais {r['familia']:.0%}, altura render/arte "
              f"{r['altura_render']}/{r['altura_arte']}{' (espelhado)' if r['espelhado'] else ''}")
    print("GABARITO:", "PASSOU" if g["ok"] else "NÃO PASSOU", "->", x.saida / "gabarito" / "gabarito.png")
    _imprimir_lista("falhas:", g["falhas"])
    return 0 if g["ok"] else 2


def cmd_animar(a):
    x = AS.abrir(a.asset)
    p = F.animar(x, previa=a.previa)
    print("PORTÕES:", "OK" if p["ok"] else "BLOQUEADO", "->", x.saida / ("previa" if a.previa else "animacao"))
    _imprimir_lista("falhas:", p["falhas"])
    _imprimir_lista("avisos:", p["avisos"])
    return 0 if p["ok"] else 2


def cmd_exportar(a):
    x = AS.abrir(a.asset)
    feitos = F.exportar(x, a.pasta)
    print(f"{len(feitos)} arquivos em {a.pasta}")


def cmd_visor(a):
    from .visor import servidor
    servidor.servir(J.raiz(), a.porta, abrir=not a.sem_navegador)


def cmd_estado(a):
    nomes = [a.asset] if a.asset else AS.listar()
    if not nomes:
        print("nenhum asset (horys novo <nome>)")
    for n in nomes:
        x = AS.abrir(n)
        ap = AP.estado(x.pasta)
        passos = [
            ("gerada.png", (x.pasta / "gerada.png").exists()),
            ("arte lida", (x.arte / "folha.png").exists()),
            ("arte aprovada", bool(ap.get("arte", {}).get("ok"))),
            ("paleta aprovada", bool(ap.get("paleta", {}).get("ok"))),
            ("modelo .blend", x.blend.exists()),
            ("gabarito ok", F.gabarito_valido(x)[0] if x.blend.exists() else False),
            ("portões ok", bool((F._ler_json(x.saida / "animacao" / "portoes.json") or {}).get("ok"))),
        ]
        print(f"{n}: " + " · ".join(f"{'✓' if ok else '✗'} {p}" for p, ok in passos))


def main(argv=None) -> int:
    for fluxo_saida in (sys.stdout, sys.stderr):          # console do Windows (cp1252) não quebra com acento ou ✓
        try:
            fluxo_saida.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(prog="horys", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("novo"); p.add_argument("asset"); p.add_argument("--tipo", default="humanoide")
    p.add_argument("--altura", type=int); p.add_argument("--descricao"); p.set_defaults(f=cmd_novo)
    p = sub.add_parser("prompt"); p.add_argument("asset"); p.set_defaults(f=cmd_prompt)
    p = sub.add_parser("ler"); p.add_argument("asset"); p.add_argument("--imagem")
    p.add_argument("--vista", choices=["frente", "lado", "costas"], help="troca só essa vista pela da --imagem"); p.set_defaults(f=cmd_ler)
    p = sub.add_parser("paleta"); p.add_argument("asset"); p.add_argument("--materiais", type=int, default=5)
    p.set_defaults(f=cmd_paleta)
    p = sub.add_parser("aprovar"); p.add_argument("asset"); p.add_argument("etapa"); p.add_argument("--comentario")
    p.set_defaults(f=cmd_aprovar)
    p = sub.add_parser("inspecionar"); p.add_argument("asset"); p.set_defaults(f=cmd_inspecionar)
    p = sub.add_parser("modelar"); p.add_argument("asset"); p.set_defaults(f=cmd_modelar)
    p = sub.add_parser("gabarito"); p.add_argument("asset"); p.set_defaults(f=cmd_gabarito)
    p = sub.add_parser("animar"); p.add_argument("asset"); p.add_argument("--previa", action="store_true")
    p.set_defaults(f=cmd_animar)
    p = sub.add_parser("exportar"); p.add_argument("asset"); p.add_argument("pasta"); p.set_defaults(f=cmd_exportar)
    p = sub.add_parser("visor"); p.add_argument("--porta", type=int, default=8770)
    p.add_argument("--sem-navegador", action="store_true"); p.set_defaults(f=cmd_visor)
    p = sub.add_parser("estado"); p.add_argument("asset", nargs="?"); p.set_defaults(f=cmd_estado)
    a = ap.parse_args(argv)
    try:
        return int(a.f(a) or 0)
    except (F.ErroFluxo, L.ErroLeitura, AP.Travado, B.ErroBlender, FileNotFoundError, FileExistsError, ValueError) as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
