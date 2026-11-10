"""Prompt de tradução: o texto que o usuário leva a QUALQUER gerador de imagem para obter uma referência chapada,
feita para ser convertida. Modelo de 11 itens do cofre (pixel-liso/pipeline/padroes/README.md); os números vêm de
padroes/<tipo>.json. Módulo puro: sem Aseprite, sem rede."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from . import padroes

NOMES_TONS = {2: ("sombra", "luz"), 3: ("sombra", "base", "luz"), 4: ("sombra", "base", "luz", "brilho")}


def _proporcao(canvas) -> str:
    w, h = canvas
    if w == h:
        return f"imagem quadrada ({w}×{h})"
    return f"imagem {'vertical' if h > w else 'paisagem'} ({w}×{h})"


def _papeis(paleta: dict) -> list[str]:
    """['rampa: sombra #x, base #y, luz #z', ...] a partir das rampas do estilo."""
    linhas = []
    for nome, cores in paleta["rampas"].items():
        tons = NOMES_TONS.get(len(cores))
        if tons:
            txt = ", ".join(f"{t} {c}" for t, c in zip(tons, cores))
        else:
            txt = ", ".join(cores)
        linhas.append(f"   - {nome}: {txt}")
    linhas.append(f"   - contorno, fendas e órbitas: {paleta['contorno']}")
    if paleta.get("brilho"):
        b = paleta["brilho"]
        linhas.append(f"   - brilho (poucos pontos): {', '.join(b) if isinstance(b, list) else b}")
    return linhas


def todos_hex(paleta: dict) -> list[str]:
    cores = [c for r in paleta["rampas"].values() for c in r] + [paleta["contorno"]]
    b = paleta.get("brilho")
    cores += b if isinstance(b, list) else ([b] if b else [])
    return list(dict.fromkeys(c.lower() for c in cores))


def amostra_paleta(paleta: dict, destino: Path) -> Path:
    """PNG com um quadrado por cor e o hex escrito embaixo (anexo do prompt)."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    cores = todos_hex(paleta)
    lado, margem, colunas = 120, 12, min(6, max(1, len(cores)))
    linhas = (len(cores) + colunas - 1) // colunas
    w, h = colunas * (lado + margem) + margem, linhas * (lado + 34 + margem) + margem
    im = Image.new("RGB", (w, h), "#ffffff")
    d = ImageDraw.Draw(im)
    for i, c in enumerate(cores):
        x = margem + (i % colunas) * (lado + margem)
        y = margem + (i // colunas) * (lado + 34 + margem)
        d.rectangle([x, y, x + lado - 1, y + lado - 1], fill=c, outline="#000000")
        d.text((x + 4, y + lado + 8), c.upper(), fill="#000000")
    im.save(destino)
    return destino


def _alvo(p: dict, altura: int | None) -> int:
    if altura:
        return int(altura)
    lo, hi = p["altura_alvo"]
    return int((lo + hi) // 2)


def gerar(tipo: str, descricao: str, paleta: dict, nome: str = "asset", altura: int | None = None,
          modo: str = "parado", poses: list[str] | None = None, referencia: str | None = None,
          referencia_propria: bool = False, foco: str | None = None, pecas: list[str] | None = None,
          cortes: list[str] | None = None, nao_fazer: list[str] | None = None, vista: str | None = None,
          arquivo_paleta: str = "paleta.png", base_aprovada: str | None = None,
          guia_pose: str | None = None) -> str:
    """Texto do prompt (markdown) com os 11 itens. 'modo' = parado | poses."""
    if modo not in ("parado", "poses"):
        raise ValueError("modo é 'parado' ou 'poses'")
    if modo == "poses" and not poses:
        raise ValueError("modo 'poses' exige a lista de poses")
    p = padroes.carregar(tipo)
    t = padroes.tipo_de(tipo)
    alvo = _alvo(p, altura)
    frac = p["detalhe_min_frac"]
    pct = f"{frac * 100:.1f}".rstrip("0").rstrip(".").replace(".", ",")
    px_min = max(1, round(frac * alvo))
    escuro = paleta["contorno"]
    fundo = p["fundo"]
    if fundo.lower() in todos_hex(paleta):
        fundo = p["fundo_alternativo"]
    anexos = []
    if referencia and referencia_propria:
        anexos.append(f"a referência do design ({Path(referencia).name})")
    anexos.append("a amostra de paleta (as únicas cores permitidas)")
    if modo == "poses":
        anexos.append("a base aprovada" + (f" ({Path(base_aprovada).name})" if base_aprovada else ""))
        if guia_pose:
            anexos.append(f"a grade de silhuetas como guia de pose ({Path(guia_pose).name})")
    L: list[str] = []
    cab = f"# Prompt de tradução: {nome} (ficha {t})"
    L += [cab, "",
          f"Padrão: `pixel-liso/pipeline/padroes/`, ficha {t}. Alvo: ~{alvo} px com contorno, quadro "
          f"{p['quadro']}, pivô {tuple(p['pivo'])}. Modo: {modo}.", "",
          f"**Anexos:** `{arquivo_paleta}` (nesta pasta)"
          + (f" e `{Path(referencia).name}` **só se a imagem for sua** (feita ou gerada por você); se for de "
             "terceiros, mande sem ela: o prompt já descreve o design." if referencia and not referencia_propria else
             (" e a referência." if referencia and referencia_propria else ".")) + "",
          "**Depois:** portão de entrada (`horys_portao_entrada`) → `horys_converter` → limpar → portão → revisor.",
          "", "---", "", "```"]
    L.append(f"Gere UMA imagem. Anexos: {', '.join(anexos)}.")
    L.append("")
    if modo == "parado":
        L.append(f"1. Formato: {_proporcao(p['canvas_geracao'])}.")
    else:
        a = p["animacao"]
        lin, col = a["layout"]
        w, h = a.get("canvas", p["canvas_geracao"])
        L.append(f"1. Formato: grade {lin}×{col} ({_proporcao([w, h])}), uma pose por célula, numeradas da esquerda "
                 f"para a direita e de cima para baixo. Mesma escala, mesmo enquadramento e mesma linha do chão em "
                 f"todas as células; cada pose redesenhada de corpo inteiro; cada figura com pelo menos "
                 f"{a['escala_min']:g}× a altura alvo.")
    L.append("")
    L.append(f"2. Design: {descricao.strip()}" + (" Fiel à referência anexada." if referencia and referencia_propria else ""))
    L.append("")
    L.append(f"3. Vista e pose: {vista or p['vista']}. Câmera {p['camera']}.")
    L.append("")
    L.append(f"4. Foco: {foco or 'o ponto focal do design (rosto ou peça principal), legível em silhueta'}.")
    L.append("")
    L.append("5. Peças (grandes e poucas; " + p["proporcao"] + "):")
    L += [f"   - {x}" for x in (pecas or ["liste aqui as peças do design, com o tamanho relativo de cada uma"])]
    L.append("")
    corte = list(dict.fromkeys((cortes or []) + p["remover"]))
    L.append(f"6. Orçamento de detalhe: o sprite final terá cerca de {alvo} px de altura. Nenhum detalhe com menos de "
             f"{pct}% da altura do corpo (~{px_min} px no sprite). Corte: {', '.join(corte)}.")
    L.append("")
    L.append(f"7. Cores (só estas, com o papel de cada uma; no máximo {p['cores_max']} no total):")
    L += _papeis(paleta)
    L.append("")
    L.append(f"8. Luz: {p['luz']}. Luz pequena (10–20%) em cima, sombra grande (30–40%) embaixo.")
    L.append("")
    L.append("9. Estilo: ilustração chapada (cel shading) em ALTA resolução, NÃO pixel art. Áreas de cor lisas com "
             f"bordas nítidas e contorno escuro uniforme {escuro}. Sem degradê, textura, ruído, brilho especular, "
             "reflexo, desfoque, névoa ou luz de borda.")
    L.append("")
    if modo == "parado":
        pct_oc = round(p["ocupacao"] * 100)
        chao = round(p["linha_chao_frac"] * 100)
        L.append(f"10. Enquadramento: a figura inteira ocupando cerca de {pct_oc}% da altura da imagem, centrada, com "
                 f"os pés numa linha horizontal a cerca de {chao}% da altura e margem em volta. Fundo liso {fundo}, "
                 "sem degradê. Sem sombra no chão, sem chão, sem texto e sem moldura.")
    else:
        L.append("10. Poses (numeradas):")
        L += [f"    {i}. {x}" for i, x in enumerate(poses, 1)]
        L.append(f"    Fundo liso {fundo}, sem degradê, em todas as células. Sem sombra no chão, sem chão, sem texto e "
                 "sem moldura. Pés de todas as poses na mesma linha horizontal; nada encostando na borda da célula.")
    L.append("")
    extra = ["render 3D", "realismo", "cores fora da lista", "mais de uma figura por célula" if modo == "poses"
             else "mais de um personagem"]
    L.append(f"11. Não fazer: {', '.join((nao_fazer or []) + extra)}.")
    L.append("```")
    return "\n".join(L) + "\n"


def escrever(pasta: Path, **kw) -> dict:
    """Grava traducao/prompt.md e traducao/paleta-<estilo>.png em 'pasta'; devolve os caminhos."""
    pasta = Path(pasta) / "traducao"
    pasta.mkdir(parents=True, exist_ok=True)
    estilo = kw.pop("nome_estilo", "estilo")
    paleta = kw["paleta"]
    png = amostra_paleta(paleta, pasta / f"paleta-{estilo}.png")
    texto = gerar(arquivo_paleta=png.name, **kw)
    md = pasta / "prompt.md"
    md.write_text(texto, encoding="utf-8")
    return {"prompt": str(md), "paleta": str(png), "texto": texto}
