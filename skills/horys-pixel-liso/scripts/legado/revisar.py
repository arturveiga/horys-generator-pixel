"""Portão de revisão da skill horys-pixel-liso: nada é entregue sem um veredito PASSA preso ao hash do PNG.

subcomandos:
  preparar  --pasta <versao> --asset X --tipo T --etapa E --rodada N --quadro Q --folha estado=png [...]
            [--modo regua] [--com-equipamento] [--com-efeito] [--centro-tile C,L] [--ficha ficha.md]
            -> roda medir.py e prancha.py em <versao>/revisao e grava pedido.json + prompt.txt
  registrar --pasta <versao> --resposta <arquivo|-> [--modelo nome]
            -> valida a resposta do revisor, aplica as regras do portão e grava <versao>/veredito.json
  processo  --pasta <versao> --motor claude|codex [--modelo X]
            -> chama o revisor como processo separado (claude -p ou codex exec) e registra
  conferir  --veredito <versao>/veredito.json --arquivo <png> [--arquivo ...]
            -> sai com 0 só se o veredito é PASSA e os hashes batem

Códigos de saída do registrar/processo: 0 PASSA, 1 NAO_PASSA, 2 INDEFINIDO, 3 resposta inválida (rode de novo).
"""
import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys

import comum as C

AQUI = os.path.dirname(os.path.abspath(__file__))
ETAPAS = ["silhueta", "cor", "poses", "animacao", "tile", "mosaico", "estados", "efeito", "final"]


def _run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)
    return r.returncode, r.stdout, r.stderr


# ------------------------------------------------------------------ preparar

def preparar(a):
    pasta = os.path.abspath(a.pasta)
    rev = os.path.join(pasta, "revisao")
    os.makedirs(rev, exist_ok=True)
    comuns = ["--tipo", a.tipo, "--quadro", str(a.quadro)]
    if a.altura_quadro:
        comuns += ["--altura-quadro", str(a.altura_quadro)]
    folhas = []
    for f in a.folha:
        folhas += ["--folha", f]
    extra = []
    for ct in a.centro_tile:
        extra += ["--centro-tile", ct]
    med = [sys.executable, os.path.join(AQUI, "medir.py")] + comuns + folhas + extra + [
        "--saida", rev, "--asset", a.asset, "--modo", a.modo]
    if a.com_equipamento:
        med.append("--com-equipamento")
    if a.com_efeito:
        med.append("--com-efeito")
    rc, out, err = _run(med)
    print(out.strip())
    if rc not in (0, 1):
        print(err, file=sys.stderr)
        return 4
    rc2, out2, err2 = _run([sys.executable, os.path.join(AQUI, "prancha.py")] + comuns + folhas + extra +
                           ["--saida", rev, "--medidas", os.path.join(rev, "medidas.json")])
    if rc2:
        print(err2, file=sys.stderr)
        return 4
    hashes = {}
    for f in a.folha:
        estado, _, caminho = f.partition("=")
        hashes[estado] = {"arquivo": os.path.abspath(caminho), "sha256": C.sha256(caminho)}
    pedido = {"asset": a.asset, "versao": os.path.basename(pasta), "tipo": a.tipo, "etapa": a.etapa,
              "rodada": a.rodada, "modo": a.modo, "folhas": hashes, "pacote": rev,
              "ficha": os.path.abspath(a.ficha) if a.ficha else None,
              "medidas_falhas": rc == 1, "criado_em": dt.datetime.now().isoformat(timespec="seconds")}
    with open(os.path.join(rev, "pedido.json"), "w", encoding="utf-8") as f:
        json.dump(pedido, f, ensure_ascii=False, indent=1)
    prompt = (f"Revise o pacote em {rev} — asset '{a.asset}', tipo '{a.tipo}', etapa '{a.etapa}', rodada {a.rodada}, "
              f"modo '{a.modo}'. Comece por indice.md, pedido.json e medidas.json nessa pasta"
              + (f"; a ficha está em {pedido['ficha']}" if pedido["ficha"] else "")
              + ". Siga a rubrica e responda só com o JSON do veredito.")
    with open(os.path.join(rev, "prompt.txt"), "w", encoding="utf-8") as f:
        f.write(prompt + "\n")
    print("pacote pronto:", rev)
    print("PROMPT:", prompt)
    return 0


# ------------------------------------------------------------------ registrar

def extrair_json(texto):
    texto = texto.strip()
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        pass
    i, j = texto.find("{"), texto.rfind("}")
    if i >= 0 and j > i:
        return json.loads(texto[i:j + 1])
    raise ValueError("a resposta não contém um objeto JSON")


