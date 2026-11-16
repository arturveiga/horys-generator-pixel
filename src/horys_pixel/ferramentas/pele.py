"""Ferramentas do fluxo Base + Pele (perfeicao.md, P3). Trabalham com arquivos PNG; não precisam do Aseprite aberto.

horys_base_ler      imagem do Codex (pixel art ampliada sobre cor-chave) -> folha 1x da base + vistas + prévia
horys_vestir        base 1x + imagem do Codex com a base vestida -> camada de pele (só as células que mudaram)
horys_propagar_pele pele + mapas de partes da base (quadro de referência e quadros alvo) -> pele de cada quadro

A lógica pura vive em horys_pixel.pele. Nenhuma delas cria forma: leem, separam, deslocam e avisam.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from .. import pele as P
from .. import travas as T
from .. import pixels
from .registro import BOOL, INT, STR, ErroFerramenta, ferramenta, imagem, texto

LISTA = {"type": "array", "items": {"type": "string"}}


def _trava(f):
    try:
        return f()
    except T.Travado as e:
        raise ErroFerramenta("TRAVADO: " + str(e))


def _abrir(caminho: str, rgba: bool = True) -> np.ndarray:
    p = Path(caminho)
    if not p.is_file():
        raise ErroFerramenta(f"arquivo não encontrado: {caminho}")
    return np.array(Image.open(p).convert("RGBA" if rgba else "RGB"))


def _pasta(caminho: str) -> Path:
    p = Path(caminho)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _previa(rgba: np.ndarray, k: int = 8, fundo=(104, 160, 87, 255)) -> Image.Image:
    big = Image.fromarray(rgba).resize((rgba.shape[1] * k, rgba.shape[0] * k), Image.NEAREST)
    bg = Image.new("RGBA", big.size, fundo)
    bg.alpha_composite(big)
    return bg


def _mapa_partes(caminho: str) -> np.ndarray:
    """Mapa de partes em PNG: cada cor opaca distinta é uma parte (rótulos 1..n na ordem das cores)."""
    a = _abrir(caminho)
    rot = np.zeros(a.shape[:2], int)
    op = a[..., 3] > 0
    cores = sorted({tuple(int(v) for v in c) for c in a[op][:, :3]})
    for i, c in enumerate(cores, 1):
        rot[op & (a[..., :3] == c).all(-1)] = i
    return rot


@ferramenta("horys_base_ler", """
Lê a imagem do Codex de um corpo-base (pixel art ampliada sobre cor-chave, vistas lado a lado) na grade nativa
dela e grava a folha 1x da base: base.png (vistas na mesma linha de chão, margem transparente para chapéu/capa),
vista_N.png, base_8x.png (prévia) e base.json (bloco, cores, alturas, avisos). Não cria forma.
Leitura pela GRADE PRÓPRIA (cortes irregulares ajustados às bordas + voto da maioria no miolo de cada célula; a
franja da chave não vira cor). 'paleta': encaixa na paleta da ficha; sem ela, 'cores' cores reais da imagem
(16 é bom para master; 4 para corpo-base liso). 'metodo': propria (padrão) | centro (o antigo).
""", {"imagem": STR, "saida": STR, "chave": STR, "cores": INT, "margem": INT, "paleta": LISTA, "metodo": STR},
            ["imagem", "saida"])
async def base_ler(ctx, a: dict) -> list:
    img = _abrir(a["imagem"], rgba=False)
    try:
        m = P.ler_master(img, a.get("chave") or "#ff00ff", n_cores=int(a.get("cores") or 4),
                         margem=int(a.get("margem") if a.get("margem") is not None else 4),
                         paleta=a.get("paleta") or None, metodo=a.get("metodo") or "propria")
    except ValueError as e:
        raise ErroFerramenta(str(e))
    out = _pasta(a["saida"])
    Image.fromarray(m.folha).save(out / "base.png")
    for i, v in enumerate(m.vistas):
        Image.fromarray(v).save(out / f"vista_{i}.png")
    _previa(m.folha).save(out / "base_8x.png")
    info = {"bloco": round(m.bloco, 3), "alturas": m.alturas, "cores": m.cores, "avisos": m.avisos,
            "tamanho": [int(m.folha.shape[1]), int(m.folha.shape[0])], "origem": str(a["imagem"])}
    (out / "base.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    msg = (f"base lida: {len(m.vistas)} vistas, altura {m.alturas}, bloco {m.bloco:.2f} px, cores {m.cores}. "
           f"Gravado em {out}.")
    if m.avisos:
        msg += " AVISOS: " + " | ".join(m.avisos)
    return [texto(msg), imagem(pixels.png_b64(_previa(m.folha, 6)))]


@ferramenta("horys_vestir", """
Separa a pele de um personagem: relê a imagem do Codex (a base vestida, pedida com "A ÚNICA MUDANÇA: vista esta
figura como <ficha>") NA GRADE DA BASE e grava só as células que mudaram. Saída: pele.png (camada de pele),
vestido.png (base + pele), vestido_8x.png e pele.json (grade achada, % da base mantida, cores, avisos).
Aviso de grade fraca = gere de novo no Codex; não conserte à mão. TRAVA: a base precisa estar aprovada pelo Artur
(horys_aprovar_arquivo).
""", {"base": STR, "imagem": STR, "saida": STR, "chave": STR, "paleta": LISTA, "max_cores": INT,
      "manter_isolados": BOOL}, ["base", "imagem", "saida"])
async def vestir(ctx, a: dict) -> list:
    _trava(lambda: T.exigir_aprovado(a["base"], "a base"))
    base = _abrir(a["base"])
    img = _abrir(a["imagem"], rgba=False)
    try:
        v = P.vestir(base, img, a.get("chave") or "#ff00ff", paleta=a.get("paleta") or None,
                     max_cores=int(a.get("max_cores") or 12), manter_isolados=bool(a.get("manter_isolados")))
    except ValueError as e:
        raise ErroFerramenta(str(e))
    out = _pasta(a["saida"])
    Image.fromarray(v.pele).save(out / "pele.png")
    Image.fromarray(v.lido).save(out / "vestido.png")
    _previa(v.lido).save(out / "vestido_8x.png")
    info = {"grade": {"celula": round(v.grade.celula, 3), "x0": round(v.grade.x0, 2), "y0": round(v.grade.y0, 2),
                      "acerto": round(v.grade.acerto, 3)},
            "mantido": round(v.mantido, 3), "celulas_pele": int(v.mudou.sum()), "removidos": v.removidos,
            "isolados_tirados": v.isolados_tirados, "cores_pele": v.cores_pele, "avisos": v.avisos}
    (out / "pele.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    msg = (f"pele: {int(v.mudou.sum())} células, {v.mantido:.0%} da base mantida, grade {v.grade.celula:.2f} px "
           f"(acerto {v.grade.acerto:.0%}), cores {v.cores_pele}. Gravado em {out}.")
    if v.avisos:
        msg += " AVISOS: " + " | ".join(v.avisos)
    return [texto(msg), imagem(pixels.png_b64(_previa(v.lido, 6)))]


@ferramenta("horys_propagar_pele", """
Leva a pele para cada quadro da animação da base. Recebe a pele (PNG, mesmo tamanho dos mapas), o mapa de partes
do quadro de referência e os mapas dos quadros alvo (PNG em que cada cor opaca é uma parte; a mesma cor = a mesma
parte em todos os quadros). Opcional: as bases de cada quadro, para gravar o composto. Saída: pele_NN.png,
composto_NN.png e propagar.json (deslocamento e IoU por parte; aviso = limpar à mão aquela parte).
""", {"pele": STR, "partes_ref": STR, "partes": LISTA, "bases": LISTA, "saida": STR, "raio": INT},
            ["pele", "partes_ref", "partes", "saida"])
async def propagar(ctx, a: dict) -> list:
    pele = _abrir(a["pele"])
    p0 = _mapa_partes(a["partes_ref"])
    alvos = a["partes"]
    bases = a.get("bases") or []
    if bases and len(bases) != len(alvos):
        raise ErroFerramenta("bases e partes precisam ter o mesmo número de quadros")
    out = _pasta(a["saida"])
    rel, avisos, quadros = [], [], []
    for i, cam in enumerate(alvos):
        pn = _mapa_partes(cam)
        try:
            r = P.propagar(pele, p0, pn, raio=int(a.get("raio") or 6))
        except ValueError as e:
            raise ErroFerramenta(f"quadro {i}: {e}")
        Image.fromarray(r.pele).save(out / f"pele_{i:02d}.png")
        if bases:
            comp = P.compor(_abrir(bases[i]), r.pele)
            Image.fromarray(comp).save(out / f"composto_{i:02d}.png")
            quadros.append(comp)
        rel.append({"quadro": i, "partes": {str(k): v for k, v in r.por_parte.items()}, "avisos": r.avisos})
        avisos += [f"q{i}: {x}" for x in r.avisos]
    (out / "propagar.json").write_text(json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")
    msg = f"pele propagada em {len(alvos)} quadros. Gravado em {out}."
    if avisos:
        msg += " AVISOS: " + " | ".join(avisos)
    res = [texto(msg)]
    if quadros:
        res.append(imagem(pixels.png_b64(pixels.filmstrip(quadros))))
    return res


# ------------------------------------------------------------------ C2/C3/C9: mapa de partes, pedido ao Codex, animar


@ferramenta("horys_partes_mapa", """
MAPA DE PARTES de uma vista (cor por parte, contrato de art-src/motion-rigs: cabeça ciano, tronco laranja, braço
esq. verde, braço dir. roxo, perna esq. amarela, perna dir. vermelha, arma rosa, enfeite branco). Sem 'mapa': faz o
RASCUNHO automático (pescoço pelo perfil de largura, virilha pelo vão das pernas, braços fora do quadril) e grava
<saida>/partes.png para corrigir no Aseprite. Com 'mapa': só checa. Sempre checa a FORMA FECHADA por parte
(cobertura exata, 1 pedaço, sem buraco, junções encostadas) e grava partes.json + partes_8x.png.
'lado': vista de perfil (uma perna só). 'enfeite_topo': linhas do topo que são chifre/cabelo/antena.
""", {"vista": STR, "saida": STR, "mapa": STR, "lado": BOOL, "cabeca_frac": {"type": "number"},
      "enfeite_topo": INT}, ["vista", "saida"])
async def partes_mapa(ctx, a: dict) -> list:
    from .. import mapa_partes as M
    vista = _abrir(a["vista"])
    out = _pasta(a["saida"])
    if a.get("mapa"):
        rot = M.rotulos(_abrir(a["mapa"]))
    else:
        rot = M.mapa_auto(vista, lado=bool(a.get("lado")), cabeca_frac=a.get("cabeca_frac"),
                          enfeite_topo=int(a.get("enfeite_topo") or 0))
        Image.fromarray(M.pintar(rot)).save(out / "partes.png")
    ch = M.checar(vista, rot)
    (out / "partes.json").write_text(json.dumps(ch.como_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    lado_a_lado = np.concatenate([vista, np.zeros((vista.shape[0], 2, 4), np.uint8), M.pintar(rot)], 1)
    _previa(lado_a_lado).save(out / "partes_8x.png")
    msg = ("FORMA FECHADA: ok" if ch.ok else "PARTES REPROVADAS: " + " | ".join(ch.problemas)) + \
          f". Partes: {', '.join(f'{k} {v['pixels']}px' for k, v in ch.partes.items())}. Gravado em {out}."
    return [texto(msg), imagem(pixels.png_b64(_previa(lado_a_lado, 6)))]


@ferramenta("horys_animar_tabela", """
ANIMA uma vista aprovada deslocando partes por uma TABELA (dx, dy por parte por quadro): 'tabela' = idle |
andar-frente | andar-lado, ou um objeto {n, ms, partes: {parte: [[dx,dy],...] | "atraso:cabeca"}}. Precisa do mapa de
partes checado (horys_partes_mapa ok). O que não mexe fica idêntico; a emenda de 1 px numa junção é fechada
esticando o vizinho; vão maior vira aviso (limpar à mão). Grava quadro_NN.png, folha PNG+JSON+GIF em 'saida'.
""", {"vista": STR, "mapa": STR, "tabela": {"type": ["string", "object"]}, "saida": STR, "estado": STR,
      "espelhar": BOOL}, ["vista", "mapa", "tabela", "saida"])
async def animar_tabela(ctx, a: dict) -> list:
    from .. import mapa_partes as M
    from .. import sequencia
    _trava(lambda: T.exigir_aprovado(a["vista"], "a vista"))
    vista = _abrir(a["vista"])
    rot = M.rotulos(_abrir(a["mapa"]))
    ch = M.checar(vista, rot)
    if not ch.ok:
        raise ErroFerramenta("mapa de partes reprovado (corrija e rode horys_partes_mapa com 'mapa'): "
                             + " | ".join(ch.problemas))
    try:
        r = M.animar(vista, rot, a["tabela"])
    except KeyError:
        raise ErroFerramenta(f"tabela '{a['tabela']}' não existe (há: {', '.join(M.TABELAS)})")
    quadros = r.quadros
    if a.get("espelhar"):
        quadros = [q[:, ::-1].copy() for q in quadros]
    out = _pasta(a["saida"])
    for i, q in enumerate(quadros):
        Image.fromarray(q).save(out / f"quadro_{i:02d}.png")
    estado = a.get("estado") or (a["tabela"] if isinstance(a["tabela"], str) else "anim")
    arqs = sequencia.spritesheet.salvar(quadros, out, estado, r.ms, estado, None, True)
    msg = f"{len(quadros)} quadros ({r.ms} ms), folha {arqs['png']}."
    if r.avisos:
        msg += " AVISOS: " + " | ".join(r.avisos)
    return [texto(msg), imagem(pixels.png_b64(pixels.filmstrip(quadros)))]


@ferramenta("horys_pedido_codex", """
PEDIDO PRONTO AO CODEX (image_gen), do jeito que funcionou: pixel art no tamanho final, simples, paleta fixa, fundo
chapado de cor-chave, todas as vistas numa imagem. 'modo': master (conceito -> folha de vistas; 'imagem' = conceito,
'ficha', 'altura', 'paleta', 'vistas', 'extras'), vestir (base 1x ampliada + "A ÚNICA MUDANÇA: vista como <ficha>"),
vista (a vista que falta ao lado do master) ou pose ("A ÚNICA MUDANÇA: <pose>"). Gera 'n' tentativas (padrão 3) em
<saida>/tentativa_NN.png; tentativa ruim se descarta, não se conserta. Com 'so_prompt' só grava prompt.md e o anexo.
Depois: master -> horys_base_ler; vestir -> horys_vestir; pose/vista -> horys_vestir com a imagem aprovada como base.
Leva minutos por tentativa (devolve um id; use horys_aguardar).
""", {"modo": STR, "saida": STR, "imagem": STR, "ficha": STR, "altura": INT, "paleta": LISTA, "chave": STR,
      "vistas": LISTA, "extras": LISTA, "vista": STR, "pose": STR, "n": INT, "escala": INT, "so_prompt": BOOL},
            ["modo", "saida"])
async def pedido_codex(ctx, a: dict) -> list:
    import asyncio
    from .. import pedido_codex as PC
    kw = {k: a[k] for k in ("ficha", "altura", "paleta", "vistas", "extras", "vista", "pose") if a.get(k)}
    try:
        ped = PC.preparar(a["saida"], a["modo"], imagem=a.get("imagem"), escala=int(a.get("escala") or 12),
                          chave=a.get("chave") or "#ff00ff", **kw)
    except (ValueError, OSError) as e:
        raise ErroFerramenta(str(e))
    if a.get("so_prompt"):
        return [texto(f"prompt em {ped.prompt}; anexos {[str(x) for x in ped.anexos]}\n\n"
                      + ped.prompt.read_text(encoding="utf-8"))]
    i = ctx.pend.criar("codex", {"saida": a["saida"]})

    async def rodar():
        try:
            r = await asyncio.to_thread(PC.gerar, ped, int(a.get("n") or 3))
            ctx.pend.resolver(i, {"tentativas": [str(t) for t in r.tentativas], "logs": r.logs},
                              estado="respondido" if r.tentativas else "erro")
        except Exception as e:     # noqa: BLE001
            ctx.pend.resolver(i, {"erro": str(e)}, estado="erro")
    asyncio.ensure_future(rodar())
    return [texto(f"id: {i}\nCodex gerando {int(a.get('n') or 3)} tentativa(s) em {a['saida']}. "
                  f"Chame horys_aguardar com id='{i}'.")]


# ------------------------------------------------------------------ C6: travas de passo


@ferramenta("horys_aprovar_arquivo", """
Registra a APROVAÇÃO de um arquivo (master, base, vista, quadro): grava <arquivo>.aprovado.json com o sha256 do
arquivo. Se o arquivo mudar, a aprovação cai. Use SÓ depois do sim do Artur: passe 'id' de um horys_aprovar já
respondido (confere que foi Aprovar e não automático) ou 'chat': true quando ele disse sim no chat (cite as palavras
dele em 'comentario'). 'quem': artur (padrão) | revisor. Vestir e animar recusam o que não foi aprovado pelo Artur.
""", {"arquivo": STR, "id": STR, "chat": BOOL, "comentario": STR, "quem": STR}, ["arquivo"])
async def aprovar_arquivo(ctx, a: dict) -> list:
    quem = a.get("quem") or "artur"
    origem = ""
    if quem == "artur":
        if a.get("id"):
            it = ctx.pend.obter(a["id"]) if ctx is not None else None
            r = (it or {}).get("resposta") or {}
            if not it or it.get("estado") != "respondido" or not r.get("aprovado") or r.get("pendente_usuario"):
                raise ErroFerramenta(f"o pedido {a['id']} não foi aprovado pelo Artur (estado "
                                     f"{(it or {}).get('estado')}, resposta {r})")
            origem = f"painel {a['id']}"
            a.setdefault("comentario", r.get("comentario") or "")
        elif a.get("chat"):
            if not (a.get("comentario") or "").strip():
                raise ErroFerramenta("chat: cite em 'comentario' as palavras do Artur")
            origem = "chat"
        else:
            raise ErroFerramenta("passe 'id' de um horys_aprovar respondido ou 'chat': true com as palavras dele")
    try:
        reg = T.aprovar(a["arquivo"], quem, a.get("comentario") or "", origem)
    except (FileNotFoundError, ValueError) as e:
        raise ErroFerramenta(str(e))
    return [texto(f"aprovado por {reg['quem']} ({origem or 'revisor'}): {a['arquivo']} sha {reg['sha256'][:12]}")]


@ferramenta("horys_ab_registrar", """
Registra uma rodada A/B CEGA do revisor em <pasta>/ab.json: 'a' = antes, 'b' = depois da correção, 'vencedor'
A | B | EMPATE e o 'motivo'. A correção só fica se B vencer (senão volte ao A). horys_entrega recusa pasta sem A/B.
""", {"pasta": STR, "a": STR, "b": STR, "vencedor": STR, "motivo": STR, "revisor": STR},
            ["pasta", "a", "b", "vencedor"])
async def ab_registrar(ctx, a: dict) -> list:
    try:
        r = T.registrar_ab(a["pasta"], a["a"], a["b"], a["vencedor"], a.get("motivo") or "", a.get("revisor") or "")
    except ValueError as e:
        raise ErroFerramenta(str(e))
    return [texto(f"A/B registrado: venceu {r['vencedor']}; fica {r['fica'].upper()} ({r[r['fica']]}).")]


@ferramenta("horys_pose_ler", """
Lê uma POSE ou VISTA do Codex (horys_pedido_codex modo pose/vista) NA GRADE DO MASTER: bloco pela altura do master,
voto da maioria na 'paleta' (padrão: as cores do master), sem o halo claro de fora do contorno e com a CABEÇA
TRAVADA (as 'cabeca' linhas do topo do master coladas por cima, no melhor encaixe). Grava <saida>/<nome>.png e
<nome>_bruto.png. Aviso de altura ou de cabeça = descarte a tentativa e gere de novo.
""", {"imagem": STR, "master": STR, "saida": STR, "nome": STR, "cabeca": INT, "paleta": LISTA, "chave": STR},
            ["imagem", "master", "saida"])
async def pose_ler(ctx, a: dict) -> list:
    master = _abrir(a["master"])
    ys, xs = np.nonzero(master[..., 3])
    master = master[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    pal = a.get("paleta") or sorted({"#%02x%02x%02x" % tuple(int(v) for v in c[:3])
                                      for c in master.reshape(-1, 4) if c[3]})
    try:
        r = P.ler_pose(_abrir(a["imagem"], rgba=False), master, paleta=pal, chave=a.get("chave") or "#ff00ff",
                       cabeca=int(a["cabeca"]) if a.get("cabeca") else None)
    except ValueError as e:
        raise ErroFerramenta(str(e))
    out = _pasta(a["saida"])
    nome = a.get("nome") or Path(a["imagem"]).stem
    Image.fromarray(r.quadro).save(out / f"{nome}.png")
    Image.fromarray(r.bruto).save(out / f"{nome}_bruto.png")
    msg = (f"pose {r.quadro.shape[1]}x{r.quadro.shape[0]} (bloco {r.bloco:.2f} px, cabeça IoU {r.cabeca_iou:.2f}) "
           f"em {out / (nome + '.png')}.")
    if r.avisos:
        msg += " AVISOS: " + " | ".join(r.avisos)
    return [texto(msg), imagem(pixels.png_b64(_previa(r.quadro, 6)))]
