"""Fatiamento modular em partes: presets, contratos de junção, validador, recorte e extensão.

Módulo independente do Aseprite: trabalha só com arrays RGBA (H, W, 4) uint8 por parte e por quadro.

Convenções
- `partes` vêm de baixo para cima (a ordem de empilhamento). `contorno` e `sombra` são camadas geradas/reservadas
  e nunca são partes. `referencia` é uma camada oculta com o desenho completo, só para consulta.
- Uma JUNÇÃO é um contrato entre duas partes: a INFERIOR (mais abaixo na pilha) continua por baixo da SUPERIOR
  (anatomia oculta) para que a parte MÓVEL possa girar/deslizar 1–2 px sem abrir buraco.
- Nenhuma operação de recorte/extensão pode mudar a imagem composta: só escreve em pixels onde a composição
  resultante é idêntica à anterior (pixels cobertos por uma parte de cima ou já da mesma cor).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage

RESERVADAS_PARTES = ("contorno", "sombra", "revisao", "referencia", "regua")
MAGENTA = (255, 0, 255, 255)
COBERTURA_MINIMA = 0.90
DIRECOES = tuple((dx, dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dx, dy) != (0, 0))   # as 8 direções
_ELEM8 = np.ones((3, 3), bool)


# ------------------------------------------------------------------ contratos

@dataclass(frozen=True)
class Juncao:
    nome: str
    inferior: str
    superior: str
    movel: str
    nota: str = ""
    linha: str = "por_contraste"

    def como_dict(self) -> dict:
        return {"nome": self.nome, "inferior": self.inferior, "superior": self.superior, "movel": self.movel,
                "nota": self.nota, "linha": self.linha}


@dataclass(frozen=True)
class Preset:
    nome: str
    descricao: str
    partes: tuple[str, ...]
    juncoes: tuple[Juncao, ...]
    componentes_max: tuple[tuple[str, int], ...] = ()
    espessura_fina: tuple[str, ...] = ()

    @property
    def oculto(self) -> tuple[str, ...]:
        """Partes que precisam de anatomia oculta: as que ficam por baixo de outra em alguma junção."""
        return tuple(p for p in self.partes if any(j.inferior == p for j in self.juncoes))


def validar_contratos(partes: list[str] | tuple[str, ...], juncoes: list[Juncao] | tuple[Juncao, ...]) -> list[str]:
    """Erros de definição (partes reservadas/duplicadas, junção que cita parte inexistente ou fora de ordem)."""
    erros = []
    if len(set(partes)) != len(partes):
        erros.append("partes duplicadas")
    for p in partes:
        if p in RESERVADAS_PARTES:
            erros.append(f"'{p}' é camada reservada/gerada, não parte desenhável")
    ordem = {p: i for i, p in enumerate(partes)}
    for j in juncoes:
        for papel, p in (("inferior", j.inferior), ("superior", j.superior)):
            if p not in ordem:
                erros.append(f"junção {j.nome}: {papel} '{p}' não está nas partes")
        if j.movel not in (j.inferior, j.superior):
            erros.append(f"junção {j.nome}: a parte móvel '{j.movel}' tem que ser a inferior ou a superior")
        if j.inferior in ordem and j.superior in ordem and ordem[j.inferior] >= ordem[j.superior]:
            erros.append(f"junção {j.nome}: '{j.inferior}' não está abaixo de '{j.superior}' na pilha")
    return erros


def _j(nome, inferior, superior, movel, nota="", linha="por_contraste"):
    return Juncao(nome, inferior, superior, movel, nota, linha)


HUMANOIDE = Preset(
    "humanoide",
    "Humanoide base alinhado ao esqueleto do SpriteKiln, sem acessórios obrigatórios.",
    ("braco-traseiro", "perna-traseira", "corpo", "perna-frente", "cabeca", "braco-frente"),
    (
        _j("perna-traseira-corpo", "perna-traseira", "corpo", "perna-traseira"),
        _j("perna-frente-corpo", "corpo", "perna-frente", "perna-frente"),
        _j("corpo-cabeca", "corpo", "cabeca", "cabeca"),
        _j("braco-traseiro-corpo", "braco-traseiro", "corpo", "braco-traseiro"),
        _j("corpo-braco-frente", "corpo", "braco-frente", "braco-frente"),
    ),
)


HUMANOIDE_FERREIRO = Preset(
    "humanoide-ferreiro",
    "Humanoide de ferreiro: perna de trás, corpo, avental, cabelo, barba, braços, martelo e óculos.",
    ("perna-traseira", "corpo-base", "avental-torso", "cabelo", "barba", "braco-traseiro", "braco-frente",
     "martelo", "oculos"),
    (
        _j("perna-corpo", "perna-traseira", "corpo-base", "perna-traseira", "quadril: a perna entra sob o corpo"),
        _j("corpo-avental", "corpo-base", "avental-torso", "avental-torso", "o corpo continua sob o avental"),
        _j("corpo-cabelo", "corpo-base", "cabelo", "cabelo", "a cabeça continua sob o cabelo"),
        _j("corpo-barba", "corpo-base", "barba", "barba", "o rosto continua sob a barba"),
        _j("corpo-oculos", "corpo-base", "oculos", "oculos", "o rosto continua sob os óculos"),
        _j("corpo-braco-traseiro", "corpo-base", "braco-traseiro", "braco-traseiro", "ombro de trás"),
        _j("avental-braco-traseiro", "avental-torso", "braco-traseiro", "braco-traseiro", "o avental sob o braço"),
        _j("corpo-braco-frente", "corpo-base", "braco-frente", "braco-frente", "ombro da frente"),
        _j("avental-braco-frente", "avental-torso", "braco-frente", "braco-frente", "o avental sob o braço"),
        _j("braco-martelo", "braco-frente", "martelo", "martelo", "a mão segura o martelo (o braço entra sob o cabo)"),
    ),
    (("oculos", 2), ("cabelo", 3), ("barba", 2)),
    ("oculos",),
)

PRESETS: dict[str, Preset] = {p.nome: p for p in (HUMANOIDE, HUMANOIDE_FERREIRO)}


def preset(nome: str) -> Preset:
    if nome not in PRESETS:
        raise ValueError(f"preset de partes '{nome}' não existe (há: {', '.join(PRESETS)})")
    return PRESETS[nome]


def juncoes_de_dicts(lista: list[dict]) -> list[Juncao]:
    return [Juncao(d["nome"], d["inferior"], d["superior"], d.get("movel") or d["superior"], d.get("nota", ""),
                   d.get("linha", "por_contraste"))
            for d in lista]


def contratos_da_ficha(ficha: dict) -> tuple[list[str], list[Juncao], list[str]]:
    """(partes, junções, partes com anatomia oculta) de uma ficha modular; completa pelo preset quando falta."""
    pr = PRESETS.get(ficha.get("preset_partes") or "")
    partes = list(ficha.get("partes") or (pr.partes if pr else []))
    if ficha.get("juncoes"):
        juncoes = juncoes_de_dicts(ficha["juncoes"])
    else:
        juncoes = list(pr.juncoes) if pr else []
    oculto = list(ficha["partes_oculto"]) if ficha.get("partes_oculto") is not None else \
        [p for p in partes if any(j.inferior == p for j in juncoes)]
    return partes, juncoes, oculto


def campos_ficha_modular(nome_preset: str | None, partes: list[str] | None = None,
                         juncoes: list[dict] | None = None) -> dict:
    """Campos de ficha de um asset modular (modular, preset_partes, partes, juncoes, partes_oculto)."""
    pr = preset(nome_preset) if nome_preset else None
    p = list(pr.partes) if pr else list(partes or [])
    j = [x.como_dict() for x in pr.juncoes] if pr else list(juncoes or [])
    oculto = list(pr.oculto) if pr else [x for x in p if any(d["inferior"] == x for d in j)]
    return {"modular": True, "preset_partes": nome_preset or "", "partes": p, "juncoes": j, "partes_oculto": oculto,
            "componentes_max": dict(pr.componentes_max) if pr else {},
            "espessura_fina": list(pr.espessura_fina) if pr else []}


# ------------------------------------------------------------------ imagem

def mascara(im: np.ndarray | None, forma: tuple[int, int] | None = None) -> np.ndarray:
    if im is None:
        return np.zeros(forma or (0, 0), bool)
    return im[..., 3] > 0


def compor(partes: dict[str, np.ndarray], ordem: list[str] | tuple[str, ...], forma: tuple[int, int] | None = None
           ) -> np.ndarray:
    """Composição das partes (de baixo para cima) por 'over' com alfa; igual ao do Aseprite para alfa binário."""
    ref = next((partes[p] for p in ordem if partes.get(p) is not None), None)
    if ref is None:
        h, w = forma or (0, 0)
        return np.zeros((h, w, 4), np.uint8)
    h, w = ref.shape[:2]
    out = np.zeros((h, w, 4), np.float32)
    for p in ordem:
        im = partes.get(p)
        if im is None:
            continue
        a = im[..., 3:4].astype(np.float32) / 255
        out[..., :3] = out[..., :3] * (1 - a) + im[..., :3] * a
        out[..., 3:4] = out[..., 3:4] + a * 255 * (1 - out[..., 3:4] / 255)
    return np.clip(out + 0.5, 0, 255).astype(np.uint8)


def _dilatar(m: np.ndarray, k: int = 1) -> np.ndarray:
    return ndimage.binary_dilation(m, _ELEM8, iterations=k) if k > 0 else m.copy()


def _deslocar(m: np.ndarray, dx: int, dy: int) -> np.ndarray:
    out = np.zeros_like(m)
    h, w = m.shape
    ys, xs = slice(max(0, dy), h + min(0, dy)), slice(max(0, dx), w + min(0, dx))
    yo, xo = slice(max(0, -dy), h + min(0, -dy)), slice(max(0, -dx), w + min(0, -dx))
    out[ys, xs] = m[yo, xo]
    return out


def _profundidade(a: np.ndarray, b: np.ndarray) -> int:
    """Quantos px a parte `a` entra por baixo de `b`: maior distância (tabuleiro) ao vazio de `b` entre os px de a∩b."""
    inter = a & b
    if not inter.any():
        return 0
    dist = ndimage.distance_transform_cdt(np.pad(b, 1), metric="chessboard")[1:-1, 1:-1]
    return int(dist[inter].max())


def _componentes(m: np.ndarray) -> int:
    return int(ndimage.label(m, _ELEM8)[1])


def _luminancia(rgb: np.ndarray) -> np.ndarray:
    return rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114


def _pontos(m: np.ndarray, limite: int = 24) -> list[list[int]]:
    ys, xs = np.nonzero(m)
    return [[int(x), int(y)] for x, y in zip(xs[:limite], ys[:limite])]


# ------------------------------------------------------------------ relatório

@dataclass
class Problema:
    gravidade: str            # 'erro' | 'aviso'
    codigo: str
    mensagem: str
    quadro: int | None = None
    parte: str | None = None
    juncao: str | None = None
    pontos: list = field(default_factory=list)

    def como_dict(self) -> dict:
        return {"gravidade": self.gravidade, "codigo": self.codigo, "mensagem": self.mensagem, "quadro": self.quadro,
                "parte": self.parte, "juncao": self.juncao, "pontos": self.pontos}

    def linha(self) -> str:
        onde = ("q%d " % self.quadro if self.quadro is not None else "") + (self.juncao or self.parte or "")
        return f"{'ERRO' if self.gravidade == 'erro' else 'aviso'} [{self.codigo}] {onde.strip()}: {self.mensagem}"


@dataclass
class Relatorio:
    preset: str
    quadros: int
    problemas: list[Problema] = field(default_factory=list)
    medidas: dict = field(default_factory=dict)

    @property
    def erros(self) -> list[Problema]:
        return [p for p in self.problemas if p.gravidade == "erro"]

    @property
    def avisos(self) -> list[Problema]:
        return [p for p in self.problemas if p.gravidade == "aviso"]

    @property
    def ok(self) -> bool:
        return not self.erros

    def texto(self, limite: int = 80) -> str:
        cab = f"PARTES {'APROVADAS' if self.ok else 'REPROVADAS'} — preset {self.preset or '—'}, {self.quadros} quadro(s): " \
              f"{len(self.erros)} erro(s), {len(self.avisos)} aviso(s)"
        linhas = [p.linha() for p in self.erros + self.avisos]
        if len(linhas) > limite:
            linhas = linhas[:limite] + [f"... (+{len(linhas) - limite}; veja medidas/partes.json)"]
        return "\n".join([cab] + linhas) + "\n"

    def como_dict(self) -> dict:
        return {"preset": self.preset, "quadros": self.quadros, "ok": self.ok, "erros": len(self.erros),
                "avisos": len(self.avisos), "medidas": self.medidas,
                "problemas": [p.como_dict() for p in self.problemas]}

    def json(self) -> str:
        return json.dumps(self.como_dict(), ensure_ascii=False, indent=1)


# ------------------------------------------------------------------ validador

def _frontier_linha(a_vis: np.ndarray, b: np.ndarray, quadro_rgba: tuple[np.ndarray, np.ndarray],
                    cores_linha: set[tuple[int, int, int]] | None) -> tuple[int, int]:
    """(pixels na fronteira entre a parte inferior visível e a superior, quantos são 'linha')."""
    fr = (b & _dilatar(a_vis)) | (a_vis & _dilatar(b))
    n = int(fr.sum())
    if not n:
        return 0, 0
    inf, sup = quadro_rgba
    rgb = np.where(b[..., None], sup[..., :3], inf[..., :3])
    if cores_linha:
        eh = np.zeros(fr.shape, bool)
        for c in cores_linha:
            eh |= np.all(rgb == np.array(c, np.uint8), axis=-1)
    else:
        eh = _luminancia(rgb.astype(np.float32)) < 70
    return n, int((fr & eh).sum())


def checar(preset_nome: str | None, quadros: list[dict[str, np.ndarray]], *, partes: list[str] | None = None,
           juncoes: list[Juncao] | None = None, oculto: list[str] | None = None,
           referencias: list[np.ndarray | None] | None = None, cores_linha: set | None = None,
           ignorar_linha: bool = False, componentes_max: dict[str, int] | None = None,
           espessura_fina: list[str] | None = None) -> Relatorio:
    """Valida as partes de cada quadro. `quadros`: [{parte: rgba}], ordem das partes = de baixo para cima.

    Por quadro: parte vazia (erro); parte desconexa (erro); referência coberta ≥ 90% (erro).
    Por junção: partes têm que se tocar (erro); inferior ≥ 1 px sob a superior (erro; aviso se < 2 px);
    deslocar a parte móvel 1 px nas 8 direções abre buraco (erro) e 2 px (aviso); cobertura da anatomia oculta
    < 90% na faixa de 1 px (erro) ou de 2 px (aviso), só para as partes de `oculto`; falta de linha interna na
    fronteira (erro se nenhuma, aviso se < 50%).
    """
    if preset_nome:
        pr = preset(preset_nome)
        partes = list(partes or pr.partes)
        juncoes = list(juncoes if juncoes is not None else pr.juncoes)
    partes, juncoes = list(partes or []), list(juncoes or [])
    pr = PRESETS.get(preset_nome or "")
    componentes_max = componentes_max or (dict(pr.componentes_max) if pr else {})
    espessura_fina = set(espessura_fina or (pr.espessura_fina if pr else ()))
    if oculto is None:
        oculto = [p for p in partes if any(j.inferior == p for j in juncoes)]
    rel = Relatorio(preset_nome or "", len(quadros))
    for e in validar_contratos(partes, juncoes):
        rel.problemas.append(Problema("erro", "contrato", e))
    if not quadros:
        rel.problemas.append(Problema("erro", "sem-quadros", "nenhum quadro para validar"))
        return rel
    resumo_juncoes: dict[str, dict] = {}
    for k, q in enumerate(quadros):
        faltam = [p for p in partes if q.get(p) is None]
        for p in faltam:
            rel.problemas.append(Problema("erro", "camada-faltando", f"a camada '{p}' não existe", k, p))
        forma = next((q[p].shape[:2] for p in partes if q.get(p) is not None), None)
        if forma is None:
            continue
        masc = {p: mascara(q.get(p), forma) for p in partes}
        for p in partes:
            if q.get(p) is None:
                continue
            n = int(masc[p].sum())
            if n == 0:
                rel.problemas.append(Problema("erro", "parte-vazia", "parte sem nenhum pixel", k, p))
            else:
                c = _componentes(masc[p])
                max_c = int(componentes_max.get(p, 1))
                if c > max_c:
                    rel.problemas.append(Problema("erro", "parte-desconexa", f"{c} pedaços separados (8-vizinhança): "
                                                  f"máximo declarado {max_c}", k, p, pontos=_pontos(masc[p])))
        if referencias and k < len(referencias) and referencias[k] is not None:
            ref = referencias[k][..., 3] > 0
            if ref.any():
                uniao = np.zeros(forma, bool)
                for p in partes:
                    uniao |= masc[p]
                cob = float((uniao & ref).sum()) / float(ref.sum())
                rel.medidas.setdefault("cobertura_referencia", []).append(round(cob, 4))
                if cob < COBERTURA_MINIMA:
                    rel.problemas.append(Problema("erro", "cobertura-referencia",
                                                  f"as partes cobrem {cob:.0%} da referência (mínimo 90%)", k,
                                                  pontos=_pontos(ref & ~uniao)))
        for j in juncoes:
            if q.get(j.inferior) is None or q.get(j.superior) is None:
                continue
            a, b = masc[j.inferior], masc[j.superior]
            if not a.any() or not b.any():
                continue                       # já reportado como parte vazia
            res = resumo_juncoes.setdefault(j.nome, {"profundidade": [], "buraco_1px": [], "buraco_2px": [],
                                                      "cobertura_1px": [], "cobertura_2px": []})
            if not (a & b).any() and not (a & _dilatar(b)).any():
                rel.problemas.append(Problema("erro", "nao-tocam", f"'{j.inferior}' e '{j.superior}' não se tocam",
                                              k, juncao=j.nome))
                continue
            prof = _profundidade(a, b)
            res["profundidade"].append(prof)
            if prof < 1:
                rel.problemas.append(Problema("erro", "sem-sobreposicao", f"'{j.inferior}' não continua nem 1 px sob "
                                              f"'{j.superior}': estenda-a por baixo (horys_partes_estender)", k,
                                              juncao=j.nome))
            elif prof < 2 and j.inferior not in espessura_fina:
                rel.problemas.append(Problema("aviso", "sobreposicao-curta", f"'{j.inferior}' entra só {prof} px sob "
                                              f"'{j.superior}' (ideal ≥ 2)", k, juncao=j.nome))
            _simular(rel, k, j, masc, partes, res)
            if j.inferior in oculto:
                _cobertura(rel, k, j, a, b, res)
            if not ignorar_linha:
                _linha_interna(rel, k, j, a, b, q, cores_linha)
    # pior valor entre os quadros: mínimo de profundidade/cobertura, máximo de buraco
    rel.medidas["juncoes"] = {n: {c: ((max(v) if c.startswith("buraco") else min(v)) if v else None)
                                  for c, v in r.items()} for n, r in resumo_juncoes.items()}
    return rel


_CRUZ = ndimage.generate_binary_structure(2, 1)


def _cruz(m: np.ndarray, k: int) -> np.ndarray:
    """Dilatação em cruz (distância de quarteirão ≤ k)."""
    return ndimage.binary_dilation(m, _CRUZ, iterations=k) if k > 0 else m.copy()


def _entre(cheio: np.ndarray, r: int) -> np.ndarray:
    """Pixels com algo preenchido a ≤ r px dos DOIS lados, na horizontal ou na vertical (cara de fresta)."""
    esq = np.zeros_like(cheio)
    dir_ = np.zeros_like(cheio)
    cima = np.zeros_like(cheio)
    baixo = np.zeros_like(cheio)
    for s in range(1, r + 1):
        esq |= _deslocar(cheio, s, 0)       # esq[y, x] = cheio[y, x - s]
        dir_ |= _deslocar(cheio, -s, 0)
        cima |= _deslocar(cheio, 0, s)
        baixo |= _deslocar(cheio, 0, -s)
    return (esq & dir_) | (cima & baixo)


def _simular(rel: Relatorio, k: int, j: Juncao, masc: dict, partes: list[str], res: dict):
    """Desloca a parte móvel 1 e 2 px nas 8 direções e procura buracos (frestas) junto da outra parte da junção.

    Buraco = pixel que a parte móvel cobria, que ninguém mais cobre depois do deslocamento, que fica a ≤ px da outra
    parte da junção e que está espremido entre pixels preenchidos (não é só a silhueta da parte andando para o vazio).
    """
    movel = j.movel
    fixa = j.superior if movel == j.inferior else j.inferior
    outras = np.zeros_like(masc[movel])
    for p in partes:
        if p != movel:
            outras |= masc[p]
    for px, gravidade, cod in ((1, "erro", "buraco-1px"), (2, "aviso", "buraco-2px")):
        pior, pior_dir, pior_pts = 0, None, []
        for dx, dy in DIRECOES:
            novo = _deslocar(masc[movel], dx * px, dy * px)
            descoberto = masc[movel] & ~novo & ~outras
            buraco = descoberto & _dilatar(masc[fixa], px) & _entre(novo | outras, px)
            n = int(buraco.sum())
            if n > pior:
                pior, pior_dir, pior_pts = n, (dx * px, dy * px), _pontos(buraco)
        res["buraco_%dpx" % px].append(pior)
        if pior:
            rel.problemas.append(Problema(gravidade, cod, f"deslocar '{movel}' {px} px abre buraco ({pior} px; pior "
                                          f"direção {pior_dir}): falta anatomia oculta sob '{j.superior}'", k,
                                          juncao=j.nome, pontos=pior_pts))


def _cobertura(rel: Relatorio, k: int, j: Juncao, a: np.ndarray, b: np.ndarray, res: dict):
    """Anatomia oculta da inferior: fração da faixa da superior junto da inferior visível que a inferior já cobre."""
    visivel = a & ~b
    if not visivel.any():
        return
    for px, gravidade, cod in ((1, "erro", "cobertura-oculta-1px"), (2, "aviso", "cobertura-oculta-2px")):
        faixa = b & _cruz(visivel, px)
        if not faixa.any():
            continue
        cob = float((faixa & a).sum()) / float(faixa.sum())
        res["cobertura_%dpx" % px].append(round(cob, 4))
        if cob < COBERTURA_MINIMA:
            rel.problemas.append(Problema(gravidade, cod, f"'{j.inferior}' cobre {cob:.0%} da faixa de {px} px sob "
                                          f"'{j.superior}' (mínimo 90%)", k, juncao=j.nome,
                                          pontos=_pontos(faixa & ~a)))


def _linha_interna(rel: Relatorio, k: int, j: Juncao, a: np.ndarray, b: np.ndarray, q: dict, cores_linha):
    a_vis = a & ~b
    fronteira_sup = b & _dilatar(a_vis)
    fronteira_inf = a_vis & _dilatar(b)
    movel_sup = j.movel == j.superior
    alvo = fronteira_sup if movel_sup else fronteira_inf
    errado = fronteira_inf if movel_sup else fronteira_sup
    rgb_alvo = q[j.superior][..., :3] if movel_sup else q[j.inferior][..., :3]
    rgb_errado = q[j.inferior][..., :3] if movel_sup else q[j.superior][..., :3]
    def eh_linha(rgb):
        out = np.zeros(a.shape, bool)
        if cores_linha:
            for c in cores_linha:
                out |= np.all(rgb == np.array(c, np.uint8), axis=-1)
        else:
            out = _luminancia(rgb.astype(np.float32)) < 70
        return out
    n, linha = int(alvo.sum()), int((alvo & eh_linha(rgb_alvo)).sum())
    if n < 4:
        return
    linha_errada = int((errado & eh_linha(rgb_errado)).sum())
    if linha == 0 and linha_errada:
        rel.problemas.append(Problema("erro", "linha-no-lado-errado", "a linha está na parte fixa e não acompanha "
                                      f"'{j.movel}'", k, juncao=j.nome))
        return
    if j.linha == "proibida":
        if linha:
            rel.problemas.append(Problema("erro", "linha-proibida", "a junção declara linha proibida", k, juncao=j.nome))
        return
    frac = linha / n
    if linha == 0 and j.linha == "por_contraste":
        # Diferença de luminância normalizada: contraste forte já separa os planos.
        lado_a = q[j.inferior][fronteira_inf, :3].astype(np.float32)
        lado_b = q[j.superior][fronteira_sup, :3].astype(np.float32)
        if len(lado_a) and len(lado_b):
            dl = abs(float(_luminancia(lado_a).mean()) - float(_luminancia(lado_b).mean())) / 255.0
            if dl >= .08:
                return
    if linha == 0:
        rel.problemas.append(Problema("erro", "sem-linha-interna", f"nenhuma linha interna entre '{j.inferior}' e "
                                      f"'{j.superior}' ({n} px de fronteira)", k, juncao=j.nome))
    elif frac < 0.5:
        rel.problemas.append(Problema("aviso", "linha-interna-fraca", f"linha interna em só {frac:.0%} da fronteira "
                                      f"entre '{j.inferior}' e '{j.superior}'", k, juncao=j.nome))


# ------------------------------------------------------------------ vista explodida

def ocultos_da_parte(partes: dict[str, np.ndarray], ordem: list[str] | tuple[str, ...], parte: str) -> np.ndarray:
    """Pixels de `parte` cobertos por alguma parte de cima (opaca)."""
    im = partes.get(parte)
    if im is None:
        return np.zeros((0, 0), bool)
    cobre = np.zeros(im.shape[:2], bool)
    for p in ordem[list(ordem).index(parte) + 1:]:
        o = partes.get(p)
        if o is not None:
            cobre |= o[..., 3] == 255
    return (im[..., 3] > 0) & cobre


def vista_explodida(partes: dict[str, np.ndarray], ordem: list[str] | tuple[str, ...], colunas: int = 5,
                    escala: int = 4, nomes: bool = True) -> np.ndarray:
    """Cada parte na sua célula (recortada à união de todas), pixels ocultos em magenta; última célula = composição."""
    from PIL import Image, ImageDraw
    existentes = [p for p in ordem if partes.get(p) is not None]
    if not existentes:
        return np.zeros((8, 8, 4), np.uint8)
    uniao = np.zeros(partes[existentes[0]].shape[:2], bool)
    for p in existentes:
        uniao |= partes[p][..., 3] > 0
    if uniao.any():
        ys, xs = np.nonzero(uniao)
        y0, y1, x0, x1 = max(0, ys.min() - 1), ys.max() + 2, max(0, xs.min() - 1), xs.max() + 2
    else:
        y0, y1, x0, x1 = 0, uniao.shape[0], 0, uniao.shape[1]
    h, w = y1 - y0, x1 - x0
    celulas = []
    for p in existentes:
        c = partes[p][y0:y1, x0:x1].copy()
        oc = ocultos_da_parte(partes, ordem, p)[y0:y1, x0:x1]
        c[oc] = MAGENTA
        celulas.append((p, c))
    celulas.append(("composto", compor(partes, ordem)[y0:y1, x0:x1]))
    linhas_n = -(-len(celulas) // colunas)
    cab = 10 if nomes else 0
    tela = np.zeros((linhas_n * (h * escala + cab + 2), colunas * (w * escala + 2), 4), np.uint8)
    tela[...] = (38, 38, 46, 255)
    img = Image.fromarray(tela, "RGBA")
    for i, (nome, c) in enumerate(celulas):
        r, col = divmod(i, colunas)
        fundo = np.zeros((h, w, 4), np.uint8)
        fundo[...] = (70, 100, 70, 255)
        a = c[..., 3:4].astype(np.float32) / 255
        fundo[..., :3] = (c[..., :3] * a + fundo[..., :3] * (1 - a)).astype(np.uint8)
        grande = Image.fromarray(fundo, "RGBA").resize((w * escala, h * escala), Image.NEAREST)
        ox, oy = col * (w * escala + 2), r * (h * escala + cab + 2)
        img.paste(grande, (ox, oy + cab))
        if nomes:
            ImageDraw.Draw(img).text((ox + 1, oy), nome, fill=(240, 240, 240, 255))
    return np.array(img)


# ------------------------------------------------------------------ recorte e extensão (preservam a composição)

def _cor_do_vizinho(cor: np.ndarray, fonte: np.ndarray, novo: np.ndarray) -> np.ndarray:
    """Para cada px de `novo`, a cor de um vizinho de `fonte` (4-vizinhos primeiro, depois diagonais)."""
    h, w = fonte.shape
    saida = cor.copy()
    pendentes = novo.copy()
    for dy, dx in ((0, -1), (0, 1), (-1, 0), (1, 0), (-1, -1), (-1, 1), (1, -1), (1, 1)):
        viz = _deslocar(fonte, dx, dy)                       # viz[y, x] = fonte[y - dy, x - dx]
        cor_viz = np.roll(np.roll(cor, dy, axis=0), dx, axis=1)
        pega = pendentes & viz
        saida[pega] = cor_viz[pega]
        pendentes &= ~pega
    return saida


def compor_com(partes: dict[str, np.ndarray], ordem: list[str], nome: str, novo: np.ndarray) -> np.ndarray:
    alt = dict(partes)
    alt[nome] = novo
    return compor(alt, ordem)


def _so_composicao_igual(partes: dict[str, np.ndarray], ordem: list[str], nome: str, candidato: np.ndarray,
                         quer: np.ndarray) -> tuple[np.ndarray, int]:
    """Aplica `candidato` na parte `nome` só nos pixels de `quer` onde a composição não muda. (novo, recusados)."""
    antes = compor(partes, ordem)
    atual = partes[nome]
    cheio = atual.copy()
    cheio[quer] = candidato[quer]
    depois = compor_com(partes, ordem, nome, cheio)
    igual = np.all(antes == depois, axis=-1)
    ok = quer & igual
    novo = atual.copy()
    novo[ok] = candidato[ok]
    return novo, int((quer & ~igual).sum())


@dataclass
class Resultado:
    novo: np.ndarray
    alterados: int
    recusados: int
    detalhe: str = ""


def recortar(partes: dict[str, np.ndarray], ordem: list[str], parte: str, referencia: np.ndarray,
             regiao: tuple[int, int, int, int], sobrescrever: bool = False) -> Resultado:
    """Copia a região (x, y, w, h) da referência para `parte`. Só escreve onde a composição final não muda
    (pixel coberto por uma parte de cima, ou da mesma cor que a composição já tem); o resto é recusado."""
    if parte not in ordem or parte not in partes:
        raise ValueError(f"parte '{parte}' desconhecida")
    x, y, w, h = regiao
    H, W = referencia.shape[:2]
    reg = np.zeros((H, W), bool)
    reg[max(0, y):max(0, min(H, y + h)), max(0, x):max(0, min(W, x + w))] = True
    quer = reg & (referencia[..., 3] > 0)
    if not sobrescrever:
        quer &= partes[parte][..., 3] == 0
    quer &= np.any(referencia != partes[parte], axis=-1)
    novo, recusados = _so_composicao_igual(partes, ordem, parte, referencia, quer)
    alterados = int(np.any(novo != partes[parte], axis=-1).sum())
    return Resultado(novo, alterados, recusados)


def estender(partes: dict[str, np.ndarray], ordem: list[str], inferior: str, superior: str, px: int = 2,
             cores_linha: set[tuple[int, int, int]] | None = None
             ) -> Resultado:
    """Estende `inferior` por `px` (1–2) px por baixo de `superior` (só dentro da silhueta da superior), com a cor
    do vizinho mais próximo. Só pixels cobertos: a composição tem que ficar idêntica."""
    if px not in (1, 2):
        raise ValueError("px tem que ser 1 ou 2")
    if ordem.index(inferior) >= ordem.index(superior):
        raise ValueError(f"'{inferior}' não está abaixo de '{superior}'")
    a_im, b_im = partes[inferior], partes[superior]
    a, b = a_im[..., 3] > 0, b_im[..., 3] == 255
    cor = a_im.copy()
    atual = a.copy()
    novo_total = np.zeros_like(a)
    for _ in range(px):
        passo = _dilatar(atual) & b & ~atual
        if not passo.any():
            break
        # A borda costuma ser linha/sombra. Busca a moda 2–4 px para dentro e exclui cores de linha.
        candidatos = _dilatar(passo, 4) & atual & ~_dilatar(passo, 1)
        vals = a_im[candidatos]
        if len(vals):
            if cores_linha:
                vals = np.array([v for v in vals if tuple(int(x) for x in v[:3]) not in cores_linha], np.uint8)
            if len(vals):
                un, cnt = np.unique(vals, axis=0, return_counts=True)
                cor[passo] = un[int(cnt.argmax())]
            else:
                cor = _cor_do_vizinho(cor, atual, passo)
        else:
            cor = _cor_do_vizinho(cor, atual, passo)
        cor[passo, 3] = 255
        atual |= passo
        novo_total |= passo
    novo, recusados = _so_composicao_igual(partes, ordem, inferior, cor, novo_total)
    alterados = int(np.any(novo != a_im, axis=-1).sum())
    return Resultado(novo, alterados, recusados)
