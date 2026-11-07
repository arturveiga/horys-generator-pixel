"""Pedidos de asset: estado salvo em disco e o motor (Claude ou Codex) rodando sem terminal."""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from pathlib import Path

from .. import config
from . import motores

log = logging.getLogger("horys.pedidos")

SKILL = motores.RAIZ_REPO / "skills" / "horys-pixel" / "SKILL.md"
SKILL_ESTILO = motores.RAIZ_REPO / "skills" / "horys-pixel-estilo" / "SKILL.md"
ETAPAS = ["novo", "briefing", "pesquisa", "praticas", "ficha", "referencia", "conversao", "limpeza", "partes", "portao",
          "revisor", "aprovacao", "animacao", "entrega", "concluido"]


def texto_skill(caminho: Path = SKILL) -> str:
    """O corpo da skill (sem o cabeçalho YAML), entregue inteiro no prompt do motor sem terminal."""
    try:
        t = caminho.read_text(encoding="utf-8")
    except OSError:
        return "(SKILL.md não encontrada; siga as instruções MCP do servidor horys)"
    if t.startswith("---"):
        fim = t.find("\n---", 3)
        if fim > 0:
            t = t[fim + 4:]
    return t.strip()


def prompt_pedido(p: dict) -> str:
    estados = ", ".join(p.get("estados") or []) or "a decidir no briefing"
    ref = p.get("referencia") or "nenhuma (peça uma no briefing)"
    return (
        "Você é o motor do horys-pixel rodando SEM TERMINAL, a pedido do usuário no Aseprite.\n"
        "A skill horys-pixel vem INTEIRA abaixo (entre as linhas ====): siga-a. Grave pesquisa.md, praticas.md e "
        f"ficha.md na pasta de trabalho ({p['pasta']}), como a skill manda, e passe os caminhos ao horys_revisar. "
        "Para desenhar, medir e revisar use as ferramentas horys_*.\n\n"
        f"PEDIDO {p['id']}\n- descrição: {p.get('descricao')}\n- tipo: {p.get('tipo') or 'a decidir'}\n"
        f"- estilo: {p.get('estilo')}\n- estados: {estados}\n- tamanho: {p.get('tamanho') or 'padrão do estilo'}\n"
        f"- referência: {ref}\n- pasta de trabalho: {p['pasta']}\n\n"
        "Este formulário já confirma o briefing informado. O usuário NÃO lê este chat: toda pergunta passa por "
        "horys_perguntar + horys_aguardar, toda aprovação por horys_aprovar + horys_aguardar, e o andamento por "
        "horys_pedido_atualizar (etapa, texto, nota). Personagem animado: escolha o preset de partes pela anatomia do "
        "briefing (não use o do ferreiro em quem não tem martelo, barba e óculos) e registre a etapa 'partes' ANTES de "
        "animar. Se horys_perguntar disser que não há painel, registre a dúvida com horys_pedido_atualizar e siga com "
        "a opção recomendada. Ao terminar, chame horys_pedido_atualizar com etapa 'concluido' e um resumo.\n\n"
        "==================== SKILL horys-pixel ====================\n"
        + texto_skill()
        + "\n==================== fim da skill ====================\n"
    )


SKILL_REVIEW = motores.RAIZ_REPO / "skills" / "horys-pixel-review" / "SKILL.md"


def prompt_revisao(p: dict) -> str:
    return (
        f"Você é o motor do horys-pixel rodando SEM TERMINAL. Leia e siga a skill em {SKILL_REVIEW}.\n"
        f"PEDIDO {p['id']}: revisar o sprite aberto no Aseprite"
        f"{' (' + p['arquivo'] + ')' if p.get('arquivo') else ''}. Pasta de trabalho: {p['pasta']}.\n"
        "Use horys_medir_arquivo (ou exporte com horys_exportar e meça), marque os problemas na camada 'revisao' "
        "com horys_marcar, e entregue o relatório pelo horys_pedido_atualizar (etapa 'concluido'). "
        "Não corrija nada sem o usuário pedir (pergunte com horys_perguntar se ele quer as correções)."
    )


def prompt_estilo(p: dict) -> str:
    return (
        f"Você é o motor do horys-pixel rodando SEM TERMINAL. Leia e siga a skill em {SKILL_ESTILO}.\n"
        f"PEDIDO {p['id']}: criar o estilo '{p.get('nome')}' a partir das imagens: {p.get('imagens')}.\n"
        f"Pasta de trabalho: {p['pasta']}. Perguntas e aprovações só por horys_perguntar/horys_aprovar; "
        "andamento por horys_pedido_atualizar."
    )


