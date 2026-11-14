"""Motor A (horys-pixel-liso): gera os quadros de um asset a partir de uma RECEITA em Python.

uso: python motor.py --receita <receita.py> --saida <pasta_versao> --nome <asset>

A receita (um arquivo por asset, na pasta de trabalho) define:
  QUADRO = (192, 192); PIVO = (96, 127)
  ESTADOS = {"idle": {"quadros": 8, "ms": 100, "loop": True}, ...}
  LINHAS_INTERNAS = [("cabeca", "corpo"), ...]      # (parte de cima, parte de baixo) que ganham linha de 1 px
  def partes(estado, i, n, P): -> lista de dicts {nome, mascara, rampa, z, tras?, chapado?, sem_contorno?, protegido?}
       (P = paleta: P["castanho"] -> [sombra, base, luz] em RGB; P.contorno; P.brilho)
       a parte é REDESENHADA a cada quadro (raios, posição e inclinação mudam): isso é o redesenho que a régua exige
  def sombra_chao(estado, i, n): -> (cx, cy, rx, ry)
Para cada quadro: cada parte vira sombra/base/luz em crescentes, as partes são compostas por z, o contorno 2/1 é
aplicado depois de compor, os órfãos são limpos e a sombra no chão (contorno com alfa 76) vai por baixo.
"""
import argparse
import importlib.util
import os
import sys

import numpy as np

import comum as C
import desenho as D
import montar as M


class Paleta(dict):
    def __init__(self, cfg):
        p = C.carregar_paleta(cfg)
        super().__init__(p["rampas"])
        self.contorno = p["contorno"]
        self.brilho = p["brilho"][0]


def carregar_receita(caminho):
    spec = importlib.util.spec_from_file_location("receita", caminho)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def tons(rampa, tras):
    """(sombra, base, luz) de uma rampa; parte de trás desce um tom."""
    r = list(rampa)
    if len(r) == 1:
        return r[0], r[0], r[0]
    if len(r) == 2:
        s, b, l = r[0], r[0], r[1]
    else:
        s, b, l = r[0], r[1], r[2]
    if tras:
        return s, s, b
    return s, b, l


def quadro(receita, estado, i, n, P):
    W, H = receita.QUADRO
    img = np.zeros((H, W, 4), np.uint8)
    visiveis, protegido = {}, np.zeros((H, W), bool)
    uniao = np.zeros((H, W), bool)
    lista = sorted(receita.partes(estado, i, n, P), key=lambda p: p["z"])
    for p in lista:
        m = p["mascara"] if (p.get("chapado") or p.get("sem_suavizar")) else D.suavizar(p["mascara"])
        if not m.any():
            continue
        if p.get("chapado"):
            D.pintar(img, m, p["rampa"][0] if isinstance(p["rampa"], list) else p["rampa"])
        else:
            s, b, l = tons(p["rampa"], p.get("tras"))
            sm, bm, lm = D.crescentes(m, *p.get("luz", (1, -1)), k_sombra=p.get("k_sombra", 4), k_luz=p.get("k_luz", 3))
            D.pintar(img, bm, b)
            D.pintar(img, sm, s)
            D.pintar(img, lm, l)
        for k in visiveis:
            visiveis[k] &= ~m
        visiveis[p["nome"]] = m.copy()
        if p.get("protegido"):
            protegido |= m
        if not p.get("sem_contorno"):
            uniao |= m
    # linhas internas (1 px) e contorno externo (2 px), depois de compor
    for cima, baixo in getattr(receita, "LINHAS_INTERNAS", []):
        if cima in visiveis and baixo in visiveis:
            D.pintar(img, D.linha_interna(visiveis[cima], visiveis[baixo]), P.contorno)
    D.pintar(img, D.contorno_externo(uniao, 2), P.contorno)
    img = D.limpar_orfaos(img, protegido)
    # sombra no chão por baixo de tudo
    cx, cy, rx, ry = receita.sombra_chao(estado, i, n)
    sombra = D.elipse(W, H, cx, cy, rx, ry) & (img[..., 3] == 0)
    D.pintar(img, sombra, P.contorno, alfa=76)
    return img


def gerar(receita, cfg):
    P = Paleta(cfg)
    return {e: [quadro(receita, e, i, d["quadros"], P) for i in range(d["quadros"])]
            for e, d in receita.ESTADOS.items()}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--receita", required=True)
    ap.add_argument("--saida", required=True)
    ap.add_argument("--nome", required=True)
    a = ap.parse_args()
    cfg = C.config()
    receita = carregar_receita(a.receita)
    quadros = gerar(receita, cfg)
    arquivos = M.montar(quadros, receita, a.saida, a.nome)
    for k, v in arquivos.items():
        print(f"{k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
