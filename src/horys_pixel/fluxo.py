"""As etapas do fluxo, na ordem. Cada uma recusa rodar sem o que a anterior aprovou.

1. ler_arte      imagem do gerador -> arte parada 1x (frente, lado, costas)
2. propor_paleta arte -> paleta.json (famílias com rampa + tinta)
   -> o Artur aprova a arte e a paleta (horys aprovar <asset> arte | paleta)
3. gabarito      render parado do modelo 3D nas vistas do jogo x arte aprovada (tem que passar)
4. animar        ações × direções no Blender -> pós -> portões (bloqueiam)
5. exportar      folhas para o jogo (só com portões ok)
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import numpy as np
from PIL import Image

from . import aprovacao as AP
from . import casco as K
from . import asset as AS
from . import blender as B
from . import gabarito as G
from . import jogo as J
from . import leitura as L
from . import paleta as P
from . import portoes as PT
from . import pos


class ErroFluxo(RuntimeError):
    pass


def _json(caminho: Path, dados) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")


def _ler_json(caminho: Path):
    return json.loads(caminho.read_text(encoding="utf-8")) if caminho.exists() else None


# ------------------------------------------------------------------ 1. arte parada


def ler_arte(a: AS.Asset, imagem: str | Path | None = None, jogo: dict | None = None, vista: str | None = None) -> dict:
    """vista: troca só essa vista (frente/lado/costas) pela da imagem dada, lida na grade da própria imagem; as
    outras vistas já lidas ficam como estão."""
    jogo = jogo or J.carregar(a.pasta)
    img = Path(imagem) if imagem else a.pasta / "gerada.png"
    if not img.exists():
        raise ErroFluxo(f"não achei a imagem do gerador: {img} (salve como gerada.png na pasta do asset)")
    pal = P.ler(a.paleta) if a.paleta.exists() else None
    cores = pal["cores"] if pal else None
    r = L.ler(L.carregar(img), a.alvo_px(jogo), paleta=cores, tinta=pal["tinta"] if pal else None,
              n_cores=min(16, int(jogo["max_cores"])), contorno=jogo.get("contorno") != "nenhum")
    a.arte.mkdir(parents=True, exist_ok=True)
    vistas = dict(r.vistas)
    if vista:
        if vista not in L.NOMES_VISTAS:
            raise ErroFluxo(f"vista desconhecida: {vista} (use {', '.join(L.NOMES_VISTAS)})")
        velhas = vistas_arte(a)
        if set(velhas) != set(L.NOMES_VISTAS):
            raise ErroFluxo("rode um horys ler completo antes de trocar uma vista")
        vistas = {**velhas, vista: r.vistas[vista]}
    for f in a.arte.glob("*.png"):
        f.unlink()
    for nome, v in vistas.items():
        Image.fromarray(v).save(a.arte / f"{nome}.png")
    folha = L.montar_folha([vistas[n] for n in L.NOMES_VISTAS if n in vistas])
    Image.fromarray(folha).save(a.arte / "folha.png")
    L.previa(folha, 8).save(a.arte / "folha_8x.png")
    rel = {**r.relatorio, "imagem": str(img), "paleta_travada": bool(pal), "quando": time.strftime("%Y-%m-%d %H:%M:%S")}
    if vista:
        antigo = _ler_json(a.arte / "leitura.json") or {}
        fontes = antigo.get("fontes") or {n: antigo.get("imagem") for n in L.NOMES_VISTAS}
        fontes[vista] = str(img)
        rel["fontes"] = fontes
        rel["vistas"] = {n: [int(v.shape[1]), int(v.shape[0])] for n, v in vistas.items()}
    _json(a.arte / "leitura.json", rel)
    return rel


def projecao(a: AS.Asset, jogo: dict) -> dict | None:
    """Projeção da arte aprovada no modelo (asset.json "projetar": true): as vistas da arte com o ângulo da direção
    de cada uma. Gabarito e animação usam a mesma projeção."""
    if not a.cfg.get("projetar"):
        return None
    vistas = {}
    for nome, d in jogo["vistas"].items():
        p = a.arte / f"{nome}.png"
        if p.exists() and d in jogo["direcoes"]:
            vistas[nome] = {"png": str(p.resolve()), "angulo": jogo["direcoes"][d]}
    return {"vistas": vistas} if vistas else None


def vistas_arte(a: AS.Asset) -> dict:
    out = {}
    for nome in L.NOMES_VISTAS:
        p = a.arte / f"{nome}.png"
        if p.exists():
            out[nome] = np.asarray(Image.open(p).convert("RGBA"))
    return out


# ------------------------------------------------------------------ 2. paleta


def propor_paleta(a: AS.Asset, n: int = 5, jogo: dict | None = None) -> dict:
    jogo = jogo or J.carregar(a.pasta)
    folha = a.arte / "folha.png"
    if not folha.exists():
        raise ErroFluxo("leia a arte antes (horys ler)")
    im = np.asarray(Image.open(folha).convert("RGBA"))
    op = im[..., 3] > 0
    cores = np.unique(im[op][:, :3], axis=0)
    tinta = min((P.C.rgb_hex(c) for c in cores), key=P.C.luminancia)
    fams = P.propor(im, n)
    for i, f in enumerate(fams):
        f["nome"] = f"material{i + 1}"
    pal = P.montar(fams, tinta=tinta, max_cores=int(jogo["max_cores"]))
    P.salvar(pal, a.pasta)
    return pal


# ------------------------------------------------------------------ 3a. modelo pelo casco visual


def _rig_casco(piv: dict) -> tuple[dict, dict]:
    def seg(nome, pai, cols, parte, objs=None):
        d = {"nome": nome, "pai": pai, "pivo": piv[nome], "colecoes": cols, "parte": parte}
        if objs:
            d["objetos"] = objs
        return d

    S = [seg("tronco", "ancora", ["Tronco"], "tronco"), seg("cabeca", "tronco", ["Cabeça"], "cabeca")]
    bracos, pernas = [], []
    for lado, l, nome, p in ((-1, "e", "Esquerda", "esq"), (1, "d", "Direita", "dir")):
        if "ombro_" + l in piv:
            S.append(seg("ombro_" + l, "tronco", ["Braço " + nome], "braco-" + p, ["Braço superior*"]))
            b = {"lado": lado, "ombro": "ombro_" + l}
            if "cotovelo_" + l in piv:
                S.append(seg("cotovelo_" + l, "ombro_" + l, ["Braço " + nome], "braco-" + p))
                b["cotovelo"] = "cotovelo_" + l
            bracos.append(b)
        if "coxa_" + l in piv:
            S.append(seg("coxa_" + l, "ancora", ["Perna " + nome], "perna-" + p, ["Coxa*"]))
            pe = {"lado": lado, "coxa": "coxa_" + l}
            if "pe_" + l in piv:
                S.append(seg("pe_" + l, "ancora", ["Perna " + nome], "perna-" + p, ["Bota*"]))
                pe["pe"] = "pe_" + l
            if "canela_" + l in piv:
                S.append(seg("canela_" + l, "ancora", ["Perna " + nome], "perna-" + p))
                pe["canela"] = "canela_" + l
            pernas.append(pe)
    rig = {"ancora": "Casco | âncora", "segmentos": S}
    papeis = {"tronco": "tronco", "cabeca": "cabeca", "bracos": bracos, "pernas": pernas}
    return rig, papeis


def modelar(a: AS.Asset, jogo: dict | None = None) -> dict:
    """Modelo 3D esculpido das vistas aprovadas (casco.py), com rig e projeção da arte ligados no asset.json.
    Ajustes de corte das partes: asset.json "casco": {quadril, pescoco, braco_x, bota, cotovelo} (frações)."""
    jogo = jogo or J.carregar(a.pasta)
    try:
        AP.exigir(a.pasta, "arte")
    except AP.Travado as e:
        raise ErroFluxo(str(e))
    arte = vistas_arte(a)
    vistas = {n: (rgba, jogo["direcoes"][jogo["vistas"][n]]) for n, rgba in arte.items() if n in jogo["vistas"]}
    c = K.Casco(vistas, jogo)
    if c.esculpir() is None or not c.ocup.any():
        raise ErroFluxo("o casco ficou vazio: as vistas da arte não se encaixam")
    rot = c.partes(**(a.cfg.get("casco") or {}))
    piv = c.pivos(rot)
    pasta = a.pasta / "blender"
    pasta.mkdir(parents=True, exist_ok=True)
    fams = P.ler(a.paleta)["familias"] if a.paleta.exists() else None
    cores = {n: f["rampa"][len(f["rampa"]) // 2] for n, f in (fams or {}).items()}
    _json(pasta / "casco.json", {"pecas": c.malhas(rot, fams), "cores": cores})
    a.cfg["blend"] = "blender/modelo.blend"
    B.construir_casco(pasta / "casco.json", a.blend)
    rig, papeis = _rig_casco(piv)
    # cada face já sai com a família lida na arte (casco.familias_faces): sem projeção no Blender
    a.cfg.update({"rig": rig, "papeis": papeis, "projetar": not fams, "partes": True,
                  "materiais": {"padrao": "auto", "regras": [["Fam | " + n, n] for n in cores]},
                  "cor_por_direcao": {n: jogo["direcoes"][jogo["vistas"][n]] for n in vistas} if fams else None})
    a.cfg.setdefault("esconder", [])
    a.salvar_cfg()
    return {"iou": c.iou(), "voxels": int(c.ocup.sum()), "pecas": len(rot), "blend": str(a.blend)}


# ------------------------------------------------------------------ 3. gabarito


def _exigir_base(a: AS.Asset) -> dict:
    try:
        AP.exigir(a.pasta, "arte")
        AP.exigir(a.pasta, "paleta")
    except AP.Travado as e:
        raise ErroFluxo(str(e))
    return P.ler(a.paleta)


def _renders_parado(saida: Path, vistas: dict) -> dict:
    out = {}
    for nome, d in vistas.items():
        p = saida / f"parado_{d}.png"
        if p.exists():
            out[nome] = np.asarray(Image.open(p).convert("RGBA"))
    return out


def gabarito(a: AS.Asset, jogo: dict | None = None) -> dict:
    jogo = jogo or J.carregar(a.pasta)
    pal = _exigir_base(a)
    arte = vistas_arte(a)
    if not arte:
        raise ErroFluxo("a pasta arte/ não tem vistas")
    vistas = {n: jogo["vistas"][n] for n in arte if n in jogo["vistas"]}
    direcoes = {d: jogo["direcoes"][d] for d in vistas.values()}
    saida = a.saida / "gabarito"
    if saida.exists():
        shutil.rmtree(saida)
    r = B.rodar(a.cfg, a.blend, jogo, pal, saida, {"parado": {"tipo": "parado", "quadros": 1, "fps": 1}}, direcoes,
                projecao=projecao(a, jogo))
    if not r["ok"]:
        raise ErroFluxo("o Blender falhou no render parado:\n" + r["log"][-2500:])
    rel_pos = pos.processar(saida, pal, jogo, aseprite=False)
    renders = _renders_parado(saida, vistas)
    res = G.avaliar(arte, renders, pal, jogo["portoes"]["gabarito"])
    res["camera"] = rel_pos.get("camera")
    res["avisos"] = [x for x in rel_pos.get("avisos", [])]
    if any(x.startswith(("JUNTA_FORA", "NAO_CABE")) for x in res["avisos"]):
        res["falhas"] += [x for x in res["avisos"] if x.startswith(("JUNTA_FORA", "NAO_CABE"))]
        res["ok"] = False
    try:
        qa = B.inspecionar(a.blend).get("qa_malhas") or {}
    except Exception as e:  # noqa: BLE001 - a checagem de malha é aviso: não derruba o gabarito
        qa = {}
        res["avisos"].append(f"QA_MALHA: não rodou ({e})")
    res["avisos"] += [f"QA_MALHA {nome}: " + ", ".join(f"{k}={v}" for k, v in d.items()) for nome, d in qa.items()]
    res["blend_sha256"] = AP.sha(a.blend)
    res["arte_sha256"] = AP.sha(a.arte / "folha.png")
    res["quando"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _json(saida / "gabarito.json", res)
    G.prancha(arte, renders).save(saida / "gabarito.png")
    return res


def gabarito_valido(a: AS.Asset) -> tuple[bool, str]:
    g = _ler_json(a.saida / "gabarito" / "gabarito.json")
    if not g:
        return False, "rode o gabarito antes (horys gabarito)"
    if not g.get("ok"):
        return False, "o gabarito não passou: " + "; ".join(g.get("falhas", [])[:3])
    if g.get("blend_sha256") != AP.sha(a.blend):
        return False, "o .blend mudou depois do gabarito: rode o gabarito de novo"
    if g.get("arte_sha256") != AP.sha(a.arte / "folha.png"):
        return False, "a arte mudou depois do gabarito: rode o gabarito de novo"
    return True, "ok"


# ------------------------------------------------------------------ 4. animação


def _resolver_fbx(a: AS.Asset, acao: dict) -> dict:
    """Ação 'mixamo': 'fbx' relativo à pasta do asset vira caminho absoluto (o Blender roda em outro diretório)."""
    if acao.get("tipo") != "mixamo":
        return acao
    if not acao.get("fbx"):
        raise ErroFluxo("ação mixamo sem 'fbx' (caminho do FBX, relativo à pasta do asset)")
    fbx = (a.pasta / acao["fbx"]).resolve()
    if not fbx.is_file():
        raise ErroFluxo(f"não achei o FBX da ação mixamo: {fbx}")
    return {**acao, "fbx": str(fbx)}


def animar(a: AS.Asset, previa: bool = False, jogo: dict | None = None) -> dict:
    jogo = jogo or J.carregar(a.pasta)
    pal = _exigir_base(a)
    ok, motivo = gabarito_valido(a)
    if not ok:
        raise ErroFluxo(motivo)
    acoes = a.cfg.get("acoes") or {}
    if not acoes:
        raise ErroFluxo("asset.json sem 'acoes'")
    acoes = {k: _resolver_fbx(a, v) for k, v in acoes.items()}
    saida = a.saida / ("previa" if previa else "animacao")
    if saida.exists():
        shutil.rmtree(saida)
    r = B.rodar(a.cfg, a.blend, jogo, pal, saida, acoes, jogo["direcoes"], previa=previa,
                projecao=projecao(a, jogo))
    if not r["ok"]:
        raise ErroFluxo("o Blender falhou na animação:\n" + r["log"][-2500:])
    rel = pos.processar(saida, pal, jogo, B.CORES_PARTES, aseprite=not previa)
    res = PT.avaliar(rel, jogo, previa=previa)
    res["avisos"] += [f"asset.json tenta mudar '{k}' do contrato do jogo: ignorado (mude no jogo.json)"
                      for k in J.checar_asset(a.cfg)]
    res["previa"] = previa
    res["blend_sha256"] = AP.sha(a.blend)
    res["quando"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _json(saida / "portoes.json", res)
    return res


# ------------------------------------------------------------------ 5. exportar


def exportar(a: AS.Asset, destino: str | Path) -> list[str]:
    saida = a.saida / "animacao"
    p = _ler_json(saida / "portoes.json")
    if not p:
        raise ErroFluxo("rode a animação antes (horys animar)")
    if not p.get("ok"):
        raise ErroFluxo("os portões não passaram: " + "; ".join(p.get("falhas", [])[:3]))
    if p.get("blend_sha256") != AP.sha(a.blend):
        raise ErroFluxo("o .blend mudou depois da animação: rode horys animar de novo")
    destino = Path(destino) / a.nome
    destino.mkdir(parents=True, exist_ok=True)
    feitos = []
    for f in sorted(saida.iterdir()):
        if f.suffix in (".png", ".json", ".aseprite") and f.name not in ("prancha.png", "pos.json", "portoes.json"):
            shutil.copy2(f, destino / f.name)
            feitos.append(str(destino / f.name))
    return feitos