def validar(v):
    with open(os.path.join(AQUI, "veredito.schema.json"), encoding="utf-8") as f:
        sch = json.load(f)
    erros = []
    for k in sch["required"]:
        if k not in v:
            erros.append(f"falta '{k}'")
    if v.get("veredito") not in ("PASSA", "NAO_PASSA", "INDEFINIDO"):
        erros.append("veredito inválido")
    if v.get("etapa") not in ETAPAS:
        erros.append(f"etapa inválida: {v.get('etapa')}")
    for c in v.get("criterios", []):
        if c.get("resultado") not in ("passa", "falha", "indefinido"):
            erros.append(f"critério {c.get('id')}: resultado inválido")
        if c.get("severidade") not in ("bloqueio", "grave", "leve"):
            erros.append(f"critério {c.get('id')}: severidade inválida")
        if c.get("resultado") == "falha" and not (c.get("evidencia") and c.get("correcao")):
            erros.append(f"critério {c.get('id')}: falha sem evidência ou correção")
    if len(v.get("pontos_fracos", [])) < 3:
        erros.append("menos de 3 pontos fracos")
    return erros


def registrar_dados(pasta, v, modelo):
    rev = os.path.join(pasta, "revisao")
    with open(os.path.join(rev, "pedido.json"), encoding="utf-8") as f:
        pedido = json.load(f)
    erros = validar(v)
    if erros:
        print("RESPOSTA INVÁLIDA:", "; ".join(erros))
        with open(os.path.join(rev, f"resposta_invalida_rodada{pedido['rodada']}.json"), "w", encoding="utf-8") as f:
            json.dump(v, f, ensure_ascii=False, indent=1)
        return 3
    regras = []
    # números vencem opinião: falha automática grave/bloqueio que o revisor não reprovou
    with open(os.path.join(rev, "medidas.json"), encoding="utf-8") as f:
        med = json.load(f)
    ids_falhos = {c["id"] for c in v["criterios"] if c["resultado"] == "falha"}
    for fa in med.get("falhas", []):
        if fa["severidade"] in ("bloqueio", "grave") and fa["criterio"] not in ids_falhos:
            v["criterios"].append({"id": fa["criterio"], "resultado": "falha", "severidade": fa["severidade"],
                                   "evidencia": f"métrica {fa['id']} [{fa['estado']}]: {fa['texto']}",
                                   "correcao": "corrigir até a métrica passar (ver KB/revisao/metricas.md)"})
            regras.append(f"falha automática {fa['id']} acrescentada (o revisor não tinha reprovado)")
    graves = [c for c in v["criterios"] if c["resultado"] == "falha" and c["severidade"] in ("bloqueio", "grave")]
    bloq_indef = [c for c in v["criterios"] if c["resultado"] == "indefinido" and c["severidade"] == "bloqueio"]
    original = v["veredito"]
    if graves:
        v["veredito"] = "NAO_PASSA"
    elif bloq_indef or v.get("perguntas_ao_usuario"):
        v["veredito"] = "INDEFINIDO" if v["veredito"] == "PASSA" or bloq_indef else v["veredito"]
    if v["veredito"] != original:
        regras.append(f"veredito {original} → {v['veredito']} pela regra do portão")
    v["png_sha256"] = {k: x["sha256"] for k, x in pedido["folhas"].items()}
    v["modelo_revisor"] = modelo or "não informado"
    v["modo"] = pedido["modo"]
    v["registrado_em"] = dt.datetime.now().isoformat(timespec="seconds")
    v["regras_do_portao"] = regras
    with open(os.path.join(rev, f"veredito_rodada{pedido['rodada']}.json"), "w", encoding="utf-8") as f:
        json.dump(v, f, ensure_ascii=False, indent=1)
    with open(os.path.join(pasta, "veredito.json"), "w", encoding="utf-8") as f:
        json.dump(v, f, ensure_ascii=False, indent=1)
    print(f"VEREDITO: {v['veredito']}  ({pedido['asset']} {pedido['versao']}, rodada {pedido['rodada']})")
    print("régua:", v.get("regua", ""))
    for c in v["criterios"]:
        if c["resultado"] != "passa":
            print(f"  {c['resultado'].upper()} {c['id']} ({c['severidade']}): {c['evidencia']} → {c['correcao']}")
    for r in regras:
        print("  regra:", r)
    return {"PASSA": 0, "NAO_PASSA": 1, "INDEFINIDO": 2}[v["veredito"]]


def registrar(a):
    texto = sys.stdin.read() if a.resposta == "-" else open(a.resposta, encoding="utf-8").read()
    try:
        v = extrair_json(texto)
    except (ValueError, json.JSONDecodeError) as e:
        print("RESPOSTA INVÁLIDA:", e)
        return 3
    return registrar_dados(os.path.abspath(a.pasta), v, a.modelo)


# ------------------------------------------------------------------ processo

