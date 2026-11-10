"""Ferramentas de estilo: o que só o horys tem (ficha, contorno e sombra do estilo, conversão, portão, revisor)."""
from __future__ import annotations

import asyncio
import base64
import json
import math
import os
import re
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

from .. import config, grade_io, pixels
from ..daemon import motores
from .desenho import ler_rgba, escrever_rgba, resumo_status
from .registro import BOOL, INT, OBJ, STR, ErroFerramenta, LISTA_STR, ferramenta, imagem, texto

SRC = Path(__file__).resolve().parents[2]


# ------------------------------------------------------------------ apoio

def _estilo(nome: str | None):
    from .. import estilos
    nome = nome or config.preferencias().get("estilo_padrao")
    try:
        return estilos.carregar(nome)
    except Exception as e:
        disponiveis = ", ".join(estilos.listar()) or "nenhum"
        raise ErroFerramenta(f"estilo '{nome}' não encontrado ({e}). Disponíveis: {disponiveis}")


def _paleta(est) -> dict:
    from .. import estilos
    return estilos.paleta(est)


def _cores_letras(est) -> dict:
    return grade_io.letras_da_paleta(_paleta(est))


def _hexes_paleta(est) -> list[str]:
    return list(dict.fromkeys(_cores_letras(est).values()))


async def _ficha(ctx) -> tuple[str, dict, dict]:
    st = await ctx.sprite_atual()
    chave = st["sprite"].get("horys_id") or st["sprite"]["arquivo"]
    f = ctx.ficha(chave)
    if not f and chave != st["sprite"]["arquivo"]:  # migração transparente de fichas antigas
        f = ctx.ficha(st["sprite"]["arquivo"])
        if f:
            ctx.salvar_ficha(chave, f)
    if not f:
        raise ErroFerramenta("este sprite não tem ficha do horys. Crie com horys_asset_novo ou defina com "
                             "horys_ficha (estilo, tipo, partes, contorno...)")
    return chave, f, st


def _partes(f: dict, st: dict) -> list[str]:
    nomes = [c["nome"] for c in st["sprite"]["camadas"]]
    if f.get("modular"):
        # asset modular: camada faltando é erro explícito (nunca se descarta parte em silêncio)
        esperadas = list(f.get("partes") or [])
        faltam = [p for p in esperadas + ["referencia"] if p not in nomes]
        if not esperadas:
            raise ErroFerramenta("asset modular sem 'partes' na ficha (use preset_partes ou horys_ficha partes=[...])")
        if faltam:
            raise ErroFerramenta("asset modular: faltam as camadas " + ", ".join(f"'{p}'" for p in faltam)
                                 + f" (o sprite tem: {', '.join(nomes)}). Recrie-as com horys_camada "
                                 "(a 'referencia' fica oculta) ou ajuste a ficha.")
        ordem_real = [n for n in nomes if n in esperadas]
        if ordem_real != esperadas:
            raise ErroFerramenta("asset modular: a ordem das camadas no Aseprite (" + ", ".join(ordem_real)
                                 + ") difere da ficha (" + ", ".join(esperadas) + "); use horys_camada acao=ordem")
        return esperadas
    partes = [p for p in f.get("partes") or [] if p in nomes]
    if not partes:
        partes = [n for n in nomes if n not in grade_io.RESERVADAS]
    return partes


def _estados(st: dict, f: dict) -> list[tuple[str, list[int], int]]:
    s = st["sprite"]
    n = len(s["quadros"])
    tags = s.get("tags") or []
    if tags:
        out = []
        for t in tags:
            idx = list(range(int(t["de"]), int(t["ate"]) + 1))
            out.append((t["nome"], idx, int(s["quadros"][idx[0]].get("ms") or 100)))
        return out
    return [(f.get("estado") or "idle", list(range(n)), int(s["quadros"][0].get("ms") or 100))]


async def _quadros_partes(ctx, partes: list[str], indices: list[int]) -> list[dict]:
    out = []
    for q in indices:
        d = {}
        for p in partes:
            d[p] = await ler_rgba(ctx, p, q)
        out.append(d)
    return out


def _env_motor(est) -> dict:
    from .. import estilos
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    env["HORYS_MOTOR_CONFIG"] = str(estilos.escrever_config_motor(est))
    return env


async def _rodar_motor(modulo: str, argumentos: list[str], est, timeout: float = 900) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(sys.executable, "-m", f"horys_pixel.motor.{modulo}", *argumentos,
                                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
                                                env=_env_motor(est))
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return 124, f"{modulo}: tempo esgotado"
    return proc.returncode, out.decode("utf-8", "replace")


def _pasta_asset(f: dict) -> Path:
    p = Path(f.get("pasta") or (config.pasta("assets") / (f.get("nome") or "asset")))
    if not config.caminho_permitido(p):
        raise ErroFerramenta(f"pasta não permitida: {p}")
    p.mkdir(parents=True, exist_ok=True)
    return p


def _proxima_versao(pasta: Path) -> str:
    ns = [int(m.group(1)) for d in pasta.glob("v*") if (m := re.fullmatch(r"v(\d+)", d.name))]
    return f"v{(max(ns) + 1) if ns else 1:02d}"


