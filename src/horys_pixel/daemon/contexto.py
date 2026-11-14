"""O estado do horysd que as ferramentas usam: ponte, pendências, pedidos, fichas dos sprites."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path

from .. import config
from .conversa import Pendencias
from .pedidos import Pedidos
from .ponte import Ponte

log = logging.getLogger("horys.ctx")

def abrir_pasta(pasta: Path):
    """Abre a pasta no gerenciador de arquivos do sistema (botão 'Abrir pasta' do painel)."""
    import os
    import subprocess
    import sys
    try:
        pasta.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(pasta))  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(pasta)])
        else:
            subprocess.Popen(["xdg-open", str(pasta)])
    except Exception:
        log.exception("não abriu a pasta %s", pasta)


TIPOS = ["personagem", "npc", "inimigo", "boss", "criatura", "animal", "efeito", "tile", "agua", "arvore", "prop",
         "recurso", "predio", "icone", "retrato"]


class Contexto:
    def __init__(self):
        self.ponte = Ponte()
        self.pend = Pendencias()
        self.pedidos = Pedidos(self)
        self.baseline: dict = {}                 # (camada, quadro) -> rgba, para horys_mudancas
        self.letras: dict = {}                   # arquivo -> {letra: hex}: letras fixas por cor nas leituras
        self.travas: dict = {}                   # arquivo -> [hex]: paleta travada do horys_pixel_map
        self.clientes_aseprite = set()
        self.pend.ouvintes.append(self._ao_resolver)

    # ------------------------------------------------------------ Aseprite
    async def aseprite(self, cmd: str, args: dict | None = None, timeout: float = 60.0) -> dict:
        return await self.ponte.pedir(cmd, args, timeout)

    async def ui(self, cmd: str, args: dict) -> bool:
        """Mostra algo no painel; False se não houver Aseprite conectado."""
        if not self.ponte.conectado:
            return False
        try:
            await self.ponte.pedir(cmd, args, timeout=10)
            return True
        except Exception as e:  # painel é opcional: nunca derruba a ferramenta
            log.info("ui %s falhou: %s", cmd, e)
            return False

    # ------------------------------------------------------------ fichas (metadados do asset por sprite)
    def _arq_ficha(self, chave: str) -> Path:
        nome = re.sub(r"[^A-Za-z0-9._-]+", "_", chave)[-120:] or "sem_nome"
        return config.pasta("fichas") / f"{nome}.json"

    def ficha(self, chave: str) -> dict:
        a = self._arq_ficha(chave)
        if a.exists():
            return json.loads(a.read_text(encoding="utf-8"))
        return {}

    def salvar_ficha(self, chave: str, ficha: dict):
        self._arq_ficha(chave).write_text(json.dumps(ficha, indent=2, ensure_ascii=False), encoding="utf-8")
        # Compatibilidade com clientes antigos que ainda consultam pelo nome; a chave canônica continua sendo o id.
        for alias in ficha.get("_horys_aliases", []):
            if alias and alias != chave:
                self._arq_ficha(alias).write_text(json.dumps(ficha, indent=2, ensure_ascii=False), encoding="utf-8")

    async def sprite_atual(self) -> dict:
        st = await self.aseprite("status")
        if not st.get("sprite"):
            raise RuntimeError("nenhum sprite aberto no Aseprite (use horys_asset_novo, horys_sprite_novo ou "
                               "horys_abrir)")
        return st

    # ------------------------------------------------------------ configuração enviada à extensão
    def config_extensao(self) -> dict:
        try:
            from .. import estilos
            lista = estilos.listar()
        except Exception:
            lista = []
        return {"estilos": lista, "tipos": TIPOS, "motores": ["claude", "codex"]}

    # ------------------------------------------------------------ eventos da extensão
    def evento(self, msg: dict):
        tipo = msg.get("tipo")
        if tipo == "resposta":
            self.pend.resolver(msg.get("id"), msg.get("respostas") or {})
        elif tipo == "aprovacao":
            self.pend.resolver(msg.get("id"), {"aprovado": bool(msg.get("aprovado")),
                                               "comentario": msg.get("comentario") or ""})
        elif tipo == "pedido_novo":
            p = self.pedidos.novo(msg.get("pedido") or {}, "asset")
            self.pedidos.iniciar(p["id"])
        elif tipo == "revisar_sprite":
            p = self.pedidos.novo({"arquivo": msg.get("arquivo"), "descricao": "revisar sprite",
                                   "motor": msg.get("motor")}, "revisao")
            self.pedidos.iniciar(p["id"])
        elif tipo == "estilo_novo":
            e = msg.get("estilo") or {}
            p = self.pedidos.novo({"nome": e.get("nome"), "imagens": e.get("imagens") or [],
                                   "motor": e.get("motor"), "descricao": f"novo estilo {e.get('nome')}"}, "estilo")
            self.pedidos.iniciar(p["id"])
        elif tipo == "cancelar":
            self.pedidos.cancelar(msg.get("pedido"))
        elif tipo == "imagem":
            self._imagem_do_painel(msg.get("id"), msg.get("caminho"))
        elif tipo == "abrir_pasta":
            it = self.pend.obter(msg.get("id")) or {}
            pasta = (it.get("dados") or {}).get("entrada")
            if pasta:
                abrir_pasta(Path(pasta))
        elif tipo == "acabamento":
            self.pend.resolver(msg.get("id"), {"feitos": msg.get("feitos") or [], "total": msg.get("total"),
                                               "comentario": msg.get("comentario") or ""})
        else:
            log.info("evento desconhecido: %s", tipo)

    def _imagem_do_painel(self, i: str | None, caminho: str | None):
        """Arquivo escolhido no painel: copia para a pasta entrada/ da espera (fica junto do pedido) e resolve."""
        import shutil
        from .conversa import EXT_IMAGEM
        it = self.pend.obter(i) if i else None
        if not it or it["estado"] != "pendente" or not caminho:
            return
        orig = Path(caminho)
        if not orig.is_file() or orig.suffix.lower() not in EXT_IMAGEM:
            log.info("imagem do painel ignorada: %s", caminho)
            return
        entrada = Path((it.get("dados") or {}).get("entrada") or orig.parent)
        destino = entrada / orig.name
        try:
            if orig.resolve() != destino.resolve():
                entrada.mkdir(parents=True, exist_ok=True)
                shutil.copy2(orig, destino)
        except OSError:
            log.exception("não copiou a imagem do painel")
            destino = orig
        self.pend.resolver(i, {"imagem": str(destino), "origem": "painel", "original": str(orig)})

    def _ao_resolver(self, item: dict):
        """Aprovação respondida no painel vira memória de gosto automaticamente."""
        if item.get("tipo") != "aprovacao":
            return
        d = item.get("dados") or {}
        if not d.get("estilo"):
            return
        try:
            from ..ferramentas import gosto
            gosto.registrar_aprovacao(d, item.get("resposta") or {})
        except Exception:
            log.exception("não registrou o gosto")