def processo(a):
    pasta = os.path.abspath(a.pasta)
    rev = os.path.join(pasta, "revisao")
    cfg = C.config()
    prompt = open(os.path.join(rev, "prompt.txt"), encoding="utf-8").read().strip()
    corpo = open(os.path.join(AQUI, "revisor_prompt.md"), encoding="utf-8").read()
    schema_path = os.path.join(AQUI, "veredito.schema.json")
    bruto = os.path.join(rev, f"resposta_{a.motor}.txt")
    if a.motor == "claude":
        exe = shutil.which("claude") or "claude"
        cmd = [exe, "-p", prompt, "--append-system-prompt", corpo, "--allowedTools", "Read,Glob,Grep",
               "--permission-mode", "dontAsk", "--output-format", "json",
               "--add-dir", rev, "--add-dir", cfg["kb"], "--add-dir", cfg["regua"]]
        if a.modelo:
            cmd += ["--model", a.modelo]
        rc, out, err = _run(cmd, cwd=rev, timeout=1800)
        open(bruto, "w", encoding="utf-8").write(out + ("\n--- stderr ---\n" + err if err else ""))
        try:
            env = json.loads(out)
            texto = env.get("result") or json.dumps(env.get("structured_output", {}))
        except json.JSONDecodeError:
            texto = out
        modelo = a.modelo or "claude (padrão)"
    else:
        exe = shutil.which("codex.cmd") or shutil.which("codex") or "codex"
        imagens = sorted(p for p in os.listdir(rev) if p.endswith(".png") and not p.startswith("recortes_8x"))
        cmd = [exe, "exec", "-s", "read-only", "--skip-git-repo-check", "--ephemeral", "-C", rev,
               "--add-dir", cfg["kb"], "--add-dir", cfg["regua"], "--output-schema", schema_path,
               "-o", os.path.join(rev, "resposta_codex.json")]
        for img in imagens[:8]:
            cmd += ["-i", os.path.join(rev, img)]
        if a.modelo:
            cmd += ["-m", a.modelo]
        # o pedido vai pelo stdin: o -i aceita várias imagens e "engoliria" um texto posicional
        rc, out, err = _run(cmd, cwd=rev, timeout=1800, input=corpo + "\n\nPEDIDO\n" + prompt)
        open(bruto, "w", encoding="utf-8").write(out + ("\n--- stderr ---\n" + err if err else ""))
        caminho = os.path.join(rev, "resposta_codex.json")
        texto = open(caminho, encoding="utf-8").read() if os.path.exists(caminho) else out
        modelo = a.modelo or "codex (padrão)"
    try:
        v = extrair_json(texto)
    except (ValueError, json.JSONDecodeError) as e:
        print("RESPOSTA INVÁLIDA:", e, "— veja", bruto)
        return 3
    return registrar_dados(pasta, v, modelo)


# ------------------------------------------------------------------ conferir

def conferir(a):
    with open(a.veredito, encoding="utf-8") as f:
        v = json.load(f)
    ok = v.get("veredito") == "PASSA"
    hashes = set((v.get("png_sha256") or {}).values())
    for arq in a.arquivo:
        h = C.sha256(arq)
        if h not in hashes:
            print(f"BLOQUEADO: {arq} não é o arquivo revisado (hash diferente)")
            ok = False
    if v.get("veredito") != "PASSA":
        print(f"BLOQUEADO: veredito {v.get('veredito')}")
    if ok:
        print("LIBERADO: veredito PASSA e hashes conferem")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("preparar")
    p.add_argument("--pasta", required=True)
    p.add_argument("--asset", required=True)
    p.add_argument("--tipo", required=True)
    p.add_argument("--etapa", required=True, choices=ETAPAS)
    p.add_argument("--rodada", type=int, default=1)
    p.add_argument("--quadro", type=int, default=0)
    p.add_argument("--altura-quadro", type=int, default=0)
    p.add_argument("--folha", action="append", required=True)
    p.add_argument("--modo", choices=["normal", "regua"], default="normal")
    p.add_argument("--com-equipamento", action="store_true")
    p.add_argument("--com-efeito", action="store_true")
    p.add_argument("--centro-tile", action="append", default=[])
    p.add_argument("--ficha", default="")
    r = sub.add_parser("registrar")
    r.add_argument("--pasta", required=True)
    r.add_argument("--resposta", required=True)
    r.add_argument("--modelo", default="")
    q = sub.add_parser("processo")
    q.add_argument("--pasta", required=True)
    q.add_argument("--motor", choices=["claude", "codex"], required=True)
    q.add_argument("--modelo", default="")
    c = sub.add_parser("conferir")
    c.add_argument("--veredito", required=True)
    c.add_argument("--arquivo", action="append", required=True)
    a = ap.parse_args()
    return {"preparar": preparar, "registrar": registrar, "processo": processo, "conferir": conferir}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
