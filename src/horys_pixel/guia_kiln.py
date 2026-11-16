"""Guia de pose do SpriteKiln: cada quadro de cada ação e direção vira um mapa de partes (perfeicao.md, §13, C9).

Uma spec do SpriteKiln é renderizada no tamanho final com UMA COR CHAPADA POR PARTE DO CORPO: sem sombreado, sem
contorno, sem linha interna, sem dither, sem brilho e sem sombra no chão. As cores são o contrato de
`mapa_partes.CORES` (o mesmo de `art-src/motion-rigs/README.md`), então `mapa_partes.rotulos()` lê os quadros direto.

Como funciona: `spec_guia` monta uma spec DERIVADA que estende a original (`extends:` com o caminho absoluto dela) e
só troca o material de cada parte por um material-guia emissivo de um tom só, desliga contorno/linhas/dither/brilho
e a sombra, e põe `mirror: false` (cada direção é renderizada de verdade, nada de cópia espelhada). A spec original
nunca é editada e nada é gravado no `out/` de um jogo: `renderizar` grava a spec derivada e o render numa pasta
de trabalho dentro de `saida`. No fim cada pixel opaco é encaixado na cor do contrato mais próxima (garantia caso
algo do render escape do tom chapado) e o quanto precisou ser encaixado vai para o índice.

Convenção de lados (esquerda/direita da IMAGEM na vista de FRENTE, direção `s`):
- No SpriteKiln +X é a esquerda do PERSONAGEM e aparece à DIREITA da tela na direção `s`.
- Então uma parte `_L` (braço/perna esquerdos do personagem) recebe `braco-dir`/`perna-dir` (roxo/vermelho) e uma
  parte `_R` recebe `braco-esq`/`perna-esq` (verde/amarelo). É o lado da imagem na vista de frente.
- A cor fica presa à parte do corpo em todas as direções: na vista de costas (`n`) o braço roxo aparece à esquerda
  da imagem. É o que a colagem precisa (a parte é a mesma; só a vista muda).

Classificação de cada parte (`classificar`), na ordem: o nome da parte; se o nome não diz nada, os ossos (o `space`
da parte e a cadeia de pais, mais os frames citados com "@" nas primitivas; os frames das cadeias IK herdam o nome
da cadeia). Prioridade das palavras: arma > enfeite > cabeca > perna > braco > tronco (então `sword_grip` é arma,
`bandana_tail` é enfeite, `headband` é cabeça). Sem pista nenhuma: tronco, com aviso. `mapeamento` ({parte:
categoria do contrato}) vence tudo; numa parte `_L` espelhada, a gêmea `_R` recebe o lado oposto automaticamente.

O SpriteKiln roda pelo CLI (`spritekiln`) e pelo Python do venv dele (`kiln.python_do_kiln`) só para ler a spec
resolvida; o Horys não depende dele instalado para importar este módulo.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

from .mapa_partes import CORES, NOMES

# ------------------------------------------------------------------ classificação (puro)

# palavras por categoria (nome da parte ou do osso, separado em "_", "-", dígitos)
PALAVRAS = {
    "arma": {"sword", "blade", "saber", "sabre", "katana", "dagger", "knife", "axe", "hammer", "mace", "club",
             "staff", "wand", "rod", "spear", "lance", "pike", "bow", "arrow", "crossbow", "gun", "pistol", "rifle",
             "musket", "shield", "weapon", "scythe", "sickle", "trident", "whip", "haft", "smear", "fx", "slash",
             "arc", "shockwave", "projectile", "bullet", "beam", "spark", "vfx", "arma", "espada", "adaga", "faca",
             "machado", "martelo", "cajado", "varinha", "lanca", "arco", "flecha", "escudo", "foice", "chicote",
             "golpe"},
    "enfeite": {"hair", "fringe", "bangs", "lock", "locks", "ponytail", "bun", "braid", "horn", "horns", "antler",
                "antenna", "crest", "plume", "feather", "cape", "cloak", "scarf", "tail", "mane", "wing", "wings",
                "cabelo", "franja", "mecha", "rabo", "chifre", "antena", "crista", "pena", "capa", "manto",
                "cachecol", "cauda", "juba", "asa", "trança", "tranca", "coque"},
    "cabeca": {"head", "face", "eye", "eyes", "brow", "brows", "mouth", "nose", "ear", "ears", "jaw", "chin",
               "skull", "cheek", "beak", "snout", "muzzle", "helmet", "helm", "hat", "hood", "headband", "bandana",
               "visor", "mask", "neck", "teeth", "tooth", "tongue", "pupil", "iris", "headbase", "cabeca", "rosto",
               "olho", "olhos", "boca", "nariz", "orelha", "queixo", "bico", "focinho", "chapeu", "elmo", "capuz",
               "mascara", "pescoco", "dente", "dentes", "lingua"},
    "perna": {"leg", "legs", "thigh", "shin", "calf", "knee", "ankle", "foot", "feet", "boot", "boots", "shoe",
              "shoes", "sole", "toe", "toes", "heel", "hoof", "legyaw", "footyaw", "perna", "pernas", "coxa",
              "canela", "joelho", "tornozelo", "pe", "pes", "bota", "botas", "sapato", "casco", "calcanhar"},
    "braco": {"arm", "arms", "upperarm", "forearm", "hand", "hands", "fist", "finger", "fingers", "thumb", "palm",
              "wrist", "elbow", "shoulder", "glove", "gloves", "gauntlet", "sleeve", "bracer", "pauldron", "claw",
              "claws", "braco", "bracos", "antebraco", "mao", "maos", "punho", "dedo", "dedos", "cotovelo", "ombro",
              "luva", "luvas", "manga", "garra", "garras"},
    "tronco": {"torso", "chest", "body", "belly", "abdomen", "spine", "pelvis", "hip", "waist", "belt", "coat",
               "jacket", "shirt", "vest", "robe", "tunic", "skirt", "dress", "collar", "back", "buckle", "pouch", "bag",
               "backpack", "coatbase", "tronco", "peito", "corpo", "barriga", "costas", "cintura",
               "quadril", "cinto", "casaco", "camisa", "colete", "tunica", "saia", "vestido", "gola", "bolsa",
               "mochila", "fivela"},
}
PRIORIDADE = ["arma", "enfeite", "cabeca", "perna", "braco", "tronco"]
LADO_L = {"l", "left", "esq", "esquerda", "esquerdo"}
LADO_R = {"r", "right", "dir", "direita", "direito"}
CONVENCAO = ("lado na IMAGEM da vista de frente (s): parte _L (esquerda do personagem) = braco-dir/perna-dir; "
             "parte _R = braco-esq/perna-esq; a cor fica presa à parte em todas as direções")


def _tokens(nome: str) -> list[str]:
    t = re.sub(r"([a-z])([A-Z])", r"\1_\2", str(nome))
    return [x for x in re.split(r"[_\-\s\d.:]+", t.lower()) if x]


def _categoria_nome(nome: str) -> str | None:
    toks = _tokens(nome)
    for cat in PRIORIDADE:
        if any(t in PALAVRAS[cat] or (t.endswith("s") and t[:-1] in PALAVRAS[cat]) for t in toks):
            return cat
    return None


def lado_do_nome(nome: str) -> str | None:
    """'L' (esquerda do personagem), 'R' ou None, pelo sufixo/termo do nome."""
    s = str(nome)
    if re.search(r"_L(?:_|$)", s):
        return "L"
    if re.search(r"_R(?:_|$)", s):
        return "R"
    toks = _tokens(s)
    if any(t in LADO_L for t in toks):
        return "L"
    if any(t in LADO_R for t in toks):
        return "R"
    return None


def _contrato(cat: str, lado: str | None) -> str:
    """Categoria (braco/perna/...) + lado do personagem -> nome do contrato (lado da imagem na vista s)."""
    if cat in ("braco", "perna"):
        return f"{cat}-dir" if lado == "L" else f"{cat}-esq"
    return cat


def oposto(nome: str) -> str:
    """braco-esq <-> braco-dir, perna-esq <-> perna-dir; o resto fica igual."""
    if nome.endswith("-esq"):
        return nome[:-4] + "-dir"
    if nome.endswith("-dir"):
        return nome[:-4] + "-esq"
    return nome


def cadeia_ossos(osso: str | None, pais: dict[str, str | None], ik: dict | None = None) -> list[str]:
    """O osso, seus pais até a raiz e, para frames de IK (joint/end), o nome da cadeia e o osso de início."""
    ik = ik or {}
    origem_ik = {}
    for nome, c in ik.items():
        for k in ("joint", "end"):
            if c.get(k):
                origem_ik[c[k]] = (nome, c.get("start"))
    out, vistos, o = [], set(), osso
    while o and o not in vistos:
        vistos.add(o)
        out.append(o)
        if o in origem_ik:
            cadeia, inicio = origem_ik[o]
            out.append(cadeia)
            o = inicio
            continue
        o = pais.get(o)
    return out


def classificar(nome: str, espaco: str | None = None, refs: list[str] | tuple = (),
                pais: dict[str, str | None] | None = None, ik: dict | None = None) -> tuple[str, str]:
    """Parte do spec -> (nome do contrato, motivo). Ver a docstring do módulo para a convenção."""
    pais = pais or {}
    cat = _categoria_nome(nome)
    motivo = "nome"
    ossos: list[str] = []
    for o in [espaco, *refs]:
        if o:
            ossos += cadeia_ossos(o, pais, ik)
    if cat is None:
        for o in ossos:
            cat = _categoria_nome(o)
            if cat:
                motivo = f"osso {o}"
                break
    if cat is None:
        return "tronco", "sem pista (padrão tronco)"
    lado = lado_do_nome(nome)
    if lado is None and cat in ("braco", "perna"):
        for o in ossos:
            lado = lado_do_nome(o)
            if lado:
                break
        if lado is None:
            motivo += ", sem lado (padrão esq)"
    return _contrato(cat, lado), motivo


def _mat_nome(contrato: str, sufixo: str = "") -> str:
    return "guia_" + contrato.replace("-", "_") + sufixo


def materiais_guia() -> dict[str, dict]:
    """Um material emissivo de um tom só por cor do contrato. Os laterais têm versões _L/_R: o espelhamento do
    SpriteKiln troca `_L` por `_R` no nome do material da gêmea, e a versão `_R` tem a cor do lado oposto."""
    def mat(cor):
        h = "#%02x%02x%02x" % cor
        return {"ramp": [h, h], "emissive": True, "band": 0, "outline": False, "line": False, "dither": False}
    out = {}
    for n in NOMES:
        if n.endswith(("-esq", "-dir")):
            out[_mat_nome(n, "_L")] = mat(CORES[n])
            out[_mat_nome(n, "_R")] = mat(CORES[oposto(n)])
        else:
            out[_mat_nome(n)] = mat(CORES[n])
    return out


def montar_spec(original: str | Path, info: dict, mapeamento: dict | None = None) -> dict:
    """Spec derivada (dict) a partir do resumo resolvido da original (`info`, ver `_ler_resolvido`).

    Devolve {"spec": dict, "partes": {parte: contrato}, "motivos": {parte: motivo}, "avisos": [...]}. Puro."""
    mapeamento = dict(mapeamento or {})
    for p, c in mapeamento.items():
        if c not in CORES:
            raise ValueError(f"mapeamento: '{c}' (parte {p}) não é do contrato {NOMES}")
    partes_info: dict = info["parts"]
    pais = info.get("bones", {})
    ik = info.get("ik", {})
    avisos: list[str] = []
    partes: dict[str, str] = {}
    motivos: dict[str, str] = {}
    sobrepor: dict[str, dict] = {}
    gemeas = {n for n, p in partes_info.items() if p.get("mirror")}
    for n in mapeamento:
        if n not in partes_info:
            avisos.append(f"mapeamento: a parte '{n}' não existe no spec")
        elif n in gemeas:
            avisos.append(f"mapeamento: '{n}' é gêmea espelhada; ela segue a parte _L (mapeie a _L)")
    # primeiro as partes escritas; a gêmea segue a _L dela
    for n, p in partes_info.items():
        if n in gemeas:
            continue
        if n in mapeamento:
            c, motivo = mapeamento[n], "mapeamento"
        else:
            c, motivo = classificar(n, p.get("space"), p.get("refs", []), pais, ik)
        partes[n], motivos[n] = c, motivo
        if "sem pista" in motivo or "sem lado" in motivo:
            avisos.append(f"parte '{n}': {motivo}")
        if c.endswith(("-esq", "-dir")):
            mat = _mat_nome(c, "_L")
        else:
            mat = _mat_nome(c)
        o: dict = {}
        if p.get("materials"):
            o["materials"] = [mat] * int(p["materials"])
        else:
            o["material"] = mat
        if p.get("paint"):
            o["paint"] = []
        sobrepor[n] = o
    for n in gemeas:
        fonte = n.replace("_R", "_L")
        if fonte in partes:
            partes[n] = oposto(partes[fonte])
            motivos[n] = f"gêmea de {fonte}"
        else:
            c, motivo = classificar(n, partes_info[n].get("space"), partes_info[n].get("refs", []), pais, ik)
            partes[n], motivos[n] = c, motivo + " (gêmea sem _L achada)"
    h = info.get("header", {})
    render = {"outline": "none", "shading": "flat", "lines": "none", "highlights": False, "dither": "none"}
    if "snap" in (h.get("render") or {}):
        render["snap"] = h["render"]["snap"]
    spec = {
        "spritekiln": 1,
        "name": f"{h.get('name') or Path(original).stem}_guia",
        "extends": Path(original).resolve().as_posix(),
        "mirror": False,
        "palette": "gothic",               # embutida; as rampas resolvidas da original vão em `ramps`
        "ramps": info.get("ramps", {}),
        "shadow": {"rx": 1, "ry": 1, "alpha": 0},
        "render": render,
        "materials": materiais_guia(),
        "parts": sobrepor,
    }
    if h.get("camera"):
        spec["camera"] = h["camera"]       # a câmera resolvida (a escala do estilo do projeto não vem junto)
    if h.get("size"):
        spec["size"] = h["size"]
    if h.get("view"):
        spec["view"] = h["view"]
    return {"spec": spec, "partes": partes, "motivos": motivos, "avisos": avisos}


def spec_yaml(spec: dict) -> str:
    """YAML do spec: uma chave de topo por linha com o valor em fluxo JSON (YAML válido, `spritekiln:` primeiro)."""
    linhas = [f"spritekiln: {json.dumps(spec.get('spritekiln', 1))}",
              "# spec DERIVADA pelo horys (guia_kiln): gerada, não edite; edite a spec original"]
    for k, v in spec.items():
        if k == "spritekiln":
            continue
        if isinstance(v, dict) and v:
            linhas.append(f"{k}:")
            for k2, v2 in v.items():
                linhas.append(f"  {json.dumps(k2)}: {json.dumps(v2, ensure_ascii=False)}")
        else:
            linhas.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
    return "\n".join(linhas) + "\n"


# ------------------------------------------------------------------ encaixe nas cores do contrato (puro)

_PAL = np.array([CORES[n] for n in NOMES], dtype=np.int32)


def encaixar(rgba: np.ndarray, tol: int = 40) -> tuple[np.ndarray, int]:
    """Todo pixel com alfa >= 128 vira a cor do contrato mais próxima (alfa 255); o resto, transparente.
    Devolve (quadro, nº de pixels opacos que estavam a mais de `tol` (soma |dRGB|) de qualquer cor do contrato)."""
    op = rgba[..., 3] >= 128
    out = np.zeros_like(rgba)
    if not op.any():
        return out, 0
    rgb = rgba[..., :3][op].astype(np.int32)
    d = np.abs(rgb[:, None, :] - _PAL[None, :, :]).sum(-1)
    k = d.argmin(1)
    fora = int((d.min(1) > tol).sum())
    out[op, :3] = _PAL[k].astype(np.uint8)
    out[op, 3] = 255
    return out, fora


# ------------------------------------------------------------------ SpriteKiln (subprocesso)

_SCRIPT_RESUMO = r"""
import json, sys
from spritekiln import spec as specmod
sp = specmod.load(sys.argv[1])
def refs(o, out):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == "at" and isinstance(v, str):
                out.append(v)
            else:
                refs(v, out)
    elif isinstance(o, (list, tuple)):
        for v in o:
            refs(v, out)
    elif isinstance(o, str):
        import re
        out += re.findall(r"@(\w+)", o)
    return out
