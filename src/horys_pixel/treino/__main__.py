"""CLI do treino: ``python -m horys_pixel.treino <comando>``.

Comandos: gpu, perfil, instalar, preparar, configurar, treinar, avaliar, notas, promover, gerar.
Tudo que baixa, treina ou gera imagem só acontece com ``--executar``; sem ele, mostra o que faria.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import gpu, kohya, perfis
from ._comum import ErroTreino
from .alvo import AlvoTreino, de_estilo, de_pasta


def _alvo(args) -> AlvoTreino:
    if getattr(args, "estilo_dados", None):
        return de_pasta(args.estilo_dados, trigger=args.trigger)
    if getattr(args, "estilo", None):
        return de_estilo(args.estilo, trigger=args.trigger)
    raise ErroTreino("informe o estilo: --estilo-dados <pasta do estilo> ou --estilo <nome>")


def _perfil(args, obrigatorio: bool = True) -> perfis.Perfil | None:
    forcar = getattr(args, "perfil", None)
    if forcar:
        return perfis.escolher(None, forcar)
    vram = getattr(args, "vram", None)
    if vram is None:
        placa = gpu.detectar()
        vram = placa["vram_mb"] if placa else None
    p = perfis.escolher(vram)
    if p is None and obrigatorio:
        raise ErroTreino(perfis.explicar(vram) + f"\nPara gerar os arquivos mesmo assim, use --perfil ({', '.join(perfis.PERFIS)}).")
    return p


def _modo(executar: bool) -> None:
    if not executar:
        print("(simulação: nada foi baixado, treinado ou gerado; repita com --executar para valer)\n")


# ---------------------------------------------------------------- comandos


def cmd_gpu(args) -> int:
    placas = gpu.listar()
    if not placas:
        print(gpu.descrever(None))
        return 0
    for p in placas:
        print(gpu.descrever(p))
    return 0


def cmd_perfil(args) -> int:
    if args.todos:
        for p in perfis.PERFIS.values():
            print(f"{p.nome:10}  {p.descricao}  (a partir de {p.vram_min_mb} MB)")
        return 0
    vram = args.vram
    if vram is None and not args.perfil:
        placa = gpu.detectar()
        print("GPU: " + gpu.descrever(placa))
        vram = placa["vram_mb"] if placa else None
    print(perfis.explicar(vram, args.perfil))
    p = perfis.escolher(vram, args.perfil)
    if p is None:
        return 0
    print(f"\nModelo-base: {'SDXL' if p.sdxl else 'SD 1.5'}  |  script: {p.script_treino}")
    print(f"Resolução {p.resolucao} px, LoRA dim {p.network_dim}/alpha {p.network_alpha}, {p.optimizer_type}, "
          f"{p.mixed_precision}, lote {p.batch_size}, {p.max_train_epochs} épocas")
    ligados = [n for n, v in (("gradient_checkpointing", p.gradient_checkpointing), ("cache_latents", p.cache_latents),
                              ("cache_text_encoder_outputs", p.cache_text_encoder_outputs),
                              ("só U-Net", p.network_train_unet_only)) if v]
    print("Otimizações: " + ", ".join(ligados))
    est = perfis.estimar(p, 30, 7)
    print(f"Estimativa (30 imagens × 7 repetições × {est['epocas']} épocas = {est['passos']} passos): "
          f"~{est['minutos_min']}–{est['minutos_max']} min")
    for obs in p.observacoes:
        print("• " + obs)
    return 0


def cmd_instalar(args) -> int:
    _modo(args.executar)
    print(f"Destino: {kohya.raiz()}")
    if kohya.instalado() and not args.executar:
        info = kohya.info_instalacao() or {}
        print(f"Já instalado (ref {info.get('ref')}, commit {str(info.get('commit'))[:10]}, torch {info.get('torch')}).")
    passos = kohya.instalar(executar=args.executar, ref=args.ref, python_base=args.python, cuda=args.cuda)
    if not args.executar:
        for i, p in enumerate(passos, 1):
            print(f"{i}. {p.texto()}")
        print(f"\nDownload aproximado: 3 a 5 GB (torch com CUDA + dependências). Log ficará em {kohya.log_instalacao()}")
    else:
        print(f"\nInstalação concluída. Python do kohya: {kohya.python_kohya()}")
    return 0


def cmd_preparar(args) -> int:
    from .conjunto import preparar

    alvo = _alvo(args)
    resolucao = args.resolucao or _perfil(args).resolucao
    trigger = args.trigger or alvo.trigger_efetivo()
    man = preparar(
        alvo.conjunto, trigger, pasta_gosto=alvo.gosto, imagens=args.imagens or (), licenca=args.licenca,
        tipo=args.tipo, resolucao=resolucao, cor_fundo=args.fundo, margem=args.margem, repeticoes=args.repeticoes,
    )
    c = man["contagem"]
    print(f"Conjunto de '{alvo.nome}' (trigger {man['trigger']}) em {man['pasta_imagens']}")
    print(f"{c['total']} imagens ({c['gosto']} da memória de gosto, {c['usuario']} enviadas), "
          f"{c['duplicadas']} duplicadas, {c['ignoradas']} ignoradas; {man['repeticoes']} repetições, {resolucao} px")
    print("Licenças: " + ("; ".join(man["licencas"]) or "—"))
    for ign in man["ignoradas"]:
        print(f"  ignorada: {ign['fonte']} ({ign['motivo']})")
    for aviso in man["avisos"]:
        print("Aviso: " + aviso)
    print(f"Manifesto: {alvo.manifesto}")
    return 0


def cmd_configurar(args) -> int:
    from .config import configurar

    alvo = _alvo(args)
    plano = configurar(alvo, args.modelo, _perfil(args), versao=args.versao, epocas=args.epocas, seed=args.seed)
    est = plano["estimativa"]
    print(f"{plano['versao']} configurada (perfil {plano['perfil']['nome']}, trigger {plano['trigger']})")
    print(f"  dataset: {plano['dataset_toml']}\n  treino:  {plano['treino_toml']}")
    print(f"  LoRA vai sair em: {plano['arquivo_lora']}")
    print(f"  {est['passos']} passos ({est['epocas']} épocas) — estimativa ~{est['minutos_min']}–{est['minutos_max']} min")
    if not plano["modelo_base_existe"]:
        print(f"Aviso: o modelo-base ainda não existe em {plano['modelo_base']}. Baixe antes de treinar.")
    return 0


def cmd_treinar(args) -> int:
    from .executar import treinar

    _modo(args.executar)
    r = treinar(_alvo(args), args.versao, executar=args.executar, usar_accelerate=not args.sem_accelerate)
    if not args.executar:
        print(f"Treino da {r['versao']} (rodaria em {r['cwd']}):\n  {r['comando_texto']}")
        if r.get("estimativa"):
            e = r["estimativa"]
            print(f"Estimativa: {e['passos']} passos, ~{e['minutos_min']}–{e['minutos_max']} min")
        print(f"Log: {r['log']}\nInfo: {r['info']}")
        if not kohya.instalado():
            print("Aviso: o kohya ainda não está instalado (rode instalar --executar).")
    else:
        print(f"\nTreino da {r['versao']} concluído em {r['duracao_s'] / 60:.1f} min → {r['arquivo_lora']}")
    return 0


def cmd_avaliar(args) -> int:
    from .avaliar import avaliar

    _modo(args.executar)
    r = avaliar(_alvo(args), args.versao, contra=args.contra, executar=args.executar)
    print(f"Avaliação: {r['contra']} × {r['versao']}")
    for col in r["colunas"]:
        estado = "reaproveitado" if col["reaproveitado"] else ("gerado" if col["imagens"] else "a gerar")
        print(f"  [{col['rotulo']}] {len(col['itens'])} imagens ({estado}) em {col['pasta']}")
        if not col["imagens"]:
            print("    " + col["comando_texto"])
    if r["executado"]:
        print(f"Prancha: {r['prancha']}\nAvaliação: {r['avaliacao']}")
        print("Próximo passo: o revisor dá nota às duas (comando notas) e você decide (comando promover).")
    return 0


def cmd_notas(args) -> int:
    from .avaliar import registrar_notas

    if args.notas_json:
        notas = json.loads(Path(args.notas_json).read_text(encoding="utf-8"))
    elif args.nota is not None:
        notas = args.nota
    else:
        raise ErroTreino("informe --nota <0-100> ou --notas-json <arquivo>")
    reg = registrar_notas(_alvo(args), args.versao, notas, revisor=args.revisor)
    print(f"Nota da {reg['versao']}: {reg['nota']}")
    return 0


def cmd_promover(args) -> int:
    from .avaliar import promover

    r = promover(_alvo(args), args.versao, aprovado_pelo_usuario=args.aprovado)
    if r["promovido"]:
        print(f"{r['versao']} agora é a versão ativa (nota {r['ativo']['nota']}).")
        return 0
    print(f"{r['versao']} NÃO foi promovida:")
    for m in r["motivos"]:
        print("  - " + m)
    ativo = r.get("ativo")
    print(f"Versão ativa: {ativo['versao']} (nota {ativo.get('nota')})" if ativo else "Nenhuma versão ativa.")
    return 1


def cmd_gerar(args) -> int:
    from .gerar import gerar_referencia, planejar

    _modo(args.executar)
    alvo = _alvo(args)
    if not args.executar:
        p = planejar(alvo, args.prompt, n=args.n, tipo=args.tipo, seed=args.seed)
        print(f"Versão ativa {p['versao']} | prompt: {p['prompt']} | seeds {p['seeds'][0]}..{p['seeds'][-1]}")
        print("  " + p["comando_texto"])
        for c in p["previstas"]:
            print(f"  → {c}")
        return 0
    for c in gerar_referencia(alvo, args.prompt, n=args.n, executar=True, tipo=args.tipo, seed=args.seed):
        print(c)
    return 0


# ---------------------------------------------------------------- argparse


def _args_estilo(p: argparse.ArgumentParser) -> None:
    g = p.add_mutually_exclusive_group()
    g.add_argument("--estilo-dados", metavar="PASTA", help="pasta do estilo (com gosto/, conjunto/, lora/)")
    g.add_argument("--estilo", metavar="NOME", help="nome de um estilo instalado (usa horys_pixel.estilos)")
    p.add_argument("--trigger", help="palavra que ativa o LoRA (padrão: estilo.json, manifesto ou o nome)")


def _args_perfil(p: argparse.ArgumentParser) -> None:
    p.add_argument("--perfil", choices=list(perfis.PERFIS), help="força um perfil em vez de detectar a GPU")
    p.add_argument("--vram", type=int, metavar="MB", help="usa esta VRAM em vez de detectar")


def montar_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python -m horys_pixel.treino", description="Treino de LoRA do estilo (kohya-ss/sd-scripts).")
    sub = ap.add_subparsers(dest="comando", required=True, metavar="comando")

    p = sub.add_parser("gpu", help="mostra a GPU NVIDIA detectada")
    p.set_defaults(func=cmd_gpu)

    p = sub.add_parser("perfil", help="perfil de treino para esta placa")
    _args_perfil(p)
    p.add_argument("--todos", action="store_true", help="lista todos os perfis")
    p.set_defaults(func=cmd_perfil)

    p = sub.add_parser("instalar", help="instala o kohya-ss/sd-scripts em ~/.horys-pixel/kohya")
    p.add_argument("--executar", action="store_true", help="baixa e instala de verdade")
    p.add_argument("--ref", default=kohya.REF_PADRAO, help="ramo, tag ou commit do sd-scripts (padrão: main)")
    p.add_argument("--python", help="Python usado para criar o venv (padrão: 3.10 se houver, senão o atual)")
    p.add_argument("--cuda", help="índice do PyTorch (cu118, cu124, cu126...); padrão pelo driver")
    p.set_defaults(func=cmd_instalar)

    p = sub.add_parser("preparar", help="monta o conjunto de treino do estilo")
    _args_estilo(p)
    _args_perfil(p)
    p.add_argument("--imagens", nargs="+", metavar="CAMINHO", help="imagens ou pastas suas para somar ao conjunto")
    p.add_argument("--licenca", help="licença das --imagens (obrigatória com --imagens)")
    p.add_argument("--tipo", help="tipo de asset das --imagens (personagem, item, tile...)")
    p.add_argument("--resolucao", type=int, help="lado em px (padrão: o do perfil)")
    p.add_argument("--fundo", default="#ffffff", help="cor do fundo liso em hex, com ou sem # (padrão ffffff)")
    p.add_argument("--margem", type=int, default=2, help="margem em pixels nativos em volta do sprite")
    p.add_argument("--repeticoes", type=int, help="repetições por época (padrão: ~200 passos por época)")
    p.set_defaults(func=cmd_preparar)

    p = sub.add_parser("configurar", help="gera dataset.toml e treino.toml da próxima versão")
    _args_estilo(p)
    _args_perfil(p)
    p.add_argument("--modelo", required=True, help="modelo-base .safetensors (SD 1.5 ou SDXL, conforme o perfil)")
    p.add_argument("--versao", help="vN (padrão: a próxima)")
    p.add_argument("--epocas", type=int, help="épocas (padrão: a do perfil)")
    p.add_argument("--seed", type=int, default=42)
    p.set_defaults(func=cmd_configurar)

    p = sub.add_parser("treinar", help="treina a versão configurada")
    _args_estilo(p)
    p.add_argument("--versao", help="vN (padrão: a mais nova configurada)")
    p.add_argument("--executar", action="store_true", help="treina de verdade (usa a GPU)")
    p.add_argument("--sem-accelerate", action="store_true", help="roda o script com python direto")
    p.set_defaults(func=cmd_treinar)

    p = sub.add_parser("avaliar", help="gera o lote de teste com duas versões e a prancha comparativa")
    _args_estilo(p)
    p.add_argument("--versao", help="versão nova (padrão: a mais nova configurada)")
    p.add_argument("--contra", help="versão de comparação ou 'base' (padrão: a ativa, a anterior ou base)")
    p.add_argument("--executar", action="store_true", help="gera as imagens de verdade")
    p.set_defaults(func=cmd_avaliar)

    p = sub.add_parser("notas", help="registra a nota do revisor para uma versão")
    _args_estilo(p)
    p.add_argument("--versao", required=True)
    p.add_argument("--nota", type=float, help="nota de 0 a 100")
    p.add_argument("--notas-json", help="arquivo JSON com {critério: nota} ou {\"nota\": x, ...}")
    p.add_argument("--revisor", help="quem deu a nota (ex.: codex, claude)")
    p.set_defaults(func=cmd_notas)

    p = sub.add_parser("promover", help="torna uma versão a ativa (precisa de nota maior e do seu sim)")
    _args_estilo(p)
    p.add_argument("--versao", required=True)
    p.add_argument("--aprovado", action="store_true", help="o seu sim para trocar a versão ativa")
    p.set_defaults(func=cmd_promover)

    p = sub.add_parser("gerar", help="gera imagens de referência com a versão ativa")
    _args_estilo(p)
    p.add_argument("--prompt", required=True, help="o que gerar (em inglês funciona melhor)")
    p.add_argument("-n", type=int, default=3, help="quantas imagens (padrão 3)")
    p.add_argument("--tipo", help="tipo de asset (personagem, item, tile...)")
    p.add_argument("--seed", type=int)
    p.add_argument("--executar", action="store_true", help="gera de verdade (usa a GPU)")
    p.set_defaults(func=cmd_gerar)
    return ap


def main(argv: list[str] | None = None) -> int:
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    args = montar_parser().parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except ErroTreino as e:
        print(f"erro: {e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\ninterrompido.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
