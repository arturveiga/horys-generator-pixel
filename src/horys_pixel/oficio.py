"""Base de ofício de pixel art: regras por assunto, modelos de grade e paletas.

Os dados vêm do aseprite-ai-artist (MIT, ver oficio_dados/LICENSE-aseprite-ai-artist e ORIGEM.txt):
62 regras em Markdown (oficio_dados/regras), ~400 modelos ```grid dentro delas e 2006 paletas
(oficio_dados/paletas.json, cada uma com autor e fonte).

É conhecimento de OFÍCIO (proporção por tamanho, mão a 16 px, ciclo de andar...), não régua de estilo:
a régua continua sendo o Artur (ficha e aprovados). Um modelo é ponto de partida para adaptar à pose,
com as cores trocadas pela paleta do asset; nunca vira asset como está.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

DADOS = Path(__file__).parent / "oficio_dados"
REGRAS = DADOS / "regras"

_RE_GRID = re.compile(r"^```grid[ \t]+([^\s`]+)[ \t]*\n(.*?)^```", re.S | re.M)
_RE_LEGENDA = re.compile(r"^(\S)\s*=\s*(\S+)\s+(#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?)\s*$")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


@dataclass
class Regra:
    codigo: str          # "34"
    nome: str            # "34-hands-and-feet"
    titulo: str          # "Hands and feet"
    arquivo: Path

    @property
    def texto(self) -> str:
        return self.arquivo.read_text(encoding="utf-8")


@dataclass
class Modelo:
    nome: str
    regra: str
    legenda: dict = field(default_factory=dict)   # letra -> (papel, hex)
    linhas: list = field(default_factory=list)
    descricao: str = ""

    @property
    def largura(self) -> int:
        return max((len(l) for l in self.linhas), default=0)

    @property
    def altura(self) -> int:
        return len(self.linhas)

    def paleta(self, mapa: dict | None = None) -> dict:
        """letra -> hex; 'mapa' troca cores por letra ou por papel (ex.: {'skin-light': '#e8b796'})."""
        mapa = mapa or {}
        out = {}
        for letra, (papel, cor) in self.legenda.items():
            out[letra] = mapa.get(letra) or mapa.get(papel) or cor
        return out


@lru_cache(maxsize=1)
def regras() -> list[Regra]:
    out = []
    for p in sorted(REGRAS.glob("[0-9][0-9]-*.md")):
        primeira = next((l for l in p.read_text(encoding="utf-8").splitlines() if l.startswith("# ")), p.stem)
        out.append(Regra(p.stem[:2], p.stem, primeira.lstrip("# ").strip(), p))
    return out


def achar_regra(chave: str) -> Regra:
    k = str(chave).strip().removeprefix("rules://").removesuffix(".md")
    for r in regras():
        if k in (r.codigo, r.nome) or r.nome.endswith(k):
            return r
    nk = _norm(k)
    cand = [r for r in regras() if nk and (nk in _norm(r.nome) or nk in _norm(r.titulo))]
    if len(cand) == 1:
        return cand[0]
    if not cand:
        raise KeyError(f"regra '{chave}' não existe; veja o índice")
    raise KeyError(f"'{chave}' é ambíguo: " + ", ".join(r.nome for r in cand))


def secoes(texto: str) -> dict[str, str]:
    """Seções de nível 2 (## Título) -> texto."""
    out, atual, buf = {}, "_topo", []
    for l in texto.splitlines():
        if l.startswith("## "):
            out[atual] = "\n".join(buf).strip()
            atual, buf = l[3:].strip(), []
        else:
            buf.append(l)
    out[atual] = "\n".join(buf).strip()
    return out


def ler_regra(chave: str, secao: str | None = None, sem_modelos: bool = False) -> str:
    r = achar_regra(chave)
    t = r.texto
    if secao:
        sec = secoes(t)
        ns = _norm(secao)
        nomes = [n for n in sec if ns in _norm(n)]
        if not nomes:
            raise KeyError(f"seção '{secao}' não existe em {r.nome}; há: " + ", ".join(n for n in sec if n != "_topo"))
        t = "\n\n".join(f"## {n}\n{sec[n]}" for n in nomes)
    if sem_modelos:
        t = _RE_GRID.sub(lambda m: f"[modelo de grade '{m.group(1)}': veja com acao 'modelo']\n", t)
    return t


def indice() -> str:
    linhas = []
    for r in regras():
        n = len(_RE_GRID.findall(r.texto))
        linhas.append(f"{r.nome} — {r.titulo}" + (f" ({n} modelos)" if n else ""))
    return "\n".join(linhas)


def buscar(termo: str, limite: int = 30) -> list[str]:
    """Linhas das regras que contêm todas as palavras do termo (sem acento, sem caixa)."""
    palavras = _norm(termo).split()
    out = []
    for r in regras():
        for i, l in enumerate(r.texto.splitlines(), 1):
            nl = _norm(l)
            if palavras and all(p in nl for p in palavras):
                out.append(f"{r.nome}:{i}: {l.strip()[:220]}")
                if len(out) >= limite:
                    return out
    return out


@lru_cache(maxsize=1)
def modelos() -> dict[str, Modelo]:
    out: dict[str, Modelo] = {}
    for r in regras():
        texto = r.texto
        for m in _RE_GRID.finditer(texto):
            nome, corpo = m.group(1), m.group(2)
            if "\n---\n" not in "\n" + corpo:
                continue
            cab, _, grade = ("\n" + corpo).partition("\n---\n")
            leg = {}
            for l in cab.strip().splitlines():
                mm = _RE_LEGENDA.match(l.strip())
                if mm:
                    leg[mm.group(1)] = (mm.group(2), mm.group(3).lower())
            linhas = [l for l in grade.rstrip("\n").split("\n")]
            # descrição = último parágrafo antes do bloco
            antes = texto[:m.start()].rstrip().split("\n\n")[-1].strip()
            out[nome] = Modelo(nome, r.nome, leg, linhas, antes[:400])
    return out


def listar_modelos(filtro: str | None = None) -> list[Modelo]:
    ms = list(modelos().values())
    if filtro:
        nf = _norm(filtro).split()
        ms = [m for m in ms if all(p in _norm(f"{m.nome} {m.regra} {m.descricao}") for p in nf)]
    return ms


def achar_modelo(nome: str) -> Modelo:
    ms = modelos()
    if nome in ms:
        return ms[nome]
    cand = listar_modelos(nome)
    if len(cand) == 1:
        return cand[0]
    if not cand:
        raise KeyError(f"modelo '{nome}' não existe; liste com acao 'modelos'")
    raise KeyError(f"'{nome}' é ambíguo: " + ", ".join(m.nome for m in cand[:15]))


@lru_cache(maxsize=1)
def _paletas() -> dict:
    return json.loads((DADOS / "paletas.json").read_text(encoding="utf-8"))["presets"]


def buscar_paletas(termo: str = "", tamanho: int | None = None, limite: int = 25) -> list[tuple[str, dict]]:
    nt = _norm(termo).split()
    out = []
    for k, p in _paletas().items():
        if tamanho and p.get("size") != tamanho:
            continue
        if nt and not all(w in _norm(f"{k} {p.get('name', '')} {p.get('author', '')} {p.get('notes', '')}") for w in nt):
            continue
        out.append((k, p))
        if len(out) >= limite:
            break
    return out


def paleta(nome: str) -> tuple[str, dict]:
    ps = _paletas()
    if nome in ps:
        return nome, ps[nome]
    cand = buscar_paletas(nome, limite=500)
    exato = [c for c in cand if _norm(c[1].get("name", "")) == _norm(nome)]
    if exato:
        return exato[0]
    if len(cand) >= 1:
        return cand[0]
    raise KeyError(f"paleta '{nome}' não encontrada")
