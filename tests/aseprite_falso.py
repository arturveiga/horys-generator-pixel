"""Um 'Aseprite' em memória que fala o protocolo do horysd (docs/protocolo.md), para testes sem interface."""
from __future__ import annotations

import asyncio
import base64
import json
import uuid

import numpy as np
from websockets.asyncio.client import connect

from horys_pixel import auth


class Sprite:
    def __init__(self, w, h, arquivo="Sprite-0001"):
        self.w, self.h, self.arquivo = w, h, arquivo
        self.horys_id = str(uuid.uuid4())
        self.camadas = [{"nome": "desenho", "visivel": True, "opacidade": 255}]
        self.quadros = [{"ms": 100}]
        self.tags = []
        self.cels = {}  # (nome, q) -> rgba
        self.paleta = []
        self.ativa, self.q = "desenho", 0
        self.hist = []

    def img(self, nome, q):
        k = (nome, q)
        if k not in self.cels:
            self.cels[k] = np.zeros((self.h, self.w, 4), np.uint8)
        return self.cels[k]

    def snapshot(self):
        import copy
        return copy.deepcopy((self.camadas, self.quadros, self.tags, {k: v.copy() for k, v in self.cels.items()}))

    def composto(self, q, excluir=()):
        out = np.zeros((self.h, self.w, 4), np.float32)
        for c in self.camadas:
            if not c["visivel"] or c["nome"] in excluir:
                continue
            im = self.cels.get((c["nome"], q))
            if im is None:
                continue
            a = im[..., 3:4].astype(np.float32) / 255 * (c["opacidade"] / 255)
            out[..., :3] = out[..., :3] * (1 - a) + im[..., :3] * a
            out[..., 3:4] = out[..., 3:4] + a * 255 * (1 - out[..., 3:4] / 255)
        return np.clip(out + 0.5, 0, 255).astype(np.uint8)


