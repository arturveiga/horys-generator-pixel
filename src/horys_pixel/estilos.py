"""Pacotes de estilo (ver docs/estilos.md).

Um pacote é uma pasta com `estilo.json` (e, em geral, `estilo.md`, `paleta.json/.gpl/.hex`, `regras/`...). Onde procurar:
  1. <repo>/estilos/<nome>/                (pacotes que vão no repo; ex.: "exemplo")
  2. ~/.horys-pixel/estilos/<nome>/        (pacotes do usuário; VENCE em conflito de nome)
A pasta ~/.horys-pixel pode ser trocada pela variável HORYS_HOME (a mesma do horys_pixel.config).

estilo.json:
  {"nome", "versao", "autor", "licenca", "descricao",
   "kb": pasta da base de conhecimento ou null,
   "paleta": JSON de paleta (absoluto, relativo ao pacote ou, se não achar, relativo à kb),
   "regua": {"pasta", "nome", "por_categoria": {categoria: [arquivo, largura_do_quadro]}} ou null,
   "chao": {nome: hex}, "contorno_regua": hex, "brilho_regua": hex ou [hex],
   "metas": caminho opcional (relativo ao pacote), "leitura": [notas da kb a ler, relativas à kb],
   "motor_padrao": "claude", "referencia_padrao": "pedir", "trigger": "<palavra do LoRA>",
   "motor": {chaves extras da config do motor: aseprite, trabalho, fundo_prancha, limite_imagem, contorno_suave...}}

API: listar(), carregar(nome), config_motor(estilo), escrever_config_motor(estilo, destino=None),
pasta_dados(estilo, "gosto"|"conjunto"|"lora"), paleta(estilo), exportar_paleta(paleta, destino_sem_extensao).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ESTILOS = Path(__file__).resolve().parents[2] / "estilos"
TIPOS_DADOS = ("gosto", "conjunto", "lora")


class EstiloNaoEncontrado(LookupError):
    pass


def home() -> Path:
    """Pasta de dados do usuário: HORYS_HOME (a mesma do horys_pixel.config), HORYS_PIXEL_HOME ou ~/.horys-pixel."""
    return Path(os.path.expanduser(os.environ.get("HORYS_HOME") or os.environ.get("HORYS_PIXEL_HOME")
                                   or "~/.horys-pixel"))


def pastas_busca() -> list[Path]:
    """Da menor para a maior prioridade (o usuário vence)."""
    return [REPO_ESTILOS, home() / "estilos"]


@dataclass
class Estilo:
    nome: str
    pasta: Path
    dados: dict
    versao: str = ""
    autor: str = ""
    licenca: str = ""
    descricao: str = ""
    kb: Path | None = None
    paleta: Path | None = None
    regua: dict | None = None          # {"pasta": Path, "nome": str, "por_categoria": {...}}
    chao: dict = field(default_factory=dict)
    contorno_regua: str | None = None
    brilho_regua: list = field(default_factory=list)
    metas: Path | None = None
    leitura: list = field(default_factory=list)
    motor_padrao: str = "claude"
    referencia_padrao: str = "pedir"
    trigger: str = ""
    no_repo: bool = False               # o pacote mora dentro do repo (dados vão para ~/.horys-pixel/estilos-dados)

    @property
    def regua_disponivel(self) -> bool:
        return bool(self.regua and self.regua.get("pasta") and Path(self.regua["pasta"]).is_dir())


# ------------------------------------------------------------------ busca

def _e_pacote(p: Path) -> bool:
    return p.is_dir() and (p / "estilo.json").is_file()


def listar() -> list[str]:
    """Nomes dos pacotes achados no repo e na pasta do usuário (sem repetição)."""
    nomes = set()
    for base in pastas_busca():
        if base.is_dir():
            nomes.update(p.name for p in base.iterdir() if _e_pacote(p))
    return sorted(nomes)


def _achar(nome: str) -> Path:
    p = Path(os.path.expanduser(str(nome)))
    if (os.sep in str(nome) or "/" in str(nome)) and _e_pacote(p):
        return p.resolve()                       # caminho direto para a pasta do pacote
    for base in reversed(pastas_busca()):        # o do usuário primeiro
        if _e_pacote(base / nome):
            return (base / nome).resolve()
    raise EstiloNaoEncontrado(f"estilo '{nome}' não encontrado em: " + ", ".join(str(b) for b in pastas_busca()))


# ------------------------------------------------------------------ carregar

def _abs(valor, base: Path) -> Path | None:
    if not valor:
        return None
    p = Path(os.path.expanduser(str(valor)))
    return p if p.is_absolute() else (base / p)


def _dentro_do_repo(pasta: Path) -> bool:
    try:
        pasta.resolve().relative_to(REPO_ESTILOS.resolve())
        return True
    except ValueError:
        return False


def carregar(nome) -> Estilo:
    """Lê o estilo.json do pacote (por nome ou caminho da pasta) e resolve os caminhos."""
    pasta = _achar(nome)
    with open(pasta / "estilo.json", encoding="utf-8") as f:
        d = json.load(f)
    if not d.get("paleta"):
        raise ValueError(f"{pasta / 'estilo.json'}: falta 'paleta'")
    kb = _abs(d.get("kb"), pasta)
    paleta = _abs(d["paleta"], pasta)
    if not paleta.is_file() and kb and not Path(str(d["paleta"])).is_absolute() and (kb / d["paleta"]).is_file():
        paleta = kb / d["paleta"]
    regua = None
    if d.get("regua"):
        r = d["regua"]
        regua = {"pasta": _abs(r.get("pasta"), pasta), "nome": r.get("nome") or "régua",
                 "por_categoria": dict(r.get("por_categoria") or {})}
    brilho = d.get("brilho_regua")
    if isinstance(brilho, str):
        brilho = [brilho]
    base_leitura = kb or pasta
    return Estilo(
        nome=d.get("nome") or pasta.name, pasta=pasta, dados=d, versao=str(d.get("versao", "")),
        autor=d.get("autor", ""), licenca=d.get("licenca", ""), descricao=d.get("descricao", ""),
        kb=kb, paleta=paleta, regua=regua, chao=dict(d.get("chao") or {}),
        contorno_regua=d.get("contorno_regua"), brilho_regua=list(brilho or []),
        metas=_abs(d.get("metas"), pasta), leitura=[base_leitura / n for n in d.get("leitura") or []],
        motor_padrao=d.get("motor_padrao") or "claude", referencia_padrao=d.get("referencia_padrao") or "pedir",
        trigger=d.get("trigger") or "", no_repo=_dentro_do_repo(pasta))


# ------------------------------------------------------------------ motor

def _config_base() -> dict:
    """Config da máquina: config_padrao.json do motor + ~/.horys-pixel/motor.json (sem HORYS_MOTOR_CONFIG)."""
    from .motor import comum
    with open(comum.CONFIG_PADRAO, encoding="utf-8") as f:
        c = json.load(f)
    usuario = home() / "motor.json"
    if usuario.is_file():
        with open(usuario, encoding="utf-8") as f:
            c.update(json.load(f))
    return c


def config_motor(estilo: Estilo | str) -> dict:
    """O JSON que o motor espera (o mesmo formato do config.json da skill), montado a partir do estilo."""
    if isinstance(estilo, str):
        estilo = carregar(estilo)
    c = _config_base()
    c.update({
        "estilo": estilo.nome,
        "kb": str(estilo.kb) if estilo.kb else None,
        "regua": str(estilo.regua["pasta"]) if estilo.regua and estilo.regua.get("pasta") else None,
        "paleta_json": str(estilo.paleta),
    })
    if estilo.regua:
        c["regua_por_categoria"] = estilo.regua["por_categoria"]
        c["regua_nome"] = estilo.regua["nome"]
    else:
        c["regua_por_categoria"] = {}
    if estilo.chao:
        c["chao"] = estilo.chao
    if estilo.contorno_regua:
        c["contorno_regua"] = estilo.contorno_regua
    if estilo.brilho_regua:
        c["brilho_regua"] = estilo.brilho_regua
    if estilo.metas:
        c["metas"] = str(estilo.metas)
    c.update(estilo.dados.get("motor") or {})
    if not c.get("aseprite"):
        try:
            from . import config as _cfg
            c["aseprite"] = _cfg.achar_aseprite()
        except Exception:
            pass
    return c


def escrever_config_motor(estilo: Estilo | str, destino=None) -> Path:
    """Grava a config do motor para o estilo (padrão ~/.horys-pixel/motor-<nome>.json). Use o caminho em
    HORYS_MOTOR_CONFIG ao chamar o motor."""
    if isinstance(estilo, str):
        estilo = carregar(estilo)
    destino = Path(destino) if destino else home() / f"motor-{estilo.nome}.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(config_motor(estilo), f, ensure_ascii=False, indent=1)
    return destino


# ------------------------------------------------------------------ dados e paleta

def pasta_dados(estilo: Estilo | str, tipo: str) -> Path:
    """Pasta de gosto/conjunto/lora do estilo (criada se faltar). Pacote dentro do repo: os dados ficam em
    ~/.horys-pixel/estilos-dados/<nome>/<tipo>, para não sujar o repo."""
    if tipo not in TIPOS_DADOS:
        raise ValueError(f"tipo de dados '{tipo}': use um de {TIPOS_DADOS}")
    if isinstance(estilo, str):
        estilo = carregar(estilo)
    p = (home() / "estilos-dados" / estilo.nome / tipo) if estilo.no_repo else (estilo.pasta / tipo)
    p.mkdir(parents=True, exist_ok=True)
    return p


def paleta(estilo: Estilo | str) -> dict:
    """{"rampas": {nome: [hex]}, "contorno": hex, "brilho": hex}."""
    if isinstance(estilo, str):
        estilo = carregar(estilo)
    with open(estilo.paleta, encoding="utf-8") as f:
        p = json.load(f)
    return {"rampas": {k: [h.lower() for h in v] for k, v in p["rampas"].items()},
            "contorno": p["contorno"].lower(), "brilho": p["brilho"].lower()}


def exportar_paleta(pal: dict, destino_sem_ext, nome: str = "") -> list[Path]:
    """Grava <destino>.gpl (GIMP/Aseprite) e <destino>.hex a partir de um dict de paleta (formato Horys).
    Cada cor aparece uma vez, na ordem das rampas."""
    base = Path(destino_sem_ext)
    base.parent.mkdir(parents=True, exist_ok=True)
    vistas, linhas_gpl, linhas_hex = set(), [], []
    for rampa, cores in pal["rampas"].items():
        for i, h in enumerate(cores, 1):
            h = h.lower().lstrip("#")
            if h in vistas:
                continue
            vistas.add(h)
            r, g, b = (int(h[k:k + 2], 16) for k in (0, 2, 4))
            linhas_gpl.append(f"{r:3d} {g:3d} {b:3d}\t{rampa} {i}")
            linhas_hex.append(h)
    gpl = base.with_suffix(".gpl")
    with open(gpl, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"GIMP Palette\nName: {nome or pal.get('nome') or base.stem}\nColumns: 4\n#\n" + "\n".join(linhas_gpl) + "\n")
    hx = base.with_suffix(".hex")
    with open(hx, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(linhas_hex) + "\n")
    return [gpl, hx]