parts = {}
for n, p in sp["parts"].items():
    parts[n] = {"material": p.get("material"), "materials": len(p.get("materials") or []),
                "space": p.get("space"), "paint": bool(p.get("paint")), "mirror": bool(p.get("_mirror")),
                "refs": sorted(set(refs(p.get("prims", []), [])))}
bones = {n: b.get("parent") for n, b in (sp.get("bones") or {}).items()}
ik = {n: {k: c.get(k) for k in ("start", "joint", "end")} for n, c in (sp.get("ik") or {}).items()}
anims = {n: int(a.get("frames", 1)) for n, a in (sp.get("animations") or {}).items()}
header = {k: sp.get(k) for k in ("name", "size", "mirror", "camera", "render", "view", "kind")}
header["directions"] = [d for d, _ in sp.get("directions", [])]
print(json.dumps({"parts": parts, "bones": bones, "ik": ik, "animations": anims, "header": header,
                  "ramps": sp.get("ramps") or {}}, default=str))
"""


def spritekiln_disponivel() -> bool:
    return shutil.which("spritekiln") is not None


def _ler_resolvido(spec_path: str | Path, python: str | None = None) -> dict:
    from .kiln import python_do_kiln
    r = subprocess.run([python or python_do_kiln(), "-c", _SCRIPT_RESUMO, str(Path(spec_path).resolve())],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    if r.returncode != 0:
        raise RuntimeError("spritekiln não conseguiu ler a spec (instalado? spec válida?): "
                           + (r.stderr or r.stdout)[-1500:])
    return json.loads(r.stdout.strip().splitlines()[-1])


def spec_guia(spec_path: str | Path, mapeamento: dict | None = None, python: str | None = None) -> dict:
    """Spec derivada de guia de pose (ver `montar_spec`). Lê a spec resolvida pelo SpriteKiln; não grava nada."""
    p = Path(spec_path)
    if not p.is_file():
        raise FileNotFoundError(f"spec não encontrada: {spec_path}")
    info = _ler_resolvido(p, python)
    out = montar_spec(p, info, mapeamento)
    out["info"] = info
    out["yaml"] = spec_yaml(out["spec"])
    return out


def _lista(v) -> list[str] | None:
    if v is None or v == "" or v == []:
        return None
    if isinstance(v, str):
        v = v.split(",")
    return [str(x).strip() for x in v if str(x).strip()]


def renderizar(spec_path: str | Path, saida: str | Path, anims=None, dirs=None, size: int | None = None,
               mapeamento: dict | None = None, python: str | None = None, forcar: bool = False) -> dict:
    """Renderiza o guia de pose: `<saida>/<anim>_<dir>_NN.png` (cores do contrato) + `<saida>/guia.json`.

    A spec derivada e o render bruto do SpriteKiln ficam em `<saida>/_kiln/` (nunca no `out/` do jogo)."""
    g = spec_guia(spec_path, mapeamento, python)
    info = g["info"]
    out = Path(saida)
    trab = out / "_kiln"
    trab.mkdir(parents=True, exist_ok=True)
    nome = g["spec"]["name"]
    arq_spec = trab / f"{nome}.yaml"
    arq_spec.write_text(g["yaml"], encoding="utf-8")
    anims = _lista(anims)
    dirs = _lista(dirs)
    if anims:
        faltam = [a for a in anims if a not in info["animations"]]
        if faltam:
            raise ValueError(f"animações que o spec não tem: {faltam}; tem {list(info['animations'])}")
    cmd = ["spritekiln", "render", str(arq_spec), "-o", str(trab / "out")]
    if anims:
        cmd += ["--anims", ",".join(anims)]
    if dirs:
        cmd += ["--dirs", ",".join(dirs)]
    if size:
        cmd += ["--size", str(int(size))]
    if forcar:
        cmd.append("--force")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
    if r.returncode != 0:
        raise RuntimeError("spritekiln render falhou: " + (r.stderr or r.stdout)[-2000:])
    atlas_json = trab / "out" / f"{nome}.json"
    if not atlas_json.is_file():
        raise RuntimeError(f"o render não gravou {atlas_json}: " + (r.stdout or "")[-1000:])
    dados = json.loads(atlas_json.read_text(encoding="utf-8"))
    folha = np.array(Image.open(atlas_json.with_name(dados["meta"]["image"])).convert("RGBA"))
    sk = dados["spritekiln"]
    for velho in out.glob("*_*_[0-9][0-9].png"):
        velho.unlink()
    indice = {"spec": str(Path(spec_path).resolve()), "spec_guia": str(arq_spec), "tamanho": sk.get("frame_size"),
              "pivo": sk.get("pivot"), "convencao": CONVENCAO,
              "cores": {n: "#%02x%02x%02x" % CORES[n] for n in NOMES},
              "partes": g["partes"], "motivos": g["motivos"], "avisos": list(g["avisos"]),
              "animacoes": {}, "fora_do_contrato": 0}
    arquivos: list[str] = []
    quadros_por_clipe: dict[str, list[np.ndarray]] = {}
    for anim, a in sk["animations"].items():
        for d, ad in a["directions"].items():
            nomes_q, quadros = [], []
            for i, fq in enumerate(ad["frames"]):
                fr = dados["frames"][fq]["frame"]
                q = folha[fr["y"]:fr["y"] + fr["h"], fr["x"]:fr["x"] + fr["w"]]
                if ad.get("flip") or ad.get("mirrored"):
                    q = q[:, ::-1]
                q, fora = encaixar(q)
                indice["fora_do_contrato"] += fora
                arq = out / f"{anim}_{d}_{i:02d}.png"
                Image.fromarray(q).save(arq)
                nomes_q.append(arq.name)
                arquivos.append(str(arq))
                quadros.append(q)
            indice["animacoes"].setdefault(anim, {})[d] = {
                "quadros": nomes_q, "duracoes": ad.get("durations", []), "loop": a.get("loop", True)}
            quadros_por_clipe[f"{anim}_{d}"] = quadros
    if indice["fora_do_contrato"]:
        indice["avisos"].append(f"{indice['fora_do_contrato']} pixels fora do contrato foram encaixados na cor "
                                "mais próxima (algo do render não saiu chapado)")
    (out / "guia.json").write_text(json.dumps(indice, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"saida": str(out), "indice": str(out / "guia.json"), "spec_guia": str(arq_spec),
            "arquivos": arquivos, "clipes": quadros_por_clipe, "partes": g["partes"], "avisos": indice["avisos"],
            "fora_do_contrato": indice["fora_do_contrato"]}