class AsepriteFalso:
    def __init__(self, porta, token):
        self.porta, self.token = porta, token
        self.sprites: list[Sprite] = []
        self.atual: Sprite | None = None
        self.ui = []          # mensagens de UI recebidas
        self.ws = None
        self.tarefa = None

    async def conectar(self):
        self.ws = await connect(f"ws://127.0.0.1:{self.porta}/", max_size=64 * 2 ** 20)
        des = json.loads(await self.ws.recv())
        n = auth.nonce()
        await self.ws.send(json.dumps({"t": "ola", "papel": "aseprite", "versao": "falso", "nonce": n,
                                       "prova": auth.prova(self.token, des["nonce"])}))
        boas = json.loads(await self.ws.recv())
        if not (boas["t"] == "bem_vindo" and auth.confere(self.token, n, boas["prova"])):
            await self.ws.close()
            raise AssertionError(boas)
        self.config = boas
        self.tarefa = asyncio.ensure_future(self._loop())

    async def fechar(self):
        if self.ws:
            await self.ws.close()

    async def evento(self, **kw):
        await self.ws.send(json.dumps({"t": "evt", **kw}))

    async def _loop(self):
        async for bruto in self.ws:
            m = json.loads(bruto)
            if m.get("t") != "req":
                continue
            try:
                data = self.tratar(m["cmd"], m.get("args") or {})
                r = {"t": "res", "id": m["id"], "ok": True, "data": data}
            except Exception as e:
                r = {"t": "res", "id": m["id"], "ok": False, "erro": f"{type(e).__name__}: {e}"}
            await self.ws.send(json.dumps(r))

    # ------------------------------------------------------------------
    def status(self):
        s = self.atual
        d = {"versao_aseprite": "falso", "sprites": [{"indice": i, "arquivo": x.arquivo} for i, x in enumerate(self.sprites)],
             "sprite": None}
        if s:
            d["sprite"] = {"arquivo": s.arquivo, "horys_id": s.horys_id, "largura": s.w, "altura": s.h, "modo": "rgb",
                           "camadas": [dict(c, indice=i) for i, c in enumerate(s.camadas)],
                           "quadros": list(s.quadros), "tags": list(s.tags), "camada_ativa": s.ativa,
                           "quadro_ativo": s.q}
        return d

    def tratar(self, cmd, a):
        s = self.atual
        if cmd == "status":
            return self.status()
        if cmd == "sprite_novo":
            s = Sprite(int(a["largura"]), int(a["altura"]), a.get("nome") or f"Sprite-{len(self.sprites) + 1:04d}")
            self.sprites.append(s)
            self.atual = s
            return self.status()
        if cmd == "selecionar_sprite":
            self.atual = self.sprites[int(a["indice"])]
            return self.status()
        if cmd in ("ui_perguntar", "ui_aprovar", "ui_progresso", "ui_fechar", "ui_imagem", "ui_acabamento"):
            self.ui.append((cmd, a))
            return {"mostrado": True}
        if s is None:
            raise RuntimeError("nenhum sprite")
        nomes = [c["nome"] for c in s.camadas]
        if cmd in ("escrever", "camada", "quadro", "tag", "limpar_camada"):
            s.hist.append(s.snapshot())
        if cmd == "camada":
            ac = a["acao"]
            if ac == "criar":
                novo = {"nome": a["nome"], "visivel": True, "opacidade": 255}
                if a.get("abaixo_de") in nomes:
                    s.camadas.insert(nomes.index(a["abaixo_de"]), novo)
                elif a.get("acima_de") in nomes:
                    s.camadas.insert(nomes.index(a["acima_de"]) + 1, novo)
                else:
                    s.camadas.append(novo)
            elif ac == "remover":
                s.camadas = [c for c in s.camadas if c["nome"] != a["nome"]]
            elif ac == "renomear":
                for c in s.camadas:
                    if c["nome"] == a["nome"]:
                        c["nome"] = a["novo"]
                s.cels = {((a["novo"] if k[0] == a["nome"] else k[0]), k[1]): v for k, v in s.cels.items()}
            elif ac == "propriedades":
                for c in s.camadas:
                    if c["nome"] == a["nome"]:
                        if "visivel" in a:
                            c["visivel"] = bool(a["visivel"])
                        if "opacidade" in a:
                            c["opacidade"] = int(a["opacidade"])
            elif ac == "ordem":
                por = {c["nome"]: c for c in s.camadas}
                s.camadas = [por[n] for n in a["nomes"]] + [c for c in s.camadas if c["nome"] not in a["nomes"]]
            elif ac == "ativar":
                s.ativa = a["nome"]
            return self.status()
        if cmd == "quadro":
            ac = a["acao"]
            if ac == "garantir":
                while len(s.quadros) < int(a["total"]):
                    s.quadros.append({"ms": s.quadros[-1]["ms"]})
            elif ac == "criar":
                s.quadros.insert(int(a.get("depois_de", len(s.quadros) - 1)) + 1, {"ms": 100})
            elif ac == "duracao":
                alvo = range(len(s.quadros)) if a.get("todos") else [int(a["indice"])]
                for i in alvo:
                    s.quadros[i]["ms"] = int(a["ms"])
            elif ac == "ativar":
                s.q = int(a["indice"])
            elif ac == "remover":
                s.quadros.pop(int(a["indice"]))
            return self.status()
        if cmd == "tag":
            if a["acao"] == "criar":
                s.tags.append({"nome": a["nome"], "de": int(a["de"]), "ate": int(a["ate"])})
            else:
                s.tags = [t for t in s.tags if t["nome"] != a["nome"]]
            return self.status()
        if cmd == "paleta":
            if a["acao"] == "definir":
                s.paleta = list(a["cores"])
            return {"cores": s.paleta}
        if cmd == "escrever":
            w, h, x, y = int(a["w"]), int(a["h"]), int(a["x"]), int(a["y"])
            rgba = np.frombuffer(base64.b64decode(a["rgba"]), np.uint8).reshape(h, w, 4)
            m = np.frombuffer(base64.b64decode(a["mascara"]), np.uint8).reshape(h, w).astype(bool)
            nome = a.get("camada") or s.ativa
            if nome not in nomes:
                raise RuntimeError(f"camada {nome} não existe")
            im = s.img(nome, int(a["quadro"]))
            reg = im[y:y + h, x:x + w]
            reg[m] = rgba[m]
            return {"escritos": int(m.sum())}
        if cmd == "ler":
            q = int(a.get("quadro", 0))
            x, y = int(a.get("x", 0)), int(a.get("y", 0))
            w, h = int(a.get("w", s.w)), int(a.get("h", s.h))
            excluir = set(a.get("excluir") or ("revisao", "referencia", "mapa-partes"))
            base = s.composto(q, excluir) if a.get("camada") is None else s.img(a["camada"], q)
            reg = np.ascontiguousarray(base[y:y + h, x:x + w])
            return {"w": w, "h": h, "rgba": base64.b64encode(reg.tobytes()).decode()}
        if cmd == "limpar_camada":
            for k in list(s.cels):
                if k[0] == a["camada"] and (a.get("todos") or k[1] == int(a.get("quadro", 0))):
                    s.cels[k][:] = 0
            return {}
        if cmd == "selecao":
            return {"vazia": True}
        if cmd == "desfazer":
            for _ in range(int(a.get("passos", 1))):
                if s.hist:
                    s.camadas, s.quadros, s.tags, s.cels = s.hist.pop()
            return {}
        if cmd == "salvar":
            if a.get("arquivo") and not a.get("copia"):
                s.arquivo = a["arquivo"]
            return {"arquivo": a.get("arquivo") or s.arquivo}
        raise RuntimeError(f"comando não suportado no falso: {cmd}")
