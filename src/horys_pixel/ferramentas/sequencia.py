"""horys_sequencia: leva N quadros de qualquer fonte (grade de poses, vídeo, pasta, atlas do Kiln) pelo motor de
sequência e escreve o resultado no Aseprite (camada da ficha, durações e tag do estado)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from .. import sequencia
from .desenho import escrever_rgba
from .estilo import _estilo, _ficha, _hexes_paleta, _miniatura, _partes, entrada_reprovada
from .registro import BOOL, INT, LISTA_STR, STR, ErroFerramenta, ferramenta, imagem, texto


def _tira(quadros: list[np.ndarray], pasta: Path, lado: int = 900) -> str:
    qs = quadros[:12]
    h, w = qs[0].shape[:2]
    tira = np.zeros((h, w * len(qs), 4), np.uint8)
    for i, q in enumerate(qs):
        tira[:, i * w:(i + 1) * w] = q
    k = max(1, lado // max(tira.shape[1], tira.shape[0]))
    im = Image.fromarray(tira, "RGBA")
    if k > 1:
        im = im.resize((im.width * k, im.height * k), Image.NEAREST)
    caminho = pasta / "sequencia_tira.png"
    im.save(caminho)
    return _miniatura(caminho, lado)


IMAGENS = {".png", ".jpg", ".jpeg", ".webp"}


def portao_da_fonte(fonte: str, forcar: bool = False, motivo: str = "") -> str | None:
    """Erro se a fonte é uma imagem (grade gerada) sem portão de entrada APROVADO, salvo forcar + motivo.
    Pasta de PNGs, vídeo e atlas do Kiln não passam por aqui (o portão de entrada mede uma imagem)."""
    p = Path(fonte)
    if p.suffix.lower() not in IMAGENS or not p.is_file():
        return None
    erro = entrada_reprovada(p)
    if erro and not (forcar and (motivo or "").strip()):
        return (erro + " Rode horys_portao_entrada (com 'grade' [linhas, colunas]) e peça a correção ao gerador; "
                "só se o usuário pediu, passe forcar: true e motivo: '<o que o usuário disse>'.")
    return None


@ferramenta("horys_sequencia", """MOTOR DE SEQUÊNCIA: trata os quadros de uma animação como um todo. 'fonte' = o
manifest.json de um render 3D com câmera fixa (Blender/Blockbench; liga o preset render3d), pasta de PNGs, uma grade
(PNG + 'linhas' e 'colunas'), um vídeo (precisa do ffmpeg) ou o JSON do atlas do Kiln. 'preset' render3d | grade |
video. Etapas: fundo por célula → registro (altura alvo, pés e pivô da ficha; 'escala' fixa | comum | por_quadro —
fixa = uma transformação para a sequência inteira, preserva quique e agachamento) → escolha de quadros
('plano' andar | golpe com 'n') → quantização conjunta na paleta do estilo → redução por moda → anti-cintilação →
trava de identidade ('base' = PNG da base aprovada no tamanho final e 'decalques' [{nome, rect [x,y,w,h], busca}]) →
limpeza (órfãos e borda) → validação objetiva (canvas, alpha, paleta, proporção, deriva, cintilação, quadros
repetidos, loop, identidade). 'proteger' = cores (#hex) que podem mudar sem a forma mudar (brilho do olho).
'prancha' = PNG com poses soltas sem grade (achadas por componentes, em ordem de leitura); 'franja' (padrão true)
tira o anel quase-fundo colado no contorno. 'saida_folha' = pasta onde gravar a folha PNG + JSON (Aseprite hash, lido pela Godot 4) + GIF. Uma grade (imagem) só entra com o portão de entrada APROVADO, salvo 'forcar' + 'motivo'.
Escreve na camada (padrão: a de cima da ficha) a partir do quadro 'quadro_inicial', cria a
tag 'estado' e devolve o relatório (deriva, % de pixels que piscam antes e depois). Depois: horys_contorno →
horys_portao.""",
            {"fonte": STR, "altura": INT, "linhas": INT, "colunas": INT, "fps": {"type": "number"},
             "estado": STR, "camada": STR, "quadro_inicial": INT, "ms": INT, "plano": STR, "n": INT, "escala": STR,
             "fator": INT, "base": STR, "decalques": {"type": "array", "items": {"type": "object"}},
             "limpar_min": INT, "regularizar": BOOL, "cor_fundo": STR, "proteger": LISTA_STR,
             "prancha": BOOL, "franja": BOOL,
             "forcar": BOOL, "motivo": STR, "preset": STR, "loop": BOOL, "saida_folha": STR},
            ["fonte", "altura"])
async def sequencia_ferramenta(ctx, a):
    erro_portao = portao_da_fonte(a["fonte"], bool(a.get("forcar")), a.get("motivo") or "")
    if erro_portao:
        raise ErroFerramenta(erro_portao)
    chave, f, st = await _ficha(ctx)
    est = _estilo(f.get("estilo"))
    sp = st["sprite"]
    Wq, Hq = int(sp["largura"]), int(sp["altura"])
    pivo = (Wq / 2, round(Hq * 127 / 192))
    camada = a.get("camada") or _partes(f, st)[-1]
    ms = int(a.get("ms") or 100)
    base = None
    if a.get("base"):
        if not Path(a["base"]).exists():
            raise ErroFerramenta(f"base não encontrada: {a['base']}")
        base = np.array(Image.open(a["base"]).convert("RGBA"), dtype=np.uint8)
    prot = None
    if a.get("proteger"):
        prot = {tuple(int(h.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4)) for h in a["proteger"]}
    try:
        r = sequencia.processar(
            a["fonte"], _hexes_paleta(est), int(a["altura"]), (Wq, Hq), pivo, a.get("linhas"), a.get("colunas"),
            a.get("fps"), a.get("cor_fundo") or "auto", a.get("plano"), a.get("n"), a.get("escala"),
            int(a.get("fator") or 4), base, a.get("decalques"),
            int(a["limpar_min"]) if a.get("limpar_min") is not None else None,
            bool(a["regularizar"]) if a.get("regularizar") is not None else None, prot, a.get("preset"),
            bool(a.get("loop", True)), prancha=bool(a.get("prancha")), franja=bool(a.get("franja", True)))
    except (sequencia.entradas.ErroEntrada, ValueError) as e:
        raise ErroFerramenta(str(e))
    quadros = r["quadros"]
    q0 = int(a.get("quadro_inicial") or 0)
    await ctx.aseprite("quadro", {"acao": "garantir", "total": q0 + len(quadros)})
    for i, q in enumerate(quadros):
        await escrever_rgba(ctx, camada, q0 + i, 0, 0, q, np.ones(q.shape[:2], np.uint8))
        await ctx.aseprite("quadro", {"acao": "duracao", "indice": q0 + i, "ms": ms})
    estado = a.get("estado")
    if estado:
        existentes = {t["nome"] for t in (await ctx.sprite_atual())["sprite"].get("tags", [])}
        if estado in existentes:
            await ctx.aseprite("tag", {"acao": "remover", "nome": estado})
        await ctx.aseprite("tag", {"acao": "criar", "nome": estado, "de": q0, "ate": q0 + len(quadros) - 1})
    rel = r["relatorio"]
    f = dict(f)
    f["sequencia"] = {"fonte": str(a["fonte"]), "estado": estado, "quadros": len(quadros),
                      "pisca_depois": rel["pisca_depois"], "indices": r["indices"]}
    ctx.salvar_ficha(chave, f)
    ident = ""
    if rel["identidade"]:
        colados = sum(1 for x in rel["identidade"] if x["colou"])
        ident = f" · identidade: {colados}/{len(rel['identidade'])} peças coladas"
    pasta = Path(f.get("pasta") or Path(a["fonte"]).parent)
    folha = ""
    if a.get("saida_folha"):
        arqs = sequencia.spritesheet.salvar(quadros, a["saida_folha"], estado or "sequencia", ms, estado, pivo,
                                            bool(a.get("loop", True)))
        folha = f" · folha {arqs['png']}"
    val = rel["validacao"]
    return [texto(sequencia.validar.resumo(val) + "\n"
                  + f"preset {rel['preset'] or '-'} · escala {rel['escala']} · "
                  + f"{len(quadros)} quadros na camada '{camada}' (quadro {q0}…{q0 + len(quadros) - 1})"
                  + (f", tag '{estado}'" if estado else "") + f" · deriva {rel['deriva']} · pisca "
                  f"{rel['pisca_antes']:.2%} → {rel['pisca_depois']:.2%}{ident}{folha}. Próximo: horys_contorno → "
                  "horys_portao → horys_revisar."),
            imagem(_tira(quadros, pasta if pasta.exists() else Path(a["fonte"]).parent))]


@ferramenta("horys_guia_poses", """GUIA DE POSE: as poses do plano em silhueta, em grade, com a mesma escala e o mesmo
chão, para anexar ao prompt de poses (horys_prompt_traducao modo poses, 'guia_pose'). 'fonte' = o JSON do atlas do
Kiln (ou do Noct 3D) ou uma pasta de PNGs já renderizados; 'linhas' × 'colunas' = poses (ex.: 2×4 = 8; o andar do
golem pede 4–8 silhuetas); 'plano' andar | golpe escolhe os quadros-chave. Grava o PNG em 'saida'.""",
            {"fonte": STR, "linhas": INT, "colunas": INT, "plano": STR, "saida": STR, "celula_w": INT,
             "celula_h": INT}, ["fonte", "saida"])
async def guia_poses(ctx, a):
    from ..sequencia import guia
    try:
        quadros = sequencia.entradas.carregar(a["fonte"])
        quadros = sequencia.fundo.tirar_fundo(quadros)
    except sequencia.entradas.ErroEntrada as e:
        raise ErroFerramenta(str(e))
    lin, col = int(a.get("linhas") or 2), int(a.get("colunas") or 4)
    im, pick = guia.grade_silhuetas(quadros, lin, col, (int(a.get("celula_w") or 384), int(a.get("celula_h") or 512)),
                                    a.get("plano"))
    saida = Path(a["saida"])
    saida.parent.mkdir(parents=True, exist_ok=True)
    im.save(saida)
    return [texto(f"guia de pose {lin}×{col} em {saida} (quadros {pick} de {len(quadros)}). Anexe ao prompt de poses."),
            imagem(_miniatura(saida, 900))]


@ferramenta("horys_validar_sequencia", """VALIDAÇÃO OBJETIVA de uma animação pronta, sem Aseprite: 'fonte' = pasta de PNGs,
manifest.json de render 3D, grade (com 'linhas' e 'colunas') ou folha PNG em tira (com 'colunas'). Mede: mesmo canvas,
alpha só 0/255, cores na paleta ('paleta' #hex, ou a do 'estilo'), proporção (altura estável), deriva horizontal,
linha dos pés, pivô ('pivo' [x,y]), cintilação, quadros repetidos, loop último→primeiro, silhueta e cabeça
reconhecíveis, elementos que somem. Os números não substituem a revisão: sequência que desliza continua reprovada.""",
            {"fonte": STR, "linhas": INT, "colunas": INT, "paleta": LISTA_STR, "estilo": STR,
             "pivo": {"type": "array", "items": {"type": "number"}}, "loop": BOOL}, ["fonte"])
async def validar_sequencia(ctx, a):
    try:
        quadros = sequencia.entradas.carregar(a["fonte"], a.get("linhas") or (1 if a.get("colunas") else None),
                                              a.get("colunas"))
    except sequencia.entradas.ErroEntrada as e:
        raise ErroFerramenta(str(e))
    paleta = a.get("paleta")
    if not paleta and a.get("estilo"):
        paleta = _hexes_paleta(_estilo(a["estilo"]))
    pivo = tuple(a["pivo"]) if a.get("pivo") else None
    rel = sequencia.validar.validar(quadros, paleta, pivo, bool(a.get("loop", True)))
    return [texto(sequencia.validar.resumo(rel) + "\nmétricas: " + str(rel["metricas"]))]


@ferramenta("horys_colagem", """COLAGEM GUIADA: o gerador só diz ONDE cada peça vai; os pixels vêm da arte-mestra.
'mestre' = conceito aprovado em pixel art ampliada (lido na grade dele: pixel quadrado, fase pelo Sobel). 'guia' = os
quadros da animação gerados a partir desse conceito (PNG em prancha de poses soltas, ou grade com 'linhas' e
'colunas', ou pasta). Os guias vão para a grade do mestre (escala única, moda na paleta) e cada peça de 'pecas'
[{nome, rect [x,y,w,h] no mestre recortado, apagar: faixa|caixa|nada, busca, espelho, erro_max}] é achada em cada
quadro e colada exata por cima, na ordem dada. Cabeça/cabelo acima dos ombros: apagar 'faixa'. Deixe de fora o que
se mexe (braço, perna): fica como o guia desenhou e é o que se limpa à mão. Paleta: 'paleta' #hex, a do 'estilo',
ou 'cores' tiradas do conceito (padrão 16). Sem 'pecas', só devolve o mestre com régua de linhas/colunas para
escolher os rects. Grava em 'saida' os quadros, o mestre, a folha PNG + JSON + GIF e devolve a estabilidade (px de
cada peça diferentes do quadro 0). Não precisa do Aseprite. Depois: horys_validar_sequencia → horys_revisar.""",
            {"mestre": STR, "guia": STR, "pecas": {"type": "array", "items": {"type": "object"}},
             "saida": STR, "linhas": INT, "colunas": INT, "paleta": LISTA_STR, "estilo": STR, "cores": INT,
             "cor_fundo": STR, "busca": INT, "ms": INT, "estado": STR, "loop": BOOL}, ["mestre", "saida"])
async def colagem_ferramenta(ctx, a):
    for k in ("mestre", "guia"):
        if a.get(k) and not Path(a[k]).exists():
            raise ErroFerramenta(f"{k} não encontrado: {a[k]}")
    paleta = a.get("paleta") or (_hexes_paleta(_estilo(a["estilo"])) if a.get("estilo") else None)
    saida = Path(a["saida"])
    saida.mkdir(parents=True, exist_ok=True)
    try:
        if not a.get("pecas") or not a.get("guia"):
            mestre, pal, info = sequencia.colagem.mestre_de_conceito(a["mestre"], paleta, int(a.get("cores") or 16),
                                                                     a.get("cor_fundo") or "auto")
            Image.fromarray(mestre).save(saida / "mestre.png")
            return [texto(f"mestre {info['tamanho'][0]}x{info['tamanho'][1]} (bloco {info['bloco']} px, "
                          f"{len(pal)} cores) em {saida / 'mestre.png'}. Escolha os rects das peças na régua."),
                    imagem(_regua(mestre, saida))]
        r = sequencia.colagem.colagem(a["mestre"], a["guia"], a["pecas"], paleta, int(a.get("cores") or 16),
                                      a.get("linhas"), a.get("colunas"), None, a.get("cor_fundo") or "auto",
                                      int(a.get("busca") or 4))
    except (sequencia.entradas.ErroEntrada, ValueError) as e:
        raise ErroFerramenta(str(e))
    quadros = r["quadros"]
    Image.fromarray(r["mestre"]).save(saida / "mestre.png")
    for i, q in enumerate(quadros):
        Image.fromarray(q).save(saida / f"quadro_{i:02d}.png")
    estado = a.get("estado") or "colagem"
    arqs = sequencia.spritesheet.salvar(quadros, saida, estado, int(a.get("ms") or 160), estado, None,
                                        bool(a.get("loop", True)))
    falhou = [f"{x['nome']}@{x['quadro']} (erro {x['erro']})" for x in r["relatorio"] if not x["colou"]]
    return [texto(f"{len(quadros)} quadros · paleta {len(r['paleta'])} cores · grade bloco {r['grade']['bloco']} px"
                  f" · estabilidade (px ≠ quadro 0): {r['estabilidade']}"
                  + (f" · NÃO coladas: {', '.join(falhou)}" if falhou else "")
                  + f" · folha {arqs['png']}. Próximo: horys_validar_sequencia → horys_revisar."),
            imagem(_tira(quadros, saida))]


def _regua(img: np.ndarray, pasta: Path, k: int = 8) -> str:
    """Mestre ampliado com linha a cada 5 px e número a cada 10, para escolher rects."""
    from PIL import ImageDraw
    h, w = img.shape[:2]
    fundo_ = Image.new("RGBA", (w * k + 30, h * k + 30), (255, 255, 255, 255))
    fundo_.paste(Image.fromarray(img).resize((w * k, h * k), Image.NEAREST), (30, 30),
                 Image.fromarray(img).resize((w * k, h * k), Image.NEAREST))
    d = ImageDraw.Draw(fundo_)
    for x in range(0, w + 1, 5):
        d.line([(30 + x * k, 30), (30 + x * k, 30 + h * k)], fill=(0, 160, 255, 255) if x % 10 else (255, 0, 0, 255))
        if x % 10 == 0:
            d.text((30 + x * k + 2, 2), str(x), fill=(0, 0, 0, 255))
    for y in range(0, h + 1, 5):
        d.line([(30, 30 + y * k), (30 + w * k, 30 + y * k)], fill=(0, 160, 255, 255) if y % 10 else (255, 0, 0, 255))
        if y % 10 == 0:
            d.text((2, 30 + y * k + 2), str(y), fill=(0, 0, 0, 255))
    caminho = pasta / "mestre_regua.png"
    fundo_.save(caminho)
    return _miniatura(caminho, 900)