def _miniatura(caminho: Path, lado: int = 900) -> str:
    im = Image.open(caminho).convert("RGBA")
    # Nunca cria pixels lógicos de tamanhos mistos. Reduz somente por divisor inteiro exato.
    if max(im.size) > lado:
        divisor = max(2, math.ceil(max(im.size) / lado))
        if im.width % divisor == 0 and im.height % divisor == 0:
            im = im.resize((im.width // divisor, im.height // divisor), Image.NEAREST)
    return pixels.png_b64(im)


# ------------------------------------------------------------------ estilos e ficha

@ferramenta("horys_estilos", "Lista os pacotes de estilo e mostra o resumo de um ('nome'): paleta, régua, KB e "
            "notas que a skill deve ler.", {"nome": STR})
async def estilos_ferramenta(ctx, a):
    from .. import estilos
    if not a.get("nome"):
        lst = estilos.listar()
        padrao = config.preferencias().get("estilo_padrao")
        return [texto("Estilos: " + ", ".join(f"{n}{' (padrão)' if n == padrao else ''}" for n in lst))]
    est = _estilo(a["nome"])
    pal = _paleta(est)
    linhas = [f"Estilo {est.nome} v{est.versao} — {est.descricao}", f"pasta: {est.pasta}",
              f"KB: {est.kb or '—'}", f"paleta: {est.paleta} ({sum(len(r) for r in pal['rampas'].values())} cores "
              f"em {len(pal['rampas'])} rampas; contorno {pal.get('contorno')})",
              f"régua: {(est.regua or {}).get('pasta') if est.regua_disponivel else 'nenhuma (o portão usa as metas padrão)'}",
              f"motor padrão: {est.motor_padrao} · referência: {est.referencia_padrao} · trigger: {est.trigger}"]
    if est.leitura:
        linhas.append("Ler antes de desenhar: " + ", ".join(str(Path(est.kb or est.pasta) / x) for x in est.leitura))
    md = est.pasta / "estilo.md"
    if md.exists():
        linhas.append(f"bíblia do estilo: {md}")
    return [texto("\n".join(linhas))]


CAMPOS_FICHA = {"estilo": STR, "nome": STR, "tipo": STR, "partes": LISTA_STR, "contorno": STR, "cor_contorno": STR,
                "sombra": BOOL, "sem_contorno": LISTA_STR, "sem_borda": LISTA_STR, "limite_cores": INT, "ritmo": STR,
                "pasta": STR, "estado": STR, "pedido": STR, "descricao": STR,
                "modular": BOOL, "preset_partes": STR, "juncoes": {"type": "array", "items": {"type": "object"}},
                "partes_oculto": LISTA_STR, "componentes_max": {"type": "object"},
                "espessura_fina": LISTA_STR, "motivo": STR}


@ferramenta("horys_ficha", "Lê ou ajusta a ficha do sprite ativo (estilo, tipo, partes de baixo para cima, contorno "
            "auto|suave|nenhum, cor_contorno, sombra, sem_contorno [hex], sem_borda [hex], limite_cores, ritmo, pasta "
            "de saída; asset modular: modular, preset_partes, juncoes [{nome, inferior, superior, movel}], "
            "partes_oculto). Sem campos, só mostra.", CAMPOS_FICHA)
async def ficha(ctx, a):
    st = await ctx.sprite_atual()
    chave = st["sprite"].get("horys_id") or st["sprite"]["arquivo"]
    f = ctx.ficha(chave)
    mud = {k: v for k, v in a.items() if k in CAMPOS_FICHA}
    if mud:
        from .. import partes as P
        motivo = mud.pop("motivo", "")
        protegidos = {"modular", "preset_partes", "partes", "juncoes", "partes_oculto",
                      "componentes_max", "espessura_fina"}
        alterados = [k for k in protegidos if k in mud and k in f and mud[k] != f[k]]
        if alterados and not motivo.strip():
            raise ErroFerramenta("alterar contrato modular exige 'motivo': " + ", ".join(sorted(alterados)))
        if mud.get("preset_partes"):
            try:
                P.preset(mud["preset_partes"])
            except ValueError as e:
                raise ErroFerramenta(str(e))
            mud.setdefault("modular", True)
        if mud.get("modular") or f.get("modular"):
            novas = {**f, **mud}
            erros = P.validar_contratos(novas.get("partes") or [], P.contratos_da_ficha(novas)[1])
            if erros:
                raise ErroFerramenta("contratos de partes inválidos: " + "; ".join(erros))
        f.update(mud)
        if alterados:
            f.setdefault("excecoes", []).append({"campos": sorted(alterados), "motivo": motivo.strip()})
            f.pop("partes_checagem", None)
        ctx.salvar_ficha(chave, f)
    if not f:
        return [texto("sem ficha")]
    saida = json.dumps(f, ensure_ascii=False, indent=1)
    from .. import padroes
    if padroes.tipo_de(f.get("tipo")):
        tipo = padroes.tipo_de(f.get("tipo"))
        saida += "\n\npadrão de entrada do tipo '" + tipo + "':\n" + json.dumps(
            padroes.carregar(tipo), ensure_ascii=False, indent=1)
    return [texto(saida)]


@ferramenta("horys_asset_novo", """Cria o sprite de um asset pela ficha, de uma vez: quadro QxQ (padrão 192; pé no
pivô (Q/2, Q·127/192) = (96,127)), camadas 'sombra' (opacidade 77) e 'contorno' embaixo, uma camada por PARTE de baixo
para cima (padrão ['desenho']) e 'revisao' (oculta) em cima, quadros e tags por estado
(estados [{nome, quadros, ms}]), paleta do estilo travada. Desenhe só nas partes: contorno e sombra são gerados por
horys_contorno, como o portão espera. Com 'preset_partes' (ex.: 'humanoide-ferreiro') cria o asset MODULAR: as partes
do preset, a camada 'referencia' (oculta, para o desenho completo) e a ficha com modular, preset_partes, juncoes
(contratos de junção) e partes_oculto; o portão passa a exigir as partes sem erro (horys_partes_checar).""",
            {**CAMPOS_FICHA, "quadro": INT, "estados": {"type": "array"}})
async def asset_novo(ctx, a):
    from .. import partes as P
    est = _estilo(a.get("estilo"))
    Q = int(a.get("quadro") or 192)
    modular = None
    if a.get("preset_partes") or a.get("modular"):
        try:
            modular = P.campos_ficha_modular(a.get("preset_partes") or None, a.get("partes"), a.get("juncoes"))
        except ValueError as e:
            raise ErroFerramenta(str(e))
        if a.get("preset_partes") and a.get("partes") and list(a["partes"]) != modular["partes"]:
            raise ErroFerramenta("preset_partes já define as partes: não passe 'partes' diferentes (use só uma das duas)")
        if not modular["partes"]:
            raise ErroFerramenta("asset modular precisa de preset_partes ou de 'partes'")
        if a.get("partes_oculto") is not None:
            modular["partes_oculto"] = list(a["partes_oculto"])
        erros = P.validar_contratos(modular["partes"], P.juncoes_de_dicts(modular["juncoes"]))
        if erros:
            raise ErroFerramenta("contratos de partes inválidos: " + "; ".join(erros))
    partes = list(modular["partes"] if modular else a.get("partes") or ["desenho"])
    if any(p in grade_io.RESERVADAS for p in partes):
        raise ErroFerramenta(f"nomes reservados não podem ser partes: {', '.join(grade_io.RESERVADAS)}")
    estados = a.get("estados") or [{"nome": a.get("estado") or "idle", "quadros": 1, "ms": 100}]
    nome = a.get("nome") or "asset"
    st = await ctx.aseprite("sprite_novo", {"largura": Q, "altura": Q, "nome": nome})
    base = st["sprite"]["camadas"][0]["nome"]
    if base != partes[0]:
        await ctx.aseprite("camada", {"acao": "renomear", "nome": base, "novo": partes[0]})
    for ant, p in zip(partes, partes[1:]):
        await ctx.aseprite("camada", {"acao": "criar", "nome": p, "acima_de": ant})
    await ctx.aseprite("camada", {"acao": "criar", "nome": "contorno", "abaixo_de": partes[0]})
    await ctx.aseprite("camada", {"acao": "criar", "nome": "sombra", "abaixo_de": "contorno"})
    await ctx.aseprite("camada", {"acao": "propriedades", "nome": "sombra", "opacidade": 77})
    await ctx.aseprite("camada", {"acao": "criar", "nome": "revisao", "acima_de": partes[-1]})
    await ctx.aseprite("camada", {"acao": "propriedades", "nome": "revisao", "visivel": False})
    if modular:
        await ctx.aseprite("camada", {"acao": "criar", "nome": "referencia", "acima_de": partes[-1]})
        await ctx.aseprite("camada", {"acao": "propriedades", "nome": "referencia", "visivel": False})
    total =sum(int(e.get("quadros", 1)) for e in estados)
    await ctx.aseprite("quadro", {"acao": "garantir", "total": total})
    i = 0
    for e in estados:
        n = int(e.get("quadros", 1))
        for k in range(i, i + n):
            await ctx.aseprite("quadro", {"acao": "duracao", "indice": k, "ms": int(e.get("ms", 100))})
        await ctx.aseprite("tag", {"acao": "criar", "nome": e["nome"], "de": i, "ate": i + n - 1})
        i += n
    await ctx.aseprite("paleta", {"acao": "definir", "cores": _hexes_paleta(est)})
    await ctx.aseprite("camada", {"acao": "ativar", "nome": partes[-1]})
    st = await ctx.aseprite("status")
    f = {k: a[k] for k in CAMPOS_FICHA if k in a}
    f.update({"estilo": est.nome, "nome": nome, "partes": partes, "quadro": Q,
              "contorno": a.get("contorno") or "auto", "sombra": a.get("sombra", True), "tipo": a.get("tipo") or "personagem"})
    if modular:
        f.update(modular)
    hid = st["sprite"].get("horys_id") or st["sprite"]["arquivo"]
    f["_horys_id"] = hid
    f["_horys_aliases"] = [st["sprite"]["arquivo"]]
    ctx.salvar_ficha(hid, f)
    px, py = grade_io.pivo_quadro(Q)
    letras = _cores_letras(est)
    extra = ""
    if modular:
        extra = (f"\n\nAsset MODULAR ({modular['preset_partes'] or 'partes próprias'}): {len(partes)} partes, "
                 f"{len(modular['juncoes'])} junções. Desenhe a referência completa na camada oculta 'referencia', "
                 "fatie por partes (horys_partes_recortar), estenda a anatomia oculta (horys_partes_estender) e valide "
                 "com horys_partes_checar antes de animar.")
    return [texto(resumo_status(st) + extra + f"\n\nPivô do pé: ({px},{py}). Paleta do estilo (use estas letras no "
                  f"horys_pixel_map): {json.dumps(letras)}")]


@ferramenta("horys_paleta_estilo", "Põe a paleta do estilo no Aseprite e devolve as letras; com 'verificar': true "
            "conta os pixels das partes fora da paleta (por cor e camada).", {"estilo": STR, "verificar": BOOL})
async def paleta_estilo(ctx, a):
    nome = a.get("estilo")
    if not nome and ctx.ponte.conectado:
        try:
            st = await ctx.sprite_atual()
            nome = ctx.ficha(st["sprite"]["arquivo"]).get("estilo")
        except Exception:
            pass
    est = _estilo(nome)
    letras = _cores_letras(est)
    await ctx.aseprite("paleta", {"acao": "definir", "cores": list(dict.fromkeys(letras.values()))})
    if not a.get("verificar"):
        return [texto("paleta do estilo no Aseprite. Letras: " + json.dumps(letras))]
    st = await ctx.sprite_atual()
    chave = st["sprite"]["arquivo"]
    f = ctx.ficha(chave)
    permitidas = set(letras.values())
    fora = {}
    for p in _partes(f, st):
        for q in range(len(st["sprite"]["quadros"])):
            im = await ler_rgba(ctx, p, q)
            m = im[..., 3] > 0
            for c in {pixels.rgba_hex((*px, 255)) for px in im[m][:, :3]}:
                if c not in permitidas:
                    fora.setdefault(c, set()).add(p)
    if not fora:
        return [texto("todas as cores das partes estão na paleta do estilo.")]
    return [texto("fora da paleta: " + "; ".join(f"{c} em {', '.join(sorted(ps))}" for c, ps in fora.items()))]


# ------------------------------------------------------------------ contorno e sombra

@ferramenta("horys_contorno", """Gera o CONTORNO e a SOMBRA do estilo (como o grade.py: anel externo de 2 px 'auto',
1 px 'suave' ou nenhum; elipse do chão) a partir das partes, nas camadas 'contorno' e 'sombra', em todos os quadros
(ou só 'quadros'). Rode depois de mexer na silhueta; o portão recompõe do mesmo jeito.""",
            {"quadros": {"type": "array", "items": INT}})
async def contorno(ctx, a):
    chave, f, st = await _ficha(ctx)
    from ..motor import grade as G
    Q = int(st["sprite"]["largura"])
    partes = _partes(f, st)
    n = len(st["sprite"]["quadros"])
    indices = a.get("quadros") or list(range(n))
    quadros = await _quadros_partes(ctx, partes, indices)
    est = _estilo(f.get("estilo"))
    ficha_c = dict(f)
    if ficha_c.get("contorno") == "nenhum":
        ficha_c["contorno"] = "manual"           # sem anel; não mexe nas linhas internas aqui
    escritos = 0
    with tempfile.TemporaryDirectory() as tmp:
        for k, q in zip(indices, quadros):
            if not any((im[..., 3] > 0).any() for im in q.values()):
                await ctx.aseprite("limpar_camada", {"camada": "contorno", "quadro": k})
                await ctx.aseprite("limpar_camada", {"camada": "sombra", "quadro": k})
                continue
            txt, _ = grade_io.grade_de_camadas(ficha_c, partes, [q], "q", 100, Q, _cores_letras(est))
            arq = Path(tmp) / f"q{k}.grade"
            arq.write_text(txt, encoding="utf-8")
            meta, cores, qs, erros = G.ler(str(arq))
            if erros:
                raise ErroFerramenta("grade inválida: " + "; ".join(erros[:3]))
            img, _ = G.montar(meta, cores, qs[0])
            for nome, im, _op in G.camadas_rgba(meta, cores, qs[0], img)[:2]:
                escritos += await escrever_rgba(ctx, nome, k, 0, 0, np.ascontiguousarray(im))
    return [texto(f"contorno ({f.get('contorno', 'auto')}) e sombra "
                  f"({'sim' if f.get('sombra', True) else 'não'}) gerados em {len(indices)} quadro(s).")]


# ------------------------------------------------------------------ conversão e limpeza mecânica

@ferramenta("horys_converter", """Converte uma imagem de referência/conceito em pixel art do estilo, direto numa
camada: reduz pela MODA (cor mais frequente por bloco, sem borrar contornos internos) para a 'altura' pedida (com
contorno), trava a paleta do estilo e põe o pé no pivô. 'tirar_contorno': anéis do contorno do conceito a descascar
(1 para conceito com contorno grosso). É só o PONTO DE PARTIDA: depois limpe (horys_limpar, horys_afinar) e redesenhe
à mão rosto e detalhes.""",
            {"imagem": STR, "altura": INT, "camada": STR, "quadro": INT, "modo": STR, "tirar_contorno": INT,
             "fundo": STR, "nativo": BOOL, "forcar": BOOL, "motivo": STR}, ["imagem", "altura"])
def entrada_reprovada(img: Path) -> str | None:
    """None se a entrada_checagem.txt ao lado da imagem aprovou ESTA imagem; senão, o motivo."""
    txt = img.parent / "entrada_checagem.txt"
    if not txt.exists():
        return f"a imagem {img.name} não passou pelo portão de entrada (falta entrada_checagem.txt)."
    conteudo = txt.read_text(encoding="utf-8")
    linhas = conteudo.splitlines()
    if len(linhas) < 2 or Path(linhas[1].split("imagem:", 1)[-1].split("  (")[0].strip()).name != img.name:
        return f"a entrada_checagem.txt ao lado não é da imagem {img.name}."
    if "APROVADO" not in linhas[0] or "REPROVADO" in linhas[0]:
        return f"o portão de entrada reprovou {img.name} (veja entrada_checagem.txt)."
    return None


async def converter(ctx, a):
    img = Path(a["imagem"])
    if not img.exists():
        raise ErroFerramenta(f"imagem não existe: {img}")
    erro_entrada = entrada_reprovada(img)
    if erro_entrada and not (a.get("forcar") and (a.get("motivo") or "").strip()):
        raise ErroFerramenta(erro_entrada + " Rode horys_portao_entrada antes (ou, se o usuário pediu, passe "
                             "forcar: true e motivo: '<o que o usuário disse>').")
    chave, f, st = await _ficha(ctx)
    est = _estilo(f.get("estilo"))
    Q = int(st["sprite"]["largura"])
    camada = a.get("camada") or _partes(f, st)[-1]
    q = int(a.get("quadro", st["sprite"].get("quadro_ativo") or 0))
    cores = _cores_letras(est)
    with tempfile.TemporaryDirectory() as tmp:
        leg = Path(tmp) / "legenda.grade"
        leg.write_text(grade_io.legenda(f, cores, Q), encoding="utf-8")
        saida = Path(tmp) / "conv.grade"
        args = ["converter", str(img), "--legenda", str(leg), "--altura", str(int(a["altura"])), "--saida", str(saida),
                "--modo", a.get("modo") or "moda", "--tirar-contorno", str(int(a.get("tirar_contorno", 1)))]
        if a.get("fundo"):
            args += ["--fundo", a["fundo"]]
        if a.get("nativo"):
            args.append("--nativo")
        codigo, out = await _rodar_motor("conceito", args, est, 600)
        if codigo != 0 or not saida.exists():
            raise ErroFerramenta("a conversão falhou:\n" + out[-1500:])
        _, cs, linhas, pivo = grade_io.ler_grade_simples(saida)
    rgba = grade_io.rgba_de_letras(linhas, cs, Q, pivo)
    await escrever_rgba(ctx, camada, q, 0, 0, rgba, (rgba[..., 3] > 0).astype(np.uint8))
    return [texto(out.strip().splitlines()[-1] if out.strip() else "convertido") ,
            texto(f"na camada '{camada}', quadro {q}. Agora: horys_limpar → horys_afinar → silhueta, vãos, cachos e "
                  "rosto à mão → horys_contorno → horys_ver critica.")]


async def _mecanico(ctx, a, operacao: str, extra: list[str]):
    chave, f, st = await _ficha(ctx)
    est = _estilo(f.get("estilo"))
    Q = int(st["sprite"]["largura"])
    camada = a.get("camada") or _partes(f, st)[-1]
    q = int(a.get("quadro", st["sprite"].get("quadro_ativo") or 0))
    atual = await ler_rgba(ctx, camada, q)
    f = dict(f)
    f.setdefault("cor_contorno", _paleta(est).get("contorno"))
    try:
        txt, (x0, y0) = grade_io.grade_de_imagem(f, atual, _cores_letras(est), Q)
    except ValueError as e:
        raise ErroFerramenta(str(e))
    with tempfile.TemporaryDirectory() as tmp:
        ent, sai = Path(tmp) / "e.grade", Path(tmp) / "s.grade"
        ent.write_text(txt, encoding="utf-8")
        codigo, out = await _rodar_motor("conceito", [operacao, str(ent), "--saida", str(sai)] + extra, est, 300)
        if codigo != 0 or not sai.exists():
            raise ErroFerramenta(f"{operacao} falhou:\n" + out[-1500:])
        _, cs, linhas, _ = grade_io.ler_grade_simples(sai)
    novo = grade_io.rgba_de_letras(linhas, cs, Q, None, origem=(x0, y0))
    masc = ((atual[..., 3] > 0) | (novo[..., 3] > 0)).astype(np.uint8)
    n = await escrever_rgba(ctx, camada, q, 0, 0, novo, masc)
    mudou = int(np.any(atual != novo, axis=-1).sum())
    return [texto(f"{operacao}: {mudou} px mudaram em '{camada}' quadro {q}. " + (out.strip().splitlines() or [""])[-1])]


def _areas(a) -> list[str]:
    out = []
    for r in a.get("proteger_area") or []:
        out += ["--proteger-area", ",".join(str(int(v)) for v in r)]
    return out


@ferramenta("horys_limpar", "Limpeza MECÂNICA de uma camada (não cria forma): funde manchas menores que 'min' px na "
            "cor vizinha. 'proteger': hex das cores que ficam (olho, brilho); 'proteger_area': [[x0,y0,x1,y1]] em "
            "coordenadas do recorte.", {"camada": STR, "quadro": INT, "min": INT, "proteger": LISTA_STR,
                                        "proteger_area": {"type": "array"}})
async def limpar(ctx, a):
    _, f, _ = await _ficha(ctx)
    letras = {v: k for k, v in _cores_letras(_estilo(f.get("estilo"))).items()}
    prot = "".join(letras.get(h.lower(), "") for h in a.get("proteger") or [])
    extra = ["--min", str(int(a.get("min", 4)))] + (["--proteger", prot] if prot else []) + _areas(a)
    return await _mecanico(ctx, a, "limpar", extra)


@ferramenta("horys_afinar", "Limpeza MECÂNICA: afina linhas internas para 1 px e tira cor de contorno encostada no "
            "vazio (o contorno externo vem do horys_contorno).", {"camada": STR, "quadro": INT,
                                                                   "proteger_area": {"type": "array"}})
async def afinar(ctx, a):
    return await _mecanico(ctx, a, "afinar", _areas(a))


# ------------------------------------------------------------------ portão de entrada (antes da conversão)

@ferramenta("horys_portao_entrada", """PORTÃO DE ENTRADA: mede a imagem gerada (ilustração chapada) ANTES do
horys_converter. Confere fundo liso e ausente da figura, figura inteira com margem (margem_min, padrão 0.01), linha dos
pés sem sombra nem chão, escala (figura >= 3× a 'altura' alvo), grade [linhas, colunas] (uma pose por célula, alturas
±3% e chão comum) e se é chapado (grupos de cor OKLab, áreas lisas, degradê). Grava entrada_checagem.txt
(APROVADO/REPROVADO) e a prévia no tamanho final ao lado da imagem. Cada falha vem como correção citando o item do
prompt de tradução: peça a correção no mesmo chat do gerador.""",
            {"imagem": STR, "altura": INT, "grade": {"type": "array", "items": {"type": "integer"}},
             "margem_min": {"type": "number"}}, ["imagem", "altura"])
async def portao_entrada(ctx, a):
    from .. import entrada
    arq = Path(a["imagem"])
    if not arq.exists():
        raise ErroFerramenta(f"imagem não encontrada: {arq}")
    altura = int(a["altura"])
    if altura <= 0:
        raise ErroFerramenta("'altura' (altura alvo do sprite em px) tem que ser positiva")
    grade = a.get("grade") or None
    if grade is not None and (len(grade) != 2 or min(int(v) for v in grade) < 1):
        raise ErroFerramenta("'grade' é [linhas, colunas], ex.: [2, 4]")
    margem = a.get("margem_min")
    r = await asyncio.to_thread(entrada.checar, arq, altura, grade, 0.01 if margem is None else float(margem))
    conteudo = [texto(entrada.relatorio(r))]
    previa = r["medidas"].get("previa")
    if previa and Path(previa).exists():
        conteudo.append(imagem(_miniatura(Path(previa))))
    return conteudo


# ------------------------------------------------------------------ portão, exportação e régua

async def gerar_versao(ctx, a) -> dict:
    chave, f, st = await _ficha(ctx)
    est = _estilo(f.get("estilo"))
    Q = int(st["sprite"]["largura"])
    if int(st["sprite"]["altura"]) != Q:
        raise ErroFerramenta("o portão espera quadro quadrado (QxQ)")
    partes = _partes(f, st)
    pasta = Path(a["pasta"]) if a.get("pasta") else _pasta_asset(f)
    versao = a.get("versao") or _proxima_versao(pasta)
    saida = pasta / versao
    if not config.caminho_permitido(saida):
        raise ErroFerramenta(f"pasta não permitida: {saida}")
    saida.mkdir(parents=True, exist_ok=True)
    pedidos = set(a.get("estados") or [])
    grades, avisos = [], []
    indices_gerados: list[int] = []
    for nome, idx, ms in _estados(st, f):
        if pedidos and nome not in pedidos:
            continue
        indices_gerados += [i for i in idx if i not in indices_gerados]
        quadros = await _quadros_partes(ctx, partes, idx)
        try:
            txt, av = grade_io.grade_de_camadas(f, partes, quadros, nome, ms, Q, _cores_letras(est))
        except ValueError as e:
            raise ErroFerramenta(f"estado {nome}: {e}")
        avisos += [f"{nome}: {x}" for x in av]
        g = saida / f"{nome}.grade"
        g.write_text(txt, encoding="utf-8")
        grades.append(g)
    if not grades:
        raise ErroFerramenta("nenhum estado para gerar (confira as tags)")
    codigo, out = await _rodar_motor("grade", ["gerar", *map(str, grades), "--saida", str(saida)], est, 1800)
    partes_erros = 0
    if f.get("modular"):
        # portão das partes: erros reprovam a versão (e a exportação); gravado depois do motor para não ser apagado
        from . import partes as tp
        rel, qs, ordem, _ = await tp.checar_asset(ctx, f, st, indices_gerados)
        tp.escrever_saidas(saida, f.get("nome") or "asset", rel, qs, ordem)
        partes_erros = len(rel.erros)
        out += "\n" + rel.texto(40)
        if partes_erros:
            codigo = codigo or 3
    # guarda também o .aseprite de trabalho, como cópia
    try:
        await ctx.aseprite("salvar", {"arquivo": str(saida / f"{f.get('nome', 'asset')}_trabalho.aseprite"),
                                      "copia": True})
    except Exception as e:
        avisos.append(f"não salvei a cópia .aseprite: {e}")
    f.setdefault("versoes", []).append({"versao": versao, "pasta": str(saida), "portao": codigo})
    ctx.salvar_ficha(chave, f)
    return {"codigo": codigo, "saida": saida, "texto": out, "avisos": avisos, "versao": versao, "ficha": f,
            "partes_erros": partes_erros}


@ferramenta("horys_portao", """PORTÃO DE MEDIDAS do sprite aberto: exporta as partes de cada estado (tag) para .grade
em <pasta>/vNN, roda o motor (grade.py gerar: folha, _8x, silhueta, _regua, _regua_anim, gif, _checagem.txt,
medidas/ e o .aseprite fatiado) e devolve APROVADO/REPROVADO com as falhas. Reprovado: corrija e rode de novo; não
chame o revisor com o portão reprovado.""",
            {"estados": LISTA_STR, "pasta": STR, "versao": STR})
async def portao(ctx, a):
    r = await gerar_versao(ctx, a)
    linhas = [l for l in r["texto"].splitlines() if l.strip()]
    resumo = "\n".join(linhas[-60:])
    status = "APROVADO" if r["codigo"] == 0 else "REPROVADO"
    saida = r["saida"]
    conteudo = [texto(f"PORTÃO {status} — {r['versao']} em {saida}\n" + ("\n".join(r["avisos"]) + "\n" if r["avisos"]
                                                                          else "") + resumo)]
    for padrao in ("*_regua_anim.png", "*_8x.png"):
        achados = sorted(saida.glob(padrao))
        if achados:
            conteudo.append(imagem(_miniatura(achados[0])))
            conteudo.append(texto(f"(imagem: {achados[0].name})"))
            break
    return conteudo


@ferramenta("horys_exportar", """Entrega: gera a versão (como o portão: PNG da folha, GIF, .grade fonte e .aseprite
fatiado) e, com 'destino', copia os arquivos finais para lá (ex.: assets/generated/<asset>-vN do jogo). Com o portão
REPROVADO nada é copiado, a não ser com 'forcar': true + 'motivo' (o usuário pediu), que fica em entrega.json.""",
            {"estados": LISTA_STR, "pasta": STR, "versao": STR, "destino": STR, "forcar": BOOL, "motivo": STR})
async def exportar(ctx, a):
    import shutil
    r = await gerar_versao(ctx, a)
    saida = r["saida"]
    copiados = []
    if r.get("partes_erros"):
        raise ErroFerramenta(f"exportação REPROVADA: as partes têm {r['partes_erros']} erro(s) (veja "
                             f"{saida / 'partes_checagem.txt'}); nada foi copiado para o destino. Corrija com "
                             "horys_partes_estender/horys_partes_recortar e rode horys_partes_checar.")
    forcado = False
    if a.get("destino") and r["codigo"] != 0:
        if not (a.get("forcar") and (a.get("motivo") or "").strip()):
            raise ErroFerramenta(f"exportação recusada: o portão de medidas está REPROVADO em {r['versao']} (veja "
                                 f"{saida}). Corrija e rode de novo; só se o usuário pediu a entrega mesmo assim, "
                                 "passe forcar: true e motivo: '<o que o usuário disse>'.")
        forcado = True
    if a.get("destino"):
        dest = Path(a["destino"]).resolve()
        if not config.caminho_permitido(dest):
            raise ErroFerramenta(f"pasta não permitida: {dest}")
        dest.mkdir(parents=True, exist_ok=True)
        for arq in saida.iterdir():
            if arq.is_file() and (arq.suffix in (".png", ".gif", ".aseprite", ".grade", ".json")) and \
                    not any(s in arq.name for s in ("_8x", "_silhueta", "_regua", "_quadros_4x", "_trabalho",
                                                    "_partes")):
                shutil.copy2(arq, dest / arq.name)
                copiados.append(arq.name)
    if forcado:
        (saida / "entrega.json").write_text(json.dumps({"forcado": True, "motivo": a["motivo"], "versao": r["versao"],
                                                        "destino": a["destino"], "codigo_portao": r["codigo"]},
                                                       ensure_ascii=False, indent=1), encoding="utf-8")
    status = "portão APROVADO" if r["codigo"] == 0 else ("portão REPROVADO — entregue FORÇADO: " + a.get("motivo", "")
                                                         if forcado else "portão REPROVADO (nada copiado)")
    return [texto(f"{r['versao']} em {saida} — {status}" + (f"\ncopiados para {a['destino']}: {', '.join(copiados)}"
                                                           if copiados else ""))]


@ferramenta("horys_regua", "Mostra a régua do estilo ao lado do sprite, na mesma escala (por categoria: idle, "
            "andar, ataque, tile, arvore, efeito...).", {"categoria": STR, "quadro": INT})
async def regua(ctx, a):
    chave, f, st = await _ficha(ctx)
    est = _estilo(f.get("estilo"))
    if not est.regua_disponivel:
        raise ErroFerramenta("este estilo não tem régua configurada")
    from .. import estilos
    cfg = estilos.config_motor(est)
    cat = a.get("categoria") or "idle"
    arq, qw = (cfg.get("regua_por_categoria") or {}).get(cat) or (cfg.get("regua_por_categoria") or {}).get("idle")
    caminho = Path(cfg["regua"]) / arq
    ref = np.array(Image.open(caminho).convert("RGBA"))
    if qw:
        ref = ref[:, :int(qw)]
    q = int(a.get("quadro", st["sprite"].get("quadro_ativo") or 0))
    meu = await ler_rgba(ctx, None, q)
    x0, y0, x1, y1 = pixels.recorte(meu, 4)
    rx0, ry0, rx1, ry1 = pixels.recorte(ref, 4)
    a1, a2 = pixels.sobre_fundo(meu[y0:y1, x0:x1], (104, 160, 87)), pixels.sobre_fundo(ref[ry0:ry1, rx0:rx1], (104, 160, 87))
    k = max(1, min(6, 700 // max(a1.width + a2.width, 1)))
    tela = Image.new("RGBA", ((a1.width + a2.width) * k + 24, max(a1.height, a2.height) * k + 16), (40, 40, 48, 255))
    tela.paste(a1.resize((a1.width * k, a1.height * k), Image.NEAREST), (8, 8))
    tela.paste(a2.resize((a2.width * k, a2.height * k), Image.NEAREST), (a1.width * k + 16, 8))
    return [imagem(pixels.png_b64(tela)), texto(f"esquerda: o seu (quadro {q}); direita: régua {arq}, mesma escala {k}×")]


@ferramenta("horys_marcar", "Marca problemas na camada 'revisao' (e a mostra): 'pontos' [[x,y]] viram cruzes, "
            "'retangulos' [[x,y,w,h]] viram molduras. 'limpar': true apaga as marcas antes.",
            {"quadro": INT, "pontos": {"type": "array"}, "retangulos": {"type": "array"}, "cor": STR, "limpar": BOOL})
async def marcar(ctx, a):
    st = await ctx.sprite_atual()
    s = st["sprite"]
    nomes = [c["nome"] for c in s["camadas"]]
    if "revisao" not in nomes:
        await ctx.aseprite("camada", {"acao": "criar", "nome": "revisao"})
    q = int(a.get("quadro", s.get("quadro_ativo") or 0))
    if a.get("limpar"):
        await ctx.aseprite("limpar_camada", {"camada": "revisao", "quadro": q})
    W, H = int(s["largura"]), int(s["altura"])
    rgba = np.zeros((H, W, 4), np.uint8)
    cor = pixels.hex_rgba(a.get("cor") or "#ff2bd6")
    for p in a.get("pontos") or []:
        x, y = int(p[0]), int(p[1])
        for dx, dy in ((0, 0), (-2, 0), (2, 0), (0, -2), (0, 2), (-1, 0), (1, 0), (0, -1), (0, 1)):
            if 0 <= x + dx < W and 0 <= y + dy < H and (dx, dy) != (0, 0):
                rgba[y + dy, x + dx] = cor
    for r in a.get("retangulos") or []:
        x, y, w, h = (int(v) for v in r[:4])
        x1, y1 = min(W - 1, x + w), min(H - 1, y + h)
        x, y = max(0, x - 1), max(0, y - 1)
        rgba[y, x:x1 + 1] = cor
        rgba[y1, x:x1 + 1] = cor
        rgba[y:y1 + 1, x] = cor
        rgba[y:y1 + 1, x1] = cor
    n = await escrever_rgba(ctx, "revisao", q, 0, 0, rgba, (rgba[..., 3] > 0).astype(np.uint8))
    await ctx.aseprite("camada", {"acao": "propriedades", "nome": "revisao", "visivel": True})
    return [texto(f"{n} px de marcação em 'revisao' quadro {q}")]


# ------------------------------------------------------------------ medição avulsa (horys-pixel-review)

@ferramenta("horys_medir_arquivo", """Medição técnica da revisão avulsa (horys-pixel-review) em PNGs: cores e alfa,
fora da paleta, pixels órfãos, contorno dobrado, degraus irregulares, simetria, pés/altura entre quadros e entre vistas,
quadros parados; 'mockup': true mede tela/conceito ('IA slop'). Sem 'caminhos', mede o sprite ativo (composto).
Devolve erros/avisos, marcas com coordenadas (para horys_marcar) e a primeira folha de overlay.""",
            {"caminhos": LISTA_STR, "estilo": STR, "paleta": STR, "fundo": STR, "quadros": INT, "vista": STR,
             "mockup": BOOL})
async def medir_arquivo(ctx, a):
    from ..motor import pixel_review as PR
    caminhos = list(a.get("caminhos") or [])
    tmpdir = None
    if not caminhos:
        st = await ctx.sprite_atual()
        s = st["sprite"]
        n = len(s["quadros"])
        tiras = [await ler_rgba(ctx, None, q) for q in range(n)]
        tmpdir = tempfile.mkdtemp(prefix="horys-medir-")
        arq = Path(tmpdir) / "sprite.png"
        Image.fromarray(np.concatenate(tiras, axis=1), "RGBA").save(arq)
        caminhos = [str(arq)]
        a.setdefault("quadros", n)
    paleta = a.get("paleta")
    if not paleta and a.get("estilo"):
        paleta = _hexes_paleta(_estilo(a["estilo"]))
    r = await asyncio.to_thread(PR.medir_arquivo, caminhos, paleta, a.get("fundo") or "#718555", a.get("quadros"),
                                None, a.get("vista") or "other", None, None, 10, None, bool(a.get("mockup")))
    linhas = [f"{'OK' if r.get('ok') else 'COM PROBLEMAS'}"]
    linhas += [f"ERRO {e}" for e in r.get("erros", [])[:30]]
    linhas += [f"aviso {e}" for e in r.get("avisos", [])[:30]]
    for arq in r.get("arquivos", []):
        for i, q in enumerate(arq.get("quadros") or arq.get("frames") or []):
            pts = q.get("marcas_pontos")
            if pts:
                linhas.append(f"quadro {i}: marcas {json.dumps(pts)[:600]}")
    conteudo = [texto("\n".join(linhas))]
    if r.get("folhas"):
        conteudo.append(imagem(_miniatura(Path(r["folhas"][0]))))
    return conteudo


# ------------------------------------------------------------------ referência e revisor

@ferramenta("horys_prompt_traducao", """Monta o PROMPT DE TRADUÇÃO (11 itens do cofre) para o usuário levar a qualquer
gerador de imagem (Codex, ChatGPT, Gemini, vídeo...): 'tipo' (personagem, criatura-pequena, criatura-grande, boss,
prop, arvore, predio, tile, icone, retrato, efeito), 'descricao' do design, 'estilo' (a paleta vira os hex e os
papéis), 'altura' alvo em px, 'modo' parado | poses (com 'poses', a lista), 'referencia' (caminho; só vai anexada se
'referencia_propria'), e opcionais foco, pecas, cortes, nao_fazer, vista, base_aprovada, guia_pose. Grava
<pasta>/traducao/prompt.md e traducao/paleta-<estilo>.png (amostra com os hex) e devolve o prompt.""",
            {"tipo": STR, "descricao": STR, "estilo": STR, "nome": STR, "altura": INT, "modo": STR, "poses": LISTA_STR,
             "referencia": STR, "referencia_propria": BOOL, "foco": STR, "pecas": LISTA_STR, "cortes": LISTA_STR,
             "nao_fazer": LISTA_STR, "vista": STR, "base_aprovada": STR, "guia_pose": STR, "pasta": STR},
            ["tipo", "descricao"])
async def prompt_traducao(ctx, a):
    from .. import traducao
    est = _estilo(a.get("estilo"))
    pasta = Path(a.get("pasta") or (config.pasta("referencias") / est.nome))
    if not config.caminho_permitido(pasta):
        raise ErroFerramenta(f"pasta não permitida: {pasta}")
    campos = {k: a[k] for k in ("nome", "altura", "modo", "poses", "referencia", "referencia_propria", "foco", "pecas",
                                "cortes", "nao_fazer", "vista", "base_aprovada", "guia_pose") if a.get(k) is not None}
    try:
        r = traducao.escrever(pasta, tipo=a["tipo"], descricao=a["descricao"], paleta=_paleta(est),
                              nome_estilo=est.nome, **campos)
    except ValueError as e:
        raise ErroFerramenta(str(e))
    return [texto("prompt: " + r["prompt"] + "\npaleta (anexo): " + r["paleta"] + "\n\n" + r["texto"]),
            imagem(_miniatura(Path(r["paleta"]), 512))]


@ferramenta("horys_referencia_gerar", """Gera imagem de referência quando o usuário não tem uma: 'fonte' manual (PADRÃO: monta o prompt
de tradução via horys_prompt_traducao para o usuário gerar onde quiser; passe 'tipo'), codex (opcional, só se o Codex
estiver instalado) ou lora (o modelo treinado do estilo, se houver).
'prompt' descreve o asset com a paleta e os princípios do estilo (nunca anexe arte de terceiros). Pode levar minutos;
devolve os caminhos das imagens.""",
            {"fonte": STR, "prompt": STR, "pasta": STR, "n": INT, "estilo": STR, "imagens": LISTA_STR, "tipo": STR,
             "altura": INT, "modo": STR, "poses": LISTA_STR},
            ["prompt"])
async def referencia_gerar(ctx, a):
    if (a.get("fonte") or "manual") == "manual":
        return await prompt_traducao(ctx, {**a, "tipo": a.get("tipo") or "personagem", "descricao": a["prompt"]})
    est = _estilo(a.get("estilo"))
    pasta = Path(a.get("pasta") or (config.pasta("referencias") / est.nome))
    pasta.mkdir(parents=True, exist_ok=True)
    if a["fonte"] == "codex":
        pr = pasta / "prompt.md"
        pr.write_text(a["prompt"], encoding="utf-8")
        args = ["gerar", "--prompt", str(pr), "--saida", str(pasta)]
        for im in a.get("imagens") or []:
            args += ["--img", im]
        codigo, out = await _rodar_motor("conceito", args, est, 1800)
        imgs = re.findall(r"imagem: (.+)", out)
        if codigo != 0 or not imgs:
            raise ErroFerramenta("o Codex não gerou imagem (limite de uso, recusa ou erro):\n" + out[-1200:])
        return [texto("imagens:\n" + "\n".join(imgs))] + [imagem(_miniatura(Path(imgs[0].strip()), 512))]
    if a["fonte"] == "lora":
        from .treino import rodar_cli
        codigo, out = await rodar_cli(["gerar", "--estilo", est.nome, "--prompt", a["prompt"], "--n",
                                       str(int(a.get("n", 3))), "--executar"], 1800)
        return [texto(f"(código {codigo})\n{out[-3000:]}")]
    raise ErroFerramenta("fonte: codex ou lora")


def _portao_reprovado(pasta: Path) -> list[str]:
    """Arquivos de checagem da pasta vNN que dizem REPROVADO (portão de medidas ou partes)."""
    ruins = []
    for arq in sorted(pasta.glob("*_checagem.txt")) + sorted(pasta.glob("partes_checagem.txt")):
        t = arq.read_text(encoding="utf-8", errors="replace")
        if "PORTÃO DE MEDIDAS: REPROVADO" in t or "PARTES REPROVADAS" in t:
            ruins.append(arq.name)
    return ruins


@ferramenta("horys_revisar", """Chama o REVISOR exigente (sem terminal; por padrão o Claude revisa). Com a
preferência revisor 'cruzado' (opcional, exige o Codex instalado), o outro motor revisa: se o Claude desenhou, o
Codex revisa. O Codex só é chamado se estiver no PATH e a preferência pedir ('cruzado' ou 'codex'). Passe a pasta vNN do portão, os estados, a ficha.md e a praticas.md, a etapa, a rodada e,
em asset fiel, a referência. Devolve um id na hora; use horys_aguardar(id) — a revisão leva alguns minutos. A
resposta traz o JSON do revisor (PASSA/NAO_PASSA, notas, aceitação, correções).""",
            {"pasta": STR, "estados": LISTA_STR, "ficha": STR, "praticas": STR, "etapa": STR, "rodada": INT,
             "referencia": STR, "motor": STR, "quem_desenhou": STR}, ["pasta"])
async def revisar(ctx, a):
    if (a.get("etapa") or "").strip().lower() != "conceito":
        ruins = _portao_reprovado(Path(a["pasta"]))
        if ruins:
            raise ErroFerramenta("revisor recusado: o portão está REPROVADO (" + ", ".join(ruins) + "). Corrija "
                                 "as falhas e rode horys_portao de novo; o revisor só olha o que já passou nas medidas "
                                 "(exceto etapa: conceito).")
    prompt_base = (Path(__file__).resolve().parents[1] / "motor" / "revisor_prompt.md").read_text(encoding="utf-8")
    pref = config.preferencias().get("revisor", "claude")
    quem = a.get("quem_desenhou") or config.preferencias().get("motor_padrao", "claude")
    codex_ok = pref in ("cruzado", "codex") and motores.executavel("codex") is not None
    motor = a.get("motor") or (motores.outro(quem) if pref == "cruzado" else pref)
    if not a.get("motor") and motor == "codex" and not codex_ok:
        motor = "claude"        # Codex é opcional: sem ele no PATH, o Claude revisa
    rodada = int(a.get("rodada") or 1)
    tarefa = (f"\n\n---\nTAREFA DE REVISÃO\n- pasta: {a['pasta']}\n- estados: {', '.join(a.get('estados') or []) or 'todos'}\n"
              f"- ficha: {a.get('ficha') or '—'}\n- praticas: {a.get('praticas') or '—'}\n- etapa: {a.get('etapa') or 'quadro base'}\n"
              f"- {'RODADA 1: inventário completo' if rodada == 1 else f'rodada {rodada}'}\n"
              + (f"- referência do usuário (asset fiel; a semelhança entra no inventário): {a['referencia']}\n"
                 if a.get("referencia") else "")
              + "Leia os arquivos da pasta (PNG, _checagem.txt, medidas/, e partes_checagem.txt/_partes.png se for modular). Não edite nada. Termine com o JSON pedido.")
    i = ctx.pend.criar("revisao", {"pasta": a["pasta"], "motor": motor})

    async def rodar():
        reserva = motores.outro(motor)
        tentativas = [motor] + ([reserva] if not a.get("motor") and (reserva != "codex" or codex_ok) else [])
        ultimo = None
        for k, m in enumerate(tentativas):
            try:
                r = await motores.rodar(m, prompt_base + tarefa, Path(a["pasta"]),
                                        nome_log=f"revisor_r{rodada}" + (f"_{m}" if k else ""), timeout=1800)
            except Exception as e:
                ultimo = {"motor": m, "erro": str(e)}
                continue
            js = motores.extrair_json(r["texto"])
            if js is None and k + 1 < len(tentativas):
                ultimo = {"motor": m, "erro": (r["texto"] or "sem resposta")[-400:]}
                continue        # ex.: o outro motor sem cota → revisa com o de reserva (não fica cruzado)
            res = {"motor": m, "codigo": r["codigo"], "json": js, "texto": None if js else r["texto"][-3000:],
                   "log": r["log"]}
            from .. import entrega
            res["entrega"] = entrega.avaliar(js)
            if k:
                res["aviso"] = (f"o revisor {tentativas[0]} falhou ({(ultimo or {}).get('erro', '')[:200]}); "
                                f"revisado pelo {m}, então NÃO foi cruzado")
            ctx.pend.resolver(i, res)
            return
        ctx.pend.resolver(i, ultimo or {"erro": "revisor não rodou"}, estado="erro")
    asyncio.ensure_future(rodar())
    return [texto(f"id: {i}\nrevisor ({motor}) trabalhando. Chame horys_aguardar com id='{i}' (repita enquanto "
                  "estiver pendente).")]


# ------------------------------------------------------------------ criar e calibrar estilos

@ferramenta("horys_estilo_novo", """Cria um PACOTE DE ESTILO a partir de imagens do estilo que a pessoa gosta: mede
escala do pixel, paleta em rampas, contorno, tamanho de cluster, tons por material, proporções e AA/dithering, e grava
em ~/.horys-pixel/estilos/<nome>/ (estilo.json, paleta, analise.json e estilo.md rascunho com os 15 itens do guia
de estilo; o que não deu para medir fica 'a confirmar'). 'licenca': origem/licença das imagens (obrigatória para
treinar depois). Depois confirme item por item com a pessoa (skill horys-pixel-estilo).""",
            {"nome": STR, "imagens": LISTA_STR, "autor": STR, "licenca": STR}, ["nome", "imagens"])
async def estilo_novo(ctx, a):
    from .. import analise_estilo
    faltam = [p for p in a["imagens"] if not Path(p).exists()]
    if faltam:
        raise ErroFerramenta("imagens não encontradas: " + ", ".join(faltam[:5]))
    pasta = await asyncio.to_thread(analise_estilo.criar_pacote, a["nome"], a["imagens"], None,
                                    a.get("autor") or "", a.get("licenca") or "")
    resumo = ""
    an = Path(pasta) / "analise.json"
    if an.exists():
        dados = json.loads(an.read_text(encoding="utf-8"))
        resumo = json.dumps({k: dados[k] for k in list(dados)[:14]}, ensure_ascii=False)[:2500]
    return [texto(f"pacote criado em {pasta}\nRevise {Path(pasta) / 'estilo.md'} com a pessoa.\nanálise: {resumo}")]


@ferramenta("horys_estilo_calibrar", """Confere se o portão de medidas está calibrado na régua do estilo: gera as
mutações (versões estragadas da régua) e mede bons e estragados. Os bons têm que passar todos e os estragados têm que
reprovar todos. Leva alguns minutos.""", {"estilo": STR})
async def estilo_calibrar(ctx, a):
    est = _estilo(a.get("estilo"))
    if not est.regua_disponivel:
        raise ErroFerramenta("o estilo não tem régua: escolha os sprites-régua primeiro (regua.pasta no estilo.json)")
    c1, o1 = await _rodar_motor("calibrar", ["mutacoes"], est, 1800)
    c2, o2 = await _rodar_motor("calibrar", ["metricas"], est, 1800)
    return [texto(f"mutacoes (código {c1}):\n{o1[-1500:]}\n\nmetricas (código {c2}):\n{o2[-3000:]}")]
