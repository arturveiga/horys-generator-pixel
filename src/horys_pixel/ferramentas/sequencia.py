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


@ferramenta("horys_sequencia", """MOTOR DE SEQUÊNCIA: trata os quadros de uma animação como um todo. 'fonte' = pasta
de PNGs, uma grade (PNG + 'linhas' e 'colunas'), um vídeo (precisa do ffmpeg) ou o JSON do atlas do Kiln. Etapas:
fundo por célula → registro (altura alvo, pés e pivô da ficha; 'escala' por_quadro | comum) → escolha de quadros
('plano' andar | golpe com 'n') → quantização conjunta na paleta do estilo → redução por moda → anti-cintilação →
trava de identidade ('base' = PNG da base aprovada no tamanho final e 'decalques' [{nome, rect [x,y,w,h], busca}]) →
limpeza (órfãos e borda). Uma grade (imagem) só entra com o portão de entrada APROVADO, salvo 'forcar' + 'motivo'.
Escreve na camada (padrão: a de cima da ficha) a partir do quadro 'quadro_inicial', cria a
tag 'estado' e devolve o relatório (deriva, % de pixels que piscam antes e depois). Depois: horys_contorno →
horys_portao.""",
            {"fonte": STR, "altura": INT, "linhas": INT, "colunas": INT, "fps": {"type": "number"},
             "estado": STR, "camada": STR, "quadro_inicial": INT, "ms": INT, "plano": STR, "n": INT, "escala": STR,
             "fator": INT, "base": STR, "decalques": {"type": "array", "items": {"type": "object"}},
             "limpar_min": INT, "regularizar": BOOL, "cor_fundo": STR, "proteger": LISTA_STR,
             "forcar": BOOL, "motivo": STR},
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
            a.get("fps"), a.get("cor_fundo") or "auto", a.get("plano"), a.get("n"), a.get("escala") or "por_quadro",
            int(a.get("fator") or 4), base, a.get("decalques"), int(a.get("limpar_min", 3)),
            bool(a.get("regularizar", True)), prot)
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
    return [texto(f"{len(quadros)} quadros na camada '{camada}' (quadro {q0}…{q0 + len(quadros) - 1})"
                  + (f", tag '{estado}'" if estado else "") + f" · deriva {rel['deriva']} · pisca "
                  f"{rel['pisca_antes']:.2%} → {rel['pisca_depois']:.2%}{ident}. Próximo: horys_contorno → "
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