class Pedidos:
    def __init__(self, ctx):
        self.ctx = ctx
        self.raiz = config.pasta("pedidos")
        self.processos: dict[str, asyncio.subprocess.Process] = {}
        self.tarefas: dict[str, asyncio.Task] = {}

    def _arq(self, i: str) -> Path:
        return self.raiz / i / "pedido.json"

    def ler(self, i: str) -> dict | None:
        a = self._arq(i)
        if not a.exists():
            return None
        return json.loads(a.read_text(encoding="utf-8"))

    def salvar(self, p: dict):
        a = self._arq(p["id"])
        a.parent.mkdir(parents=True, exist_ok=True)
        p["atualizado"] = time.time()
        a.write_text(json.dumps(p, indent=2, ensure_ascii=False), encoding="utf-8")

    def listar(self, n: int = 20) -> list[dict]:
        out = []
        for d in sorted(self.raiz.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)[:n]:
            p = self.ler(d.name)
            if p:
                out.append({k: p.get(k) for k in ("id", "descricao", "motor", "etapa", "estado", "nota")})
        return out

    def novo(self, dados: dict, tipo: str = "asset") -> dict:
        i = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
        prefs = config.preferencias()
        dados = {k: v for k, v in dados.items() if v not in (None, "", [])}   # vazio não apaga o padrão
        p = {"id": i, "tipo_pedido": tipo, "criado": time.time(), "etapa": "novo", "estado": "novo",
             "motor": dados.get("motor") or prefs.get("motor_padrao", "claude"),
             "estilo": dados.get("estilo") or prefs.get("estilo_padrao"),
             "historico": [], **{k: v for k, v in dados.items() if k not in ("id",)}}
        p["pasta"] = str(self.raiz / i)
        self.salvar(p)
        return p

    def atualizar(self, i: str, etapa: str | None = None, texto: str | None = None, nota=None, **extra) -> dict:
        p = self.ler(i)
        if p is None:
            raise KeyError(f"pedido {i} não existe")
        if etapa:
            p["etapa"] = etapa
        if nota is not None:
            p["nota"] = nota
        p.update(extra)
        p["historico"].append({"t": time.time(), "etapa": p["etapa"], "texto": texto, "nota": nota})
        self.salvar(p)
        asyncio.ensure_future(self.ctx.ui("ui_progresso", {"pedido": i, "etapa": p["etapa"], "texto": texto or "",
                                                           "nota": nota}))
        return p

    def iniciar(self, i: str) -> dict:
        p = self.ler(i)
        if p is None:
            raise KeyError(f"pedido {i} não existe")
        if i in self.tarefas and not self.tarefas[i].done():
            return p
        p["estado"] = "rodando"
        p["iniciado"] = time.time()
        self.salvar(p)
        self.tarefas[i] = asyncio.ensure_future(self._rodar(p))
        return p

    async def _rodar(self, p: dict):
        i = p["id"]
        prompt = {"estilo": prompt_estilo, "revisao": prompt_revisao}.get(p.get("tipo_pedido"), prompt_pedido)(p)
        await self.ctx.ui("ui_progresso", {"pedido": i, "etapa": "iniciando", "texto": f"motor: {p['motor']}"})
        try:
            r = await motores.rodar(p["motor"], prompt, Path(p["pasta"]), nome_log="motor",
                                    ao_iniciar=lambda proc: self.processos.__setitem__(i, proc))
        except Exception as e:  # motor ausente, etc.
            log.exception("motor falhou")
            self.atualizar(i, etapa="erro", texto=str(e), estado="erro")
            return
        finally:
            self.processos.pop(i, None)
        atual = self.ler(i) or p
        estado = "concluido" if r["codigo"] == 0 else "erro"
        if atual.get("estado") == "cancelado":
            estado = "cancelado"
        self.atualizar(i, etapa=atual.get("etapa") if estado == "concluido" else estado,
                       texto=(r["texto"] or "")[-1500:], estado=estado, log=r["log"], segundos=r["segundos"])

    def cancelar(self, i: str) -> bool:
        proc = self.processos.get(i)
        p = self.ler(i)
        if p:
            p["estado"] = "cancelado"
            self.salvar(p)
        if proc and proc.returncode is None:
            proc.kill()
            return True
        return False
